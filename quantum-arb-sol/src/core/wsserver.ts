// Local WebSocket server. The engine runs as an independent Node process; the
// UI and CLI connect here and receive a read-only stream of bus events. No
// command channel — clients cannot drive execution, only observe.

import { WebSocketServer, type WebSocket } from 'ws';
import type { Bus } from './bus.js';

export interface WsMessage {
  type: 'quotes' | 'opportunity' | 'fill' | 'metric' | 'ledger' | 'error';
  payload: unknown;
}

export class EngineWsServer {
  private readonly wss: WebSocketServer;
  private readonly clients = new Set<WebSocket>();
  private readonly unsubs: Array<() => void> = [];

  constructor(bus: Bus, port: number) {
    this.wss = new WebSocketServer({ port });
    this.wss.on('connection', (ws) => {
      this.clients.add(ws);
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
    forward('error');
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
