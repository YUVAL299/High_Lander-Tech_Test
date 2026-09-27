import type {
  ClientMessage,
  LatLngPos,
  ServerMessageType,
  ServerMessages,
} from "../types/protocol";

export type SocketStatus = "connecting" | "open" | "reconnecting" | "closed";

type Handler<T extends ServerMessageType> = (payload: ServerMessages[T]) => void;

const PING_INTERVAL_MS = 20_000;
const MAX_BACKOFF_MS = 10_000;
/** Close codes the server uses when retrying is pointless. */
const FATAL_CLOSE_CODES = new Set([4404, 4409]);

/**
 * WebSocket connection to one game session, with automatic reconnection
 * (exponential backoff) and a keep-alive ping.
 */
export class GameSocket {
  private ws: WebSocket | null = null;
  private handlers = new Map<ServerMessageType, Set<Handler<never>>>();
  private statusListeners = new Set<(s: SocketStatus, reason?: string) => void>();
  private attempt = 0;
  private pingTimer: number | undefined;
  private reconnectTimer: number | undefined;
  private closedByUs = false;

  constructor(
    private readonly sessionId: string,
    private readonly playerId: string,
  ) {}

  connect(): void {
    this.closedByUs = false;
    this.setStatus(this.attempt === 0 ? "connecting" : "reconnecting");
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${location.host}/ws/sessions/${encodeURIComponent(
      this.sessionId,
    )}?player_id=${encodeURIComponent(this.playerId)}`;
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.attempt = 0;
      this.setStatus("open");
      this.pingTimer = window.setInterval(() => this.send({ type: "ping" }), PING_INTERVAL_MS);
    };
    ws.onmessage = (ev) => {
      let msg: { type: ServerMessageType; payload: unknown };
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      this.handlers.get(msg.type)?.forEach((h) => (h as Handler<typeof msg.type>)(msg.payload as never));
    };
    ws.onclose = (ev) => {
      window.clearInterval(this.pingTimer);
      if (this.ws !== ws) return; // superseded
      if (this.closedByUs || FATAL_CLOSE_CODES.has(ev.code)) {
        this.setStatus("closed", ev.reason || undefined);
        return;
      }
      const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** this.attempt++);
      this.setStatus("reconnecting");
      this.reconnectTimer = window.setTimeout(() => this.connect(), delay);
    };
  }

  close(): void {
    this.closedByUs = true;
    window.clearTimeout(this.reconnectTimer);
    window.clearInterval(this.pingTimer);
    this.ws?.close(1000);
  }

  sendPosition(pos: LatLngPos): boolean {
    return this.send({ type: "position.update", payload: { lat: pos.lat, lng: pos.lng } });
  }

  on<T extends ServerMessageType>(type: T, handler: Handler<T>): () => void {
    let set = this.handlers.get(type);
    if (!set) {
      set = new Set();
      this.handlers.set(type, set);
    }
    set.add(handler as Handler<never>);
    return () => set.delete(handler as Handler<never>);
  }

  onStatus(listener: (s: SocketStatus, reason?: string) => void): void {
    this.statusListeners.add(listener);
  }

  private send(msg: ClientMessage): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(msg));
    return true;
  }

  private setStatus(s: SocketStatus, reason?: string): void {
    this.statusListeners.forEach((l) => l(s, reason));
  }
}
