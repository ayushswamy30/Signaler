"use client";

/** Voice and video calling over WebRTC.
 *
 *  The server never carries audio or video. It relays two small JSON blobs —
 *  a session description and a stream of network candidates — and once the two
 *  browsers agree on a path, the media flows directly between the devices.
 *  That is why a call keeps working at full quality on a free-tier server that
 *  could never push video itself.
 *
 *  A one-to-one call is one peer connection. A group call is a mesh: this
 *  client holds a separate connection to every other person in the call, so
 *  the same code path serves both and a one-to-one call is simply the case
 *  where the mesh has one peer. A mesh uploads the local camera once per peer,
 *  which is why it suits small group chats and would not suit large ones —
 *  those need a media server, and a media server is exactly the cost this
 *  design avoids.
 *
 *  Who offers and who answers is settled without any server state: on learning
 *  of another person in the call, the lower user id sends the offer. Someone
 *  who learns of a peer they are *not* responsible for offering re-announces
 *  themselves instead, so the pair always ends up knowing about each other
 *  exactly once, in one direction, with no glare. */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { socket } from "./socket";
import { toUser } from "./adapt";
import type { UserDTO } from "./dto";
import type { Conversation, User } from "./types";

export type CallKind = "audio" | "video";

/** `dialling` is waiting for them to pick up; `ringing` is being called. */
export type CallStatus =
  | "idle"
  | "dialling"
  | "ringing"
  | "connecting"
  | "active"
  | "ended";

/** STUN tells a browser its own public address, which is enough for most home
 *  and office networks. It is *not* enough behind symmetric NAT or a strict
 *  corporate/carrier firewall, where the two peers cannot address each other
 *  at all and the media needs relaying through a TURN server — signalling
 *  succeeds, `onconnectionstatechange` never leaves "connecting" or flips
 *  straight to `failed`, and no audio or video crosses in either direction.
 *  That is not a rare edge case: two ordinary phones on two different mobile
 *  carriers, or two people on two different home networks, hit it routinely.
 *
 *  The actual server list is fetched from the backend (see fetchIceServers)
 *  rather than hardcoded here, because a TURN credential needs to be able to
 *  rotate — or a dead provider needs to be swappable for a working one —
 *  without a frontend redeploy. This is only the offline fallback: Google's
 *  public STUN, free and keyless, used if the backend itself cannot be
 *  reached. It has no TURN entry, so a call that needs relaying will still
 *  fail in that specific case — but signalling and every STUN-reachable call
 *  keeps working instead of an unrelated network hiccup blocking calls
 *  outright. */
const FALLBACK_ICE_SERVERS: RTCIceServer[] = [
  { urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] },
];

/** How long a fetched ICE server list is reused before asking the backend
 *  again. Long enough that placing several calls in a row does not refetch
 *  every time; short enough that a rotated or newly-configured TURN
 *  credential reaches an open tab within a session rather than only on
 *  reload. */
const ICE_CACHE_TTL_MS = 5 * 60 * 1000;

let iceCache: { servers: RTCIceServer[]; fetchedAt: number } | null = null;

/** The ICE servers for the next call: cached, with a network or server
 *  failure degrading to STUN-only rather than blocking the call from being
 *  attempted at all. */
async function fetchIceServers(): Promise<RTCIceServer[]> {
  if (iceCache && Date.now() - iceCache.fetchedAt < ICE_CACHE_TTL_MS) {
    return iceCache.servers;
  }
  try {
    const { ice_servers } = await api.iceServers();
    const servers: RTCIceServer[] = ice_servers.map((entry) => ({
      urls: entry.urls,
      username: entry.username ?? undefined,
      credential: entry.credential ?? undefined,
    }));
    iceCache = { servers, fetchedAt: Date.now() };
    return servers;
  } catch {
    return FALLBACK_ICE_SERVERS;
  }
}

/** Why calling cannot work here at all, or null if it can.
 *
 *  Checked before anything is attempted, because these failures are about the
 *  page rather than about a device: on a plain-HTTP origin
 *  `navigator.mediaDevices` is not merely blocked, it is `undefined`, so the
 *  attempt would surface as a confusing TypeError about reading a property
 *  rather than as "this needs HTTPS". localhost counts as secure, so local
 *  development is unaffected. */
function unsupportedReason(): string | null {
  if (typeof window === "undefined") return null;
  if (!window.isSecureContext) {
    return "Calls need a secure connection. Open Signaler over HTTPS and try again.";
  }
  if (
    typeof window.RTCPeerConnection !== "function" ||
    typeof navigator.mediaDevices?.getUserMedia !== "function"
  ) {
    return "This browser does not support calls. Try a recent Chrome, Edge, Firefox or Safari.";
  }
  return null;
}

