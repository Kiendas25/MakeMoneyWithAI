// React hook: subscribe to the engine's read-only WS stream and expose the
// latest derived state. Auto-reconnects. Pure consumer — never sends commands.

import { useCallback, useEffect, useRef, useState } from 'react';
import type { Quote } from '../exchange/types.js';
import type { Opportunity } from '../models/arbitrage.js';
import type { LedgerSnapshot } from '../simulator/paper.js';
import type { TickMetric, SizingState } from '../core/bus.js';
import type { WsMessage } from '../core/wsserver.js';

export interface EngineState {
  connected: boolean;
  quotesByPair: Record<string, Quote[]>;
  opportunities: Opportunity[];
  ledger: LedgerSnapshot | null;
  lastMetric: TickMetric | null;
  notionalUsd: number;
}

export interface EngineSocket extends EngineState {
  setNotional: (usd: number) => void; // paper sizing command
}

export function useEngineSocket(url: string): EngineSocket {
  const [state, setState] = useState<EngineState>({
    connected: false,
    quotesByPair: {},
    opportunities: [],
    ledger: null,
    lastMetric: null,
    notionalUsd: 0,
  });
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let closed = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => setState((s) => ({ ...s, connected: true }));
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (!closed) retry = setTimeout(connect, 1000);
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data as string) as WsMessage;
        setState((s) => reduce(s, msg));
      };
    };
    connect();

    return () => {
      closed = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [url]);

  const setNotional = useCallback((usd: number) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === ws.OPEN) {
      ws.send(JSON.stringify({ type: 'set_sizing', payload: { notionalUsd: usd } }));
    }
  }, []);

  return { ...state, setNotional };
}

function reduce(s: EngineState, msg: WsMessage): EngineState {
  switch (msg.type) {
    case 'quotes': {
      const quotes = msg.payload as Quote[];
      const byPair: Record<string, Quote[]> = {};
      for (const q of quotes) (byPair[q.pair.key] ??= []).push(q);
      return { ...s, quotesByPair: byPair };
    }
    case 'opportunity': {
      const opp = msg.payload as Opportunity;
      return { ...s, opportunities: [opp, ...s.opportunities].slice(0, 50) };
    }
    case 'ledger':
      return { ...s, ledger: msg.payload as LedgerSnapshot };
    case 'metric':
      return { ...s, lastMetric: msg.payload as TickMetric };
    case 'sizing':
      return { ...s, notionalUsd: (msg.payload as SizingState).notionalUsd };
    default:
      return s;
  }
}
