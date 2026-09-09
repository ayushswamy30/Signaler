/** The HTTP client: one place that knows the base URL, the token, and what a
 *  failure looks like.
 *
 *  Tokens live in localStorage rather than an httpOnly cookie. That is a real
 *  trade-off — a cookie would be out of reach of any script on the page —
 *  but the backend is a separate origin authenticated by a bearer header, and
 *  the socket needs the token as a query parameter, so the token has to be
 *  readable by this code either way. Access tokens are short-lived and refresh
 *  tokens rotate on every use, which is what limits the damage. */

import type {
  ContactDTO,
  ConversationDTO,
  IceServersDTO,
  MeDTO,
  MessageDTO,
  MessagePageDTO,
  ParticipantDTO,
  TokenDTO,
  UserDTO,
} from "./dto";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const ACCESS_KEY = "signaler-access-token";
const REFRESH_KEY = "signaler-refresh-token";

/** A failed request, carrying the status and the backend's own message.
 *
 *  Every error response from the API has the same `{detail}` body, so callers
 *  can show `error.message` directly instead of inventing their own wording. */
export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the session is gone and the user has to sign in again. */
  get isAuthError() {
    return this.status === 401;
  }
}

/** localStorage throws in private-mode Safari and when cookies are blocked, so
 *  every access is guarded: a browser that cannot store tokens should land on
 *  the sign-in screen, not on a blank page. */
function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* Storage unavailable; the session lasts only as long as this page. */
  }
}

export const tokens = {
  get access() {
    return read(ACCESS_KEY);
  },
  get refresh() {
    return read(REFRESH_KEY);
  },
  save(token: TokenDTO) {
    write(ACCESS_KEY, token.access_token);
    write(REFRESH_KEY, token.refresh_token);
  },
  clear() {
    write(ACCESS_KEY, null);
    write(REFRESH_KEY, null);
  },
};

/** Set while a refresh is in flight, so several 401s at once queue behind one
 *  exchange. Without it, a screen that fires four requests on mount would spend
 *  four refresh tokens, and rotation would invalidate three of them. */
let refreshing: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  const refresh_token = tokens.refresh;
  if (!refresh_token) return false;

  refreshing ??= (async () => {
    try {
      const response = await fetch(`${API_URL}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token }),
      });
      if (!response.ok) {
        tokens.clear();
        return false;
      }
      tokens.save((await response.json()) as TokenDTO);
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();

  return refreshing;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Set false for the endpoints that run before a session exists. */
  auth?: boolean;
  /** Internal: stops a refreshed request from refreshing again in a loop. */
  retried?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, retried = false } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const access = tokens.access;
    if (access) headers.Authorization = `Bearer ${access}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // fetch only rejects when the request never completed: the server is down,
    // DNS failed, or the device is offline. There is no status to report.
    throw new ApiError(0, "Cannot reach the server. Check your connection.");
  }

  if (response.status === 401 && auth && !retried && (await refreshSession())) {
    return request<T>(path, { ...options, retried: true });
  }

  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Pull the message out of a failure, whatever shape it arrived in.
 *
 *  The API always sends `{detail}`, but FastAPI's own request validation sends
 *  `detail` as a list of field errors, and a proxy or crash may send no JSON at
 *  all — so all three are handled rather than showing "[object Object]". */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0];
      const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : null;
      const message = typeof first?.msg === "string" ? first.msg : "is not valid";
      return field ? `${String(field).replace(/_/g, " ")}: ${message}` : message;
    }
  } catch {
    /* Not JSON. */
  }
  return response.status >= 500
    ? "Something went wrong on the server. Please try again."
    : "That request could not be completed.";
}

