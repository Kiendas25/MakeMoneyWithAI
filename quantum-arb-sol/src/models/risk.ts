// Risk gates. Stateless given (opportunity, config, current inventory). The
// paper ledger supplies inventory; risk never mutates state. Per-pair limits.

import type { PairKey } from '../exchange/types.js';
import type { Opportunity } from './arbitrage.js';

export interface RiskConfig {
  maxNotionalUsd: number; // cap on a single simulated leg
  minEdgeBps: number; // reject opportunities below this net edge
  inventoryCapUsd: number; // max absolute inventory per pair
  maxConcurrent: number; // max simultaneous open paper positions
}

export interface RiskContext {
  openPositions: number;
  inventoryUsdByPair: Map<PairKey, number>;
}

export type RiskVerdict =
  | { ok: true; notionalUsd: number }
  | { ok: false; reason: string };

export class RiskModel {
  constructor(private readonly cfg: RiskConfig) {}

  /** Decide whether an opportunity may be (paper-)executed, and at what size. */
  evaluate(opp: Opportunity, ctx: RiskContext): RiskVerdict {
    if (opp.netBps < this.cfg.minEdgeBps) {
      return { ok: false, reason: `edge ${opp.netBps.toFixed(2)}bps < min ${this.cfg.minEdgeBps}` };
    }
    if (ctx.openPositions >= this.cfg.maxConcurrent) {
      return { ok: false, reason: `maxConcurrent ${this.cfg.maxConcurrent} reached` };
    }

    const inv = ctx.inventoryUsdByPair.get(opp.pair.key) ?? 0;
    const headroom = this.cfg.inventoryCapUsd - Math.abs(inv);
    if (headroom <= 0) {
      return { ok: false, reason: `inventory cap reached for ${opp.pair.key}` };
    }

    const notionalUsd = Math.min(this.cfg.maxNotionalUsd, headroom, opp.maxNotionalUsd);
    if (notionalUsd <= 0) {
      return { ok: false, reason: 'no sizeable notional after caps' };
    }
    return { ok: true, notionalUsd };
  }
}
