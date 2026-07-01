// Orca Whirlpools. AMM concentrated-liquidity pools have no native L2 book; we
// derive a price from pool state and expose a SYNTHETIC OrderbookL2 built from
// tick-array depth so slippage.ts can walk it. executable: false — the detector
// applies slippage.ts to this venue.
//
// The pool-address lookup and tick-array decoding are stubbed until the laptop's
// Whirlpool client + on-chain reads are attached. The Exchange shape is final.

import type {
  Exchange,
  OrderbookL2,
  Pair,
  Quote,
  SubscribeHandle,
  Venue,
  VenueKind,
} from '../exchange/types.js';

const TAKER_FEE_BPS = 30; // typical Whirlpool fee tier; per-pool override later.

// Placeholder: pair -> whirlpool address. Filled from universe symbol map online.
const STUB_POOLS: Record<string, string> = {
  'SOL/USDC': '__WHIRLPOOL_SOL_USDC__',
};

export class OrcaExchange implements Exchange {
  readonly venue: Venue = 'orca';
  readonly kind: VenueKind = 'dex';

  async supports(pair: Pair): Promise<boolean> {
    return Boolean(STUB_POOLS[pair.key]);
  }

  async listPairs(): Promise<Pair[]> {
    return [];
  }

  async fetchQuote(pair: Pair): Promise<Quote> {
    const pool = STUB_POOLS[pair.key];
    if (!pool) throw new Error(`orca: no pool for ${pair.key}`);

    // Real impl: read sqrtPrice + liquidity, decode adjacent tick arrays, build
    // bids/asks from CL depth. Stub raises so the engine routes around an
    // unwired venue instead of emitting fake prices.
    throw new Error(`orca: pool ${pool} not wired (offline)`);
  }

  /** Build a synthetic L2 book from concentrated-liquidity tick depth. */
  static synthBook(_pool: string): OrderbookL2 {
    return { bids: [], asks: [], ts: Date.now() };
  }

  subscribe?(_pairs: Pair[], _onQuote: (q: Quote) => void): SubscribeHandle {
    return () => {};
  }
}
