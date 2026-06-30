// Universe management. Static top-10 Solana pairs (by liquidity/volume) with a
// .env override, then the hard "present in ALL active venues" filter. Symbol
// divergence across venues (Coinbase SOL-USDC, Binance SOLUSDC, DEX mints) is
// the #1 failure point for the intersection filter, so the canonical->venue
// symbol map lives here and is the single source of truth.

import type { Exchange, Pair, Venue } from '../exchange/types.js';
import { makePair } from '../exchange/types.js';

export interface ActivePair {
  pair: Pair;
  venues: Venue[]; // venues that quote this pair (== all active, post-filter)
  refreshMs: number; // suggested per-pair poll cadence
}

// Static default universe: top-10 Solana pairs by liquidity/volume. Kept
// hardcoded for reproducible backtests; override via UNIVERSE_OVERRIDE.
const DEFAULT_UNIVERSE: ReadonlyArray<readonly [string, string]> = [
  ['SOL', 'USDC'],
  ['SOL', 'USDT'],
  ['JUP', 'USDC'],
  ['JTO', 'USDC'],
  ['BONK', 'USDC'],
  ['WIF', 'USDC'],
  ['PYTH', 'USDC'],
  ['RAY', 'USDC'],
  ['ORCA', 'USDC'],
  ['MSOL', 'USDC'],
];

export interface UniverseConfig {
  override?: string; // "BASE/QUOTE,BASE/QUOTE,..." — empty = default
  refreshMs?: number;
}

function seedPairs(cfg: UniverseConfig): Pair[] {
  const raw = (cfg.override ?? '').trim();
  if (raw) {
    return raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => {
        const [b, q] = s.split('/');
        if (!b || !q) throw new Error(`Bad UNIVERSE_OVERRIDE entry: "${s}"`);
        return makePair(b, q);
      });
  }
  return DEFAULT_UNIVERSE.map(([b, q]) => makePair(b, q));
}

export class Universe {
  private active: ActivePair[] = [];

  constructor(private readonly cfg: UniverseConfig = {}) {}

  /**
   * Resolve the active universe by intersecting the seed pairs with venue
   * support. A pair survives only if EVERY active venue supports it. Dropped
   * pairs are returned for diagnostics so the operator sees why coverage shrank.
   */
  async resolve(venues: Exchange[]): Promise<{ active: ActivePair[]; dropped: DropReason[] }> {
    const seed = seedPairs(this.cfg);
    const refreshMs = this.cfg.refreshMs ?? 200;
    const active: ActivePair[] = [];
    const dropped: DropReason[] = [];

    for (const pair of seed) {
      const checks = await Promise.all(
        venues.map(async (v) => ({ venue: v.venue, ok: await safeSupports(v, pair) })),
      );
      const missing = checks.filter((c) => !c.ok).map((c) => c.venue);
      if (missing.length === 0) {
        active.push({ pair, venues: venues.map((v) => v.venue), refreshMs });
      } else {
        dropped.push({ pair, missing });
      }
    }
    this.active = active;
    return { active, dropped };
  }

  /** Immutable snapshot for this session. */
  activePairs(): readonly ActivePair[] {
    return this.active;
  }
}

export interface DropReason {
  pair: Pair;
  missing: Venue[];
}

async function safeSupports(v: Exchange, pair: Pair): Promise<boolean> {
  try {
    return await v.supports(pair);
  } catch {
    return false;
  }
}
