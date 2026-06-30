// Raydium AMM/CLMM. Reserve-based price for constant-product pools; CLMM handled
// like Orca (tick depth). executable: false — slippage.ts applies. No native L2.
//
// Pool reserve reads are stubbed until the laptop's Raydium client is attached.

import type {
  Exchange,
  OrderbookL2,
  Pair,
  Quote,
  SubscribeHandle,
  Venue,
  VenueKind,
} from '../exchange/types.js';

const TAKER_FEE_BPS = 25; // Raydium AMM fee; per-pool override later.

const STUB_POOLS: Record<string, string> = {
  'SOL/USDC': '__RAYDIUM_SOL_USDC__',
};

export class RaydiumExchange implements Exchange {
  readonly venue: Venue = 'raydium';
  readonly kind: VenueKind = 'dex';

  async supports(pair: Pair): Promise<boolean> {
    return Boolean(STUB_POOLS[pair.key]);
  }

  async listPairs(): Promise<Pair[]> {
    return [];
  }

  async fetchQuote(pair: Pair): Promise<Quote> {
    const pool = STUB_POOLS[pair.key];
    if (!pool) throw new Error(`raydium: no pool for ${pair.key}`);
    // Real impl: x*y=k → mid = reserveQuote/reserveBase; CLMM → tick walk.
    throw new Error(`raydium: pool ${pool} not wired (offline)`);
  }

  /** Constant-product synthetic book from reserves (impact = k/(x±q) curve). */
  static synthBook(_reserveBase: number, _reserveQuote: number): OrderbookL2 {
    return { bids: [], asks: [], ts: Date.now() };
  }

  subscribe?(_pairs: Pair[], _onQuote: (q: Quote) => void): SubscribeHandle {
    return () => {};
  }
}
