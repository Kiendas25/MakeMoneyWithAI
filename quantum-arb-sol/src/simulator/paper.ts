// Paper-trade simulator — the ONLY terminal of "execution" in this codebase.
// It NEVER signs or sends a transaction. There is no keypair, no RPC sendTx, no
// @solana/web3.js signing import anywhere downstream of here. A guard test
// (test/no-signer.test.ts) fails the build if any signing symbol appears.

import type { PairKey } from '../exchange/types.js';
import type { Opportunity } from '../models/arbitrage.js';

export interface Fill {
  ts: number;
  pair: PairKey;
  buyVenue: string;
  sellVenue: string;
  notionalUsd: number;
  filledNotionalUsd: number; // < notional on partial fill
  realizedPnlUsd: number; // net of modeled fees/slippage/gas
  netBps: number;
}

export interface Position {
  inventoryUsd: number; // signed net inventory for the pair
  realizedPnlUsd: number;
  fills: number;
}

export interface LedgerSnapshot {
  realizedPnlUsd: number;
  fills: number;
  openPositions: number;
  byPair: Record<string, Position>;
}

export class PaperTrader {
  private readonly positions = new Map<PairKey, Position>();
  private totalRealized = 0;
  private totalFills = 0;

  /**
   * Simulate executing an opportunity at a risk-approved notional. The fill
   * model converts the detector's net edge (already net of fees/slippage/gas)
   * into PnL on the FILLED notional. Partial fills shrink notional when the
   * probe exceeds modeled top-of-book depth (passed via fillRatio, default 1).
   */
  execute(opp: Opportunity, notionalUsd: number, fillRatio = 1): Fill {
    const filled = notionalUsd * clamp01(fillRatio);
    const realizedPnlUsd = (filled * opp.netBps) / 1e4;

    const pos = this.positions.get(opp.pair.key) ?? {
      inventoryUsd: 0,
      realizedPnlUsd: 0,
      fills: 0,
    };
    // Arb round-trip is delta-neutral by construction; inventory tracks residual
    // imbalance from partials. Here the leg pair nets to ~0 on full fill.
    pos.inventoryUsd += filled * (1 - clamp01(fillRatio));
    pos.realizedPnlUsd += realizedPnlUsd;
    pos.fills += 1;
    this.positions.set(opp.pair.key, pos);

    this.totalRealized += realizedPnlUsd;
    this.totalFills += 1;

    return {
      ts: opp.ts,
      pair: opp.pair.key,
      buyVenue: opp.buyVenue,
      sellVenue: opp.sellVenue,
      notionalUsd,
      filledNotionalUsd: filled,
      realizedPnlUsd,
      netBps: opp.netBps,
    };
  }

  snapshot(): LedgerSnapshot {
    const byPair: Record<string, Position> = {};
    let open = 0;
    for (const [k, p] of this.positions) {
      byPair[k] = { ...p };
      if (Math.abs(p.inventoryUsd) > 1e-6) open += 1;
    }
    return {
      realizedPnlUsd: this.totalRealized,
      fills: this.totalFills,
      openPositions: open,
      byPair,
    };
  }
}

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x;
}
