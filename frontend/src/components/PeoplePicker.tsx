"use client";

/** Find people: contacts by default, the directory once you type.
 *
 *  Shared by "new message", "new group" and "add members", which differ only in
 *  whether one person or several can be chosen. */

import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { toContact, toUser } from "@/lib/adapt";
import { clsx } from "@/lib/clsx";
import type { User } from "@/lib/types";
import { Icon } from "./Icon";
import { Avatar, Chip, EmptyState, Spinner } from "./Primitives";

/** Wait this long after the last keystroke before searching. Long enough that
 *  typing a name is one request rather than eight, short enough to feel live. */
const DEBOUNCE_MS = 250;

export function usePeopleSearch(excludeIds: number[] = []) {
  const [query, setQuery] = useState("");
  const [contacts, setContacts] = useState<User[]>([]);
  const [results, setResults] = useState<User[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    api
      .listContacts()
      .then((rows) => setContacts(rows.map(toContact).map((c) => c.user)))
      .catch(() => setContacts([]));
  }, []);

  // Tracks the newest request so a slow earlier one cannot overwrite the
  // results of a later, more specific query.
  const latest = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults(null);
      setSearching(false);
      return;
    }

    setSearching(true);
    const ticket = ++latest.current;
    const timer = setTimeout(async () => {
      try {
        const found = await api.searchUsers(trimmed);
        if (ticket === latest.current) setResults(found.map(toUser));
      } catch {
        if (ticket === latest.current) setResults([]);
      } finally {
        if (ticket === latest.current) setSearching(false);
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [query]);

  const excluded = useMemo(() => new Set(excludeIds), [excludeIds]);
  const people = useMemo(
    () => (results ?? contacts).filter((user) => !excluded.has(user.id)),
    [results, contacts, excluded],
  );

  return { query, setQuery, people, searching, searchingDirectory: results !== null };
}

export function PeopleSearchField({
  value,
  onChange,
  placeholder = "Search by name or username",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="flex h-11 items-center gap-sm rounded-md border border-line bg-hover px-md
      focus-within:border-line-focus md:h-10">
      <Icon name="search" size={18} className="text-ink-faint" />
      <label htmlFor="people-search" className="sr-only">Search people</label>
      <input
        id="people-search"
        autoFocus
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="flex-1 bg-transparent text-base outline-none placeholder:text-ink-faint
          focus-visible:!outline-none"
      />
      {value && (
        <button type="button" onClick={() => onChange("")} aria-label="Clear search"
          className="text-ink-faint hover:text-ink"><Icon name="close" size={16} /></button>
      )}
    </div>
  );
}

export function PeopleList({
  people,
  selectedIds,
  onToggle,
  multiple = false,
  searching,
  query,
  emptyBody,
}: {
  people: User[];
  selectedIds: number[];
  onToggle: (user: User) => void;
  multiple?: boolean;
  searching: boolean;
  query: string;
  emptyBody?: string;
}) {
  if (searching && people.length === 0) {
    return (
      <p className="flex items-center gap-sm rounded-md bg-hover px-md py-[10px] text-sm text-ink-muted">
        <Spinner size={13} /> Searching…
      </p>
    );
  }

  if (people.length === 0) {
    return (
      <EmptyState
        icon={<Icon name="search" size={24} strokeWidth={1.5} />}
        title={query ? `No one found for “${query}”` : "No contacts yet"}
        body={
          emptyBody ??
          (query
            ? "Search matches usernames, display names and phone numbers."
            : "Search for someone by username to start your first conversation.")
        }
      />
    );
  }

  return (
    <ul className="flex max-h-[320px] flex-col gap-[2px] overflow-y-auto">
      <li className="px-md pb-xs text-xs font-semibold tracking-wide text-ink-faint">
        {query ? "RESULTS" : "CONTACTS"}
      </li>
      {people.map((user) => {
        const selected = selectedIds.includes(user.id);
        return (
          <li key={user.id}>
            <button
              type="button"
              onClick={() => onToggle(user)}
              aria-pressed={selected}
              className={clsx(
                "flex w-full items-center gap-md rounded-lg p-[9px_12px] text-left",
                selected ? "bg-active" : "hover:bg-hover",
              )}
            >
              <Avatar name={user.displayName} size={38} online={user.isOnline} />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-base font-medium">{user.displayName}</span>
                <span className="truncate text-sm text-ink-faint">@{user.username}</span>
              </span>
              {multiple ? (
                <span
                  aria-hidden
                  className={clsx(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-[6px] border",
                    selected ? "border-accent bg-accent text-white" : "border-line-strong",
                  )}
                >
                  {selected && <Icon name="check" size={13} strokeWidth={3} />}
                </span>
              ) : (
                selected && <Chip tone="accent">Selected</Chip>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
