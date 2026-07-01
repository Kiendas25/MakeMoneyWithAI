import { describe, it, expect } from 'vitest';
import { Universe } from '../src/models/universe.js';
import { makePair, type Exchange, type Pair, type Quote, type Venue } from '../src/exchange/types.js';

function fakeVenue(venue: Venue, supported: string[]): Exchange {
  const set = new Set(supported);
  return {
    venue,
    kind: venue === 'binance' || venue === 'coinbase' ? 'cex' : 'dex',
    async supports(pair: Pair) {
      return set.has(pair.key);
    },
    async listPairs() {
      return supported.map((k) => {
        const [b, q] = k.split('/') as [string, string];
        return makePair(b, q);
      });
    },
    async fetchQuote(): Promise<Quote> {
      throw new Error('not used');
    },
  };
}

describe('Universe present-in-all-venues filter', () => {
  it('keeps only pairs supported by every active venue', async () => {
    const u = new Universe({ override: 'SOL/USDC,JUP/USDC' });
    const venues = [
      fakeVenue('jupiter', ['SOL/USDC', 'JUP/USDC']),
      fakeVenue('binance', ['SOL/USDC']), // missing JUP/USDC
    ];
    const { active, dropped } = await u.resolve(venues);
    expect(active.map((a) => a.pair.key)).toEqual(['SOL/USDC']);
    expect(dropped).toHaveLength(1);
    expect(dropped[0]!.missing).toContain('binance');
  });

  it('treats a venue that throws on supports() as not supporting the pair', async () => {
    const flaky: Exchange = {
      ...fakeVenue('orca', []),
      async supports() {
        throw new Error('rpc down');
      },
    };
    const u = new Universe({ override: 'SOL/USDC' });
    const { active } = await u.resolve([fakeVenue('jupiter', ['SOL/USDC']), flaky]);
    expect(active).toHaveLength(0);
  });
});
