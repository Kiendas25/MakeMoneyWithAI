// Typed internal event bus. UI, CLI, and backtester only ever listen here, so
// the engine is fully decoupled from any consumer/transport.

import { EventEmitter } from 'node:events';
import type { Quote } from '../exchange/types.js';
import type { Opportunity } from '../models/arbitrage.js';
import type { Fill, LedgerSnapshot } from '../simulator/paper.js';

export interface TickMetric {
  tick: number;
  ts: number;
  quotes: number;
  opportunities: number;
  fills: number;
  durationMs: number;
  droppedTicks: number;
}

export interface SizingState {
  notionalUsd: number; // global paper notional applied per opportunity
}

export interface BusEvents {
  quotes: [Quote[]];
  opportunity: [Opportunity];
  fill: [Fill];
  metric: [TickMetric];
  ledger: [LedgerSnapshot];
  sizing: [SizingState];
  error: [{ where: string; message: string }];
}

export class Bus {
  private readonly ee = new EventEmitter();

  constructor() {
    this.ee.setMaxListeners(64);
  }

  emit<K extends keyof BusEvents>(event: K, ...args: BusEvents[K]): void {
    this.ee.emit(event, ...args);
  }

  on<K extends keyof BusEvents>(event: K, fn: (...args: BusEvents[K]) => void): () => void {
    this.ee.on(event, fn as (...a: unknown[]) => void);
    return () => this.ee.off(event, fn as (...a: unknown[]) => void);
  }
}
