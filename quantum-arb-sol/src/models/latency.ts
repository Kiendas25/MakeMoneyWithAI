// Latency model. In live mode we record observed RTT (quote.latencyMs). In sim
// mode we INJECT RTT per venue so the backtester does not reward physically
// impossible zero-latency fills. Three samplers: const | normal | empirical.

import type { Venue } from '../exchange/types.js';

export type LatencySampler =
  | { kind: 'const'; ms: number }
  | { kind: 'normal'; meanMs: number; stdMs: number }
  | { kind: 'empirical'; samplesMs: number[] };

// Rough per-venue RTT priors (ms). DEX = RPC round-trip; CEX = REST/WS RTT.
const DEFAULTS: Record<Venue, LatencySampler> = {
  jupiter: { kind: 'normal', meanMs: 120, stdMs: 40 },
  orca: { kind: 'normal', meanMs: 90, stdMs: 30 },
  raydium: { kind: 'normal', meanMs: 90, stdMs: 30 },
  binance: { kind: 'normal', meanMs: 45, stdMs: 15 },
  coinbase: { kind: 'normal', meanMs: 55, stdMs: 18 },
};

export class LatencyModel {
  constructor(
    private readonly overrides: Partial<Record<Venue, LatencySampler>> = {},
    private readonly rng: () => number = Math.random,
  ) {}

  sampleMs(venue: Venue): number {
    const s = this.overrides[venue] ?? DEFAULTS[venue];
    switch (s.kind) {
      case 'const':
        return Math.max(0, s.ms);
      case 'normal':
        return Math.max(0, s.meanMs + gaussian(this.rng) * s.stdMs);
      case 'empirical': {
        if (s.samplesMs.length === 0) return 0;
        const i = Math.floor(this.rng() * s.samplesMs.length);
        return Math.max(0, s.samplesMs[i] ?? 0);
      }
    }
  }
}

// Box–Muller standard normal from a uniform rng.
function gaussian(rng: () => number): number {
  let u = 0;
  let v = 0;
  while (u === 0) u = rng();
  while (v === 0) v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
