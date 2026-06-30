// Slippage model. Two regimes:
//  1. L2 book present  -> walk the book, exact average fill price.
//  2. No book / proxy  -> parametric impact: k_lin*q + k_sqrt*sqrt(q), in bps.
// Returns the one-way slippage cost in BASIS POINTS relative to top-of-book.
// Jupiter quotes are executable (impact already embedded) and must skip this.

import type { OrderbookL2, Quote, Venue } from '../exchange/types.js';

export interface SlippageParams {
  kLin: number; // linear coeff (bps per unit notional, normalized)
  kSqrt: number; // sqrt coeff (bps per sqrt notional)
  refNotional: number; // normalization notional in quote currency
}

// Per-venue fallback params for the parametric model (no L2 available).
const DEFAULTS: Record<Venue, SlippageParams> = {
  jupiter: { kLin: 0, kSqrt: 0, refNotional: 1 }, // unused: executable
  orca: { kLin: 1.5, kSqrt: 8, refNotional: 10_000 },
  raydium: { kLin: 2.0, kSqrt: 10, refNotional: 10_000 },
  binance: { kLin: 0.5, kSqrt: 3, refNotional: 10_000 },
  coinbase: { kLin: 0.8, kSqrt: 4, refNotional: 10_000 },
};

export type Side = 'buy' | 'sell';

/** One-way slippage in bps for trading `notionalQuote` against this quote. */
export function slippageBps(quote: Quote, side: Side, notionalQuote: number): number {
  if (quote.executable) return 0; // impact already in the price (e.g. Jupiter)
  if (notionalQuote <= 0) return 0;

  if (quote.book && hasDepth(quote.book, side)) {
    return walkBookBps(quote, side, notionalQuote);
  }
  return parametricBps(DEFAULTS[quote.venue], notionalQuote);
}

function parametricBps(p: SlippageParams, notionalQuote: number): number {
  const q = notionalQuote / p.refNotional;
  return p.kLin * q + p.kSqrt * Math.sqrt(q);
}

function hasDepth(book: OrderbookL2, side: Side): boolean {
  return side === 'buy' ? book.asks.length > 0 : book.bids.length > 0;
}

/** Average fill vs top-of-book, in bps, walking real L2 levels. */
function walkBookBps(quote: Quote, side: Side, notionalQuote: number): number {
  const book = quote.book!;
  const levels = side === 'buy' ? book.asks : book.bids;
  const top = side === 'buy' ? quote.ask : quote.bid;

  let remaining = notionalQuote;
  let baseFilled = 0;
  let quoteSpent = 0;

  for (const lvl of levels) {
    const lvlNotional = lvl.px * lvl.sz;
    const take = Math.min(remaining, lvlNotional);
    const baseTaken = take / lvl.px;
    baseFilled += baseTaken;
    quoteSpent += take;
    remaining -= take;
    if (remaining <= 1e-9) break;
  }

  if (baseFilled <= 0) return parametricBps(DEFAULTS[quote.venue], notionalQuote);

  // Partial fill: charge parametric tail on the unfilled notional.
  const avgPx = quoteSpent / baseFilled;
  const bookBps = Math.abs(avgPx - top) / top * 1e4;
  if (remaining > 1e-9) {
    return bookBps + parametricBps(DEFAULTS[quote.venue], remaining);
  }
  return bookBps;
}
