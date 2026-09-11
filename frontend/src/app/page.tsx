"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { clsx } from "@/lib/clsx";
import { useAuth, useRequireAuth } from "@/lib/auth";
import { useCall, type CallKind } from "@/lib/call";
import { useMessenger } from "@/lib/useMessenger";
import { counterpart, crossesDay, formatDateSeparator, subtitle, title } from "@/lib/format";
import type { Message } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Avatar, Button, EmptyState, Skeleton } from "@/components/Primitives";
import { Sidebar } from "@/components/Sidebar";
import { Composer } from "@/components/Composer";
import { NewMessageModal } from "@/components/NewMessageModal";
import { NewGroupModal } from "@/components/NewGroupModal";
import { ConversationInfo } from "@/components/ConversationInfo";
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

function BootScreen() {
  const contentRef = useRef<HTMLDivElement>(null);
  return (
    <div className="flex h-dvh items-center justify-center bg-canvas">
      <CursorWave avoidRef={contentRef} />
      <div ref={contentRef} className="flex flex-col items-center gap-md" role="status"
        aria-label="Loading Signaler">
        <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-accent text-white">
          <Icon name="send" size={22} strokeWidth={1.9} />
        </span>
        <Skeleton className="h-[10px] w-[120px]" />
      </div>
    </div>
  );
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
              {active.type === "direct" && (
                <div className="flex items-center pr-xs">
                  <IconButton label="Start voice call" icon="phone"
                    onClick={() => startCall("audio")} />
                  <IconButton label="Start video call" icon="video"
                    onClick={() => startCall("video")} />
                </div>
              )}
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

/** One message, plus the actions that hover over it.
 *
 *  The buttons are positioned outside the bubble and revealed on hover, but
 *  they stay in the tab order and appear on focus — hiding with `opacity`
 *  rather than `display` is what keeps them reachable from the keyboard. */
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

  return (
    <div className="group relative">
      <MessageBubble
        message={message}
        mine={mine}
        first={first}
        last={last}
        showSender={showSender}
      />

      {failed ? (
        <p className={clsx("mt-[2px] flex gap-sm text-sm text-ink-danger",
          mine ? "justify-end" : "justify-start")}>
          Not delivered.
          <button onClick={onDiscard} className="font-semibold underline">Discard</button>
        </p>
      ) : (
        <div
          className={clsx(
            "absolute top-1 flex gap-[2px] opacity-0 transition-opacity",
            "group-hover:opacity-100 focus-within:opacity-100",
            mine ? "left-[-64px]" : "right-[-64px]",
          )}
        >
          <ActionButton label={`Reply to ${message.sender.displayName}`} icon="reply" onClick={onReply} />
          {mine && !message.pending && (
            <>
              <ActionButton label="Edit message" icon="edit" onClick={onEdit} />
              <ActionButton label="Delete message" icon="close" onClick={onDelete} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ActionButton({
  label,
  icon,
  onClick,
}: {
  label: string;
  icon: "reply" | "edit" | "close";
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="rounded-md p-1 text-ink-faint hover:bg-hover hover:text-ink"
    >
      <Icon name={icon} size={15} />
    </button>
  );
}
