"use client";
import { useMemo, useState } from "react";
import { clsx } from "@/lib/clsx";
import { Icon } from "@/components/Icon";
import { Avatar, Button, Chip, EmptyState } from "@/components/Primitives";
import { Sidebar } from "@/components/Sidebar";
import { Composer } from "@/components/Composer";
import { NewMessageModal } from "@/components/NewMessageModal";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  ChatHeader, DateSeparator, IconButton, MessageBubble, TypingIndicator, UnreadDivider,
} from "@/components/Chat";
import { conversations as seedConversations, counterpart, me, messages as seedMessages, title }
  from "@/lib/mock";
import type { Conversation, Message, User } from "@/lib/types";

export default function AppPage() {
  const [conversations, setConversations] = useState<Conversation[]>(seedConversations);
  const [threads, setThreads] = useState<Record<number, Message[]>>(seedMessages);
  const [activeId, setActiveId] = useState<number | null>(1);
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [mobilePane, setMobilePane] = useState<"list" | "chat">("list");

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? null, [conversations, activeId]);
  const thread = activeId ? threads[activeId] ?? [] : [];
  const unread = active?.unreadCount ?? 0;

  function openConversation(id: number) {
    setActiveId(id);
    setReplyTo(null);
    setMobilePane("chat");
    setConversations((cs) => cs.map((c) => (c.id === id ? { ...c, unreadCount: 0 } : c)));
  }

  function send(text: string) {
    if (!activeId) return;
    const message: Message = {
      id: Date.now(), conversationId: activeId, sender: me, content: text,
      createdAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      editedAt: null, status: "sent",
      replyTo: replyTo ? { sender: replyTo.sender.displayName, content: replyTo.content } : null,
    };
    setThreads((t) => ({ ...t, [activeId]: [...(t[activeId] ?? []), message] }));
    setConversations((cs) => cs.map((c) =>
      c.id === activeId ? { ...c, lastMessage: text, lastActivity: message.createdAt } : c));
    setReplyTo(null);
    // Optimistic progression: sent -> delivered -> read, as a real socket would drive it.
    const advance = (status: Message["status"], delay: number) =>
      setTimeout(() => setThreads((t) => ({
        ...t,
        [activeId]: (t[activeId] ?? []).map((m) => (m.id === message.id ? { ...m, status } : m)),
      })), delay);
    advance("delivered", 700);
    advance("read", 1900);
  }

  function startChatWith(user: User) {
    const existing = conversations.find(
      (c) => c.type === "direct" && c.participants.some((p) => p.user.id === user.id));
    if (existing) { openConversation(existing.id); return; }
    const id = Math.max(0, ...conversations.map((c) => c.id)) + 1;
    const created: Conversation = {
      id, type: "direct", name: null,
      participants: [{ user: me, role: "member" }, { user, role: "member" }],
      lastMessage: "No messages yet", lastActivity: "now", unreadCount: 0, muted: false,
    };
    setConversations((cs) => [created, ...cs]);
    setThreads((t) => ({ ...t, [id]: [] }));
    openConversation(id);
  }

  const existingIds = conversations.flatMap((c) => c.participants.map((p) => p.user.id));

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas">
      <Sidebar conversations={conversations} activeId={activeId}
        onSelect={openConversation} onNewMessage={() => setShowNew(true)}
        onSettings={() => { window.location.href = "/settings"; }}
        className={clsx(mobilePane === "chat" && "hidden md:flex")} />

      <main id="main" className={clsx("flex min-w-0 flex-1 flex-col",
        mobilePane === "list" && "hidden md:flex")}>
        {!active ? (
          <div className="flex flex-1 items-center justify-center">
            <EmptyState icon={<Icon name="edit" size={38} strokeWidth={1.4} />}
              title="No conversation selected"
              body="Pick a conversation from the list, or start a new one."
              action={<Button icon={<Icon name="plus" size={18} strokeWidth={2} />}
                onClick={() => setShowNew(true)}>New message</Button>} />
          </div>
        ) : (
          <>
            <div className="flex items-center gap-sm border-b border-line bg-surface pl-sm md:hidden">
              <IconButton label="Back to conversations" icon="back" size={22}
                onClick={() => setMobilePane("list")} />
              <div className="flex-1"><ChatHeaderCompact conversation={active} /></div>
            </div>
            <div className="hidden md:block">
              <div className="relative">
                <ChatHeader conversation={active} onOpenInfo={() => setShowInfo((v) => !v)} />
                <div className="absolute right-[132px] top-1/2 -translate-y-1/2"><ThemeToggle /></div>
              </div>
            </div>

            <div className="flex flex-1 flex-col justify-end gap-[6px] overflow-y-auto px-lg py-lg md:px-xl"
              role="log" aria-label="Message history">
              <DateSeparator label="Today" />
              {thread.map((m, i) => {
                const mine = m.sender.id === me.id;
                const prev = thread[i - 1], next = thread[i + 1];
                const first = !prev || prev.sender.id !== m.sender.id;
                const last = !next || next.sender.id !== m.sender.id;
                return (
                  <div key={m.id} className="group relative">
                    {unread > 0 && i === thread.length - unread && <UnreadDivider count={unread} />}
                    <MessageBubble message={m} mine={mine} first={first} last={last}
                      showSender={active.type === "group" && first} />
                    <button onClick={() => setReplyTo(m)} aria-label={`Reply to ${m.sender.displayName}`}
                      className={clsx("absolute top-1 hidden rounded-md p-1 text-ink-faint",
                        "hover:bg-hover hover:text-ink group-hover:block",
                        mine ? "left-[-30px]" : "right-[-30px]")}>
                      <Icon name="reply" size={15} />
                    </button>
                  </div>
                );
              })}
              {active.id === 1 && <TypingIndicator name={counterpart(active).displayName} />}
            </div>

            <Composer onSend={send}
              replyTo={replyTo ? { sender: replyTo.sender.displayName, content: replyTo.content } : null}
              onCancelReply={() => setReplyTo(null)} />
          </>
        )}
      </main>

      {showInfo && active && (
        <InfoPanel conversation={active} onClose={() => setShowInfo(false)} />
      )}

      <NewMessageModal open={showNew} onClose={() => setShowNew(false)}
        onStart={startChatWith} existingIds={existingIds} />
    </div>
  );
}

