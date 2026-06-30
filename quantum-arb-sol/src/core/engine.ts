// Orchestrator. Async event loop + tick scheduler + parallel fan-out fetchers →
// normalize → detector → risk → paper simulator → bus. Backpressure-aware:
// overlapping ticks are dropped, never queued. The same processTick() pipeline
// is reused by the backtester (fed replayed quotes) so live/replay stay in parity.

import type { ActivePair } from '../models/universe.js';
import type { EngineConfig } from './config.js';
import type { Clock } from './clock.js';
import { WallClock } from './clock.js';
import { Bus } from './bus.js';
import { VenueRegistry, normalize } from '../exchange/index.js';
import type { Quote } from '../exchange/types.js';
import { Universe } from '../models/universe.js';
import { detect } from '../models/arbitrage.js';
import { RiskModel } from '../models/risk.js';
import { PaperTrader } from '../simulator/paper.js';

export interface EngineDeps {
  config: EngineConfig;
  registry: VenueRegistry;
  bus: Bus;
  clock?: Clock;
}

export class Engine {
  readonly bus: Bus;
  private readonly cfg: EngineConfig;
  private readonly registry: VenueRegistry;
  private readonly clock: Clock;
  private readonly universe: Universe;
  private readonly risk: RiskModel;
  private readonly paper = new PaperTrader();

  private active: readonly ActivePair[] = [];
  private timer: NodeJS.Timeout | null = null;
  private running = false;
  private inFlight = false;
  private tickSeq = 0;
  private droppedTicks = 0;

  constructor(deps: EngineDeps) {
    this.cfg = deps.config;
    this.registry = deps.registry;
    this.bus = deps.bus;
    this.clock = deps.clock ?? new WallClock();
    this.universe = new Universe({
      override: this.cfg.universeOverride,
      refreshMs: this.cfg.tickIntervalMs,
    });
    this.risk = new RiskModel(this.cfg.risk);
  }

  /** Resolve universe (present-in-all-venues filter) before the loop starts. */
  async init(): Promise<readonly ActivePair[]> {
    const { active, dropped } = await this.universe.resolve(this.registry.all());
    this.active = active;
    if (dropped.length) {
      for (const d of dropped) {
        this.bus.emit('error', {
          where: 'universe',
          message: `dropped ${d.pair.key}: missing on ${d.missing.join(',')}`,
        });
      }
    }
    return active;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    const loop = () => {
      if (!this.running) return;
      void this.tick();
    };
    this.timer = setInterval(loop, this.cfg.tickIntervalMs);
  }

  async stop(): Promise<void> {
    this.running = false;
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  /** One scheduled tick: fan-out fetch, then run the shared pipeline. */
  private async tick(): Promise<void> {
    if (this.inFlight) {
      this.droppedTicks += 1; // backpressure: drop, don't queue
      return;
    }
    this.inFlight = true;
    try {
      const quotes = await this.fanOutFetch();
      this.processTick(quotes);
    } catch (err) {
      this.bus.emit('error', { where: 'tick', message: String(err) });
    } finally {
      this.inFlight = false;
    }
  }

  /** Parallel fetch across every (pair, venue), tolerant of per-leg failure. */
  private async fanOutFetch(): Promise<Quote[]> {
    const jobs: Promise<Quote | null>[] = [];
    for (const ap of this.active) {
      for (const venue of ap.venues) {
        const ex = this.registry.get(venue);
        jobs.push(
          withTimeout(ex.fetchQuote(ap.pair), this.cfg.fetchTimeoutMs)
            .then((q) => q)
            .catch((e) => {
              this.bus.emit('error', { where: `fetch:${venue}`, message: String(e) });
              return null;
            }),
        );
      }
    }
    const settled = await Promise.all(jobs);
    return settled.filter((q): q is Quote => q !== null);
  }

  /**
   * Shared pipeline: normalize → detect → risk → paper → emit. Pure w.r.t. the
   * supplied quotes + clock; the backtester calls this directly with replayed
   * quotes so it exercises the exact same detector and simulator as live.
   */
  processTick(rawQuotes: Quote[]): void {
    const t0 = performance.now();
    const now = this.clock.now();
    const tick = ++this.tickSeq;

    const quotes: Quote[] = [];
    for (const q of rawQuotes) {
      try {
        quotes.push(normalize(q, now, this.cfg.staleMs));
      } catch (e) {
        this.bus.emit('error', { where: 'normalize', message: String(e) });
      }
    }
    this.bus.emit('quotes', quotes);

    const opps = detect(quotes, this.cfg.detector);
    let fills = 0;
    const ledgerForCtx = this.paper.snapshot();
    const inventory = new Map<string, number>();
    for (const [k, p] of Object.entries(ledgerForCtx.byPair)) {
      inventory.set(k, p.inventoryUsd);
    }

    for (const opp of opps) {
      this.bus.emit('opportunity', opp);
      const verdict = this.risk.evaluate(opp, {
        openPositions: ledgerForCtx.openPositions,
        inventoryUsdByPair: inventory as Map<never, number>,
      });
      if (!verdict.ok) continue;
      const fill = this.paper.execute(opp, verdict.notionalUsd);
      fills += 1;
      this.bus.emit('fill', fill);
    }

    const ledger = this.paper.snapshot();
    this.bus.emit('ledger', ledger);
    this.bus.emit('metric', {
      tick,
      ts: now,
      quotes: quotes.length,
      opportunities: opps.length,
      fills,
      durationMs: performance.now() - t0,
      droppedTicks: this.droppedTicks,
    });
  }

  ledger() {
    return this.paper.snapshot();
  }
}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`timeout ${ms}ms`)), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      },
    );
  });
}
