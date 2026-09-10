"use client";

/** The application's state: conversations, threads, and the realtime events
 *  that keep them current.
 *
 *  One hook rather than a store library. Everything here is owned by a single
 *  screen (the chat page), so React state plus the socket subscription is
 *  enough, and it keeps the data flow readable end to end: an action calls the
 *  API, the API broadcasts, and the socket handler applies the result — the
 *  same path whether the change originated on this device or another one. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { toConversation, toMessage, toUser } from "./adapt";
import type { ConversationDTO, MessageDTO, UserDTO } from "./dto";
import { socket, type SocketState } from "./socket";
import type { Conversation, Me, Message } from "./types";

/** How long a typing indicator survives without a refresh. Clients send
 *  `typing.stop`, but a browser that closes mid-word never will, so the
 *  indicator has to expire on its own. */
const TYPING_TIMEOUT = 5000;

const PAGE_SIZE = 40;

interface TypingUser {
  id: number;
  name: string;
  /** Epoch milliseconds after which this indicator is stale. */
  expiresAt: number;
}

/** Newest last, which is the order a thread is read in. */
function insertMessage(thread: Message[], message: Message): Message[] {
  if (thread.some((m) => m.id === message.id)) {
    return thread.map((m) => (m.id === message.id ? message : m));
  }
  const next = [...thread, message];
  next.sort((a, b) => a.id - b.id);
  return next;
}

function sortConversations(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort(
    (a, b) => new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime(),
  );
}

