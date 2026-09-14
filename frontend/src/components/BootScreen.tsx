"use client";

/** The screen shown while the app works out whether you are signed in.
 *
 *  Shared by every auth-gated page, because the wait it covers is the same
 *  one: a session check against a backend that, on the free tier, may be
 *  asleep. It is deliberately wordy for a loading screen -- a stall here used
 *  to be indistinguishable from a broken page, which is exactly the report
 *  that produced this file. */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { Icon } from "./Icon";
import { CursorWave } from "./CursorWave";

export function BootScreen() {
  const { waking } = useAuth();
  const contentRef = useRef<HTMLDivElement>(null);
  // The escape hatch appears on a delay rather than immediately: on a warm
  // server this screen is gone within a frame or two, and an offer to "go to
  // sign in" that flashed past every time would read as a failure that had
  // not happened.
  const [stalled, setStalled] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setStalled(true), 4000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flex h-dvh items-center justify-center bg-canvas p-lg">
      <CursorWave avoidRef={contentRef} />
      <div ref={contentRef} className="flex w-full max-w-[380px] flex-col items-center gap-lg
        text-center" role="status" aria-label="Loading Signaler">
        <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-accent text-white">
          <Icon name="send" size={22} strokeWidth={1.9} />
        </span>

        {/* This screen used to be an icon and a faint grey bar: no words at
            all, so a stall was indistinguishable from a page that had failed
            to render. It now says what it is waiting for. */}
        <div className="flex flex-col gap-xs">
          <p className="text-lg font-semibold">
            {waking ? "Waking the server…" : "Signing you in…"}
          </p>
          <p aria-live="polite" className="text-md text-ink-muted">
            {waking
              ? "The free-tier backend sleeps after 15 minutes without traffic. The first request wakes it, which can take up to a minute."
              : "Checking your saved session."}
          </p>
        </div>

        {/* A bar that actually moves. The old one was a pulsing block in the
            hover tint, which on the canvas background is very nearly the
            background -- it read as nothing happening at all. */}
        <div className="h-[4px] w-[180px] overflow-hidden rounded-full bg-hover">
          <div className="h-full w-1/3 rounded-full bg-accent motion-safe:animate-boot-sweep" />
        </div>

        {stalled && (
          <Link href="/login" className="text-md font-medium text-ink-link">
            Go to sign in
          </Link>
        )}
      </div>
    </div>
  );
}
