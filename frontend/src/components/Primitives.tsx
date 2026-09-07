"use client";
import { clsx } from "@/lib/clsx";
import { Icon } from "./Icon";
import type { ReactNode } from "react";

export function Avatar({ name, size = 40, online = false, accent = false }: {
  name: string; size?: number; online?: boolean; accent?: boolean;
}) {
  const initials = name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const dot = Math.max(8, Math.round(size * 0.28));
  const font = size <= 28 ? 11 : size <= 36 ? 12 : size <= 48 ? 14 : size <= 72 ? 20 : 28;
  return (
    <span className="relative shrink-0 inline-flex items-center justify-center rounded-full font-semibold"
      style={{
        width: size, height: size, fontSize: font,
        background: accent ? "var(--color-accent-subtle)" : "var(--color-bg-hover)",
        color: accent ? "var(--color-accent-default)" : "var(--color-text-secondary)",
      }}>
      {initials}
      {online && (
        <span className="absolute rounded-full border-2 border-surface bg-status-online"
          style={{ width: dot, height: dot, right: -1, bottom: -1 }} />
      )}
    </span>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({ variant = "primary", loading = false, icon, children,
  className, ...rest }: {
  variant?: ButtonVariant; loading?: boolean; icon?: ReactNode; children?: ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const looks: Record<ButtonVariant, string> = {
    primary: "bg-accent text-ink-onAccent hover:bg-accent-hover border-transparent",
    secondary: "bg-surface text-ink border-line hover:bg-hover hover:border-line-strong",
    ghost: "bg-transparent text-ink-muted border-transparent hover:bg-hover hover:text-ink",
    danger: "bg-status-danger text-ink-onAccent border-transparent hover:opacity-90",
  };
  return (
    <button
      className={clsx("inline-flex h-10 items-center justify-center gap-sm rounded-md border px-lg",
        "text-md font-medium transition-colors disabled:opacity-70 disabled:pointer-events-none",
        looks[variant], className)}
      disabled={loading || rest.disabled} {...rest}>
      {loading && <Spinner />}{icon}{children}
    </button>
  );
}

export function Spinner({ size = 14 }: { size?: number }) {
  return (
    <span className="inline-block animate-spin rounded-full border-2 border-current border-t-transparent"
      style={{ width: size, height: size, opacity: 0.65 }} role="status" aria-label="Loading" />
  );
}

export function Field({ label, helper, error, id, ...rest }: {
  label: string; helper?: string; error?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  const describedBy = error ? `${id}-error` : helper ? `${id}-helper` : undefined;
  return (
    <div className="flex flex-col gap-xs">
      <label htmlFor={id} className="text-md font-medium">{label}</label>
      <input id={id} aria-invalid={!!error} aria-describedby={describedBy}
        className={clsx("h-10 rounded-md border bg-surface px-md text-base outline-none",
          "placeholder:text-ink-faint focus:border-2 focus:border-line-focus",
          error ? "border-2 border-status-danger" : "border-line")}
        {...rest} />
      {error ? (
        <p id={`${id}-error`} className="flex items-center gap-[5px] text-sm text-ink-danger">
          <Icon name="warn" size={13} strokeWidth={2} />{error}
        </p>
      ) : helper ? (
        <p id={`${id}-helper`} className="text-sm text-ink-muted">{helper}</p>
      ) : null}
    </div>
  );
}

export function Badge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full px-[6px]
      text-xs font-semibold bg-status-unread text-status-unreadText"
      aria-label={`${count} unread messages`}>
      {count > 99 ? "99+" : count}
    </span>
  );
}

export function Chip({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "accent" }) {
  return (
    <span className={clsx("rounded-full px-[9px] py-[3px] text-xs font-semibold",
      tone === "accent" ? "bg-accent-subtle text-accent" : "bg-hover text-ink-muted")}>
      {children}
    </span>
  );
}

export function Skeleton({ className, ...rest }: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={clsx("block animate-pulse rounded-md bg-hover", className)} {...rest} />;
}

export function EmptyState({ icon, title, body, action }: {
  icon: ReactNode; title: string; body: string; action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-lg p-2xl text-center">
      <div className="flex h-[88px] w-[88px] items-center justify-center rounded-full
        bg-accent-subtle text-accent">{icon}</div>
      <div className="flex flex-col gap-xs">
        <h2 className="text-xl font-semibold">{title}</h2>
        <p className="max-w-[380px] text-base text-ink-muted">{body}</p>
      </div>
      {action}
    </div>
  );
}
