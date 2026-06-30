// Coinbase Exchange public market data. REST /products/<id>/book?level=1 for
// snapshots, WS level2 for streaming. Public only — NO auth, NO keys.
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

const REST = process.env.COINBASE_REST_URL ?? 'https://api.exchange.coinbase.com';
const TAKER_FEE_BPS = 40; // conservative public taker tier.

// Pair -> Coinbase product id. Source of truth is universe.symbolMap('coinbase').
const PRODUCTS: Record<string, string> = {
  'SOL/USDC': 'SOL-USDC',
  'SOL/USDT': 'SOL-USDT',
};

interface ProductBook {
  bids: [string, string, number][]; // [price, size, num-orders]
  asks: [string, string, number][];
}

export class CoinbaseExchange implements Exchange {
  readonly venue: Venue = 'coinbase';
  readonly kind: VenueKind = 'cex';

  async supports(pair: Pair): Promise<boolean> {
    return Boolean(PRODUCTS[pair.key]);
  }

  async listPairs(): Promise<Pair[]> {
    return [];
  }

  async fetchQuote(pair: Pair): Promise<Quote> {
    const id = PRODUCTS[pair.key];
    if (!id) throw new Error(`coinbase: no product for ${pair.key}`);
    const t0 = performance.now();
    const r = await getJson<ProductBook>(`${REST}/products/${id}/book?level=1`, {
      timeoutMs: 1500,
      headers: { 'user-agent': 'quantum-arb-sol/research' },
    });
    const topBid = r.bids[0];
    const topAsk = r.asks[0];
    if (!topBid || !topAsk) throw new Error(`coinbase: empty book for ${pair.key}`);
    const bid = Number(topBid[0]);
    const ask = Number(topAsk[0]);
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
        bids: [{ px: bid, sz: Number(topBid[1]) }],
        asks: [{ px: ask, sz: Number(topAsk[1]) }],
        ts: Date.now(),
      },
      ts: Date.now(),
      latencyMs: performance.now() - t0,
      stale: false,
    };
  }

  subscribe?(_pairs: Pair[], _onQuote: (q: Quote) => void): SubscribeHandle {
    return () => {};
  }
}
