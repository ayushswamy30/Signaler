"use client";
import { useMemo, useState } from "react";
import { clsx } from "@/lib/clsx";
import { Icon } from "./Icon";
import { Avatar, EmptyState, Skeleton } from "./Primitives";
import { ConversationItem } from "./Chat";
import { preview, title } from "@/lib/format";
import type { Conversation, Me } from "@/lib/types";

export function Sidebar({ me, conversations, activeId, onSelect, onNewMessage, onNewGroup, onSettings,
  loading = false, className }: {
  me: Me; conversations: Conversation[]; activeId: number | null;
  onSelect: (id: number) => void; onNewMessage: () => void; onNewGroup: () => void; onSettings: () => void;
  loading?: boolean; className?: string;
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) =>
      title(c, me.id).toLowerCase().includes(q) ||
      preview(c, me.id).toLowerCase().includes(q));
  }, [conversations, query, me.id]);

  return (
    <aside className={clsx("flex h-full w-full flex-col border-r border-line bg-sidebar md:w-[340px] md:shrink-0",
      className)}>
      <div className="flex items-center gap-md border-b border-line-subtle p-lg">
        <Avatar name={me.displayName} size={36} online accent />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-base font-semibold">{me.displayName}</span>
          <span className="text-xs text-ink-faint">@{me.username}</span>
        </div>
        <button onClick={onNewMessage} aria-label="New message"
          className="inline-flex h-11 w-11 items-center justify-center rounded-md text-ink-muted
            hover:bg-hover hover:text-ink md:h-8 md:w-8"><Icon name="edit" size={20} /></button>
        <button onClick={onNewGroup} aria-label="New group"
          className="inline-flex h-11 w-11 items-center justify-center rounded-md text-ink-muted
            hover:bg-hover hover:text-ink md:h-8 md:w-8"><Icon name="users" size={20} /></button>
        <button onClick={onSettings} aria-label="Settings"
          className="inline-flex h-11 w-11 items-center justify-center rounded-md text-ink-muted
            hover:bg-hover hover:text-ink md:h-8 md:w-8"><Icon name="settings" size={20} /></button>
      </div>

      <div className="px-lg py-md">
        <label htmlFor="conv-search" className="sr-only">Search conversations</label>
        <div className="flex h-11 items-center gap-sm rounded-md bg-hover px-md
          focus-within:ring-2 focus-within:ring-line-focus md:h-9">
          <Icon name="search" size={18} className="text-ink-faint" />
          <input id="conv-search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search" className="flex-1 bg-transparent text-base outline-none
              placeholder:text-ink-faint" />
          {query && (
            <button onClick={() => setQuery("")} aria-label="Clear search"
              className="text-ink-faint hover:text-ink"><Icon name="close" size={16} /></button>
          )}
        </div>
      </div>

      <nav aria-label="Conversations" className="flex flex-1 flex-col gap-[2px] overflow-y-auto px-sm pb-sm">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-md p-[10px_12px]">
              <Skeleton className="h-11 w-11 rounded-full" />
              <div className="flex flex-1 flex-col gap-[7px]">
                <Skeleton className="h-[11px] w-[45%]" /><Skeleton className="h-[10px] w-[70%]" />
              </div>
            </div>
          ))
        ) : filtered.length === 0 ? (
          <EmptyState icon={<Icon name="search" size={30} strokeWidth={1.4} />}
            title={query ? "No matches" : "No conversations"}
            body={query ? `Nothing matches “${query}”. Try a different name.`
              : "Start a conversation and it will show up here."} />
        ) : (
          filtered.map((c) => (
            <ConversationItem key={c.id} conversation={c} meId={me.id} active={c.id === activeId}
              onSelect={() => onSelect(c.id)} />
          ))
        )}
      </nav>
    </aside>
  );
}