export function useMessenger(me: Me) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [threads, setThreads] = useState<Record<number, Message[]>>({});
  /** Pagination cursor per conversation; null once history is exhausted. */
  const [cursors, setCursors] = useState<Record<number, number | null>>({});
  const [activeId, setActiveId] = useState<number | null>(null);
  const [typing, setTyping] = useState<Record<number, TypingUser[]>>({});
  const [connection, setConnection] = useState<SocketState>(socket.state);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Read inside socket handlers, which are registered once and would otherwise
  // close over the value of activeId at subscription time.
  const activeIdRef = useRef<number | null>(null);
  activeIdRef.current = activeId;

  const fail = useCallback((problem: unknown) => {
    setError(problem instanceof ApiError ? problem.message : "Something went wrong.");
  }, []);

  // ---------------------------------------------------------------- loading

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(sortConversations((await api.listConversations()).map(toConversation)));
    } catch (problem) {
      fail(problem);
    } finally {
      setLoading(false);
    }
  }, [fail]);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  const loadThread = useCallback(
    async (conversationId: number) => {
      try {
        const page = await api.listMessages(conversationId, { limit: PAGE_SIZE });
        setThreads((current) => ({ ...current, [conversationId]: page.messages.map(toMessage) }));
        setCursors((current) => ({ ...current, [conversationId]: page.next_before_id }));
      } catch (problem) {
        fail(problem);
      }
    },
    [fail],
  );

  /** Fetch the page before the oldest message on screen. */
  const loadOlder = useCallback(
    async (conversationId: number) => {
      const cursor = cursors[conversationId];
      if (!cursor) return;
      try {
        const page = await api.listMessages(conversationId, {
          limit: PAGE_SIZE,
          before_id: cursor,
        });
        setThreads((current) => ({
          ...current,
          [conversationId]: [...page.messages.map(toMessage), ...(current[conversationId] ?? [])],
        }));
        setCursors((current) => ({ ...current, [conversationId]: page.next_before_id }));
      } catch (problem) {
        fail(problem);
      }
    },
    [cursors, fail],
  );

  // ---------------------------------------------------------------- actions

  const markRead = useCallback((conversationId: number) => {
    // Cleared locally at once so the badge disappears on tap; the socket sends
    // the receipt, and the HTTP call is the fallback when it is down.
    setConversations((current) =>
      current.map((c) => (c.id === conversationId ? { ...c, unreadCount: 0 } : c)),
    );
    socket.send({ type: "message.read", conversation_id: conversationId });
    void api.markRead(conversationId).catch(() => undefined);
  }, []);

  const openConversation = useCallback(
    (conversationId: number) => {
      setActiveId(conversationId);
      if (!threads[conversationId]) void loadThread(conversationId);
      markRead(conversationId);
    },
    [threads, loadThread, markRead],
  );

  const sendMessage = useCallback(
    async (conversationId: number, content: string, replyToId: number | null) => {
      // A temporary negative id: it cannot collide with a server id, and it
      // makes the optimistic row identifiable when the real one replaces it.
      const temporaryId = -Date.now();
      const optimistic: Message = {
        id: temporaryId,
        conversationId,
        sender: me,
        content,
        createdAt: new Date().toISOString(),
        editedAt: null,
        status: "sent",
        replyTo: null,
        pending: true,
      };
      setThreads((current) => ({
        ...current,
        [conversationId]: [...(current[conversationId] ?? []), optimistic],
      }));

      try {
        const sent = toMessage(await api.sendMessage(conversationId, {
          content,
          reply_to_id: replyToId,
        }));
        setThreads((current) => ({
          ...current,
          [conversationId]: (current[conversationId] ?? []).map((m) =>
            m.id === temporaryId ? sent : m,
          ),
        }));
      } catch (problem) {
        // Left in place and marked failed rather than removed: text someone
        // typed must never disappear because the network did.
        setThreads((current) => ({
          ...current,
          [conversationId]: (current[conversationId] ?? []).map((m) =>
            m.id === temporaryId ? { ...m, status: "failed", pending: false } : m,
          ),
        }));
        fail(problem);
      }
    },
    [me, fail],
  );

  const editMessage = useCallback(
    async (messageId: number, content: string) => {
      try {
        await api.editMessage(messageId, content);
      } catch (problem) {
        fail(problem);
      }
    },
    [fail],
  );

  const deleteMessage = useCallback(
    async (messageId: number) => {
      try {
        await api.deleteMessage(messageId);
      } catch (problem) {
        fail(problem);
      }
    },
    [fail],
  );

  /** Remove a message that never reached the server. */
  const discardFailed = useCallback((conversationId: number, messageId: number) => {
    setThreads((current) => ({
      ...current,
      [conversationId]: (current[conversationId] ?? []).filter((m) => m.id !== messageId),
    }));
  }, []);

  const startDirect = useCallback(
    async (userId: number) => {
      try {
        const conversation = toConversation(await api.openDirect(userId));
        setConversations((current) =>
          sortConversations([
            conversation,
            ...current.filter((c) => c.id !== conversation.id),
          ]),
        );
        openConversation(conversation.id);
        return conversation;
      } catch (problem) {
        fail(problem);
        return null;
      }
    },
    [openConversation, fail],
  );

  const createGroup = useCallback(
    async (name: string, memberIds: number[]) => {
      try {
        const conversation = toConversation(await api.createGroup({ name, member_ids: memberIds }));
        // The creator is a participant, so the "conversation.created" broadcast
        // reaches this same device too -- and can arrive before this HTTP
        // response does, since the server sends it right after committing the
        // row. Filtering out any existing id before prepending (the same guard
        // startDirect and applyConversation already use) is what keeps that
        // race from leaving the new group in the list twice.
        setConversations((current) =>
          sortConversations([conversation, ...current.filter((c) => c.id !== conversation.id)]),
        );
        openConversation(conversation.id);
        return conversation;
      } catch (problem) {
        fail(problem);
        return null;
      }
    },
    [openConversation, fail],
  );

  /** Replace one conversation with the server's version of it. */
  const applyConversation = useCallback((dto: ConversationDTO) => {
    const conversation = toConversation(dto);
    setConversations((current) =>
      sortConversations(
        current.some((c) => c.id === conversation.id)
          ? current.map((c) => (c.id === conversation.id ? conversation : c))
          : [conversation, ...current],
      ),
    );
    return conversation;
  }, []);

  const setMuted = useCallback(
    async (conversationId: number, muted: boolean) => {
      try {
        applyConversation(await api.setMuted(conversationId, muted));
      } catch (problem) {
        fail(problem);
      }
    },
    [applyConversation, fail],
  );

  const renameGroup = useCallback(
    async (conversationId: number, name: string) => {
      try {
        applyConversation(await api.updateGroup(conversationId, { name }));
      } catch (problem) {
        fail(problem);
      }
    },
    [applyConversation, fail],
  );

  /** Drop a conversation from the list, and from the screen if it was open. */
  const forget = useCallback((conversationId: number) => {
    setConversations((current) => current.filter((c) => c.id !== conversationId));
    setThreads((current) => {
      const { [conversationId]: _removed, ...rest } = current;
      return rest;
    });
    setActiveId((current) => (current === conversationId ? null : current));
  }, []);

  const leaveGroup = useCallback(
    async (conversationId: number) => {
      try {
        await api.leaveGroup(conversationId);
        forget(conversationId);
      } catch (problem) {
        fail(problem);
      }
    },
    [forget, fail],
  );

  const refreshConversation = useCallback(
    async (conversationId: number) => {
      try {
        applyConversation(await api.getConversation(conversationId));
      } catch (problem) {
        // A 404 here means membership ended between the event and the fetch,
        // which is not an error worth showing.
        if (problem instanceof ApiError && problem.status === 404) forget(conversationId);
      }
    },
    [applyConversation, forget],
  );

  const addMembers = useCallback(
    async (conversationId: number, memberIds: number[]) => {
      try {
        await api.addMembers(conversationId, memberIds);
        await refreshConversation(conversationId);
      } catch (problem) {
        fail(problem);
      }
    },
    [refreshConversation, fail],
  );

  const removeMember = useCallback(
    async (conversationId: number, memberId: number) => {
      try {
        await api.removeMember(conversationId, memberId);
        await refreshConversation(conversationId);
      } catch (problem) {
        fail(problem);
      }
    },
    [refreshConversation, fail],
  );

  const setRole = useCallback(
    async (conversationId: number, memberId: number, role: "admin" | "member") => {
      try {
        await api.setRole(conversationId, memberId, role);
        await refreshConversation(conversationId);
      } catch (problem) {
        fail(problem);
      }
    },
    [refreshConversation, fail],
  );

  const notifyTyping = useCallback((conversationId: number, isTyping: boolean) => {
    socket.send({
      type: isTyping ? "typing.start" : "typing.stop",
      conversation_id: conversationId,
    });
  }, []);

  // ------------------------------------------------------- realtime events

  const applyIncomingMessage = useCallback(
    (dto: MessageDTO) => {
      const message = toMessage(dto);
      const isMine = message.sender.id === me.id;

      setThreads((current) => {
        const thread = current[message.conversationId];
        // Only touch a thread already loaded. Inserting into one that has never
        // been opened would leave a single message masquerading as the whole
        // history, and the first page load would then duplicate it.
        if (!thread) return current;
        // Drop the optimistic copy of a message this device just sent.
        const withoutPending = isMine
          ? thread.filter((m) => !(m.pending && m.content === message.content))
          : thread;
        return { ...current, [message.conversationId]: insertMessage(withoutPending, message) };
      });

      setConversations((current) =>
        sortConversations(
          current.map((c) =>
            c.id === message.conversationId
              ? {
                  ...c,
                  lastMessage: message,
                  lastActivity: message.createdAt,
                  unreadCount:
                    isMine || activeIdRef.current === c.id ? c.unreadCount : c.unreadCount + 1,
                }
              : c,
          ),
        ),
      );

      // Reading a conversation that is already on screen: acknowledge at once
      // so the sender's ticks turn blue while they are still looking.
      if (!isMine && activeIdRef.current === message.conversationId) {
        socket.send({ type: "message.read", conversation_id: message.conversationId });
      }
    },
    [me.id],
  );

  useEffect(() => {
    const unsubscribeState = socket.onStateChange(setConnection);

    const unsubscribe = socket.on((event) => {
      const data = event.data as Record<string, unknown>;

      switch (event.type) {
        case "message.new":
          applyIncomingMessage(data.message as MessageDTO);
          break;

        case "message.updated": {
          const message = toMessage(data.message as MessageDTO);
          setThreads((current) => {
            const thread = current[message.conversationId];
            if (!thread) return current;
            return {
              ...current,
              [message.conversationId]: thread.map((m) => (m.id === message.id ? message : m)),
            };
          });
          break;
        }

        case "message.deleted": {
          const conversationId = data.conversation_id as number;
          const messageId = data.message_id as number;
          setThreads((current) => {
            const thread = current[conversationId];
            if (!thread) return current;
            return { ...current, [conversationId]: thread.filter((m) => m.id !== messageId) };
          });
          break;
        }

        case "message.status": {
          const conversationId = data.conversation_id as number;
          const ids = new Set(data.message_ids as number[]);
          const status = data.status as Message["status"];
          setThreads((current) => {
            const thread = current[conversationId];
            if (!thread) return current;
            return {
              ...current,
              [conversationId]: thread.map((m) => (ids.has(m.id) ? { ...m, status } : m)),
            };
          });
          break;
        }

        case "typing.start": {
          const conversationId = data.conversation_id as number;
          const user = toUser(data.user as UserDTO);
          setTyping((current) => {
            const others = (current[conversationId] ?? []).filter((t) => t.id !== user.id);
            return {
              ...current,
              [conversationId]: [
                ...others,
                { id: user.id, name: user.displayName, expiresAt: Date.now() + TYPING_TIMEOUT },
              ],
            };
          });
          break;
        }

        case "typing.stop": {
          const conversationId = data.conversation_id as number;
          const user = data.user as UserDTO;
          setTyping((current) => ({
            ...current,
            [conversationId]: (current[conversationId] ?? []).filter((t) => t.id !== user.id),
          }));
          break;
        }

        case "presence": {
          const userId = data.user_id as number;
          const isOnline = data.is_online as boolean;
          const lastSeen = (data.last_seen as string | null) ?? null;
          // Presence lives on the participant records, so every conversation
          // this person is in has to be updated, not just the open one.
          setConversations((current) =>
            current.map((c) => ({
              ...c,
              participants: c.participants.map((p) =>
                p.user.id === userId
                  ? { ...p, user: { ...p.user, isOnline, lastSeen } }
                  : p,
              ),
            })),
          );
          break;
        }

        case "conversation.created":
        case "conversation.updated":
          applyConversation(data.conversation as ConversationDTO);
          break;

        case "conversation.deleted":
          forget(data.conversation_id as number);
          break;

        case "group.members_added":
        case "group.member_removed":
        case "group.role_changed":
          void refreshConversation(data.conversation_id as number);
          break;
      }
    });

    return () => {
      unsubscribe();
      unsubscribeState();
    };
  }, [applyIncomingMessage, applyConversation, forget, refreshConversation]);

  // A stale indicator is worse than none: it says someone is still typing when
  // they stopped, or closed the tab, minutes ago.
  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      setTyping((current) => {
        let changed = false;
        const next: Record<number, TypingUser[]> = {};
        for (const [id, users] of Object.entries(current)) {
          const live = users.filter((t) => t.expiresAt > now);
          if (live.length !== users.length) changed = true;
          if (live.length) next[Number(id)] = live;
        }
        return changed ? next : current;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // The socket carries only what happens while it is open, so a reconnection
  // leaves a gap. Refetching the list closes it.
  const wasOpen = useRef(false);
  useEffect(() => {
    if (connection === "open" && wasOpen.current) {
      void refreshConversations();
      const openThread = activeIdRef.current;
      if (openThread) void loadThread(openThread);
    }
    wasOpen.current = connection === "open";
  }, [connection, refreshConversations, loadThread]);

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? null,
    [conversations, activeId],
  );

  return {
    conversations,
    active,
    activeId,
    thread: activeId ? (threads[activeId] ?? []) : [],
    hasOlder: activeId ? Boolean(cursors[activeId]) : false,
    typing: activeId ? (typing[activeId] ?? []) : [],
    connection,
    loading,
    error,
    clearError: () => setError(null),
    openConversation,
    closeConversation: () => setActiveId(null),
    loadOlder,
    sendMessage,
    editMessage,
    deleteMessage,
    discardFailed,
    startDirect,
    createGroup,
    setMuted,
    renameGroup,
    leaveGroup,
    addMembers,
    removeMember,
    setRole,
    notifyTyping,
  };
}

export type Messenger = ReturnType<typeof useMessenger>;