/** Turn a getUserMedia rejection into something worth showing a person.
 *
 *  These are the cases a user can actually act on: the browser's own message
 *  ("Requested device not found") explains nothing about what to do next. */
function describeMediaError(error: unknown, kind: CallKind): string {
  const name = error instanceof DOMException ? error.name : "";
  const devices = kind === "video" ? "camera and microphone" : "microphone";

  switch (name) {
    case "NotAllowedError":
    case "PermissionDeniedError":
      return `Signaler needs permission to use your ${devices}. Allow it in your browser's address bar, then try again.`;
    case "NotFoundError":
    case "DevicesNotFoundError":
      return `No ${devices} found. Plug one in, or start a voice call instead.`;
    case "NotReadableError":
    case "TrackStartError":
      return `Your ${devices} is already in use by another app. Close it and try again.`;
    case "OverconstrainedError":
      return `Your ${devices} does not support the requested settings.`;
    default:
      return `Could not start your ${devices}.`;
  }
}

/** How long a call may sit in "disconnected" before it is given up on. Well
 *  clear of the browser's own escalation to "failed", which is the signal
 *  that should normally end a call. */
const STALL_LIMIT_MS = 30_000;

interface CandidateReport { id: string; candidateType?: string }
interface PairReport { localCandidateId: string; remoteCandidateId: string; state: string; nominated?: boolean }

/** What ICE actually gathered and agreed on, printed when a call fails.
 *
 *  Every explanation for a failed call has been a guess so far because the
 *  browser's own verdict ("failed") says nothing about *why*. These three
 *  numbers separate the cases that need completely different fixes:
 *
 *  - no `relay` in gathered      -> TURN produced nothing: credentials
 *                                   rejected, or its ports are blocked here.
 *  - relay on both sides, no pair -> the relay works and the two ends still
 *                                   cannot meet; a different relay is needed.
 *  - a working pair, still failed -> not networking at all; look at DTLS or
 *                                   the tracks. */
async function reportIceFailure(pc: RTCPeerConnection): Promise<void> {
  try {
    const stats = await pc.getStats();
    const candidates = new Map<string, CandidateReport>();
    const pairs: PairReport[] = [];
    const gathered = new Set<string>();
    const received = new Set<string>();

    stats.forEach((report) => {
      const entry = report as unknown as CandidateReport & PairReport & { type: string };
      if (entry.type === "local-candidate") {
        candidates.set(entry.id, entry);
        if (entry.candidateType) gathered.add(entry.candidateType);
      } else if (entry.type === "remote-candidate") {
        candidates.set(entry.id, entry);
        if (entry.candidateType) received.add(entry.candidateType);
      } else if (entry.type === "candidate-pair") {
        pairs.push(entry);
      }
    });

    const working = pairs.find((pair) => pair.state === "succeeded" || pair.nominated);
    const describe = (id: string) => candidates.get(id)?.candidateType ?? "?";

    console.warn("[call] why it failed:", {
      gathered: [...gathered].join(", ") || "none",
      received: [...received].join(", ") || "none",
      workingPair: working
        ? `${describe(working.localCandidateId)} -> ${describe(working.remoteCandidateId)}`
        : "none",
      pairsTried: pairs.length,
      iceGathering: pc.iceGatheringState,
      ice: pc.iceConnectionState,
    });
  } catch {
    // Diagnostics must never be the thing that breaks a call.
  }
}

const MIC_DEVICE_KEY = "signaler:call-mic";
const CAMERA_DEVICE_KEY = "signaler:call-camera";

/** The device picker remembers a choice across calls (and reloads), but only
 *  as a nicety -- a private window or storage disabled by policy just means
 *  the choice does not survive, not a broken picker. */
function readStoredDevice(key: string): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function writeStoredDevice(key: string, value: string) {
  if (typeof window === "undefined") return;
  try {
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  } catch {
    // Ignored -- see readStoredDevice.
  }
}

/** `""` means "system default", which is also what a browser does with a
 *  bare `audio: true`. An empty deviceId is never sent as a constraint. */
function buildAudioConstraint(deviceId: string): MediaTrackConstraints | boolean {
  return deviceId ? { deviceId: { exact: deviceId } } : true;
}

function buildVideoConstraint(deviceId: string): MediaTrackConstraints {
  return {
    width: { ideal: 1280 },
    height: { ideal: 720 },
    ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
  };
}
interface CallDevices {
  mics: MediaDeviceInfo[];
  cameras: MediaDeviceInfo[];
}

/** One other person in the call, as the UI needs to see them. */
export interface CallParticipant {
  user: User;
  stream: MediaStream | null;
  /** Their media is flowing. Before that the tile is still negotiating, which
   *  is worth showing rather than presenting an empty square as a live one. */
  connected: boolean;
}

