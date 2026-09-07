export type DeliveryStatus = "sent" | "delivered" | "read" | "failed";
export type ConversationType = "direct" | "group";
export type ParticipantRole = "member" | "admin";

export interface User {
  id: number; username: string; displayName: string;
  avatarUrl: string | null; isOnline: boolean; lastSeen: string | null;
}
export interface Participant { user: User; role: ParticipantRole }
export interface Message {
  id: number; conversationId: number; sender: User; content: string;
  createdAt: string; editedAt: string | null;
  status: DeliveryStatus | null; replyTo: { sender: string; content: string } | null;
}
export interface Conversation {
  id: number; type: ConversationType; name: string | null;
  participants: Participant[]; lastMessage: string; lastActivity: string;
  unreadCount: number; muted: boolean;
}
