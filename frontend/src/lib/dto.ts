/** The shapes the backend actually returns, field for field.
 *
 *  Kept separate from the view models in `types.ts`, and named in the API's own
 *  snake_case, so that the boundary is visible: everything that converts one
 *  into the other lives in `adapt.ts`, and a backend change shows up as a type
 *  error there rather than somewhere deep in a component. */

export type DeliveryStatusDTO = "sent" | "delivered" | "read";
export type ConversationTypeDTO = "direct" | "group";
export type ParticipantRoleDTO = "member" | "admin";

export interface UserDTO {
  id: number;
  username: string;
  display_name: string;
  avatar_url: string | null;
  about: string | null;
  is_online: boolean;
  last_seen: string | null;
}

/** The signed-in user's own record, which carries their private fields too. */
export interface MeDTO extends UserDTO {
  phone_number: string | null;
  created_at: string;
}

export interface ParticipantDTO {
  user: UserDTO;
  role: ParticipantRoleDTO;
  joined_at: string;
}

export interface ReplyPreviewDTO {
  id: number;
  sender_display_name: string;
  content: string;
}

export interface MessageDTO {
  id: number;
  conversation_id: number;
  sender: UserDTO;
  content: string;
  message_type: "text";
  created_at: string;
  edited_at: string | null;
  /** Only meaningful on your own messages; null when nobody else is in the room. */
  status: DeliveryStatusDTO | null;
  reply_to: ReplyPreviewDTO | null;
}

export interface MessagePageDTO {
  messages: MessageDTO[];
  /** Cursor for the page *before* this one; null at the start of history. */
  next_before_id: number | null;
}

export interface ConversationDTO {
  id: number;
  type: ConversationTypeDTO;
  name: string | null;
  avatar_url: string | null;
  participants: ParticipantDTO[];
  last_message: MessageDTO | null;
  unread_count: number;
  muted: boolean;
  my_role: ParticipantRoleDTO;
  created_at: string;
  updated_at: string;
}

export interface ContactDTO {
  contact_user: UserDTO;
  created_at: string;
}

export interface TokenDTO {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: MeDTO;
}

/** Every realtime frame: a name, and a payload whose shape the name decides. */
export interface SocketEvent<T = Record<string, unknown>> {
  type: string;
  data: T;
}