/** One live peer connection and the bookkeeping that belongs to it alone.
 *
 *  Kept in a ref-held map rather than in state: these are mutable objects
 *  whose own events fire dozens of times a call, and re-rendering on each
 *  would be both wasteful and a source of stale closures. `syncPeers` copies
 *  the parts the UI needs into state at the moments they actually change. */
interface Peer {
  user: User;
  pc: RTCPeerConnection;
  stream: MediaStream | null;
  connected: boolean;
}

interface CallSnapshot {
  status: CallStatus;
  kind: CallKind;
  conversationId: number | null;
  /** True for a group call, where several people can be on the line at once. */
  isGroup: boolean;
  /** One-to-one: the other end. Group: whoever started the call, which is what
   *  an incoming-call screen needs to name before anyone has been connected. */
  peer: User | null;
  /** Everyone whose connection this client currently holds. One entry for a
   *  one-to-one call; up to everyone else in the conversation for a group. */
  participants: CallParticipant[];
  localStream: MediaStream | null;
  micOn: boolean;
  cameraOn: boolean;
  /** Connected, then the checks started failing. The call is still alive and
   *  the browser is still trying -- worth saying so rather than hiding it. */
  reconnecting: boolean;
  error: string | null;
  /** When the media actually connected, for the in-call timer. */
  startedAt: number | null;
}

const IDLE: CallSnapshot = {
  status: "idle",
  kind: "audio",
  conversationId: null,
  isGroup: false,
  peer: null,
  participants: [],
  localStream: null,
  micOn: true,
  cameraOn: true,
  reconnecting: false,
  error: null,
  startedAt: null,
};

