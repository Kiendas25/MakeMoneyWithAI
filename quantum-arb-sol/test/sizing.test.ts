import { describe, it, expect } from 'vitest';
import { Engine } from '../src/core/engine.js';
import { Bus } from '../src/core/bus.js';
import { VenueRegistry } from '../src/exchange/index.js';
import { loadConfig } from '../src/core/config.js';
import { makePair, type Quote } from '../src/exchange/types.js';
import type { Fill } from '../src/simulator/paper.js';

function q(venue: Quote['venue'], bid: number, ask: number, executable = false): Quote {
  return {
    venue,
    kind: venue === 'binance' || venue === 'coinbase' ? 'cex' : 'dex',
    pair: makePair('SOL', 'USDC'),
    bid,
    ask,
    mid: (bid + ask) / 2,
    feeBps: 0,
    executable,
    ts: Date.now(),
    latencyMs: 0,
    stale: false,
  };
}

function engineWith(): { engine: Engine; bus: Bus } {
  const cfg = loadConfig();
  const bus = new Bus();
  const registry = new VenueRegistry({ activeVenues: cfg.activeVenues, staleMs: cfg.staleMs });
  return { engine: new Engine({ config: cfg, registry, bus }), bus };
}

describe('global paper sizing', () => {
  it('scales fill notional with setNotional', () => {
    const { engine, bus } = engineWith();
    const fills: Fill[] = [];
    bus.on('fill', (f) => fills.push(f));

    // wide, clean edge so it always clears the risk threshold
    const quotes = [q('jupiter', 100, 100, true), q('binance', 102, 102.01)];

    engine.setNotional(1_000);
    engine.processTick(quotes);
    engine.setNotional(5_000);
    engine.processTick(quotes);

    expect(fills.length).toBe(2);
    expect(fills[0]!.notionalUsd).toBe(1_000);
    expect(fills[1]!.notionalUsd).toBe(5_000);
    // Larger notional → more PnL in absolute terms, but sub-linearly because
    // slippage eats into the edge as size grows (net bps shrinks with size).
    expect(fills[1]!.realizedPnlUsd).toBeGreaterThan(fills[0]!.realizedPnlUsd);
    expect(fills[1]!.realizedPnlUsd).toBeLessThan(fills[0]!.realizedPnlUsd * 5);
    expect(fills[1]!.netBps).toBeLessThan(fills[0]!.netBps);
  });

  it('emits a sizing event when notional changes', () => {
    const { engine, bus } = engineWith();
    const seen: number[] = [];
    bus.on('sizing', (s) => seen.push(s.notionalUsd));
    engine.setNotional(2_500);
    expect(seen).toContain(2_500);
  });

  it('ignores non-positive notional', () => {
    const { engine } = engineWith();
    const before = engine.getNotional();
    engine.setNotional(-1);
    engine.setNotional(0);
    expect(engine.getNotional()).toBe(before);
  });
});
