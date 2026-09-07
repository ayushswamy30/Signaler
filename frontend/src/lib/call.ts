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

/** Public STUN only. STUN just tells a browser its own public address, which is
 *  enough for the great majority of home and office networks. It is *not*
 *  enough behind symmetric NAT or a strict corporate firewall, where the two
 *  peers cannot address each other at all and the media needs relaying through
 *  a TURN server. Running one costs bandwidth, so there is none here, and a
 *  call on such a network will connect its signalling and then fail to carry
 *  media — which `onconnectionstatechange` reports as `failed`. */
const ICE_SERVERS: RTCIceServer[] = [
  { urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] },
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
  error: null,
  startedAt: null,
};

export function useCall() {
  const [call, setCall] = useState<CallSnapshot>(IDLE);

  // Read inside the socket handler, which is subscribed once and would
  // otherwise close over the status as it was at subscription time.
  const statusRef = useRef<CallStatus>("idle");
  statusRef.current = call.status;

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

  /** Release the camera, microphone and peer connection.
   *
   *  Stopping every track matters: a MediaStream that is merely dropped leaves
   *  the camera light on, which reads — correctly — as still being watched. */
  const teardown = useCallback(() => {
    localStream.current?.getTracks().forEach((track) => track.stop());
    localStream.current = null;

    if (connection.current) {
      // Detach the handlers first: closing fires state changes that would
      // otherwise re-enter this and re-render a call that no longer exists.
      connection.current.onicecandidate = null;
      connection.current.ontrack = null;
      connection.current.onconnectionstatechange = null;
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

  /** Build the peer connection and wire its four callbacks. */
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

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "connected") {
          setCall((current) =>
            current.status === "active"
              ? current
              : { ...current, status: "active", startedAt: Date.now() },
          );
        }
        if (pc.connectionState === "failed") {
          // Signalling worked and media did not: almost always a network that
          // needs a TURN relay, so the message says so rather than blaming the
          // other person's connection.
          finish("Could not connect. One of you may be on a network that blocks direct calls.");
        }
        if (pc.connectionState === "disconnected" || pc.connectionState === "closed") {
          finish();
        }
      };

      connection.current = pc;
      return pc;
    },
    [finish],
  );

  /** Ask for the microphone (and camera), and add the tracks to the call.
   *
   *  This is the call that raises the browser's permission prompt, so it is
   *  deliberately the first thing that happens in both directions — there is no
   *  point negotiating a call that the person then cannot speak into. */
  const captureMedia = useCallback(async (kind: CallKind, pc: RTCPeerConnection) => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: kind === "video" ? { width: { ideal: 1280 }, height: { ideal: 720 } } : false,
    });
    localStream.current = stream;
    stream.getTracks().forEach((track) => pc.addTrack(track, stream));
    setCall((current) => ({ ...current, localStream: stream, micOn: true, cameraOn: true }));
    return stream;
  }, []);

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

          // Already on a call: decline automatically. The server keeps no call
          // state, so "busy" is something only this client can know.
          if (connection.current) {
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
          if (!pc) return;
          setCall((current) => ({ ...current, status: "connecting" }));
          void (async () => {
            await pc.setRemoteDescription(
              new RTCSessionDescription(data.sdp as RTCSessionDescriptionInit),
            );
            for (const candidate of earlyCandidates.current) {
              await pc.addIceCandidate(new RTCIceCandidate(candidate));
            }
            earlyCandidates.current = [];
          })();
          break;
        }

        case "call.candidate": {
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

  return { call, start, accept, decline, hangup, toggleMic, toggleCamera, dismissError };
}

export type CallController = ReturnType<typeof useCall>;
