// Historical replay harness. Reads NDJSON snapshots (one tick per line), drives
// the SAME Engine.processTick pipeline under a VirtualClock, and aggregates
// metrics. Because it reuses the live detector + simulator, backtest results are
// the parity reference for live behaviour.

import { createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';
import type { Quote } from '../exchange/types.js';
import type { Bus, TickMetric } from '../core/bus.js';
import type { Fill } from '../simulator/paper.js';
import { Engine } from '../core/engine.js';
import { VirtualClock } from '../core/clock.js';
import { VenueRegistry } from '../exchange/index.js';
import { Bus as BusClass } from '../core/bus.js';
import type { EngineConfig } from '../core/config.js';

export interface TickSnapshot {
  ts: number;
  quotes: Quote[];
}

export interface BacktestMetrics {
  ticks: number;
  quotes: number;
  opportunities: number;
  fills: number;
  realizedPnlUsd: number;
  hitRate: number; // fills / opportunities
  avgNetBps: number; // mean netBps over fills
  sharpe: number; // per-fill PnL Sharpe (unannualized)
  maxDrawdownUsd: number;
  opportunitiesPerSec: number;
}

export class Backtester {
  private readonly clock: VirtualClock;
  private readonly engine: Engine;
  private readonly bus: Bus;

  // accumulators
  private ticks = 0;
  private quotes = 0;
  private opportunities = 0;
  private readonly fillPnls: number[] = [];
  private readonly fillNetBps: number[] = [];
  private firstTs = 0;
  private lastTs = 0;

  constructor(config: EngineConfig) {
    this.bus = new BusClass();
    this.clock = new VirtualClock(0);
    const registry = new VenueRegistry({
      activeVenues: config.activeVenues,
      staleMs: config.staleMs,
    });
    this.engine = new Engine({ config, registry, bus: this.bus, clock: this.clock });

    this.bus.on('metric', (m: TickMetric) => {
      this.ticks += 1;
      this.quotes += m.quotes;
      this.opportunities += m.opportunities;
    });
    this.bus.on('fill', (f: Fill) => {
      this.fillPnls.push(f.realizedPnlUsd);
      this.fillNetBps.push(f.netBps);
    });
  }

  /** Replay every snapshot line in file order under the virtual clock. */
  async run(file: string): Promise<BacktestMetrics> {
    const rl = createInterface({ input: createReadStream(file), crlfDelay: Infinity });
    for await (const line of rl) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const snap = JSON.parse(trimmed) as TickSnapshot;
      if (!this.firstTs) this.firstTs = snap.ts;
      this.lastTs = snap.ts;
      this.clock.set(snap.ts);
      this.engine.processTick(snap.quotes);
    }
    return this.metrics();
  }

  private metrics(): BacktestMetrics {
    const fills = this.fillPnls.length;
    const realized = this.fillPnls.reduce((a, b) => a + b, 0);
    const avgNetBps = fills ? this.fillNetBps.reduce((a, b) => a + b, 0) / fills : 0;
    const spanSec = Math.max(1e-3, (this.lastTs - this.firstTs) / 1000);

    return {
      ticks: this.ticks,
      quotes: this.quotes,
      opportunities: this.opportunities,
      fills,
      realizedPnlUsd: realized,
      hitRate: this.opportunities ? fills / this.opportunities : 0,
      avgNetBps,
      sharpe: sharpe(this.fillPnls),
      maxDrawdownUsd: maxDrawdown(this.fillPnls),
      opportunitiesPerSec: this.opportunities / spanSec,
    };
  }
}

function sharpe(pnls: number[]): number {
  if (pnls.length < 2) return 0;
  const mean = pnls.reduce((a, b) => a + b, 0) / pnls.length;
  const variance = pnls.reduce((a, b) => a + (b - mean) ** 2, 0) / (pnls.length - 1);
  const sd = Math.sqrt(variance);
  return sd === 0 ? 0 : mean / sd;
}

function maxDrawdown(pnls: number[]): number {
  let equity = 0;
  let peak = 0;
  let maxDd = 0;
  for (const p of pnls) {
    equity += p;
    if (equity > peak) peak = equity;
    const dd = peak - equity;
    if (dd > maxDd) maxDd = dd;
  }
  return maxDd;
}
