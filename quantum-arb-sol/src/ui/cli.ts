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

  // --live
  const cfg = loadConfig();
  const bus = new Bus();
  const registry = new VenueRegistry({ activeVenues: cfg.activeVenues, staleMs: cfg.staleMs });
  const engine = new Engine({ config: cfg, registry, bus });
  const ws = new EngineWsServer(bus, cfg.wsPort);

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

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
