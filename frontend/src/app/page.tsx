"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { clsx } from "@/lib/clsx";
import { useAuth, useRequireAuth } from "@/lib/auth";
import { useCall, type CallKind } from "@/lib/call";
import { useMessenger } from "@/lib/useMessenger";
import { counterpart, crossesDay, formatDateSeparator, subtitle, title } from "@/lib/format";
import { parseSticker } from "@/lib/emoji";
import type { Message } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Avatar, Button, EmptyState } from "@/components/Primitives";
import { Sidebar } from "@/components/Sidebar";
import { Composer } from "@/components/Composer";
import { NewMessageModal } from "@/components/NewMessageModal";
import { NewGroupModal } from "@/components/NewGroupModal";
import { ConversationInfo } from "@/components/ConversationInfo";
import { BootScreen } from "@/components/BootScreen";
import { CallOverlay } from "@/components/CallOverlay";
import { ThemeToggle } from "@/components/ThemeToggle";
import { CursorWave } from "@/components/CursorWave";
import {
  ChatHeader,
  DateSeparator,
  IconButton,
  MessageBubble,
  TypingIndicator,
  UnreadDivider,
} from "@/components/Chat";

export default function AppPage() {
  const me = useRequireAuth();
  // A loading shell rather than null: the sign-in redirect is a frame or two
  // away, and an empty document in between reads as a broken page.
  if (!me) return <BootScreen />;
  return <Messenger />;
}

