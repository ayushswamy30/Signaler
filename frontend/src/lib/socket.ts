/** The realtime connection.
 *
 *  A small class rather than a hook, because the socket must outlive React's
 *  render cycle: a strict-mode double-effect, or a component remounting, must
 *  not tear down and re-establish a live connection. The hook in
 *  `useMessenger` subscribes to it and unsubscribes on unmount; the socket
 *  itself is opened and closed explicitly. */

import { API_URL, tokens } from "./api";
import type { SocketEvent } from "./dto";

type Listener = (event: SocketEvent) => void;

export type SocketState = "connecting" | "open" | "closed";

/** Backoff between reconnection attempts, in milliseconds. Capped, because a
 *  laptop that wakes after a night asleep should retry in seconds, not hours. */
const RETRY_DELAYS = [500, 1000, 2000, 5000, 10000, 15000];

function socketUrl(token: string): string {
  const base = API_URL.replace(/^http/, "ws");
  return `${base}/ws?token=${encodeURIComponent(token)}`;
}

export class SignalerSocket {
  private socket: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private stateListeners = new Set<(state: SocketState) => void>();
  private attempt = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  /** Set when close() was called deliberately, so the reconnect loop stops. */
  private closed = false;
  private _state: SocketState = "closed";

  get state(): SocketState {
    return this._state;
  }

  /** Subscribe to events. Returns the unsubscribe function. */
  on(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  onStateChange(listener: (state: SocketState) => void): () => void {
    this.stateListeners.add(listener);
    return () => this.stateListeners.delete(listener);
  }

  connect() {
    if (this.socket || typeof window === "undefined") return;
    const token = tokens.access;
    if (!token) return;

    this.closed = false;
    this.setState("connecting");

    const socket = new WebSocket(socketUrl(token));
    this.socket = socket;

    socket.onopen = () => {
      this.attempt = 0;
      this.setState("open");
    };

    socket.onmessage = (event) => {
      let payload: SocketEvent;
      try {
        payload = JSON.parse(event.data as string) as SocketEvent;
      } catch {
        return; // Not our protocol; ignoring is better than throwing in a handler.
      }
      for (const listener of this.listeners) listener(payload);
    };

    socket.onclose = () => {
      this.socket = null;
      this.setState("closed");
      if (!this.closed) this.scheduleReconnect();
    };

    // An error is always followed by a close, so reconnection is handled there
    // rather than in both places.
    socket.onerror = () => socket.close();
  }

  private scheduleReconnect() {
    const delay = RETRY_DELAYS[Math.min(this.attempt, RETRY_DELAYS.length - 1)];
    this.attempt += 1;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      // The access token may have been refreshed since the drop, so connect()
      // reads it again rather than reusing the one this socket was opened with.
      this.connect();
    }, delay);
  }

  private setState(state: SocketState) {
    this._state = state;
    for (const listener of this.stateListeners) listener(state);
  }

  send(payload: Record<string, unknown>) {
    // Dropped rather than queued when the socket is down: every message this
    // carries (typing, read receipts) is only meaningful right now, and a
    // replayed backlog after a reconnect would be worse than silence.
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  close() {
    this.closed = true;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    this.socket?.close();
    this.socket = null;
    this.setState("closed");
  }
}

/** One socket for the application. A second connection would double every
 *  event and count as a second device for presence. */
export const socket = new SignalerSocket();
