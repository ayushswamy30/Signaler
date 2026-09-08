"use client";
import Link from "next/link";
import { useRef, type ReactNode } from "react";
import { Icon } from "@/components/Icon";
import { CursorWave } from "@/components/CursorWave";

export function AuthShell({ title, subtitle, children, footer, width = 400 }: {
  title: string; subtitle: string; children: ReactNode; footer?: ReactNode; width?: number;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  return (
    <main id="main" className="flex min-h-dvh items-center justify-center bg-canvas p-lg">
      <CursorWave avoidRef={cardRef} />
      <div ref={cardRef} className="flex w-full flex-col gap-xl rounded-xl border border-line
        bg-surface p-2xl shadow-sm" style={{ maxWidth: width }}>
        <Link href="/" className="flex items-center gap-[10px] text-ink no-underline">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent text-white">
            <Icon name="send" size={17} strokeWidth={1.9} />
          </span>
          <span className="text-2xl font-bold tracking-tight">Signaler</span>
        </Link>
        <div className="flex flex-col gap-[4px]">
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="text-base text-ink-muted">{subtitle}</p>
        </div>
        {children}
        {footer}
      </div>
    </main>
  );
}
