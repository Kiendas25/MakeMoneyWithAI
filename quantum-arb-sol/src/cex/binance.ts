// Binance public market data. REST /api/v3/ticker/bookTicker for snapshots,
// WS <symbol>@depth for streaming. Public endpoints only — NO auth, NO keys.
// executable: false — slippage.ts walks the L2 book.

import type {
  Exchange,
  Pair,
  Quote,
  SubscribeHandle,
  Venue,
  VenueKind,
} from '../exchange/types.js';
import { getJson } from '../core/http.js';

const REST = process.env.BINANCE_REST_URL ?? 'https://api.binance.com';
const TAKER_FEE_BPS = 10; // 0.10% spot taker.

// Pair -> Binance symbol. Source of truth is universe.symbolMap('binance');
// this stub covers the default universe so the venue works offline-of-laptop.
const SYMBOLS: Record<string, string> = {
  'SOL/USDC': 'SOLUSDC',
  'SOL/USDT': 'SOLUSDT',
};

interface BookTicker {
  symbol: string;
  bidPrice: string;
  bidQty: string;
  askPrice: string;
  askQty: string;
}

export class BinanceExchange implements Exchange {
  readonly venue: Venue = 'binance';
  readonly kind: VenueKind = 'cex';

  async supports(pair: Pair): Promise<boolean> {
    return Boolean(SYMBOLS[pair.key]);
  }

  async listPairs(): Promise<Pair[]> {
    return [];
  }

  async fetchQuote(pair: Pair): Promise<Quote> {
    const sym = SYMBOLS[pair.key];
    if (!sym) throw new Error(`binance: no symbol for ${pair.key}`);
    const t0 = performance.now();
    const r = await getJson<BookTicker>(`${REST}/api/v3/ticker/bookTicker?symbol=${sym}`, {
      timeoutMs: 1500,
    });
    const bid = Number(r.bidPrice);
    const ask = Number(r.askPrice);
    return {
      venue: this.venue,
      kind: this.kind,
      pair,
      bid,
      ask,
      mid: (bid + ask) / 2,
      feeBps: TAKER_FEE_BPS,
      executable: false,
      book: {
        bids: [{ px: bid, sz: Number(r.bidQty) }],
        asks: [{ px: ask, sz: Number(r.askQty) }],
        ts: Date.now(),
      },
      ts: Date.now(),
      latencyMs: performance.now() - t0,
      stale: false,
    };
  }

  // WS streaming stub: real impl opens BINANCE_WS_URL/<sym>@depth and pushes
  // normalized quotes via onQuote. Returns unsubscribe.
  subscribe?(_pairs: Pair[], _onQuote: (q: Quote) => void): SubscribeHandle {
    return () => {};
  }
}