/** The endpoints, named for what they do rather than for their URL. */
export const api = {
  register: (body: {
    username: string;
    password: string;
    display_name: string;
    phone_number?: string | null;
  }) => request<TokenDTO>("/api/auth/register", { method: "POST", body, auth: false }),

  login: (body: { username: string; password: string }) =>
    request<TokenDTO>("/api/auth/login", { method: "POST", body, auth: false }),

  logout: (refresh_token: string) =>
    request<{ detail: string }>("/api/auth/logout", {
      method: "POST",
      body: { refresh_token },
      auth: false,
    }),

  me: () => request<MeDTO>("/api/users/me"),

  updateProfile: (body: { display_name?: string; about?: string; avatar_url?: string }) =>
    request<MeDTO>("/api/users/me", { method: "PATCH", body }),

  changePassword: (body: { current_password: string; new_password: string }) =>
    request<{ detail: string }>("/api/users/me/password", { method: "POST", body }),

  searchUsers: (query: string) =>
    request<UserDTO[]>(`/api/users/search?q=${encodeURIComponent(query)}`),

  listContacts: () => request<ContactDTO[]>("/api/contacts"),

  addContact: (user_id: number) =>
    request<ContactDTO>("/api/contacts", { method: "POST", body: { user_id } }),

  removeContact: (user_id: number) =>
    request<{ detail: string }>(`/api/contacts/${user_id}`, { method: "DELETE" }),

  listConversations: () => request<ConversationDTO[]>("/api/conversations"),

  getConversation: (id: number) => request<ConversationDTO>(`/api/conversations/${id}`),

  openDirect: (user_id: number) =>
    request<ConversationDTO>("/api/conversations/direct", { method: "POST", body: { user_id } }),

  listMembers: (id: number) => request<ParticipantDTO[]>(`/api/conversations/${id}/members`),

  listMessages: (id: number, params: { limit?: number; before_id?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.limit) query.set("limit", String(params.limit));
    if (params.before_id) query.set("before_id", String(params.before_id));
    const suffix = query.size ? `?${query}` : "";
    return request<MessagePageDTO>(`/api/conversations/${id}/messages${suffix}`);
  },

  sendMessage: (id: number, body: { content: string; reply_to_id?: number | null }) =>
    request<MessageDTO>(`/api/conversations/${id}/messages`, { method: "POST", body }),

  editMessage: (messageId: number, content: string) =>
    request<MessageDTO>(`/api/messages/${messageId}`, { method: "PATCH", body: { content } }),

  deleteMessage: (messageId: number) =>
    request<{ detail: string }>(`/api/messages/${messageId}`, { method: "DELETE" }),

  markRead: (id: number, up_to_message_id?: number) =>
    request<{ detail: string }>(`/api/conversations/${id}/read`, {
      method: "POST",
      body: { up_to_message_id: up_to_message_id ?? null },
    }),

  setMuted: (id: number, muted: boolean) =>
    request<ConversationDTO>(`/api/conversations/${id}/mute`, { method: "PATCH", body: { muted } }),

  createGroup: (body: { name: string; member_ids: number[] }) =>
    request<ConversationDTO>("/api/groups", { method: "POST", body }),

  updateGroup: (id: number, body: { name?: string; avatar_url?: string }) =>
    request<ConversationDTO>(`/api/groups/${id}`, { method: "PATCH", body }),

  addMembers: (id: number, member_ids: number[]) =>
    request<ParticipantDTO[]>(`/api/groups/${id}/members`, { method: "POST", body: { member_ids } }),

  removeMember: (id: number, memberId: number) =>
    request<{ detail: string }>(`/api/groups/${id}/members/${memberId}`, { method: "DELETE" }),

  setRole: (id: number, memberId: number, role: "admin" | "member") =>
    request<ParticipantDTO>(`/api/groups/${id}/members/${memberId}`, {
      method: "PATCH",
      body: { role },
    }),

  leaveGroup: (id: number) =>
    request<{ detail: string }>(`/api/groups/${id}/leave`, { method: "POST" }),

  iceServers: () => request<IceServersDTO>("/api/calls/ice-servers"),
};
