// Venue registry + quote normalization. The registry is the only place that
// knows the concrete venue implementations; core/models depend on this module,
// never on dex/* or cex/* directly.

import type { Exchange, Pair, Quote, Venue } from './types.js';
import { JupiterExchange } from '../dex/jupiter.js';
import { OrcaExchange } from '../dex/orca.js';
import { RaydiumExchange } from '../dex/raydium.js';
import { BinanceExchange } from '../cex/binance.js';
import { CoinbaseExchange } from '../cex/coinbase.js';

export interface RegistryConfig {
  activeVenues: Venue[];
  staleMs: number;
}

const FACTORIES: Record<Venue, () => Exchange> = {
  jupiter: () => new JupiterExchange(),
  orca: () => new OrcaExchange(),
  raydium: () => new RaydiumExchange(),
  binance: () => new BinanceExchange(),
  coinbase: () => new CoinbaseExchange(),
};

export class VenueRegistry {
  private readonly venues = new Map<Venue, Exchange>();

  constructor(private readonly cfg: RegistryConfig) {
    for (const v of cfg.activeVenues) {
      const make = FACTORIES[v];
      if (!make) throw new Error(`Unknown venue in ACTIVE_VENUES: ${v}`);
      this.venues.set(v, make());
    }
  }

  get(venue: Venue): Exchange {
    const ex = this.venues.get(venue);
    if (!ex) throw new Error(`Venue not active: ${venue}`);
    return ex;
  }

  all(): Exchange[] {
    return [...this.venues.values()];
  }

  activeVenues(): Venue[] {
    return [...this.venues.keys()];
  }
}

/**
 * Enforce the invariants every downstream module relies on. Returns a defensive
 * copy with `mid`, `stale`, and ordering corrected. Throws only on structurally
 * impossible input (NaN/negative prices) — staleness is a flag, not an error.
 */
export function normalize(raw: Quote, now: number, staleMs: number): Quote {
  if (!Number.isFinite(raw.bid) || !Number.isFinite(raw.ask)) {
    throw new Error(`[${raw.venue}] non-finite price for ${raw.pair.key}`);
  }
  if (raw.bid <= 0 || raw.ask <= 0) {
    throw new Error(`[${raw.venue}] non-positive price for ${raw.pair.key}`);
  }
  // Tolerate crossed snapshots from racing feeds by swapping rather than throwing.
  let bid = raw.bid;
  let ask = raw.ask;
  if (bid > ask) [bid, ask] = [ask, bid];

  const ts = Number.isFinite(raw.ts) ? raw.ts : now;
  return {
    ...raw,
    bid,
    ask,
    mid: (bid + ask) / 2,
    ts,
    stale: now - ts > staleMs,
  };
}

export * from './types.js';
