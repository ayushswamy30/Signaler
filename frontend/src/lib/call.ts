"use client";

/** Voice and video calling over WebRTC.
 *
 *  The server never carries audio or video. It relays two small JSON blobs —
 *  a session description and a stream of network candidates — and once the two
 *  browsers agree on a path, the media flows directly between the devices.
 *  That is why a call keeps working at full quality on a free-tier server that
 *  could never push video itself.
 *
 *  Everything here is one-to-one. A group call needs either a mesh of N×(N−1)
 *  peer connections or a media server to mix the streams; the backend refuses
 *  group conversations outright rather than half-connecting three people. */

import { useCallback, useEffect, useRef, useState } from "react";
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
 *  carriers hit it routinely.
 *
 *  Open Relay Project (metered.ca) is a free, keyless TURN relay meant for
 *  exactly this gap. Its bandwidth is rate-limited and shared with everyone
 *  using the same public credentials, so it is a fallback path, not a
 *  guarantee — a paid TURN provider (credentials from an env var, injected at
 *  build time like `NEXT_PUBLIC_API_URL`) is the production-grade version of
 *  this same fix. */
const ICE_SERVERS: RTCIceServer[] = [
  { urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] },
  {
    urls: [
      "turn:openrelay.metered.ca:80",
      "turn:openrelay.metered.ca:443",
      "turn:openrelay.metered.ca:443?transport=tcp",
      "turn:openrelay.metered.ca:3478",
      "turn:openrelay.metered.ca:3478?transport=tcp",
    ],
    username: "openrelayproject",
    credential: "openrelayproject",
  },
];

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

interface CallSnapshot {
  status: CallStatus;
  kind: CallKind;
  conversationId: number | null;
  /** Who is on the other end. Known from the moment a call starts or arrives. */
  peer: User | null;
  localStream: MediaStream | null;
  remoteStream: MediaStream | null;
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
  peer: null,
  localStream: null,
  remoteStream: null,
  micOn: true,
  cameraOn: true,
  reconnecting: false,
  error: null,
  startedAt: null,
};

