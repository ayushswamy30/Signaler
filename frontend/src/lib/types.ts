/** View models: what the components render.
 *
 *  Close to the API shapes but not identical — camelCase, and every timestamp
 *  is a raw ISO string that the components format at render time. Formatting on
 *  arrival would freeze "2 minutes ago" at the moment the data was fetched. */

export type DeliveryStatus = "sent" | "delivered" | "read" | "failed";
export type ConversationType = "direct" | "group";
export type ParticipantRole = "member" | "admin";

export interface User {
  id: number;
  username: string;
  displayName: string;
  avatarUrl: string | null;
  about: string | null;
  isOnline: boolean;
  /** ISO timestamp, or null for an account that has never connected. */
  lastSeen: string | null;
}

export interface Me extends User {
  phoneNumber: string | null;
  createdAt: string;
}

export interface Participant {
  user: User;
  role: ParticipantRole;
  joinedAt: string;
}

export interface Message {
  id: number;
  conversationId: number;
  sender: User;
  content: string;
  /** ISO timestamp. */
  createdAt: string;
  editedAt: string | null;
  /** Set on your own messages only; "failed" is client-side, never from the API. */
  status: DeliveryStatus | null;
  replyTo: { id: number; sender: string; content: string } | null;
  /** True while an optimistic message waits for the server to confirm it.
   *  Such a message has a temporary negative id, replaced when the real one
   *  arrives — see `sendMessage` in useMessenger. */
  pending?: boolean;
}

export interface Conversation {
  id: number;
  type: ConversationType;
  name: string | null;
  avatarUrl: string | null;
  participants: Participant[];
  lastMessage: Message | null;
  unreadCount: number;
  muted: boolean;
  myRole: ParticipantRole;
  /** ISO timestamp of the last message, or of creation when there is none. */
  lastActivity: string;
}

export interface Contact {
  user: User;
  createdAt: string;
}
