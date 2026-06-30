// Jupiter aggregator. We treat Jupiter's /quote as an EXECUTABLE quote: the
// returned outAmount already embeds route + price impact for the probe size, so
// the detector must not re-apply slippage.ts to it (executable: true).
//
// NOTE: token mints + exact reference sizes are wired through the universe symbol
// map (src/models/universe.ts). The HTTP shape below matches Jupiter v6; the
// mint/decimals lookup is stubbed until the laptop's real token map is attached.

import type { Exchange, Pair, Quote, SubscribeHandle, Venue, VenueKind } from '../exchange/types.js';
import { getJson } from '../core/http.js';

const BASE = process.env.JUPITER_QUOTE_URL ?? 'https://quote-api.jup.ag/v6';
// Probe size used to obtain an executable mid. Tune per-pair via universe later.
const PROBE_BASE_UNITS = 1;
const TAKER_FEE_BPS = 0; // Jupiter charges no protocol fee; LP fees are in the route impact.

interface JupQuoteResponse {
  inAmount: string;
  outAmount: string;
  priceImpactPct?: string;
}

// Placeholder mint map. Replaced by universe.symbolMap('jupiter') when online.
const STUB_MINTS: Record<string, { mint: string; decimals: number }> = {
  SOL: { mint: 'So11111111111111111111111111111111111111112', decimals: 9 },
  USDC: { mint: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', decimals: 6 },
};

export class JupiterExchange implements Exchange {
  readonly venue: Venue = 'jupiter';
  readonly kind: VenueKind = 'dex';

  async supports(pair: Pair): Promise<boolean> {
    return Boolean(STUB_MINTS[pair.base] && STUB_MINTS[pair.quote]);
  }

  async listPairs(): Promise<Pair[]> {
    // Real impl: derive from Jupiter token list ∩ tradable routes.
    return [];
  }

  async fetchQuote(pair: Pair): Promise<Quote> {
    const t0 = performance.now();
    const inTok = STUB_MINTS[pair.base];
    const outTok = STUB_MINTS[pair.quote];
    if (!inTok || !outTok) throw new Error(`jupiter: no mint for ${pair.key}`);

    const amount = BigInt(Math.round(PROBE_BASE_UNITS * 10 ** inTok.decimals)).toString();
    const url =
      `${BASE}/quote?inputMint=${inTok.mint}&outputMint=${outTok.mint}` +
      `&amount=${amount}&slippageBps=50&swapMode=ExactIn`;

    const r = await getJson<JupQuoteResponse>(url, { timeoutMs: 1500 });
    const out = Number(r.outAmount) / 10 ** outTok.decimals;
    const inAmt = Number(r.inAmount) / 10 ** inTok.decimals;
    const px = out / inAmt; // quote per base, impact already applied
    const latencyMs = performance.now() - t0;

    return {
      venue: this.venue,
      kind: this.kind,
      pair,
      bid: px,
      ask: px,
      mid: px,
      feeBps: TAKER_FEE_BPS,
      executable: true,
      ts: Date.now(),
      latencyMs,
      stale: false,
    };
  }

  // Jupiter has no public stream; engine polls fetchQuote on tick.
  subscribe?(_pairs: Pair[], _onQuote: (q: Quote) => void): SubscribeHandle {
    return () => {};
  }
}
