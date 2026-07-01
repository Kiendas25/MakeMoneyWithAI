import { describe, it, expect } from 'vitest';
import { slippageBps } from '../src/models/slippage.js';
import { makePair, type Quote } from '../src/exchange/types.js';

function quote(partial: Partial<Quote>): Quote {
  return {
    venue: 'binance',
    kind: 'cex',
    pair: makePair('SOL', 'USDC'),
    bid: 99.99,
    ask: 100.01,
    mid: 100,
    feeBps: 10,
    executable: false,
    ts: 0,
    latencyMs: 0,
    stale: false,
    ...partial,
  };
}

describe('slippageBps', () => {
  it('returns 0 for executable quotes (impact already embedded)', () => {
    expect(slippageBps(quote({ executable: true }), 'buy', 10_000)).toBe(0);
  });

  it('returns 0 for non-positive notional', () => {
    expect(slippageBps(quote({}), 'buy', 0)).toBe(0);
  });

  it('walks an L2 book and charges more for deeper fills', () => {
    const q = quote({
      book: {
        bids: [{ px: 99.99, sz: 50 }],
        asks: [
          { px: 100.01, sz: 50 },
          { px: 100.05, sz: 1000 },
        ],
        ts: 0,
      },
    });
    const small = slippageBps(q, 'buy', 1_000);
    const large = slippageBps(q, 'buy', 50_000);
    expect(large).toBeGreaterThan(small);
  });

  it('grows monotonically with size under the parametric model', () => {
    const q = quote({ venue: 'orca' }); // no book → parametric model
    expect(slippageBps(q, 'buy', 50_000)).toBeGreaterThan(slippageBps(q, 'buy', 5_000));
  });
});
