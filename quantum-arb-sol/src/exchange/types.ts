// Single source of truth for the cross-venue contract. dex/* and cex/* implement
// `Exchange`; everything above (models, core) speaks only in these types so the
// detector stays agnostic to where a quote came from.

export type Venue = 'jupiter' | 'orca' | 'raydium' | 'binance' | 'coinbase';
export type VenueKind = 'dex' | 'cex';

export const DEX_VENUES = ['jupiter', 'orca', 'raydium'] as const;
export const CEX_VENUES = ['binance', 'coinbase'] as const;

export type PairKey = `${string}/${string}`;

export interface Pair {
  base: string; // e.g. "SOL"
  quote: string; // e.g. "USDC"
  key: PairKey; // canonical "BASE/QUOTE"
}

export interface OrderbookLevel {
  px: number;
  sz: number; // size in base units
}

export interface OrderbookL2 {
  bids: OrderbookLevel[]; // descending px
  asks: OrderbookLevel[]; // ascending px
  ts: number; // epoch ms of book snapshot
}

export interface Quote {
  venue: Venue;
  kind: VenueKind;
  pair: Pair;
  bid: number; // best bid in quote currency
  ask: number; // best ask in quote currency
  mid: number; // (bid + ask) / 2
  feeBps: number; // taker fee in basis points for this venue/pair
  // True when the venue's price already embeds route/AMM impact for a
  // reference size (Jupiter). The detector must NOT re-apply slippage.ts to it.
  executable: boolean;
  book?: OrderbookL2; // present for L2-capable venues; synthetic for AMMs
  ts: number; // epoch ms the quote refers to
  latencyMs: number; // observed/injected round-trip for this quote
  stale: boolean; // set by normalize() when ts age > QUOTE_STALE_MS
}

export interface SubscribeHandle {
  (): void; // call to unsubscribe
}

export interface Exchange {
  readonly venue: Venue;
  readonly kind: VenueKind;

  /** Whether this venue can quote the given pair (used by the universe filter). */
  supports(pair: Pair): Promise<boolean>;

  /** Pairs this venue advertises, used for universe discovery/diagnostics. */
  listPairs(): Promise<Pair[]>;

  /** One-shot REST snapshot. Must return a fully normalized Quote. */
  fetchQuote(pair: Pair): Promise<Quote>;

  /** Optional streaming. Returns an unsubscribe handle. */
  subscribe?(pairs: Pair[], onQuote: (q: Quote) => void): SubscribeHandle;
}

export function makePair(base: string, quote: string): Pair {
  const b = base.toUpperCase();
  const q = quote.toUpperCase();
  return { base: b, quote: q, key: `${b}/${q}` as PairKey };
}
