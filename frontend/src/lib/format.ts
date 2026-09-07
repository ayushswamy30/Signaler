/** Presentation helpers: naming a conversation, and turning timestamps into
 *  the short labels a messenger shows. */

import type { Conversation, Message, User } from "./types";

/** The other person in a direct conversation.
 *
 *  Falls back to the first participant so a malformed conversation renders
 *  something rather than crashing the list. */
export function counterpart(conversation: Conversation, meId: number): User | null {
  const other = conversation.participants.find((p) => p.user.id !== meId);
  return other?.user ?? conversation.participants[0]?.user ?? null;
}

/** What to call a conversation: a group's name, or the other person's. */
export function title(conversation: Conversation, meId: number): string {
  if (conversation.type === "group") return conversation.name ?? "Group";
  return counterpart(conversation, meId)?.displayName ?? "Conversation";
}

/** The one-line preview under a conversation's name.
 *
 *  Group previews are prefixed with the sender, the way every messenger does
 *  it, because in a group "on my way" means nothing without a name. */
export function preview(conversation: Conversation, meId: number): string {
  const message = conversation.lastMessage;
  if (!message) return "No messages yet";
  if (conversation.type !== "group") return message.content;
  const who = message.sender.id === meId ? "You" : message.sender.displayName.split(" ")[0];
  return `${who}: ${message.content}`;
}

const DAY = 24 * 60 * 60 * 1000;

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** "14:32" — the time a message was sent. */
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** The label on a conversation-list row: time today, weekday this week, date beyond.
 *
 *  Progressive precision, because "09:24" is only useful while today is
 *  obvious, and a full date on every row is noise. */
export function formatListTime(iso: string): string {
  const date = new Date(iso);
  const days = Math.round((startOfDay(new Date()) - startOfDay(date)) / DAY);
  if (days <= 0) return formatTime(iso);
  if (days === 1) return "Yesterday";
  if (days < 7) return date.toLocaleDateString([], { weekday: "short" });
  return date.toLocaleDateString([], { day: "numeric", month: "short" });
}

/** The heading on a date separator inside a thread. */
export function formatDateSeparator(iso: string): string {
  const date = new Date(iso);
  const days = Math.round((startOfDay(new Date()) - startOfDay(date)) / DAY);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return date.toLocaleDateString([], { weekday: "long" });
  return date.toLocaleDateString([], { day: "numeric", month: "long", year: "numeric" });
}

/** "last seen 5 minutes ago". Null when the account has never connected. */
export function formatLastSeen(iso: string | null): string | null {
  if (!iso) return null;
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  return formatListTime(iso).toLowerCase();
}

/** The line under a conversation title: membership, or the other side's presence. */
export function subtitle(conversation: Conversation, meId: number): string {
  if (conversation.type === "group") {
    const count = conversation.participants.length;
    return `${count} member${count === 1 ? "" : "s"}`;
  }
  const other = counterpart(conversation, meId);
  if (!other) return "";
  if (other.isOnline) return "Online";
  const seen = formatLastSeen(other.lastSeen);
  return seen ? `Last seen ${seen}` : `@${other.username}`;
}

/** True when two messages should be separated by a date heading. */
export function crossesDay(previous: Message | undefined, current: Message): boolean {
  if (!previous) return true;
  return startOfDay(new Date(previous.createdAt)) !== startOfDay(new Date(current.createdAt));
}
