import { describe, it, expect } from 'vitest';
import { detect, type DetectorConfig } from '../src/models/arbitrage.js';
import { makePair, type Quote } from '../src/exchange/types.js';

const cfg: DetectorConfig = {
  probeNotionalUsd: 10_000,
  minEdgeBps: 5,
  gasBpsByVenue: { jupiter: 1, orca: 1, raydium: 1 },
};

function q(venue: Quote['venue'], bid: number, ask: number, extra: Partial<Quote> = {}): Quote {
  const pair = makePair('SOL', 'USDC');
  return {
    venue,
    kind: venue === 'binance' || venue === 'coinbase' ? 'cex' : 'dex',
    pair,
    bid,
    ask,
    mid: (bid + ask) / 2,
    feeBps: 10,
    executable: venue === 'jupiter',
    ts: 1000,
    latencyMs: 0,
    stale: false,
    ...extra,
  };
}

describe('detect', () => {
  it('finds a profitable cross-venue opportunity', () => {
    const quotes = [q('binance', 100.0, 100.02), q('coinbase', 100.5, 100.52)];
    const opps = detect(quotes, cfg);
    expect(opps).toHaveLength(1);
    expect(opps[0]!.buyVenue).toBe('binance');
    expect(opps[0]!.sellVenue).toBe('coinbase');
    expect(opps[0]!.netBps).toBeGreaterThan(cfg.minEdgeBps);
  });

  it('rejects sub-threshold edges', () => {
    const quotes = [q('binance', 100.0, 100.02), q('coinbase', 100.03, 100.05)];
    expect(detect(quotes, cfg)).toHaveLength(0);
  });

  it('ignores stale quotes', () => {
    const quotes = [q('binance', 100.0, 100.02), q('coinbase', 100.5, 100.52, { stale: true })];
    expect(detect(quotes, cfg)).toHaveLength(0);
  });

  it('is deterministic — identical input yields identical output (sim/replay parity)', () => {
    const quotes = [
      q('binance', 100.0, 100.02),
      q('coinbase', 100.5, 100.52),
      q('jupiter', 100.3, 100.3),
    ];
    const a = detect(quotes, cfg);
    const b = detect(quotes, cfg);
    expect(a).toEqual(b);
  });

  it('does not re-apply slippage to executable (Jupiter) quotes', () => {
    // Buy on Jupiter (executable → 0 slip on that leg), sell on Binance. The
    // opportunity's slipBps must come only from the Binance leg; the Jupiter
    // leg contributes none. Wide edge + zero fees so the opp clears threshold.
    const quotes = [
      q('jupiter', 100.0, 100.0, { feeBps: 0 }),
      q('binance', 102.0, 102.01, { feeBps: 0 }),
    ];
    const opps = detect(quotes, cfg);
    expect(opps).toHaveLength(1);
    expect(opps[0]!.buyVenue).toBe('jupiter');
    // Binance has no book here → parametric slip for one leg only (< two legs).
    const oneLegSlip = opps[0]!.slipBps;
    expect(oneLegSlip).toBeGreaterThan(0);
    expect(oneLegSlip).toBeLessThan(100);
  });
});