export function useCall() {
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

  // WebRTC objects are mutable and long-lived, and must not trigger renders.
  const connection = useRef<RTCPeerConnection | null>(null);
  const localStream = useRef<MediaStream | null>(null);
  const conversationId = useRef<number | null>(null);
  /** The offer that arrived with an incoming call, replayed on accept. */
  const pendingOffer = useRef<RTCSessionDescriptionInit | null>(null);
  /** Candidates that arrive before the remote description is set.
   *  addIceCandidate throws in that window, and the first candidates routinely
   *  beat the answer, so they are held and replayed rather than dropped. */
  const earlyCandidates = useRef<RTCIceCandidateInit[]>([]);
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

  /** Release the camera, microphone and peer connection.
   *
   *  Stopping every track matters: a MediaStream that is merely dropped leaves
   *  the camera light on, which reads — correctly — as still being watched. */
  const teardown = useCallback(() => {
    if (stallTimer.current) clearTimeout(stallTimer.current);
    stallTimer.current = null;

    localStream.current?.getTracks().forEach((track) => track.stop());
    localStream.current = null;

    if (connection.current) {
      // Detach the handlers first: closing fires state changes that would
      // otherwise re-enter this and re-render a call that no longer exists.
      connection.current.onicecandidate = null;
      connection.current.ontrack = null;
      connection.current.onconnectionstatechange = null;
      connection.current.oniceconnectionstatechange = null;
      connection.current.close();
      connection.current = null;
    }

    conversationId.current = null;
    pendingOffer.current = null;
    earlyCandidates.current = [];
  }, []);

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

  /** The backstop under a call sitting in "disconnected".
   *
   *  Recovery is the browser's job -- it will either get the checks passing
   *  again or escalate to "failed" -- and it is better at judging that than a
   *  timer here would be. This exists only for the case where it does
   *  neither, so a call cannot sit on "Reconnecting…" forever. */
  const startStall = useCallback(
    (pc: RTCPeerConnection) => {
      if (stallTimer.current) return; // already counting down for this drop
      stallTimer.current = setTimeout(() => {
        stallTimer.current = null;
        if (connection.current !== pc || pc.connectionState === "connected") return;
        finish("The connection dropped and could not be recovered.");
      }, STALL_LIMIT_MS);
    },
    [finish],
  );

  /** Build the peer connection and wire its callbacks. */
  const createConnection = useCallback(
    (forConversation: number) => {
      const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

      pc.onicecandidate = (event) => {
        // A null candidate means gathering has finished; there is nothing to
        // send, and the other side does not need to be told.
        if (!event.candidate) return;
        socket.send({
          type: "call.candidate",
          conversation_id: forConversation,
          candidate: event.candidate.toJSON(),
        });
      };

      pc.ontrack = (event) => {
        setCall((current) => ({ ...current, remoteStream: event.streams[0] ?? null }));
      };

      // Not user-facing -- this is here so a call that still fails after the
      // TURN fallback above can be diagnosed from one console log instead of
      // another guess: "checking" stuck with no relay candidate means the
      // TURN relay itself was unreachable; "connected" with silence points
      // elsewhere entirely (a track/codec problem, not networking).
      pc.oniceconnectionstatechange = () => {
        console.info("[call] ICE state:", pc.iceConnectionState);
      };

      pc.onconnectionstatechange = () => {
        console.info("[call] connection state:", pc.connectionState);

        if (pc.connectionState === "connected") {
          clearStall();
          setCall((current) => ({
            ...current,
            status: "active",
            reconnecting: false,
            // Preserved across a recovery, or the in-call timer restarts at
            // zero every time the network hiccups.
            startedAt: current.startedAt ?? Date.now(),
          }));
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
          setCall((current) => ({ ...current, reconnecting: true }));
          startStall(pc);
        }

        if (pc.connectionState === "failed") {
          clearStall();
          // Read the stats before finish() closes the connection out from
          // under them -- getStats on a closed peer connection reports
          // nothing, which is how a diagnostic silently becomes useless.
          void reportIceFailure(pc).finally(() => {
            finish("Could not connect. One of you may be on a network that blocks direct calls.");
          });
        }
      };

      connection.current = pc;
      return pc;
    },
    [finish, clearStall, startStall],
  );

  /** Open a fresh track of `kind` and put it in place of whatever this call is
   *  currently sending.
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
    pc: RTCPeerConnection,
    deviceId?: string,
  ) => {
    if (connection.current !== pc) return; // this call has already ended
    const stream = localStream.current;
    if (!stream) return;

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

      const sender = pc.getSenders().find((s) => s.track?.kind === kind);
      await sender?.replaceTrack(newTrack);

      for (const old of stream.getTracks().filter((t) => t.kind === kind)) {
        stream.removeTrack(old);
        old.stop();
      }
      stream.addTrack(newTrack);
      // Recovery always chases the stored preference, not this specific id --
      // if the device that just answered disappears too, the next attempt
      // should still try the one the person actually asked for.
      newTrack.onended = () => void switchDevice(kind, pc);
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
    if (connection.current) void switchDevice("audio", connection.current, id);
  }, [switchDevice]);

  const setCameraDevice = useCallback((id: string) => {
    writeStoredDevice(CAMERA_DEVICE_KEY, id);
    cameraDeviceRef.current = id;
    setCameraDeviceIdState(id);
    if (connection.current) void switchDevice("video", connection.current, id);
  }, [switchDevice]);

  /** Ask for the microphone (and camera), and add the tracks to the call.
   *
   *  This is the call that raises the browser's permission prompt, so it is
   *  deliberately the first thing that happens in both directions — there is no
   *  point negotiating a call that the person then cannot speak into. */
  const captureMedia = useCallback(async (kind: CallKind, pc: RTCPeerConnection) => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: buildAudioConstraint(micDeviceRef.current),
      video: kind === "video" ? buildVideoConstraint(cameraDeviceRef.current) : false,
    });
    localStream.current = stream;
    stream.getTracks().forEach((track) => {
      pc.addTrack(track, stream);
      track.onended = () => void switchDevice(track.kind as "audio" | "video", pc);
    });
    void refreshDevices(); // labels are only populated once permission is granted
    setCall((current) => ({ ...current, localStream: stream, micOn: true, cameraOn: true }));
    return stream;
  }, [refreshDevices, switchDevice]);

  /** Place a call. */
  const start = useCallback(
    async (conversation: Conversation, peer: User, kind: CallKind) => {
      if (conversation.type !== "direct") return;

      const unsupported = unsupportedReason();
      if (unsupported) {
        finish(unsupported);
        return;
      }

      setCall({ ...IDLE, status: "dialling", kind, conversationId: conversation.id, peer });
      conversationId.current = conversation.id;

      try {
        const pc = createConnection(conversation.id);
        await captureMedia(kind, pc);

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

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
    [createConnection, captureMedia, finish],
  );

  /** Answer the call that is currently ringing. */
  const accept = useCallback(async () => {
    const offer = pendingOffer.current;
    const id = conversationId.current;
    if (!offer || id === null) return;

    const unsupported = unsupportedReason();
    if (unsupported) {
      socket.send({ type: "call.decline", conversation_id: id });
      finish(unsupported);
      return;
    }

    setCall((current) => ({ ...current, status: "connecting" }));

    try {
      const pc = createConnection(id);
      await captureMedia(call.kind, pc);

      await pc.setRemoteDescription(new RTCSessionDescription(offer));
      // Safe now that a remote description exists.
      for (const candidate of earlyCandidates.current) {
        await pc.addIceCandidate(new RTCIceCandidate(candidate));
      }
      earlyCandidates.current = [];

      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      socket.send({
        type: "call.accept",
        conversation_id: id,
        sdp: { type: answer.type, sdp: answer.sdp },
      });
    } catch (error) {
      socket.send({ type: "call.decline", conversation_id: id });
      finish(describeMediaError(error, call.kind));
    }
  }, [call.kind, createConnection, captureMedia, finish]);

  /** Refuse an incoming call. */
  const decline = useCallback(() => {
    const id = conversationId.current;
    if (id !== null) socket.send({ type: "call.decline", conversation_id: id });
    finish();
  }, [finish]);

  /** Hang up a call that is dialling, connecting or active. */
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

      switch (event.type) {
        case "call.incoming": {
          const id = data.conversation_id as number;
          const caller = toUser(data.caller as UserDTO);

          // Already on a call, or already ringing with one: decline
          // automatically. The server keeps no call state, so "busy" is
          // something only this client can know. connection.current alone
          // isn't enough -- it stays null for the whole "ringing" phase,
          // since createConnection() only ever runs from start()/accept();
          // without the status check, a second incoming call while the
          // first is still just ringing silently overwrote it instead of
          // being declined.
          if (connection.current || statusRef.current !== "idle") {
            socket.send({ type: "call.decline", conversation_id: id });
            return;
          }

          conversationId.current = id;
          pendingOffer.current = data.sdp as RTCSessionDescriptionInit;
          setCall({
            ...IDLE,
            status: "ringing",
            kind: data.call_type as CallKind,
            conversationId: id,
            peer: caller,
          });
          break;
        }

        case "call.accepted": {
          const pc = connection.current;
          // Guards against an accept meant for a call that has already
          // ended (this one hung up, or a fresh one started) landing on
          // whatever connection happens to exist now.
          if (!pc || data.conversation_id !== conversationId.current) return;
          setCall((current) => ({ ...current, status: "connecting" }));
          void (async () => {
            try {
              await pc.setRemoteDescription(
                new RTCSessionDescription(data.sdp as RTCSessionDescriptionInit),
              );
              for (const candidate of earlyCandidates.current) {
                await pc.addIceCandidate(new RTCIceCandidate(candidate));
              }
              earlyCandidates.current = [];
            } catch {
              // Without this the answer silently fails to apply and the
              // caller sits on "Connecting…" with nothing to act on.
              finish("The call could not be set up. Try again.");
            }
          })();
          break;
        }

        case "call.candidate": {
          // Checked before anything else: a candidate for a call that has
          // already ended (this one hung up, or a fresh one started since)
          // must never be queued at all, or it sits in earlyCandidates and
          // gets replayed into the *next* call's connection instead --
          // wrong ICE credentials, thrown addIceCandidate, a perfectly
          // healthy new call torn down over a leftover from the last one.
          if (data.conversation_id !== conversationId.current) return;

          const candidate = data.candidate as RTCIceCandidateInit;
          const pc = connection.current;
          // Held until there is a remote description to attach them to; the
          // first candidates routinely arrive before the answer does.
          if (!pc || !pc.remoteDescription) {
            earlyCandidates.current.push(candidate);
            return;
          }
          void pc.addIceCandidate(new RTCIceCandidate(candidate)).catch(() => {
            // A candidate that cannot be added is not fatal: the connection
            // continues with whichever paths did work.
          });
          break;
        }

        case "call.ended":
          finish();
          break;

        case "call.unavailable":
          finish("They are not online right now.");
          break;

        case "error": {
          // The server rejects an invite it will not relay -- and, briefly
          // after a deploy, a backend that predates call support rejects every
          // one of them. Without this the caller sits on "Calling..." forever.
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
  }, [finish]);

  // A call must not outlive the page, or the camera stays on after navigation.
  useEffect(() => teardown, [teardown]);

  return {
    call, start, accept, decline, hangup, toggleMic, toggleCamera, dismissError,
    devices, micDeviceId, cameraDeviceId, setMicDevice, setCameraDevice,
  };
}

export type CallController = ReturnType<typeof useCall>;
