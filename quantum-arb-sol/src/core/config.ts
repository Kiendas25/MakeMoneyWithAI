// Central config loaded from process.env with safe defaults. No secrets — this
// system reads only public market data and never signs.

import type { Venue } from '../exchange/types.js';
import type { RiskConfig } from '../models/risk.js';
import type { DetectorConfig } from '../models/arbitrage.js';

export interface EngineConfig {
  wsPort: number;
  tickIntervalMs: number;
  staleMs: number;
  fetchTimeoutMs: number;
  enableObjectPool: boolean;
  activeVenues: Venue[];
  universeOverride: string;
  risk: RiskConfig;
  detector: DetectorConfig;
}

function num(key: string, def: number): number {
  const v = process.env[key];
  if (v == null || v === '') return def;
  const n = Number(v);
  return Number.isFinite(n) ? n : def;
}

function str(key: string, def: string): string {
  const v = process.env[key];
  return v == null || v === '' ? def : v;
}

function bool(key: string, def: boolean): boolean {
  const v = process.env[key];
  if (v == null || v === '') return def;
  return v === 'true' || v === '1';
}

const ALL_VENUES: Venue[] = ['jupiter', 'orca', 'raydium', 'binance', 'coinbase'];

function parseVenues(raw: string): Venue[] {
  const set = new Set(ALL_VENUES);
  const out = raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean) as Venue[];
  for (const v of out) {
    if (!set.has(v)) throw new Error(`Unknown venue in ACTIVE_VENUES: ${v}`);
  }
  return out.length ? out : ALL_VENUES;
}

export function loadConfig(): EngineConfig {
  const probeNotionalUsd = num('RISK_MAX_NOTIONAL_USD', 10_000);
  const minEdgeBps = num('RISK_MIN_EDGE_BPS', 5);
  return {
    wsPort: num('ENGINE_WS_PORT', 8787),
    tickIntervalMs: num('TICK_INTERVAL_MS', 200),
    staleMs: num('QUOTE_STALE_MS', 2000),
    fetchTimeoutMs: num('FETCH_TIMEOUT_MS', 1500),
    enableObjectPool: bool('ENABLE_OBJECT_POOL', true),
    activeVenues: parseVenues(str('ACTIVE_VENUES', ALL_VENUES.join(','))),
    universeOverride: str('UNIVERSE_OVERRIDE', ''),
    risk: {
      maxNotionalUsd: probeNotionalUsd,
      minEdgeBps,
      inventoryCapUsd: num('RISK_INVENTORY_CAP_USD', 50_000),
      maxConcurrent: num('RISK_MAX_CONCURRENT', 4),
    },
    detector: {
      probeNotionalUsd,
      minEdgeBps,
      // DEX legs pay gas; CEX legs don't. Bps-of-notional approximation.
      gasBpsByVenue: { jupiter: 1, orca: 1, raydium: 1 },
    },
  };
}
