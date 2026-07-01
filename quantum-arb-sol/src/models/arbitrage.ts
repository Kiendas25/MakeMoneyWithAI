// Cross-venue arbitrage detector. PURE function: detect(quotes, cfg) with zero
// I/O and zero retained state, so live and backtest produce identical output for
// identical input (sim/replay parity is a test invariant). Multi-pair: callers
// pass a tick's worth of quotes; we group by pair internally.

import type { Pair, PairKey, Quote, Venue } from '../exchange/types.js';
import { slippageBps } from './slippage.js';

export interface DetectorConfig {
  probeNotionalUsd: number; // size used to price slippage for the edge
  gasBpsByVenue: Partial<Record<Venue, number>>; // DEX gas as bps of notional
  minEdgeBps: number; // pre-filter; risk re-checks downstream
}

export interface Opportunity {
  pair: Pair;
  buyVenue: Venue;
  sellVenue: Venue;
  buyPx: number; // ask we buy at
  sellPx: number; // bid we sell into
  grossBps: number; // raw cross-venue edge
  feeBps: number; // buy.fee + sell.fee
  slipBps: number; // buy slip + sell slip
  gasBps: number; // buy gas + sell gas (DEX legs)
  netBps: number; // grossBps - fee - slip - gas
  maxNotionalUsd: number; // probe notional (risk may shrink)
  ts: number; // max(buy.ts, sell.ts)
}

/**
 * Detect best directional arbitrage per pair across all venue combinations.
 * Returns one Opportunity per pair (the best net edge), filtered by minEdgeBps.
 */
export function detect(quotes: Quote[], cfg: DetectorConfig): Opportunity[] {
  const byPair = groupByPair(quotes);
  const out: Opportunity[] = [];

  for (const group of byPair.values()) {
    const fresh = group.filter((q) => !q.stale);
    if (fresh.length < 2) continue;

    let best: Opportunity | null = null;
    // Evaluate every ordered (buy, sell) venue pair: buy low ask, sell high bid.
    for (const buy of fresh) {
      for (const sell of fresh) {
        if (buy.venue === sell.venue) continue;
        const opp = evaluate(buy, sell, cfg);
        if (opp.netBps >= cfg.minEdgeBps && (!best || opp.netBps > best.netBps)) {
          best = opp;
        }
      }
    }
    if (best) out.push(best);
  }

  // Deterministic ordering for sim/replay parity.
  out.sort((a, b) => (a.pair.key < b.pair.key ? -1 : a.pair.key > b.pair.key ? 1 : 0));
  return out;
}

function evaluate(buy: Quote, sell: Quote, cfg: DetectorConfig): Opportunity {
  const grossBps = ((sell.bid - buy.ask) / buy.ask) * 1e4;
  const feeBps = buy.feeBps + sell.feeBps;
  const slipBps =
    slippageBps(buy, 'buy', cfg.probeNotionalUsd) +
    slippageBps(sell, 'sell', cfg.probeNotionalUsd);
  const gasBps = (cfg.gasBpsByVenue[buy.venue] ?? 0) + (cfg.gasBpsByVenue[sell.venue] ?? 0);
  const netBps = grossBps - feeBps - slipBps - gasBps;

  return {
    pair: buy.pair,
    buyVenue: buy.venue,
    sellVenue: sell.venue,
    buyPx: buy.ask,
    sellPx: sell.bid,
    grossBps,
    feeBps,
    slipBps,
    gasBps,
    netBps,
    maxNotionalUsd: cfg.probeNotionalUsd,
    ts: Math.max(buy.ts, sell.ts),
  };
}

function groupByPair(quotes: Quote[]): Map<PairKey, Quote[]> {
  const m = new Map<PairKey, Quote[]>();
  for (const q of quotes) {
    const arr = m.get(q.pair.key);
    if (arr) arr.push(q);
    else m.set(q.pair.key, [q]);
  }
  return m;
}