function ChatHeaderCompact({ conversation }: { conversation: Conversation }) {
  const other = counterpart(conversation);
  const sub = conversation.type === "group"
    ? `${conversation.participants.length} members`
    : other.isOnline ? "Online" : `Last seen ${other.lastSeen ?? "recently"}`;
  return (
    <div className="flex items-center gap-md py-[10px]">
      <Avatar name={title(conversation)} size={38} />
      <div className="flex min-w-0 flex-col">
        <span className="truncate text-lg font-semibold">{title(conversation)}</span>
        <span className="text-sm text-ink-muted">{sub}</span>
      </div>
    </div>
  );
}

function InfoPanel({ conversation, onClose }: { conversation: Conversation; onClose: () => void }) {
  const isGroup = conversation.type === "group";
  const iAmAdmin = conversation.participants.find((p) => p.user.id === me.id)?.role === "admin";
  return (
    <aside aria-label={isGroup ? "Group info" : "Contact info"}
      className="hidden w-[360px] shrink-0 flex-col overflow-y-auto border-l border-line bg-surface lg:flex">
      <div className="flex items-center gap-md border-b border-line-subtle px-lg py-md">
        <h2 className="flex-1 text-lg font-semibold">{isGroup ? "Group info" : "Contact info"}</h2>
        <button onClick={onClose} aria-label="Close panel" className="text-ink-faint hover:text-ink">
          <Icon name="close" size={18} />
        </button>
      </div>
      <div className="flex flex-col items-center gap-[10px] border-b border-line-subtle px-lg py-xl">
        <Avatar name={title(conversation)} size={84} />
        <div className="flex flex-col items-center gap-[3px]">
          <p className="text-xl font-semibold">{title(conversation)}</p>
          <p className="text-md text-ink-muted">
            {isGroup ? `${conversation.participants.length} members`
              : `@${counterpart(conversation).username}`}
          </p>
        </div>
        {isGroup && iAmAdmin && (
          <div className="flex gap-sm">
            <Button variant="secondary">Edit</Button>
            <Button variant="secondary">Add member</Button>
          </div>
        )}
      </div>
      {isGroup && (
        <div className="flex flex-col gap-[2px] p-sm">
          <p className="px-md pb-sm pt-md text-xs font-semibold tracking-wide text-ink-faint">
            MEMBERS · {conversation.participants.length}
          </p>
          {conversation.participants.map((p) => (
            <div key={p.user.id} className="flex items-center gap-md rounded-lg p-[9px_12px]">
              <Avatar name={p.user.displayName} size={38} />
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-base font-medium">{p.user.displayName}</span>
                <span className="text-sm text-ink-faint">@{p.user.username}</span>
              </div>
              {p.role === "admin" && <Chip tone="accent">Admin</Chip>}
            </div>
          ))}
        </div>
      )}
      <div className="mt-auto border-t border-line-subtle p-sm">
        <button className="flex w-full items-center gap-md rounded-lg p-[11px_12px] text-ink-danger
          hover:bg-hover">
          <Icon name="close" size={18} />
          <span className="text-base font-medium">{isGroup ? "Leave group" : "Block contact"}</span>
        </button>
      </div>
    </aside>
  );
}