function Messenger() {
  const router = useRouter();
  const { user } = useAuth();
  const me = user!;
  const app = useMessenger(me);
  const calls = useCall(me.id);

  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [showNewGroup, setShowNewGroup] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [mobilePane, setMobilePane] = useState<"list" | "chat">("list");
  const [editing, setEditing] = useState<Message | null>(null);

  const { active, thread } = app;
  const bottom = useRef<HTMLDivElement>(null);

  // Follow the conversation as it grows. Keyed on the last message rather than
  // the array so an unrelated status change does not yank the view down.
  const lastId = thread[thread.length - 1]?.id;
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [lastId, active?.id]);

  function open(id: number) {
    app.openConversation(id);
    setReplyTo(null);
    setEditing(null);
    setMobilePane("chat");
  }

  function send(text: string) {
    if (!active) return;
    if (editing) {
      void app.editMessage(editing.id, text);
      setEditing(null);
      return;
    }
    void app.sendMessage(active.id, text, replyTo?.id ?? null);
    setReplyTo(null);
  }

  const unread = active?.unreadCount ?? 0;

  /** Start a call in the open conversation. */
  function startCall(kind: CallKind) {
    if (!active) return;
    // A group has no single counterpart: the invite rings everyone in it, and
    // whoever answers joins the same call.
    void calls.start(active, counterpart(active, me.id) ?? null, kind);
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas">
      <Sidebar
        me={me}
        conversations={app.conversations}
        activeId={app.activeId}
        loading={app.loading}
        onSelect={open}
        onNewMessage={() => setShowNew(true)}
        onNewGroup={() => setShowNewGroup(true)}
        onSettings={() => router.push("/settings")}
        className={clsx(mobilePane === "chat" && "hidden md:flex")}
      />

      <main
        id="main"
        className={clsx("flex min-w-0 flex-1 flex-col", mobilePane === "list" && "hidden md:flex")}
      >
        {app.connection !== "open" && !app.loading && (
          <p
            role="status"
            className="flex items-center justify-center gap-sm bg-accent-subtle px-lg py-[6px]
              text-sm font-medium text-accent"
          >
            <Icon name="wifi" size={14} />
            {app.connection === "connecting"
              ? "Reconnecting…"
              : "Offline — messages will not arrive live."}
          </p>
        )}

        {app.error && (
          <p
            role="alert"
            className="flex items-center gap-sm bg-status-danger px-lg py-sm text-sm
              font-medium text-white"
          >
            <Icon name="warn" size={15} />
            <span className="flex-1">{app.error}</span>
            <button onClick={app.clearError} aria-label="Dismiss error">
              <Icon name="close" size={15} />
            </button>
          </p>
        )}

        {!active ? (
          <div className="flex flex-1 items-center justify-center">
            <EmptyState
              icon={<Icon name="edit" size={38} strokeWidth={1.4} />}
              title={app.conversations.length ? "No conversation selected" : "No conversations yet"}
              body={
                app.conversations.length
                  ? "Pick a conversation from the list, or start a new one."
                  : "Start a conversation with a contact, or create a group."
              }
              action={
                <div className="flex gap-sm">
                  <Button icon={<Icon name="plus" size={18} strokeWidth={2} />}
                    onClick={() => setShowNew(true)}>New message</Button>
                  <Button variant="secondary" icon={<Icon name="users" size={18} />}
                    onClick={() => setShowNewGroup(true)}>New group</Button>
                </div>
              }
            />
          </div>
        ) : (
          <>
            <div className="flex items-center gap-sm border-b border-line bg-surface pl-sm md:hidden">
              <IconButton label="Back to conversations" icon="back" size={22}
                onClick={() => setMobilePane("list")} />
              <button onClick={() => setShowInfo(true)}
                className="flex flex-1 items-center gap-md py-[10px] text-left">
                <Avatar name={title(active, me.id)} size={38} />
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-lg font-semibold">{title(active, me.id)}</span>
                  <span className="truncate text-sm text-ink-muted">{subtitle(active, me.id)}</span>
                </span>
              </button>
              <div className="flex items-center pr-xs">
                <IconButton label={active.type === "group" ? "Start group voice call" : "Start voice call"}
                  icon="phone" onClick={() => startCall("audio")} />
                <IconButton label={active.type === "group" ? "Start group video call" : "Start video call"}
                  icon="video" onClick={() => startCall("video")} />
                <IconButton label={active.type === "group" ? "Group info" : "Contact info"}
                  icon="info" onClick={() => setShowInfo(true)} />
                <ThemeToggle />
              </div>
            </div>

            <div className="hidden md:block">
              <div className="relative">
                <ChatHeader conversation={active} meId={me.id}
                  onOpenInfo={() => setShowInfo((value) => !value)}
                  onCall={startCall} />
                <div className="absolute right-[132px] top-1/2 -translate-y-1/2"><ThemeToggle /></div>
              </div>
            </div>

            <div
              className="flex flex-1 flex-col gap-[6px] overflow-y-auto px-lg py-lg md:px-xl"
              role="log"
              aria-label="Message history"
            >
              {app.hasOlder && (
                <div className="flex justify-center pb-sm">
                  <Button variant="secondary" onClick={() => void app.loadOlder(active.id)}>
                    Load earlier messages
                  </Button>
                </div>
              )}

              {thread.length === 0 ? (
                <div className="flex flex-1 items-center justify-center">
                  <EmptyState
                    icon={<Icon name="send" size={34} strokeWidth={1.4} />}
                    title="No messages yet"
                    body={`Say hello to ${title(active, me.id)}.`}
                  />
                </div>
              ) : (
                thread.map((message, index) => {
                  const previous = thread[index - 1];
                  const next = thread[index + 1];
                  const mine = message.sender.id === me.id;
                  const first = !previous || previous.sender.id !== message.sender.id;
                  const last = !next || next.sender.id !== message.sender.id;
                  return (
                    <div key={message.id}>
                      {crossesDay(previous, message) && (
                        <DateSeparator label={formatDateSeparator(message.createdAt)} />
                      )}
                      {unread > 0 && index === thread.length - unread && (
                        <UnreadDivider count={unread} />
                      )}
                      <MessageRow
                        message={message}
                        mine={mine}
                        first={first}
                        last={last}
                        showSender={active.type === "group" && first}
                        onReply={() => { setEditing(null); setReplyTo(message); }}
                        onEdit={() => { setReplyTo(null); setEditing(message); }}
                        onDelete={() => void app.deleteMessage(message.id)}
                        onDiscard={() => app.discardFailed(active.id, message.id)}
                      />
                    </div>
                  );
                })
              )}

              {app.typing.length > 0 && (
                <TypingIndicator
                  name={
                    app.typing.length === 1
                      ? app.typing[0].name
                      : `${app.typing.length} people`
                  }
                />
              )}
              <div ref={bottom} />
            </div>

            <Composer
              key={editing?.id ?? "new"}
              initialValue={editing?.content ?? ""}
              onSend={send}
              onTyping={(isTyping) => app.notifyTyping(active.id, isTyping)}
              replyTo={
                editing
                  ? { sender: "Editing your message", content: editing.content }
                  : replyTo
                    ? { sender: replyTo.sender.displayName, content: replyTo.content }
                    : null
              }
              onCancelReply={() => { setReplyTo(null); setEditing(null); }}
            />
          </>
        )}
      </main>

      {showInfo && active && (
        <div
          className={clsx(
            "fixed inset-0 z-40 bg-canvas lg:static lg:z-auto lg:flex",
            "lg:w-[360px] lg:shrink-0",
          )}
        >
          <ConversationInfo
            conversation={active}
            me={me}
            onClose={() => setShowInfo(false)}
            onRename={(name) => void app.renameGroup(active.id, name)}
            onAddMembers={(ids) => app.addMembers(active.id, ids)}
            onRemoveMember={(id) => void app.removeMember(active.id, id)}
            onSetRole={(id, role) => void app.setRole(active.id, id, role)}
            onLeave={() => { setShowInfo(false); void app.leaveGroup(active.id); }}
            onToggleMute={() => void app.setMuted(active.id, !active.muted)}
          />
        </div>
      )}

      <NewMessageModal
        open={showNew}
        onClose={() => setShowNew(false)}
        onStart={(user) => {
          void app.startDirect(user.id).then(() => setMobilePane("chat"));
        }}
      />

      <CallOverlay controller={calls} />

      <NewGroupModal
        open={showNewGroup}
        onClose={() => setShowNewGroup(false)}
        onSubmit={({ name, memberIds }) =>
          app.createGroup(name, memberIds).then(() => setMobilePane("chat"))
        }
      />
    </div>
  );
}

