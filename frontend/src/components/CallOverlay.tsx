"use client";

/** The call surfaces: an incoming-call prompt, and the in-call screen.
 *
 *  Both are full-screen and sit above everything else, because a ringing phone
 *  that can be lost behind a window is a ringing phone you miss. */

import { useEffect, useRef, useState } from "react";
import { clsx } from "@/lib/clsx";
import type { CallController } from "@/lib/call";
import { Icon } from "./Icon";
import { Avatar, Button } from "./Primitives";

/** Attach a MediaStream to a <video>, and keep it attached as it changes.
 *
 *  `srcObject` is a property, not an attribute, so React cannot set it from
 *  JSX — it has to be assigned imperatively. */
function useStream(stream: MediaStream | null) {
  const ref = useRef<HTMLVideoElement>(null);
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
  const remoteVideo = useStream(call.remoteStream);
  const elapsed = useElapsed(call.startedAt);

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
            : elapsed ?? "Connected";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${call.kind === "video" ? "Video" : "Voice"} call with ${name}`}
      className="fixed inset-0 z-[60] flex flex-col bg-[#0B0F14] text-white"
    >
      {/* The remote video fills the screen once it arrives. Until then — and
          for every voice call — an avatar stands in, so the layout never jumps
          between an empty black rectangle and a face. */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
        {isVideo && call.remoteStream ? (
          <video
            ref={remoteVideo}
            autoPlay
            playsInline
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex flex-col items-center gap-lg">
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
            ref={localVideo}
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
        {isVideo && call.remoteStream && (
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

function CallButton({
  label,
  icon,
  onClick,
  tone = "neutral",
  pressed = false,
}: {
  label: string;
  icon: "phone" | "video" | "close" | "mute";
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