export function useCall(meId: number) {
  const [call, setCall] = useState<CallSnapshot>(IDLE);

  // Read inside the socket handler, which is subscribed once and would
  // otherwise close over the status as it was at subscription time.
  const statusRef = useRef<CallStatus>("idle");
  statusRef.current = call.status;

  // Same reason: read inside switchDevice, which is created once (stable
  // deps) and must still see this call's current mute state, not the one
  // from whenever the track it is replacing was first captured.
  const micOnRef = useRef(true);
  micOnRef.current = call.micOn;
  const cameraOnRef = useRef(true);
  cameraOnRef.current = call.cameraOn;
  // Decides which side of each pair sends the offer; see the header note.
  const meIdRef = useRef(meId);
  meIdRef.current = meId;

  // WebRTC objects are mutable and long-lived, and must not trigger renders.
  /** Every connection this client holds, keyed by the other person's id. */
  const peers = useRef<Map<number, Peer>>(new Map());
  const localStream = useRef<MediaStream | null>(null);
  const conversationId = useRef<number | null>(null);
  const isGroup = useRef(false);
  /** Audio or video, readable from the socket handler when answering an offer
   *  that arrives before any of this call's state has re-rendered. */
  const callKind = useRef<CallKind>("audio");
  /** The offer that arrived with an incoming one-to-one call, replayed on
   *  accept. A group invite carries no offer -- each pair negotiates its own. */
  const pendingOffer = useRef<RTCSessionDescriptionInit | null>(null);
  /** Who is ringing us, so their hanging up can end a call we have not
   *  answered yet -- in a group, everyone else's leaving must not. */
  const ringingFrom = useRef<number | null>(null);
  /** Candidates that arrive before their peer connection has a remote
   *  description -- or before it exists at all, which is normal for the person
   *  being called, whose connection is only built when they answer.
   *  addIceCandidate throws in that window, so they are held and replayed. */
  const early = useRef<Map<number, RTCIceCandidateInit[]>>(new Map());
  /** Counts down while a call sits in "disconnected". See startStall. */
  const stallTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- devices -------------------------------------------------------------

  const [devices, setDevices] = useState<CallDevices>({ mics: [], cameras: [] });
  const [micDeviceId, setMicDeviceIdState] = useState(() => readStoredDevice(MIC_DEVICE_KEY));
  const [cameraDeviceId, setCameraDeviceIdState] = useState(() => readStoredDevice(CAMERA_DEVICE_KEY));
  // Read inside captureMedia/switchDevice, which must see the preference in
  // effect *right now* -- including one just chosen in the same event handler,
  // before the state update above has re-rendered.
  const micDeviceRef = useRef(micDeviceId);
  const cameraDeviceRef = useRef(cameraDeviceId);

  /** Device labels are blank until permission has been granted at least once,
   *  so this is re-run after every capture, not just on mount. */
  const refreshDevices = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) return;
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      setDevices({
        mics: all.filter((d) => d.kind === "audioinput"),
        cameras: all.filter((d) => d.kind === "videoinput"),
      });
    } catch {
      // Enumeration itself is not essential -- the picker just stays empty.
    }
  }, []);

  useEffect(() => {
    void refreshDevices();
    const media = navigator.mediaDevices;
    media?.addEventListener?.("devicechange", refreshDevices);
    return () => media?.removeEventListener?.("devicechange", refreshDevices);
  }, [refreshDevices]);

  // --- peers ---------------------------------------------------------------

  /** Copy the peer map into state, so the UI re-renders with it. */
  const syncPeers = useCallback(() => {
    const list = [...peers.current.values()].map((peer) => ({
      user: peer.user,
      stream: peer.stream,
      connected: peer.connected,
    }));
    setCall((current) => ({ ...current, participants: list }));
  }, []);

  /** Close one connection and forget it. Everything else in the call lives on,
   *  which is the whole point of the mesh: one person leaving a group call is
   *  not the call ending. */
  const closePeer = useCallback((id: number) => {
    const peer = peers.current.get(id);
    if (!peer) return;
    // Detach the handlers first: closing fires state changes that would
    // otherwise re-enter this and re-render a peer that no longer exists.
    peer.pc.onicecandidate = null;
    peer.pc.ontrack = null;
    peer.pc.onconnectionstatechange = null;
    peer.pc.oniceconnectionstatechange = null;
    peer.pc.close();
    peers.current.delete(id);
    early.current.delete(id);
  }, []);

  /** Release the camera, microphone and every peer connection.
   *
   *  Stopping every track matters: a MediaStream that is merely dropped leaves
   *  the camera light on, which reads — correctly — as still being watched. */
  const teardown = useCallback(() => {
    if (stallTimer.current) clearTimeout(stallTimer.current);
    stallTimer.current = null;

    localStream.current?.getTracks().forEach((track) => track.stop());
    localStream.current = null;

    for (const id of [...peers.current.keys()]) closePeer(id);

    conversationId.current = null;
    isGroup.current = false;
    pendingOffer.current = null;
    ringingFrom.current = null;
    early.current.clear();
  }, [closePeer]);

  /** End the call locally and show why, if there is anything worth saying. */
  const finish = useCallback(
    (error: string | null = null) => {
      teardown();
      setCall((current) =>
        current.status === "idle" && !error
          ? current
          : { ...IDLE, status: error ? "idle" : "ended", error },
      );
      // A brief "Call ended" is worth showing; leaving it up forever is not.
      if (!error) setTimeout(() => setCall((c) => (c.status === "ended" ? IDLE : c)), 1200);
    },
    [teardown],
  );

  const clearStall = useCallback(() => {
    if (stallTimer.current) clearTimeout(stallTimer.current);
    stallTimer.current = null;
  }, []);

  /** The backstop under a one-to-one call sitting in "disconnected".
   *
   *  Recovery is the browser's job -- it will either get the checks passing
   *  again or escalate to "failed" -- and it is better at judging that than a
   *  timer here would be. This exists only for the case where it does
   *  neither, so a call cannot sit on "Reconnecting…" forever. A group call
   *  does not need it: one peer stalling is not the call stalling, and a peer
   *  that never recovers is dropped on "failed" without taking the rest with
   *  it. */
  const startStall = useCallback(
    (pc: RTCPeerConnection) => {
      if (stallTimer.current) return; // already counting down for this drop
      stallTimer.current = setTimeout(() => {
        stallTimer.current = null;
        const live = [...peers.current.values()].some((peer) => peer.pc === pc);
        if (!live || pc.connectionState === "connected") return;
        finish("The connection dropped and could not be recovered.");
      }, STALL_LIMIT_MS);
    },
    [finish],
  );

  /** Replay the candidates held for a peer now that it can accept them. */
  const flushEarly = useCallback(async (peer: Peer) => {
    const held = early.current.get(peer.user.id);
    if (!held) return;
    early.current.delete(peer.user.id);
    for (const candidate of held) {
      await peer.pc.addIceCandidate(new RTCIceCandidate(candidate)).catch(() => {
        // A candidate that cannot be added is not fatal: the connection
        // continues with whichever paths did work.
      });
    }
  }, []);

  /** Build a connection to one person and wire its callbacks.
   *
   *  Async because the ICE server list is fetched (and cached) rather than
   *  hardcoded — see fetchIceServers. */
  const createPeer = useCallback(
    async (user: User): Promise<Peer | null> => {
      const forConversation = conversationId.current;
      if (forConversation === null) return null;

      const existing = peers.current.get(user.id);
      if (existing) return existing;

      const iceServers = await fetchIceServers();
      // The call can end while that is in flight.
      if (conversationId.current !== forConversation) return null;

      const pc = new RTCPeerConnection({ iceServers });
      const peer: Peer = { user, pc, stream: null, connected: false };
      peers.current.set(user.id, peer);

      pc.onicecandidate = (event) => {
        // A null candidate means gathering has finished; there is nothing to
        // send, and the other side does not need to be told.
        if (!event.candidate) return;
        socket.send({
          type: "call.candidate",
          conversation_id: forConversation,
          candidate: event.candidate.toJSON(),
          // A one-to-one conversation has only one possible recipient and the
          // server addresses it; a mesh has to say which peer this is for.
          ...(isGroup.current ? { target_user_id: user.id } : {}),
        });
      };

      pc.ontrack = (event) => {
        peer.stream = event.streams[0] ?? null;
        syncPeers();
      };

      // Not user-facing -- this is here so a call that still fails after the
      // TURN fallback above can be diagnosed from one console log instead of
      // another guess: "checking" stuck with no relay candidate means the
      // TURN relay itself was unreachable; "connected" with silence points
      // elsewhere entirely (a track/codec problem, not networking).
      pc.oniceconnectionstatechange = () => {
        console.info("[call] ICE state:", user.id, pc.iceConnectionState);
      };

      pc.onconnectionstatechange = () => {
        console.info("[call] connection state:", user.id, pc.connectionState);
        // A connection that has already been replaced or dropped must not
        // still be driving the call's state.
        if (peers.current.get(user.id) !== peer) return;

        if (pc.connectionState === "connected") {
          clearStall();
          peer.connected = true;
          setCall((current) => ({
            ...current,
            status: "active",
            reconnecting: false,
            // Preserved across a recovery, or the in-call timer restarts at
            // zero every time the network hiccups.
            startedAt: current.startedAt ?? Date.now(),
          }));
          syncPeers();
        }

        // "disconnected" is WebRTC's word for "connectivity checks are
        // failing *right now*", not "the call is over": the ICE agent is
        // still trying, and it recovers on its own within a second or two
        // routinely -- when a candidate pair flaps, or when the connection
        // moves onto the relay pair. Ending the call here (which this did)
        // killed the call the instant either side hiccuped, and, because
        // finish() sends nothing to the peer, left the other end to die by
        // itself and blame the network. The browser is the right judge of
        // when checks have genuinely run out; that verdict is "failed".
        if (pc.connectionState === "disconnected") {
          peer.connected = false;
          syncPeers();
          if (!isGroup.current) {
            setCall((current) => ({ ...current, reconnecting: true }));
            startStall(pc);
          }
        }

        if (pc.connectionState === "failed") {
          if (isGroup.current) {
            // One connection of several. Dropping this person is the whole
            // call for everybody else, so the rest of the mesh carries on.
            closePeer(user.id);
            syncPeers();
            if (peers.current.size === 0 && statusRef.current === "active") {
              finish("Everyone else has left the call.");
            }
            return;
          }
          clearStall();
          // Read the stats before finish() closes the connection out from
          // under them -- getStats on a closed peer connection reports
          // nothing, which is how a diagnostic silently becomes useless.
          void reportIceFailure(pc).finally(() => {
            finish("Could not connect. One of you may be on a network that blocks direct calls.");
          });
        }
      };

      // Whatever this client is already sending goes to the new peer too. On
      // the calling side the capture happens first; on the answering side a
      // peer can be built from an offer that arrives while it is still in
      // flight, and captureMedia adds the tracks to it when it completes.
      const stream = localStream.current;
      if (stream) stream.getTracks().forEach((track) => pc.addTrack(track, stream));

      syncPeers();
      return peer;
    },
    [syncPeers, closePeer, finish, clearStall, startStall],
  );

  /** Open a fresh track of `kind` and put it in place of whatever this call is
   *  currently sending, on every connection at once.
   *
   *  Two callers share this: a track's own `onended` -- fired when its device
   *  disappears mid-call (unplugged, revoked, put to sleep) -- and the device
   *  menu, when the person picks a different one on purpose. `deviceId`
   *  defaults to the stored preference so recovery always reopens *that*
   *  device, not whichever one happened to answer first.
   *
   *  If nothing answers -- the unplugged device had no sibling, or the newly
   *  chosen one stopped responding -- the call does not end over it; the
   *  corresponding control just reads "off", exactly as if the person had
   *  turned it off themselves. */
  const switchDevice = useCallback(async (
    kind: "audio" | "video",
    deviceId?: string,
  ) => {
    const stream = localStream.current;
    if (!stream) return; // no call is running

    const id = deviceId ?? (kind === "audio" ? micDeviceRef.current : cameraDeviceRef.current);
    const wasEnabled = kind === "audio" ? micOnRef.current : cameraOnRef.current;

    try {
      const fresh = await navigator.mediaDevices.getUserMedia(
        kind === "audio"
          ? { audio: buildAudioConstraint(id) }
          : { video: buildVideoConstraint(id) },
      );
      const newTrack = fresh.getTracks()[0];
      newTrack.enabled = wasEnabled;

      // The call can end while the device is opening; without this the fresh
      // track would be left running with nothing to attach it to.
      if (localStream.current !== stream) {
        newTrack.stop();
        return;
      }

      // Replaced on every connection: in a mesh the same camera feeds all of
      // them, and a device change that reached only one peer would leave the
      // others watching a frozen frame.
      for (const peer of peers.current.values()) {
        const sender = peer.pc.getSenders().find((s) => s.track?.kind === kind);
        await sender?.replaceTrack(newTrack);
      }

      for (const old of stream.getTracks().filter((t) => t.kind === kind)) {
        stream.removeTrack(old);
        old.stop();
      }
      stream.addTrack(newTrack);
      // Recovery always chases the stored preference, not this specific id --
      // if the device that just answered disappears too, the next attempt
      // should still try the one the person actually asked for.
      newTrack.onended = () => void switchDevice(kind);
      void refreshDevices();
    } catch {
      setCall((current) =>
        kind === "audio" ? { ...current, micOn: false } : { ...current, cameraOn: false });
    }
  }, [refreshDevices]);

  /** Remember a device choice and, if a call is live, switch to it now rather
   *  than on the next call. */
  const setMicDevice = useCallback((id: string) => {
    writeStoredDevice(MIC_DEVICE_KEY, id);
    micDeviceRef.current = id;
    setMicDeviceIdState(id);
    if (localStream.current) void switchDevice("audio", id);
  }, [switchDevice]);

  const setCameraDevice = useCallback((id: string) => {
    writeStoredDevice(CAMERA_DEVICE_KEY, id);
    cameraDeviceRef.current = id;
    setCameraDeviceIdState(id);
    if (localStream.current) void switchDevice("video", id);
  }, [switchDevice]);

  /** Ask for the microphone (and camera), and add the tracks to the call.
   *
   *  This is the call that raises the browser's permission prompt, so it is
   *  deliberately the first thing that happens in both directions — there is no
   *  point negotiating a call that the person then cannot speak into. */
  const captureMedia = useCallback(async (kind: CallKind) => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: buildAudioConstraint(micDeviceRef.current),
      video: kind === "video" ? buildVideoConstraint(cameraDeviceRef.current) : false,
    });
    localStream.current = stream;
    stream.getTracks().forEach((track) => {
      // Any connection built before permission was granted gets the tracks now.
      for (const peer of peers.current.values()) peer.pc.addTrack(track, stream);
      track.onended = () => void switchDevice(track.kind as "audio" | "video");
    });
    void refreshDevices(); // labels are only populated once permission is granted
    setCall((current) => ({ ...current, localStream: stream, micOn: true, cameraOn: true }));
    return stream;
  }, [refreshDevices, switchDevice]);

  /** Place a call.
   *
   *  `peer` is the person being called in a one-to-one conversation, and is
   *  ignored for a group, where the invite rings everybody and there is no one
   *  offer to make -- each person who answers negotiates their own connection. */
  const start = useCallback(
    async (conversation: Conversation, peer: User | null, kind: CallKind) => {
      const group = conversation.type !== "direct";
      if (!group && !peer) return;

      const unsupported = unsupportedReason();
      if (unsupported) {
        finish(unsupported);
        return;
      }

      setCall({
        ...IDLE,
        status: "dialling",
        kind,
        conversationId: conversation.id,
        isGroup: group,
        peer,
      });
      conversationId.current = conversation.id;
      isGroup.current = group;
      callKind.current = kind;

      try {
        await captureMedia(kind);

        if (group) {
          socket.send({
            type: "call.invite",
            conversation_id: conversation.id,
            call_type: kind,
          });
          return;
        }

        const created = await createPeer(peer!);
        if (!created) return;
        const offer = await created.pc.createOffer();
        await created.pc.setLocalDescription(offer);

        socket.send({
          type: "call.invite",
          conversation_id: conversation.id,
          call_type: kind,
          sdp: { type: offer.type, sdp: offer.sdp },
        });
      } catch (error) {
        finish(describeMediaError(error, kind));
      }
    },
    [createPeer, captureMedia, finish],
  );

  /** Answer the call that is currently ringing. */
  const accept = useCallback(async () => {
    const id = conversationId.current;
    if (id === null) return;
    const group = isGroup.current;
    const offer = pendingOffer.current;
    const caller = call.peer;
    if (!group && (!offer || !caller)) return;

    const unsupported = unsupportedReason();
    if (unsupported) {
      socket.send({ type: "call.decline", conversation_id: id });
      finish(unsupported);
      return;
    }

    setCall((current) => ({ ...current, status: "connecting" }));

    try {
      await captureMedia(call.kind);

      if (group) {
        // "I am in this call." Everyone already in it opens a connection to
        // us, and we open one to whoever we are responsible for offering as
        // their own announcements arrive -- see the call.joined handler.
        socket.send({ type: "call.accept", conversation_id: id });
        return;
      }

      const created = await createPeer(caller!);
      if (!created) return;

      await created.pc.setRemoteDescription(new RTCSessionDescription(offer!));
      // Safe now that a remote description exists.
      await flushEarly(created);

      const answer = await created.pc.createAnswer();
      await created.pc.setLocalDescription(answer);

      socket.send({
        type: "call.accept",
        conversation_id: id,
        sdp: { type: answer.type, sdp: answer.sdp },
      });
    } catch (error) {
      socket.send({ type: "call.decline", conversation_id: id });
      finish(describeMediaError(error, call.kind));
    }
  }, [call.kind, call.peer, createPeer, captureMedia, flushEarly, finish]);

  /** Refuse an incoming call. */
  const decline = useCallback(() => {
    const id = conversationId.current;
    if (id !== null) socket.send({ type: "call.decline", conversation_id: id });
    finish();
  }, [finish]);

  /** Leave a call that is dialling, connecting or active. In a group this ends
   *  it for this client only -- the others carry on without us. */
  const hangup = useCallback(() => {
    const id = conversationId.current;
    if (id !== null) socket.send({ type: "call.hangup", conversation_id: id });
    finish();
  }, [finish]);

  /** Mute and unmute.
   *
   *  `track.enabled = false` keeps the track in the connection but sends
   *  silence, so the negotiated session stays intact. Stopping the track
   *  instead would require renegotiating to get audio back. */
  const toggleMic = useCallback(() => {
    const track = localStream.current?.getAudioTracks()[0];
    if (!track) return;
    track.enabled = !track.enabled;
    setCall((current) => ({ ...current, micOn: track.enabled }));
  }, []);

  const toggleCamera = useCallback(() => {
    const track = localStream.current?.getVideoTracks()[0];
    if (!track) return;
    track.enabled = !track.enabled;
    setCall((current) => ({ ...current, cameraOn: track.enabled }));
  }, []);

  const dismissError = useCallback(() => {
    setCall((current) => ({ ...current, error: null }));
  }, []);

  // --- signalling ---------------------------------------------------------

  useEffect(() => {
    const unsubscribe = socket.on((event) => {
      const data = event.data as Record<string, unknown>;
      /** Frames for a call that has already ended -- this one hung up, or a
       *  fresh one started since -- must never be applied to whatever
       *  connection happens to exist now. */
      const mine = () => data.conversation_id === conversationId.current;
      const joined = () =>
        statusRef.current === "dialling"
        || statusRef.current === "connecting"
        || statusRef.current === "active";

      switch (event.type) {
        case "call.incoming": {
          const id = data.conversation_id as number;
          const caller = toUser(data.caller as UserDTO);

          // Already on a call, or already ringing with one: decline
          // automatically. The server keeps no call state, so "busy" is
          // something only this client can know. The peer map alone isn't
          // enough -- it stays empty for the whole "ringing" phase, since
          // connections are only built from start()/accept(); without the
          // status check, a second incoming call while the first is still
          // just ringing silently overwrote it instead of being declined.
          if (peers.current.size || statusRef.current !== "idle") {
            socket.send({ type: "call.decline", conversation_id: id });
            return;
          }

          const group = data.is_group === true;
          const kind = data.call_type as CallKind;
          conversationId.current = id;
          isGroup.current = group;
          callKind.current = kind;
          // A group invite carries no offer: the connections are negotiated
          // per pair once this client announces that it has joined.
          pendingOffer.current = group ? null : (data.sdp as RTCSessionDescriptionInit);
          ringingFrom.current = caller.id;
          setCall({
            ...IDLE,
            status: "ringing",
            kind,
            conversationId: id,
            isGroup: group,
            peer: caller,
          });
          break;
        }

        case "call.accepted": {
          // One-to-one only: the answer to the offer that went out with the
          // invite.
          if (!mine()) return;
          const peer = peers.current.values().next().value as Peer | undefined;
          if (!peer) return;
          setCall((current) => ({ ...current, status: "connecting" }));
          void (async () => {
            try {
              await peer.pc.setRemoteDescription(
                new RTCSessionDescription(data.sdp as RTCSessionDescriptionInit),
              );
              await flushEarly(peer);
            } catch {
              // Without this the answer silently fails to apply and the
              // caller sits on "Connecting…" with nothing to act on.
              finish("The call could not be set up. Try again.");
            }
          })();
          break;
        }

        case "call.joined": {
          // Someone is in this group call. Exactly one of the pair offers,
          // and it is the lower user id -- a rule both sides can apply from
          // what they already know, with no server state and no glare.
          if (!mine() || !joined()) return;
          const person = toUser(data.participant as UserDTO);
          if (person.id === meIdRef.current || peers.current.has(person.id)) return;

          if (meIdRef.current > person.id) {
            // They offer -- but they cannot, because they do not know we are
            // here: they joined before us, so we never appeared in an
            // announcement they saw. Announcing ourselves again is what tells
            // them. Anyone who already has us ignores it, so this settles
            // rather than echoes.
            socket.send({ type: "call.accept", conversation_id: data.conversation_id });
            return;
          }

          void (async () => {
            const peer = await createPeer(person);
            if (!peer) return;
            const offer = await peer.pc.createOffer();
            await peer.pc.setLocalDescription(offer);
            socket.send({
              type: "call.offer",
              conversation_id: data.conversation_id,
              target_user_id: person.id,
              call_type: callKind.current,
              sdp: { type: offer.type, sdp: offer.sdp },
            });
          })().catch(() => {
            closePeer(person.id);
            syncPeers();
          });
          break;
        }

        case "call.peer_offer": {
          if (!mine() || !joined()) return;
          const person = toUser(data.peer as UserDTO);
          void (async () => {
            const peer = await createPeer(person);
            if (!peer) return;
            await peer.pc.setRemoteDescription(
              new RTCSessionDescription(data.sdp as RTCSessionDescriptionInit),
            );
            await flushEarly(peer);
            const answer = await peer.pc.createAnswer();
            await peer.pc.setLocalDescription(answer);
            socket.send({
              type: "call.answer",
              conversation_id: data.conversation_id,
              target_user_id: person.id,
              sdp: { type: answer.type, sdp: answer.sdp },
            });
          })().catch(() => {
            // One peer failing to negotiate is not the call failing; the rest
            // of the mesh is unaffected.
            closePeer(person.id);
            syncPeers();
          });
          break;
        }

        case "call.peer_answer": {
          if (!mine()) return;
          const person = toUser(data.peer as UserDTO);
          const peer = peers.current.get(person.id);
          if (!peer) return;
          void (async () => {
            await peer.pc.setRemoteDescription(
              new RTCSessionDescription(data.sdp as RTCSessionDescriptionInit),
            );
            await flushEarly(peer);
          })().catch(() => {
            closePeer(person.id);
            syncPeers();
          });
          break;
        }

        case "call.candidate": {
          if (!mine()) return;

          const candidate = data.candidate as RTCIceCandidateInit;
          const from = data.from_user_id as number;
          const peer = peers.current.get(from);
          // Held until there is a connection with a remote description to
          // attach them to; the first candidates routinely arrive before the
          // answer does, and, for the person being called, before their
          // connection has been built at all.
          if (!peer || !peer.pc.remoteDescription) {
            const held = early.current.get(from) ?? [];
            held.push(candidate);
            early.current.set(from, held);
            return;
          }
          void peer.pc.addIceCandidate(new RTCIceCandidate(candidate)).catch(() => {
            // A candidate that cannot be added is not fatal: the connection
            // continues with whichever paths did work.
          });
          break;
        }

        case "call.ended": {
          if (!mine()) return;
          if (!isGroup.current) {
            finish();
            return;
          }

          // A group call outlives any one person leaving it.
          const from = data.from_user_id as number;
          if (statusRef.current === "ringing") {
            // Nobody has been connected yet, so the only leaving that matters
            // is the caller's: that is this call being cancelled.
            if (from === ringingFrom.current) finish();
            return;
          }
          if (!peers.current.has(from)) return; // someone who never joined
          closePeer(from);
          syncPeers();
          if (peers.current.size === 0 && statusRef.current === "active") finish();
          break;
        }

        case "call.unavailable":
          finish(
            isGroup.current
              ? "Nobody else in this group is online right now."
              : "They are not online right now.",
          );
          break;

        case "error": {
          // The server rejects an invite it will not relay -- and, briefly
          // after a deploy, a backend that predates group call support rejects
          // every group one. Without this the caller sits on "Calling..."
          // forever.
          //
          // Error frames are generic, so this only acts while a call is being
          // set up: during an active call an unrelated error must not drop it.
          if (statusRef.current !== "dialling" && statusRef.current !== "connecting") return;
          finish((data.detail as string) || "The call could not be placed.");
          break;
        }
      }
    });

    return unsubscribe;
  }, [finish, createPeer, closePeer, syncPeers, flushEarly]);

  // A call must not outlive the page, or the camera stays on after navigation.
  useEffect(() => teardown, [teardown]);

  return {
    call, start, accept, decline, hangup, toggleMic, toggleCamera, dismissError,
    devices, micDeviceId, cameraDeviceId, setMicDevice, setCameraDevice,
  };
}

export type CallController = ReturnType<typeof useCall>;
