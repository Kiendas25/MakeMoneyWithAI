// Synthetic throughput benchmark — no network. Generates the default universe's
// worth of quotes per tick and pushes them through the real detector so we can
// measure checks/sec and tick latency before deciding worker_threads/Rust ports.

import type { EngineConfig } from '../core/config.js';
import type { Quote } from '../exchange/types.js';
import { makePair } from '../exchange/types.js';
import { detect } from '../models/arbitrage.js';

export interface BenchResult {
  ticks: number;
  totalChecks: number;
  checksPerSec: number;
  p50TickUs: number;
  p99TickUs: number;
  opportunities: number;
}

const VENUES = ['jupiter', 'orca', 'raydium', 'binance', 'coinbase'] as const;
const PAIRS = ['SOL/USDC', 'SOL/USDT', 'JUP/USDC', 'JTO/USDC', 'BONK/USDC'];

function synthQuotes(now: number, rng: () => number): Quote[] {
  const out: Quote[] = [];
  for (const key of PAIRS) {
    const [base, quote] = key.split('/') as [string, string];
    const pair = makePair(base, quote);
    const ref = 100 * (1 + rng() * 0.001);
    for (const venue of VENUES) {
      const drift = (rng() - 0.5) * 0.004; // ±20bps dispersion across venues
      const mid = ref * (1 + drift);
      const half = mid * 0.0002;
      out.push({
        venue,
        kind: venue === 'binance' || venue === 'coinbase' ? 'cex' : 'dex',
        pair,
        bid: mid - half,
        ask: mid + half,
        mid,
        feeBps: 10,
        executable: venue === 'jupiter',
        ts: now,
        latencyMs: 0,
        stale: false,
      });
    }
  }
  return out;
}

export function runBench(cfg: EngineConfig, ticks: number): BenchResult {
  let seed = 0x9e3779b9;
  const rng = () => {
    // xorshift32 — deterministic, fast.
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    return ((seed >>> 0) % 1_000_000) / 1_000_000;
  };

  const durs: number[] = [];
  let totalChecks = 0;
  let opportunities = 0;
  const now = Date.now();

  for (let i = 0; i < ticks; i++) {
    const quotes = synthQuotes(now, rng);
    const t0 = performance.now();
    const opps = detect(quotes, cfg.detector);
    durs.push((performance.now() - t0) * 1000); // microseconds
    opportunities += opps.length;
    // checks = ordered venue pairs per pair = P*(V*(V-1))
    totalChecks += PAIRS.length * VENUES.length * (VENUES.length - 1);
  }

  durs.sort((a, b) => a - b);
  const totalMs = durs.reduce((a, b) => a + b, 0) / 1000;
  return {
    ticks,
    totalChecks,
    checksPerSec: Math.round(totalChecks / (totalMs / 1000)),
    p50TickUs: Math.round(durs[Math.floor(durs.length * 0.5)] ?? 0),
    p99TickUs: Math.round(durs[Math.floor(durs.length * 0.99)] ?? 0),
    opportunities,
  };
}
