"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { clsx } from "@/lib/clsx";
import { api, ApiError } from "@/lib/api";
import { toMe } from "@/lib/adapt";
import { useAuth, useRequireAuth } from "@/lib/auth";
import type { Me } from "@/lib/types";
import { Icon, type IconName } from "@/components/Icon";
import { Avatar, Button, Chip, Field } from "@/components/Primitives";
import { useTheme } from "@/components/ThemeToggle";

const SECTIONS: Array<{ id: string; label: string; icon: IconName; placeholder?: boolean }> = [
  { id: "profile", label: "Profile", icon: "settings" },
  { id: "account", label: "Account", icon: "lock" },
  { id: "privacy", label: "Privacy", icon: "users", placeholder: true },
  { id: "notifications", label: "Notifications", icon: "bell", placeholder: true },
  { id: "calls", label: "Calls", icon: "phone", placeholder: true },
  { id: "devices", label: "Linked devices", icon: "devices", placeholder: true },
  { id: "appearance", label: "Appearance", icon: "palette" },
];

export default function SettingsPage() {
  const me = useRequireAuth();
  const [section, setSection] = useState("profile");

  if (!me) return null;

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas">
      <nav
        aria-label="Settings sections"
        className={clsx(
          "flex w-full shrink-0 flex-col gap-[2px] overflow-y-auto border-r border-line",
          "bg-surface p-md md:w-[300px]",
        )}
      >
        <Link href="/" className="mb-sm flex items-center gap-sm rounded-md p-[10px_12px]
          text-md font-medium text-ink-muted hover:bg-hover hover:text-ink">
          <Icon name="back" size={18} /> Back to chats
        </Link>
        <p className="px-md pb-sm pt-sm text-xs font-semibold tracking-wide text-ink-faint">SETTINGS</p>
        {SECTIONS.map((entry) => (
          <button
            key={entry.id}
            onClick={() => setSection(entry.id)}
            aria-current={section === entry.id}
            className={clsx(
              "flex items-center gap-[11px] rounded-lg p-[10px_12px] text-left",
              section === entry.id ? "bg-active text-accent" : "hover:bg-hover",
            )}
          >
            <Icon name={entry.icon} size={19} />
            <span className={clsx("flex-1 text-base",
              section === entry.id ? "font-semibold" : "font-medium")}>
              {entry.label}
            </span>
            {entry.placeholder && <Chip>Placeholder</Chip>}
            <Icon name="chevron" size={15} strokeWidth={2} className="text-ink-faint" />
          </button>
        ))}
        <p className="mt-sm flex items-start gap-sm rounded-md bg-hover px-md py-[10px] text-sm text-ink-muted">
          <Icon name="info" size={15} strokeWidth={1.8} className="mt-[1px] shrink-0" />
          Sections marked <strong className="font-semibold">Placeholder</strong> are out of scope for
          this build. They are shown so the navigation is complete.
        </p>
      </nav>

      <main id="main" className="hidden min-w-0 flex-1 flex-col overflow-y-auto md:flex">
        <header className="flex items-center gap-md border-b border-line bg-surface px-2xl py-lg">
          <h1 className="flex-1 text-xl font-semibold">
            {SECTIONS.find((entry) => entry.id === section)?.label}
          </h1>
        </header>

        <div className="max-w-[620px] p-2xl">
          {section === "profile" && <ProfileSection me={me} />}
          {section === "account" && <AccountSection me={me} />}
          {section === "appearance" && <AppearanceSection />}
          {!["profile", "account", "appearance"].includes(section) && (
            <div className="flex flex-col items-start gap-md rounded-lg border border-line bg-surface p-xl">
              <Chip>Placeholder</Chip>
              <h2 className="text-lg font-semibold">
                {SECTIONS.find((entry) => entry.id === section)?.label} isn&apos;t built yet
              </h2>
              <p className="text-base text-ink-muted">
                This section is intentionally out of scope. It appears in the navigation so the
                information architecture is complete and reviewable.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

/** A one-line result under a form, so saving and failing look the same shape. */
function Notice({ tone, children }: { tone: "ok" | "bad"; children: React.ReactNode }) {
  return (
    <p
      role={tone === "bad" ? "alert" : "status"}
      className={clsx(
        "flex items-center gap-sm rounded-md px-md py-[10px] text-md font-medium",
        tone === "ok" ? "bg-accent-subtle text-accent" : "bg-hover text-ink-danger",
      )}
    >
      <Icon name={tone === "ok" ? "check" : "warn"} size={16} strokeWidth={1.9} />
      {children}
    </p>
  );
}

function ProfileSection({ me }: { me: Me }) {
  const { setUser } = useAuth();
  const [displayName, setDisplayName] = useState(me.displayName);
  const [about, setAbout] = useState(me.about ?? "");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  const changed = displayName.trim() !== me.displayName || about.trim() !== (me.about ?? "");

  async function save(event: FormEvent) {
    event.preventDefault();
    setResult(null);
    setSaving(true);
    try {
      setUser(toMe(await api.updateProfile({ display_name: displayName.trim(), about: about.trim() })));
      setResult({ tone: "ok", text: "Profile updated." });
    } catch (problem) {
      setResult({
        tone: "bad",
        text: problem instanceof ApiError ? problem.message : "Could not save your profile.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-xl">
      <div className="flex items-center gap-xl border-b border-line-subtle pb-xl">
        <Avatar name={me.displayName} size={76} accent />
        <div className="flex flex-col gap-[4px]">
          <p className="text-lg font-semibold">{me.displayName}</p>
          <p className="text-md text-ink-muted">@{me.username}</p>
          <p className="text-sm text-ink-faint">Photo uploads are not part of this build.</p>
        </div>
      </div>

      <Field id="display-name" label="Display name"
        helper="Shown to everyone you message."
        value={displayName} maxLength={100}
        onChange={(event) => setDisplayName(event.target.value)} />
      <Field id="about" label="About"
        helper="A short line under your name. Optional."
        value={about} maxLength={200} placeholder="Designer. Tea, not coffee."
        onChange={(event) => setAbout(event.target.value)} />

      <ReadOnlyRow label="Username" sub="Permanent. Others find you with this."
        value={`@${me.username}`} />
      <ReadOnlyRow label="Phone number" sub="Optional, and only used to help friends find you."
        value={me.phoneNumber ?? "Not set"} />

      {result && <Notice tone={result.tone}>{result.text}</Notice>}
      <div>
        <Button type="submit" loading={saving} disabled={!changed}>Save changes</Button>
      </div>
    </form>
  );
}

function AccountSection({ me }: { me: Me }) {
  const router = useRouter();
  const { signOut } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  async function change(event: FormEvent) {
    event.preventDefault();
    setResult(null);
    if (next.length < 8) {
      setResult({ tone: "bad", text: "The new password must be at least 8 characters." });
      return;
    }
    setSaving(true);
    try {
      await api.changePassword({ current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      // Every session was revoked, including this one's refresh token, so the
      // honest next step is to sign in again rather than to keep going until
      // the access token quietly expires.
      setResult({ tone: "ok", text: "Password changed. Signing you out of this device…" });
      setTimeout(() => {
        void signOut().then(() => router.replace("/login"));
      }, 1200);
    } catch (problem) {
      setResult({
        tone: "bad",
        text: problem instanceof ApiError ? problem.message : "Could not change your password.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-2xl">
      <form onSubmit={change} className="flex flex-col gap-lg">
        <div className="flex flex-col gap-xs">
          <h2 className="text-lg font-semibold">Change password</h2>
          <p className="text-base text-ink-muted">
            Changing your password signs you out everywhere, including on this device.
          </p>
        </div>
        <Field id="current-password" label="Current password" type="password"
          autoComplete="current-password" value={current}
          onChange={(event) => setCurrent(event.target.value)} />
        <Field id="new-password" label="New password" type="password"
          autoComplete="new-password" helper="At least 8 characters." value={next}
          onChange={(event) => setNext(event.target.value)} />
        {result && <Notice tone={result.tone}>{result.text}</Notice>}
        <div>
          <Button type="submit" loading={saving} disabled={!current || !next}>
            Change password
          </Button>
        </div>
      </form>

      <div className="flex flex-col gap-lg border-t border-line-subtle pt-xl">
        <div className="flex flex-col gap-xs">
          <h2 className="text-lg font-semibold">Sign out</h2>
          <p className="text-base text-ink-muted">
            Ends this session on this device. Signed in as @{me.username}.
          </p>
        </div>
        <div>
          <Button
            variant="danger"
            onClick={() => void signOut().then(() => router.replace("/login"))}
          >
            Sign out
          </Button>
        </div>
      </div>
    </div>
  );
}

function AppearanceSection() {
  const { theme, toggle } = useTheme();
  return (
    <div className="flex flex-col gap-lg">
      <p className="text-base text-ink-muted">
        Light and dark share the same token names, so switching reskins every screen.
      </p>
      <div className="flex gap-lg">
        {(["light", "dark"] as const).map((option) => (
          <button key={option} onClick={() => toggle(option)}
            aria-pressed={theme === option}
            className={clsx("flex flex-col gap-sm rounded-lg border-2 p-sm text-left",
              theme === option ? "border-accent" : "border-line")}>
            <span className="flex h-[96px] w-[150px] gap-[6px] overflow-hidden rounded-md p-sm"
              style={{ background: option === "dark" ? "#0B0F14" : "#F7F8FA" }}>
              <span className="w-[40px] rounded-sm"
                style={{ background: option === "dark" ? "#141A21" : "#FFFFFF" }} />
              <span className="flex flex-1 flex-col gap-[5px]">
                <span className="h-[9px] rounded-sm"
                  style={{ background: option === "dark" ? "#141A21" : "#FFFFFF" }} />
                <span className="h-[20px] w-[70%] rounded-md"
                  style={{ background: option === "dark" ? "#1F262F" : "#E1E5EB" }} />
                <span className="h-[20px] w-[80%] self-end rounded-md"
                  style={{ background: option === "dark" ? "#1E55C9" : "#2C6BED" }} />
              </span>
            </span>
            <span className="text-md font-medium capitalize">{option}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ReadOnlyRow({ label, sub, value }: { label: string; sub?: string; value: string }) {
  return (
    <div className="flex items-center gap-lg border-b border-line-subtle pb-lg">
      <div className="flex flex-1 flex-col gap-[2px]">
        <span className="text-base font-medium">{label}</span>
        {sub && <span className="text-sm text-ink-muted">{sub}</span>}
      </div>
      <span className="text-base text-ink-muted">{value}</span>
    </div>
  );
}
