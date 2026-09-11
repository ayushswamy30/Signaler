"use client";

/** The call surfaces: an incoming-call prompt, and the in-call screen.
 *
 *  Both are full-screen and sit above everything else, because a ringing phone
 *  that can be lost behind a window is a ringing phone you miss. */

import { useEffect, useRef, useState, type RefObject } from "react";
import { clsx } from "@/lib/clsx";
import type { CallController, CallParticipant } from "@/lib/call";
import { Icon } from "./Icon";
import { Avatar, Button } from "./Primitives";

/** Attach a MediaStream to a <video> or <audio>, and keep it attached as it
 *  changes.
 *
 *  Typed to `HTMLMediaElement` — the interface both share, and the one that
 *  actually declares `srcObject` — rather than `HTMLVideoElement`, so the
 *  same ref can be handed to either tag: a voice call has no picture to show
 *  but still needs an element playing the remote audio back.
 *
 *  `srcObject` is a property, not an attribute, so React cannot set it from
 *  JSX — it has to be assigned imperatively. */
function useStream(stream: MediaStream | null) {
  const ref = useRef<HTMLMediaElement>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (element.srcObject !== stream) element.srcObject = stream;
  }, [stream]);
  return ref;
}

/** "05:31" — how long the call has been connected. */
function useElapsed(startedAt: number | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (startedAt === null) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [startedAt]);

  if (startedAt === null) return null;
  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function CallOverlay({ controller }: { controller: CallController }) {
  const { call, accept, decline, hangup, toggleMic, toggleCamera, dismissError } = controller;

  const localVideo = useStream(call.localStream);
  // One-to-one only. A group call has a stream per person, each attached by
  // the tile that renders it.
  const remoteStream = call.isGroup ? null : call.participants[0]?.stream ?? null;
  const remoteVideo = useStream(remoteStream);
  const elapsed = useElapsed(call.startedAt);
  const [devicePickerOpen, setDevicePickerOpen] = useState(false);
  const devicePickerBox = useRef<HTMLDivElement>(null);
  // A new call starts this component back at "ringing"/"dialling" without
  // ever unmounting it, so a picker left open from the last one would
  // otherwise reappear already open.
  useEffect(() => { if (call.status === "idle") setDevicePickerOpen(false); }, [call.status]);

  // The ref spans both the toggle button and the popover, so a click on the
  // button to close it does not also count as "outside" and reopen it.
  useEffect(() => {
    if (!devicePickerOpen) return;
    function onPointerDown(event: PointerEvent) {
      if (devicePickerBox.current && !devicePickerBox.current.contains(event.target as Node)) {
        setDevicePickerOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setDevicePickerOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [devicePickerOpen]);

  // A permission refusal or an unreachable peer is worth reporting even though
  // the call itself is over, so it renders on its own.
  if (call.error) {
    return (
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-lg">
        <div role="alertdialog" aria-labelledby="call-error"
          className="flex w-full max-w-[420px] flex-col gap-lg rounded-xl bg-raised p-xl shadow-lg">
          <div className="flex items-start gap-md">
            <span className="mt-[2px] text-ink-danger"><Icon name="warn" size={22} /></span>
            <div className="flex flex-col gap-xs">
              <h2 id="call-error" className="text-lg font-semibold">Call failed</h2>
              <p className="text-base text-ink-muted">{call.error}</p>
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={dismissError}>Close</Button>
          </div>
        </div>
      </div>
    );
  }

  if (call.status === "idle") return null;

  const name = call.peer?.displayName ?? "Unknown";
  const isVideo = call.kind === "video";
  const isRinging = call.status === "ringing";

  const statusLine =
    call.status === "dialling" ? "Calling…"
      : call.status === "ringing" ? `Incoming ${call.kind} call`
        : call.status === "connecting" ? "Connecting…"
          : call.status === "ended" ? "Call ended"
            // A drop is worth saying out loud while it is being recovered --
            // silence here reads as a call that has already died.
            : call.reconnecting ? "Reconnecting…"
              : elapsed ?? "Connected";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={
        call.isGroup
          ? `Group ${call.kind === "video" ? "video" : "voice"} call`
          : `${call.kind === "video" ? "Video" : "Voice"} call with ${name}`
      }
      className="fixed inset-0 z-[60] flex flex-col bg-[#0B0F14] text-white"
    >
      {/* The remote video fills the screen once it arrives. Until then — and
          for every voice call — an avatar stands in, so the layout never jumps
          between an empty black rectangle and a face. */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
        {call.isGroup ? (
          <GroupStage call={call} name={name} statusLine={statusLine} />
        ) : isVideo && remoteStream ? (
          <video
            ref={remoteVideo as RefObject<HTMLVideoElement>}
            autoPlay
            playsInline
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex flex-col items-center gap-lg">
            {/* A voice call has no picture, but still has a remote audio
                track that needs an element to play through — without this
                the call can connect perfectly and still be silent. Hidden
                because it has no `controls` and nothing to show; it only
                exists for its audio output. */}
            {!isVideo && (
              <audio ref={remoteVideo as RefObject<HTMLAudioElement>} autoPlay hidden />
            )}
            <Avatar name={name} size={128} />
            <div className="flex flex-col items-center gap-xs">
              <p className="text-2xl font-semibold">{name}</p>
              <p aria-live="polite" className="text-lg text-white/70">{statusLine}</p>
            </div>
          </div>
        )}

        {/* Your own camera, small and mirrored — mirrored because people expect
            to see themselves as they do in a mirror, not as others see them.
            Muted, or you would hear yourself echo. */}
        {isVideo && call.localStream && (
          <video
            ref={localVideo as RefObject<HTMLVideoElement>}
            autoPlay
            playsInline
            muted
            className={clsx(
              "absolute bottom-lg right-lg h-[150px] w-[112px] scale-x-[-1] rounded-lg",
              "border border-white/15 object-cover shadow-lg md:h-[200px] md:w-[150px]",
              !call.cameraOn && "hidden",
            )}
          />
        )}

        {/* When video is running, the name moves to a banner so it does not
            cover the picture. */}
        {isVideo && remoteStream && (
          <div className="absolute left-lg top-lg flex flex-col gap-[2px] rounded-lg
            bg-black/45 px-lg py-md backdrop-blur">
            <p className="text-lg font-semibold">{name}</p>
            <p aria-live="polite" className="text-md text-white/70">{statusLine}</p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-center gap-lg border-t border-white/10 px-lg py-xl">
        {isRinging ? (
          <>
            <CallButton label="Decline" tone="danger" icon="close" onClick={decline} />
            <CallButton
              label={`Accept ${call.kind} call`}
              tone="accept"
              icon={isVideo ? "video" : "phone"}
              onClick={() => void accept()}
            />
          </>
        ) : (
          <>
            <div className="relative" ref={devicePickerBox}>
              <CallButton
                label="Choose microphone and camera"
                pressed={devicePickerOpen}
                icon="devices"
                onClick={() => setDevicePickerOpen((open) => !open)}
              />
              {devicePickerOpen && <DevicePicker controller={controller} showCamera={isVideo} />}
            </div>
            <CallButton
              label={call.micOn ? "Mute microphone" : "Unmute microphone"}
              pressed={!call.micOn}
              icon="mute"
              onClick={toggleMic}
            />
            {isVideo && (
              <CallButton
                label={call.cameraOn ? "Turn camera off" : "Turn camera on"}
                pressed={!call.cameraOn}
                icon="video"
                onClick={toggleCamera}
              />
            )}
            <CallButton label="Hang up" tone="danger" icon="close" onClick={hangup} />
          </>
        )}
      </div>
    </div>
  );
}

/** The in-call view for a group: one tile per person, plus your own.
 *
 *  A grid rather than the one-to-one screen's full-bleed video, because in a
 *  group there is no single "other end" to fill the screen with, and a layout
 *  that promoted one person would have to demote everybody else on some basis
 *  the call itself does not have. The columns follow the count, so two people
 *  are side by side and five are not five slivers. */
function GroupStage({ call, name, statusLine }: {
  call: CallController["call"]; name: string; statusLine: string;
}) {
  const isVideo = call.kind === "video";
  const people = call.participants;

  // Ringing, or nobody has answered yet: there is no grid to show, so this
  // falls back to the same single-avatar screen a one-to-one call uses. The
  // caller is the one name worth showing at this point.
  if (people.length === 0) {
    return (
      <div className="flex flex-col items-center gap-lg">
        <Avatar name={name} size={128} />
        <div className="flex flex-col items-center gap-xs">
          <p className="text-2xl font-semibold">{name}</p>
          <p aria-live="polite" className="text-lg text-white/70">
            {call.status === "dialling" ? "Waiting for someone to join…" : statusLine}
          </p>
        </div>
      </div>
    );
  }

  const columns = people.length <= 1 ? 1 : people.length <= 4 ? 2 : 3;

  return (
    <div className="flex h-full w-full flex-col gap-md p-md">
      <p aria-live="polite" className="text-center text-md text-white/70">{statusLine}</p>
      <div
        className="grid flex-1 gap-md"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {people.map((person) => (
          <PeerTile key={person.user.id} person={person} isVideo={isVideo} />
        ))}
      </div>
    </div>
  );
}

/** One person in a group call.
 *
 *  Every tile carries its own media element even in a voice call: the audio
 *  track has to be attached to something to be heard, and in a mesh there is
 *  one track per person rather than one for the call. */
function PeerTile({ person, isVideo }: { person: CallParticipant; isVideo: boolean }) {
  const media = useStream(person.stream);
  const showVideo = isVideo && person.stream !== null;

  return (
    <div className="relative flex min-h-[120px] items-center justify-center overflow-hidden
      rounded-lg bg-white/5">
      {showVideo ? (
        <video ref={media as RefObject<HTMLVideoElement>} autoPlay playsInline
          className="h-full w-full object-cover" />
      ) : (
        <>
          <audio ref={media as RefObject<HTMLAudioElement>} autoPlay hidden />
          <Avatar name={person.user.displayName} size={72} />
        </>
      )}

      <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between gap-sm
        bg-black/45 px-md py-sm backdrop-blur">
        <p className="truncate text-sm font-medium">{person.user.displayName}</p>
        {!person.connected && <p className="shrink-0 text-sm text-white/70">Connecting…</p>}
      </div>
    </div>
  );
}

/** Which microphone and camera a call uses.
 *
 *  A popover rather than a settings page: switching mid-call is the moment
 *  it is actually useful, when a call has just revealed that the wrong
 *  device answered. */
function DevicePicker({ controller, showCamera }: {
  controller: CallController; showCamera: boolean;
}) {
  const { devices, micDeviceId, cameraDeviceId, setMicDevice, setCameraDevice } = controller;

  return (
    <div role="dialog" aria-label="Choose microphone and camera"
      className="absolute bottom-full left-1/2 z-20 mb-md flex w-[240px] -translate-x-1/2 flex-col
        gap-md rounded-lg border border-white/15 bg-[#141A21] p-md shadow-lg">
      <DeviceSelect label="Microphone" value={micDeviceId} onChange={setMicDevice}
        options={devices.mics} fallback="Microphone" />
      {showCamera && (
        <DeviceSelect label="Camera" value={cameraDeviceId} onChange={setCameraDevice}
          options={devices.cameras} fallback="Camera" />
      )}
    </div>
  );
}

function DeviceSelect({ label, value, onChange, options, fallback }: {
  label: string; value: string; onChange: (id: string) => void;
  options: MediaDeviceInfo[]; fallback: string;
}) {
  return (
    <label className="flex flex-col gap-xs text-sm text-white">
      <span className="text-white/60">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-white/15 bg-white/10 px-sm py-[6px] text-sm text-white">
        <option className="text-black" value="">System default</option>
        {options.map((device, index) => (
          <option className="text-black" key={device.deviceId || index} value={device.deviceId}>
            {device.label || `${fallback} ${index + 1}`}
          </option>
        ))}
      </select>
    </label>
  );
}

function CallButton({
  label,
  icon,
  onClick,
  tone = "neutral",
  pressed = false,
}: {
  label: string;
  icon: "phone" | "video" | "close" | "mute" | "devices";
  onClick: () => void;
  tone?: "neutral" | "danger" | "accept";
  pressed?: boolean;
}) {
  const looks =
    tone === "danger"
      ? "bg-status-danger text-white hover:opacity-90"
      : tone === "accept"
        ? "bg-status-online text-white hover:opacity-90"
        // Pressed is a filled swap, not a colour change: the control has to
        // read as "off" without relying on colour alone.
        : pressed
          ? "bg-white text-[#0B0F14]"
          : "bg-white/15 text-white hover:bg-white/25";

  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      aria-pressed={tone === "neutral" ? pressed : undefined}
      className={clsx(
        "inline-flex h-[60px] w-[60px] items-center justify-center rounded-full transition-colors",
        looks,
      )}
    >
      <Icon name={icon} size={24} strokeWidth={1.8} />
    </button>
  );
}
