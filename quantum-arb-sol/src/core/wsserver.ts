// Local WebSocket server. The engine runs as an independent Node process; the
// UI and CLI connect here and receive a read-only stream of bus events. No
// command channel — clients cannot drive execution, only observe.

import { WebSocketServer, type WebSocket } from 'ws';
import type { Bus } from './bus.js';

export interface WsMessage {
  type: 'quotes' | 'opportunity' | 'fill' | 'metric' | 'ledger' | 'sizing' | 'error';
  payload: unknown;
}

// The ONLY inbound command clients may send. It adjusts paper sizing — never
// signing or order execution (there is none). Anything else is ignored.
export interface SetSizingCommand {
  type: 'set_sizing';
  payload: { notionalUsd: number };
}

export interface WsServerHooks {
  // Called when a client requests a new global paper notional. Already
  // validated + clamped. The engine applies it and echoes via the bus.
  onSetNotional?: (notionalUsd: number) => void;
}

const MIN_NOTIONAL = 1;
const MAX_NOTIONAL = 10_000_000; // sanity clamp; paper only

export class EngineWsServer {
  private readonly wss: WebSocketServer;
  private readonly clients = new Set<WebSocket>();
  private readonly unsubs: Array<() => void> = [];

  constructor(bus: Bus, port: number, hooks: WsServerHooks = {}) {
    this.wss = new WebSocketServer({ port });
    this.wss.on('connection', (ws) => {
      this.clients.add(ws);
      ws.on('message', (data) => this.handleInbound(data.toString(), hooks));
      ws.on('close', () => this.clients.delete(ws));
      ws.on('error', () => this.clients.delete(ws));
    });

    const forward = (type: WsMessage['type']) =>
      this.unsubs.push(bus.on(type, (payload: unknown) => this.broadcast({ type, payload })));
    forward('quotes');
    forward('opportunity');
    forward('fill');
    forward('metric');
    forward('ledger');
    forward('sizing');
    forward('error');
  }

  /** Parse + validate the one allowed command. Reject everything else. */
  private handleInbound(raw: string, hooks: WsServerHooks): void {
    let msg: unknown;
    try {
      msg = JSON.parse(raw);
    } catch {
      return; // ignore malformed input
    }
    if (
      typeof msg === 'object' &&
      msg !== null &&
      (msg as { type?: unknown }).type === 'set_sizing'
    ) {
      const n = (msg as SetSizingCommand).payload?.notionalUsd;
      if (typeof n === 'number' && Number.isFinite(n)) {
        const clamped = Math.min(MAX_NOTIONAL, Math.max(MIN_NOTIONAL, n));
        hooks.onSetNotional?.(clamped);
      }
    }
    // No other command type exists. There is deliberately no execution channel.
  }

  private broadcast(msg: WsMessage): void {
    const data = JSON.stringify(msg);
    for (const ws of this.clients) {
      if (ws.readyState === ws.OPEN) ws.send(data);
    }
  }

  get port(): number {
    const addr = this.wss.address();
    return typeof addr === 'object' && addr ? addr.port : 0;
  }

  close(): Promise<void> {
    for (const u of this.unsubs) u();
    return new Promise((resolve) => this.wss.close(() => resolve()));
  }
}
