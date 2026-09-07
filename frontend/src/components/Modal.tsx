"use client";
import { useEffect, useRef, type ReactNode } from "react";

export function Modal({ open, onClose, title, subtitle, children, footer, width = 460 }: {
  open: boolean; onClose: () => void; title: string; subtitle?: string;
  children: ReactNode; footer?: ReactNode; width?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-lg"
      style={{ background: "rgba(11,15,20,.42)" }} onClick={onClose}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[85vh] w-full flex-col overflow-hidden rounded-xl bg-raised shadow-lg outline-none"
        style={{ maxWidth: width }}>
        <div className="flex items-start gap-md px-xl pb-md pt-lg">
          <div className="flex flex-1 flex-col gap-[2px]">
            <h2 className="text-lg font-semibold">{title}</h2>
            {subtitle && <p className="text-md text-ink-muted">{subtitle}</p>}
          </div>
          <button onClick={onClose} aria-label="Close"
            className="text-ink-faint hover:text-ink">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="1.6" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-xl pb-sm">{children}</div>
        {footer && (
          <div className="flex justify-end gap-[10px] border-t border-line-subtle px-xl py-md">{footer}</div>
        )}
      </div>
    </div>
  );
}
