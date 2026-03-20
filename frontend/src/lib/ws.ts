/**
 * WebSocket client. Connects to /ws?token=<token>.
 * Emits events to registered handlers.
 * Auto-reconnects on close.
 */
import type { WsEvent } from './types';

type Handler = (event: WsEvent) => void;

let socket: WebSocket | null = null;
const handlers: Set<Handler> = new Set();
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function onWsEvent(handler: Handler): () => void {
  handlers.add(handler);
  return () => handlers.delete(handler);
}

export function connectWs(token: string): void {
  if (socket && socket.readyState < 2) return; // already open or connecting

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/ws?token=${encodeURIComponent(token)}`;
  socket = new WebSocket(url);

  socket.onmessage = (e) => {
    try {
      const event: WsEvent = JSON.parse(e.data);
      for (const h of handlers) h(event);
    } catch {
      // ignore malformed messages
    }
  };

  socket.onclose = () => {
    socket = null;
    // Reconnect after 3 seconds
    reconnectTimer = setTimeout(() => connectWs(token), 3000);
  };

  socket.onerror = () => {
    socket?.close();
  };
}

export function disconnectWs(): void {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  socket?.close();
  socket = null;
}
