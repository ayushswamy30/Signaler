"use client";
import { clsx } from "@/lib/clsx";
import { Icon } from "./Icon";
import { Avatar, Badge } from "./Primitives";
import type { Conversation, DeliveryStatus, Message } from "@/lib/types";
import { counterpart, title } from "@/lib/mock";

/** Status uses a distinct glyph per state — never colour alone (brief §6, §19). */
export function MessageStatusIcon({ status, onAccent }: {
  status: DeliveryStatus; onAccent?: boolean;
}) {
  const label = { sent: "Sent", delivered: "Delivered", read: "Read", failed: "Not delivered" }[status];
  const cls = onAccent ? "text-white/75" : "text-ink-faint";
  return (
    <span className={clsx("inline-flex", status === "read" && (onAccent ? "text-white" : "text-accent"),
      status === "failed" && "text-status-danger", status !== "read" && status !== "failed" && cls)}
      title={label} aria-label={label} role="img">
      {status === "sent" && <Icon name="check" size={13} strokeWidth={2} />}
      {status === "delivered" && <Icon name="checks" size={15} strokeWidth={2} />}
      {status === "read" && <Icon name="checks" size={15} strokeWidth={2.6} />}
      {status === "failed" && <Icon name="warn" size={13} strokeWidth={2} />}
    </span>
  );
}

export function ConversationItem({ conversation, active, onSelect }: {
  conversation: Conversation; active: boolean; onSelect: () => void;
}) {
  const name = title(conversation);
  const unread = conversation.unreadCount > 0;
  return (
    <button onClick={onSelect} aria-current={active ? "true" : undefined}
      className={clsx("flex w-full items-center gap-md rounded-lg p-[10px_12px] text-left transition-colors",
        active ? "bg-active" : "hover:bg-hover")}>
      <Avatar name={name} size={44} />
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="flex items-center gap-[6px]">
          <span className={clsx("truncate text-base", unread ? "font-semibold" : "font-medium")}>{name}</span>
          {conversation.muted && <Icon name="mute" size={14} strokeWidth={1.7} className="text-ink-faint" />}
          <span className="flex-1" />
          <span className="shrink-0 text-xs text-ink-faint">{conversation.lastActivity}</span>
        </span>
        <span className="flex items-center gap-sm">
          <span className={clsx("flex-1 truncate text-md",
            unread ? "font-medium text-ink" : "text-ink-muted")}>{conversation.lastMessage}</span>
          <Badge count={conversation.unreadCount} />
        </span>
      </span>
    </button>
  );
}

export function MessageBubble({ message, mine, showSender, first, last }: {
  message: Message; mine: boolean; showSender: boolean; first: boolean; last: boolean;
}) {
  const near = "4px", far = "14px";
  const radius = mine
    ? `${far} ${first ? far : near} ${last ? far : near} ${far}`
    : `${first ? far : near} ${far} ${far} ${last ? far : near}`;
  return (
    <div className={clsx("flex", mine ? "justify-end" : "justify-start")}>
      <div className={clsx("max-w-[min(460px,78%)] px-md py-sm",
          mine ? "bg-bubble-out text-bubble-outText" : "bg-bubble-in text-bubble-inText")}
        style={{ borderRadius: radius }}>
        {showSender && !mine && (
          <p className="mb-[2px] text-sm font-semibold text-accent">{message.sender.displayName}</p>
        )}
        {message.replyTo && (
          <div className={clsx("mb-[6px] rounded-sm border-l-[3px] px-[10px] py-[6px]",
            mine ? "border-white bg-white/15" : "border-bubble-quoteBorder bg-bubble-quote")}>
            <p className={clsx("text-sm font-semibold", mine ? "text-white/95" : "text-accent")}>
              {message.replyTo.sender}</p>
            <p className={clsx("truncate text-sm", mine ? "text-white/80" : "text-ink-muted")}>
              {message.replyTo.content}</p>
          </div>
        )}
        <p className="whitespace-pre-wrap text-base">{message.content}</p>
        <p className={clsx("mt-[2px] flex items-center justify-end gap-[5px] text-xs",
          mine ? "text-white/75" : "text-ink-faint")}>
          {message.editedAt && <span>edited</span>}
          <span>{message.createdAt}</span>
          {mine && message.status && <MessageStatusIcon status={message.status} onAccent />}
        </p>
      </div>
    </div>
  );
}

export function DateSeparator({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-md py-xs" role="separator">
      <span className="h-px flex-1 bg-line-subtle" />
      <span className="text-xs font-medium text-ink-faint">{label}</span>
      <span className="h-px flex-1 bg-line-subtle" />
    </div>
  );
}

export function UnreadDivider({ count }: { count: number }) {
  return (
    <div className="flex items-center gap-md py-xs" role="separator">
      <span className="h-px flex-1 bg-accent/35" />
      <span className="text-xs font-semibold text-accent">{count} unread messages</span>
      <span className="h-px flex-1 bg-accent/35" />
    </div>
  );
}

export function TypingIndicator({ name }: { name: string }) {
  return (
    <div className="flex items-center gap-[10px] pt-[2px]" aria-live="polite">
      <Avatar name={name} size={26} />
      <span className="sr-only">{name} is typing</span>
      <span className="flex items-center gap-[5px] rounded-[14px_14px_14px_4px] bg-bubble-in px-[13px] py-[9px]">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-[6px] w-[6px] animate-bounce rounded-full bg-ink-faint"
            style={{ animationDelay: `${i * 140}ms`, animationDuration: "1s" }} />
        ))}
      </span>
    </div>
  );
}

export function ChatHeader({ conversation, onOpenInfo }: {
  conversation: Conversation; onOpenInfo: () => void;
}) {
  const isGroup = conversation.type === "group";
  const other = counterpart(conversation);
  const online = isGroup ? false : other.isOnline;
  const sub = isGroup
    ? `${conversation.participants.length} members`
    : online ? "Online" : `Last seen ${other.lastSeen ?? "recently"}`;
  return (
    <header className="flex items-center gap-md border-b border-line bg-surface px-xl py-md">
      <Avatar name={title(conversation)} size={38} />
      <div className="flex min-w-0 flex-1 flex-col">
        <h1 className="truncate text-lg font-semibold">{title(conversation)}</h1>
        <p className="flex items-center gap-[6px] text-sm text-ink-muted">
          {online && <span className="h-[7px] w-[7px] shrink-0 rounded-full bg-status-online" />}
          {sub}
        </p>
      </div>
      <div className="flex items-center gap-xs text-ink-muted">
        <IconButton label="Start voice call" icon="phone" />
        <IconButton label="Start video call" icon="video" />
        <IconButton label={isGroup ? "Group info" : "Contact info"} icon="info" onClick={onOpenInfo} />
      </div>
    </header>
  );
}

export function IconButton({ label, icon, onClick, size = 19, className }: {
  label: string; icon: Parameters<typeof Icon>[0]["name"]; onClick?: () => void;
  size?: number; className?: string;
}) {
  return (
    <button onClick={onClick} aria-label={label} title={label}
      className={clsx("inline-flex h-11 w-11 items-center justify-center rounded-md",
        "text-ink-muted transition-colors hover:bg-hover hover:text-ink md:h-[34px] md:w-[34px]",
        className)}>
      <Icon name={icon} size={size} />
    </button>
  );
}
