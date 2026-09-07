"use client";
import { useMemo, useState } from "react";
import { Modal } from "./Modal";
import { Icon } from "./Icon";
import { Avatar, Button, Chip, EmptyState, Spinner } from "./Primitives";
import { directory } from "@/lib/mock";
import type { User } from "@/lib/types";

export function NewMessageModal({ open, onClose, onStart, existingIds }: {
  open: boolean; onClose: () => void; onStart: (user: User) => void; existingIds: number[];
}) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<User | null>(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return directory;
    return directory.filter((u) =>
      u.displayName.toLowerCase().includes(q) || u.username.toLowerCase().includes(q));
  }, [query]);

  return (
    <Modal open={open} onClose={onClose} title="New message"
      subtitle="Find someone by name or username, then start a conversation."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={!selected} onClick={() => { if (selected) { onStart(selected); onClose(); } }}>
            Start chat
          </Button>
        </>
      }>
      <div className="flex flex-col gap-lg">
        <div className="flex h-10 items-center gap-sm rounded-md border border-line-focus bg-hover px-md">
          <Icon name="search" size={18} className="text-ink-faint" />
          <label htmlFor="people-search" className="sr-only">Search people</label>
          <input id="people-search" autoFocus value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or username"
            className="flex-1 bg-transparent text-base outline-none placeholder:text-ink-faint" />
        </div>

        {results.length === 0 ? (
          <EmptyState icon={<Icon name="search" size={24} strokeWidth={1.5} />}
            title={`No one found for “${query}”`}
            body="Usernames are exact. Check the spelling, or invite them to Signaler."
            action={<Button variant="secondary">Invite by link</Button>} />
        ) : (
          <ul className="flex flex-col gap-[2px]">
            <li className="px-md pb-xs text-xs font-semibold tracking-wide text-ink-faint">RESULTS</li>
            {results.map((u) => {
              const known = existingIds.includes(u.id);
              const active = selected?.id === u.id;
              return (
                <li key={u.id}>
                  <button onClick={() => setSelected(u)} aria-pressed={active}
                    className={`flex w-full items-center gap-md rounded-lg p-[9px_12px] text-left
                      ${active ? "bg-active" : "hover:bg-hover"}`}>
                    <Avatar name={u.displayName} size={38} />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-base font-medium">{u.displayName}</span>
                      <span className="text-sm text-ink-faint">@{u.username}</span>
                    </span>
                    {known ? <Chip>Already a contact</Chip> : <Chip tone="accent">Add</Chip>}
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <p className="flex items-center gap-sm rounded-md bg-hover px-md py-[10px] text-sm text-ink-muted">
          <Spinner size={13} /> Searching the directory…
        </p>
      </div>
    </Modal>
  );
}
