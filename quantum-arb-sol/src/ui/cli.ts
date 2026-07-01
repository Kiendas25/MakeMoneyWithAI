// Headless entrypoint. Three modes:
//   --live              run the engine + WS server (UI connects to it)
//   --bench [ticks]     synthetic throughput benchmark (no network)
//   --backtest <file>   replay an NDJSON snapshot through the shared pipeline
//
// Run: node --import tsx src/ui/cli.ts --live

import { loadConfig } from '../core/config.js';
import { Bus } from '../core/bus.js';
import { VenueRegistry } from '../exchange/index.js';
import { Engine } from '../core/engine.js';
import { EngineWsServer } from '../core/wsserver.js';
import { closeHttp } from '../core/http.js';
import { Backtester } from '../backtester/index.js';
import { runBench } from './bench.js';
import { buildPreviewHtml, syntheticSnapshot, type PreviewSnapshot } from './preview.js';
import { writeFileSync } from 'node:fs';
import type { Quote } from '../exchange/types.js';

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const mode = args[0] ?? '--live';

  if (mode === '--backtest') {
    const file = args[1];
    if (!file) throw new Error('usage: --backtest <file.ndjson>');
    const metrics = await new Backtester(loadConfig()).run(file);
    console.log(JSON.stringify(metrics, null, 2));
    return;
  }

  if (mode === '--bench') {
    const ticks = Number(args[1] ?? 5000);
    const res = runBench(loadConfig(), ticks);
    console.log(JSON.stringify(res, null, 2));
    return;
  }

  if (mode === '--preview') {
    // Synthetic, deterministic, interactive HTML — no network.
    const out = args[1] ?? 'quantum-arb-preview.html';
    writeFileSync(out, buildPreviewHtml(syntheticSnapshot()));
    console.log(`wrote ${out} (synthetic, interactive)`);
    return;
  }

  if (mode === '--snapshot') {
    // Run the live engine for N ticks, capture quotes, emit interactive HTML.
    const ticks = Number(args[1] ?? 20);
    const out = args[2] ?? 'quantum-arb-snapshot.html';
    await runSnapshot(ticks, out);
    return;
  }

  // --live
  const cfg = loadConfig();
  const bus = new Bus();
  const registry = new VenueRegistry({ activeVenues: cfg.activeVenues, staleMs: cfg.staleMs });
  const engine = new Engine({ config: cfg, registry, bus });
  const ws = new EngineWsServer(bus, cfg.wsPort, {
    onSetNotional: (usd) => engine.setNotional(usd),
  });

  bus.on('error', (e) => console.error(`[engine:${e.where}] ${e.message}`));
  bus.on('metric', (m) =>
    console.log(
      `tick ${m.tick} q=${m.quotes} opp=${m.opportunities} fill=${m.fills} ` +
        `${m.durationMs.toFixed(1)}ms drop=${m.droppedTicks}`,
    ),
  );

  const active = await engine.init();
  console.log(`universe: ${active.map((a) => a.pair.key).join(', ') || '(empty)'}`);
  console.log(`ws server: ws://localhost:${ws.port}`);
  engine.start();

  const shutdown = async () => {
    await engine.stop();
    await ws.close();
    await closeHttp();
    process.exit(0);
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

/**
 * Drive the live engine for `ticks` ticks, accumulating the most recent quote
 * per (venue, pair), then write a self-contained interactive preview embedding
 * that real snapshot. Offline-of-laptop, only the wired venues will contribute.
 */
async function runSnapshot(ticks: number, out: string): Promise<void> {
  const cfg = loadConfig();
  const bus = new Bus();
  const registry = new VenueRegistry({ activeVenues: cfg.activeVenues, staleMs: cfg.staleMs });
  const engine = new Engine({ config: cfg, registry, bus });

  const latest = new Map<string, Quote>(); // key: `${venue}:${pair.key}`
  bus.on('quotes', (qs) => {
    for (const q of qs) latest.set(`${q.venue}:${q.pair.key}`, q);
  });
  bus.on('error', (e) => console.error(`[engine:${e.where}] ${e.message}`));

  const active = await engine.init();
  engine.start();

  await new Promise<void>((resolve) => {
    let seen = 0;
    const unsub = bus.on('metric', () => {
      if (++seen >= ticks) {
        unsub();
        resolve();
      }
    });
  });
  await engine.stop();
  await closeHttp();

  const quotes = [...latest.values()];
  const universe = [...new Set(quotes.map((q) => q.pair.key))].sort();
  const snap: PreviewSnapshot = {
    universe: universe.length ? universe : active.map((a) => a.pair.key),
    quotes,
    defaultNotionalUsd: cfg.risk.maxNotionalUsd,
    minEdgeBps: cfg.risk.minEdgeBps,
    source: `live snapshot (${ticks} ticks, ${quotes.length} quotes)`,
  };
  writeFileSync(out, buildPreviewHtml(snap));
  console.log(`wrote ${out} — ${quotes.length} quotes across ${snap.universe.length} pairs`);
  process.exit(0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
