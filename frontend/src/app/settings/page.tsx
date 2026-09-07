"use client";
import Link from "next/link";
import { useState } from "react";
import { clsx } from "@/lib/clsx";
import { Icon, type IconName } from "@/components/Icon";
import { Avatar, Button, Chip } from "@/components/Primitives";
import { useTheme } from "@/components/ThemeToggle";

const SECTIONS: Array<{ id: string; label: string; icon: IconName; placeholder?: boolean }> = [
  { id: "profile", label: "Profile", icon: "settings" },
  { id: "privacy", label: "Privacy", icon: "lock", placeholder: true },
  { id: "notifications", label: "Notifications", icon: "bell", placeholder: true },
  { id: "calls", label: "Calls", icon: "phone", placeholder: true },
  { id: "devices", label: "Linked devices", icon: "devices", placeholder: true },
  { id: "appearance", label: "Appearance", icon: "palette" },
];

export default function SettingsPage() {
  const [section, setSection] = useState("profile");
  const { theme, toggle } = useTheme();

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas">
      <nav aria-label="Settings sections"
        className="flex w-full shrink-0 flex-col gap-[2px] border-r border-line bg-surface p-md md:w-[300px]">
        <Link href="/" className="mb-sm flex items-center gap-sm rounded-md p-[10px_12px]
          text-md font-medium text-ink-muted hover:bg-hover hover:text-ink">
          <Icon name="back" size={18} /> Back to chats
        </Link>
        <p className="px-md pb-sm pt-sm text-xs font-semibold tracking-wide text-ink-faint">SETTINGS</p>
        {SECTIONS.map((s) => (
          <button key={s.id} onClick={() => setSection(s.id)} aria-current={section === s.id}
            className={clsx("flex items-center gap-[11px] rounded-lg p-[10px_12px] text-left",
              section === s.id ? "bg-active text-accent" : "hover:bg-hover")}>
            <Icon name={s.icon} size={19} />
            <span className={clsx("flex-1 text-base", section === s.id ? "font-semibold" : "font-medium")}>
              {s.label}
            </span>
            {s.placeholder && <Chip>Placeholder</Chip>}
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
            {SECTIONS.find((s) => s.id === section)?.label}
          </h1>
          {section === "profile" && <Button>Save changes</Button>}
        </header>

        <div className="max-w-[620px] p-2xl">
          {section === "profile" && <ProfileSection />}
          {section === "appearance" && (
            <div className="flex flex-col gap-lg">
              <p className="text-base text-ink-muted">
                Light and dark share the same token names, so switching reskins every screen.
              </p>
              <div className="flex gap-lg">
                {(["light", "dark"] as const).map((t) => (
                  <button key={t} onClick={() => toggle(t)}
                    className={clsx("flex flex-col gap-sm rounded-lg border-2 p-sm text-left",
                      theme === t ? "border-accent" : "border-line")}>
                    <span className="flex h-[96px] w-[150px] gap-[6px] overflow-hidden rounded-md p-sm"
                      style={{ background: t === "dark" ? "#0B0F14" : "#F7F8FA" }}>
                      <span className="w-[40px] rounded-sm"
                        style={{ background: t === "dark" ? "#141A21" : "#FFFFFF" }} />
                      <span className="flex flex-1 flex-col gap-[5px]">
                        <span className="h-[9px] rounded-sm"
                          style={{ background: t === "dark" ? "#141A21" : "#FFFFFF" }} />
                        <span className="h-[20px] w-[70%] rounded-md"
                          style={{ background: t === "dark" ? "#1F262F" : "#E1E5EB" }} />
                        <span className="h-[20px] w-[80%] self-end rounded-md"
                          style={{ background: t === "dark" ? "#1E55C9" : "#2C6BED" }} />
                      </span>
                    </span>
                    <span className="text-md font-medium capitalize">{t}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          {!["profile", "appearance"].includes(section) && (
            <div className="flex flex-col items-start gap-md rounded-lg border border-line bg-surface p-xl">
              <Chip>Placeholder</Chip>
              <h2 className="text-lg font-semibold">
                {SECTIONS.find((s) => s.id === section)?.label} isn&apos;t built yet
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

function Row({ label, sub, value }: { label: string; sub?: string; value: string }) {
  return (
    <div className="flex items-center gap-lg border-b border-line-subtle py-lg">
      <div className="flex flex-1 flex-col gap-[2px]">
        <span className="text-base font-medium">{label}</span>
        {sub && <span className="text-sm text-ink-muted">{sub}</span>}
      </div>
      <span className="text-base text-ink-muted">{value}</span>
    </div>
  );
}

function ProfileSection() {
  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-xl border-b border-line-subtle pb-xl">
        <span className="relative">
          <Avatar name="Ayush Swamy" size={76} accent />
          <span className="absolute -bottom-[2px] -right-[2px] flex h-7 w-7 items-center
            justify-center rounded-full border border-line bg-surface text-ink-muted">
            <Icon name="camera" size={15} strokeWidth={1.7} />
          </span>
        </span>
        <div className="flex flex-col gap-[4px]">
          <p className="text-lg font-semibold">Ayush Swamy</p>
          <p className="text-md text-ink-muted">@ayush</p>
          <p className="text-sm text-ink-faint">Your photo is visible to people you chat with.</p>
        </div>
      </div>
      <Row label="Display name" sub="Shown to everyone you message." value="Ayush Swamy" />
      <Row label="Username" sub="Permanent. Others find you with this." value="@ayush" />
      <Row label="Phone number" sub="Hidden except from your contacts." value="+91 98••• ••210" />
    </div>
  );
}