/** One message, plus a WhatsApp-style options menu on it.
 *
 *  A small chevron sits inside the bubble's own top corner (revealed on
 *  hover, kept visible on focus or while its menu is open) and opens a menu
 *  with Reply/Edit/Delete. It is positioned relative to the bubble itself
 *  rather than the full-width row, so it always lands on the bubble no
 *  matter how wide the chat pane is. */
function MessageRow({
  message,
  mine,
  first,
  last,
  showSender,
  onReply,
  onEdit,
  onDelete,
  onDiscard,
}: {
  message: Message;
  mine: boolean;
  first: boolean;
  last: boolean;
  showSender: boolean;
  onReply: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onDiscard: () => void;
}) {
  const failed = message.status === "failed";
  const sticker = !message.replyTo && parseSticker(message.content);
  const accent = mine && !sticker;
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <>
      <MessageBubble
        message={message}
        mine={mine}
        first={first}
        last={last}
        showSender={showSender}
        actions={failed ? undefined : (
          <div ref={box}
            className={clsx("absolute right-1 top-1 opacity-0 transition-opacity",
              "group-hover:opacity-100 focus-within:opacity-100", open && "opacity-100")}>
            <button onClick={() => setOpen((v) => !v)} aria-label="Message options"
              aria-haspopup="menu" aria-expanded={open}
              className={clsx("flex h-6 w-6 items-center justify-center rounded-full transition-colors",
                accent ? "text-white/80 hover:bg-white/20 hover:text-white"
                  : "text-ink-faint hover:bg-hover hover:text-ink")}>
              <Icon name="chevronDown" size={14} />
            </button>
            {open && (
              <div role="menu"
                className={clsx("absolute top-full z-10 mt-1 w-[160px] overflow-hidden rounded-lg",
                  "border border-line bg-raised py-xs shadow-lg",
                  mine ? "right-0" : "left-0")}>
                <MenuItem label="Reply" icon="reply" onClick={() => { setOpen(false); onReply(); }} />
                {mine && !message.pending && (
                  <>
                    <MenuItem label="Edit" icon="edit" onClick={() => { setOpen(false); onEdit(); }} />
                    <MenuItem label="Delete" icon="trash" onClick={() => { setOpen(false); onDelete(); }} />
                  </>
                )}
              </div>
            )}
          </div>
        )}
      />
      {failed && (
        <p className={clsx("mt-[2px] flex gap-sm text-sm text-ink-danger",
          mine ? "justify-end" : "justify-start")}>
          Not delivered.
          <button onClick={onDiscard} className="font-semibold underline">Discard</button>
        </p>
      )}
    </>
  );
}

function MenuItem({ label, icon, onClick }: {
  label: string; icon: "reply" | "edit" | "trash"; onClick: () => void;
}) {
  return (
    <button role="menuitem" onClick={onClick}
      className="flex w-full items-center gap-sm px-md py-[7px] text-left text-sm text-ink hover:bg-hover">
      <Icon name={icon} size={16} className="text-ink-faint" />
      {label}
    </button>
  );
}
