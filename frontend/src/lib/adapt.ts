/** DTO -> view model. The only place the API's field names are spelled out. */

import type {
  ContactDTO,
  ConversationDTO,
  MeDTO,
  MessageDTO,
  ParticipantDTO,
  UserDTO,
} from "./dto";
import type { Contact, Conversation, Me, Message, Participant, User } from "./types";

export function toUser(dto: UserDTO): User {
  return {
    id: dto.id,
    username: dto.username,
    displayName: dto.display_name,
    avatarUrl: dto.avatar_url,
    about: dto.about,
    isOnline: dto.is_online,
    lastSeen: dto.last_seen,
  };
}

export function toMe(dto: MeDTO): Me {
  return { ...toUser(dto), phoneNumber: dto.phone_number, createdAt: dto.created_at };
}

export function toParticipant(dto: ParticipantDTO): Participant {
  return { user: toUser(dto.user), role: dto.role, joinedAt: dto.joined_at };
}

export function toMessage(dto: MessageDTO): Message {
  return {
    id: dto.id,
    conversationId: dto.conversation_id,
    sender: toUser(dto.sender),
    content: dto.content,
    createdAt: dto.created_at,
    editedAt: dto.edited_at,
    status: dto.status,
    replyTo: dto.reply_to
      ? {
          id: dto.reply_to.id,
          sender: dto.reply_to.sender_display_name,
          content: dto.reply_to.content,
        }
      : null,
  };
}

export function toConversation(dto: ConversationDTO): Conversation {
  const lastMessage = dto.last_message ? toMessage(dto.last_message) : null;
  return {
    id: dto.id,
    type: dto.type,
    name: dto.name,
    avatarUrl: dto.avatar_url,
    participants: dto.participants.map(toParticipant),
    lastMessage,
    unreadCount: dto.unread_count,
    muted: dto.muted,
    myRole: dto.my_role,
    // An empty conversation has never had activity, so it is ordered by when it
    // was created rather than sorting to the bottom with no timestamp at all.
    lastActivity: lastMessage?.createdAt ?? dto.updated_at,
  };
}

export function toContact(dto: ContactDTO): Contact {
  return { user: toUser(dto.contact_user), createdAt: dto.created_at };
}
