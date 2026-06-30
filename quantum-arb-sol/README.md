# Quantum-Arb-SOL

Solana DEX/CEX arbitrage **research** engine. Simulation, backtesting,
paper-trading and microstructure analysis only.

> **No real execution.** There is no signer, no keypair, and no
> `sendTransaction` anywhere in this codebase. A guard test
> (`test/no-signer.test.ts`) fails the build if any signing surface is added.
> `simulator/paper.ts` is the single terminal of "execution".

## Stack

Node 20 (ESM) · TypeScript (strict) · undici (keep-alive HTTP) · `ws` ·
Vite + React (UI) · Vitest.

## Architecture

```
ui / cli ──ws──▶ core (engine, scheduler, bus, ws server)
                      │
                      ▼
                 models (universe, arbitrage, slippage, latency, risk)
                      │
                      ▼
                 exchange (types, registry, normalize)
                    ▲                       ▲
                 dex/* (jupiter,         cex/* (binance,
                 orca, raydium)          coinbase)
                      │
                      ▼
              backtester / simulator (paper)
```

`exchange/` is the parent contract: `dex/*` and `cex/*` implement the same
`Exchange` interface, so the detector is agnostic to the source.

### Tick flow

```
scheduler tick
  └─ parallel fetchers (undici pool + WS): jupiter/orca/raydium/binance/coinbase
        ↓ normalize → Quote[]            (exchange/)
        ↓ filter by ActivePair[]         (models/universe)
        ↓ detect spreads (net fees+gas+slippage)  (models/arbitrage)
        ↓ apply slippage + latency       (models/*)
        ↓ risk gate                      (models/risk)
        ↓ simulate execution — NO real orders     (simulator/paper)
        ↓ log → backtester metrics / UI bus
```

Live and backtest share `Engine.processTick`, so replay is the parity reference
for live behaviour.

## Universe

Static top-10 Solana pairs (reproducible backtests), override via
`UNIVERSE_OVERRIDE` in `.env`. Hard rule: a pair is active **only if every
active venue supports it** (present-in-all-venues). Per-venue symbol divergence
(Coinbase `SOL-USDC`, Binance `SOLUSDC`, DEX mints) is mapped in
`models/universe.ts` — the single source of truth for the intersection filter.

## Commands

```bash
npm install
npm run typecheck          # tsc --noEmit
npm test                   # vitest
npm run bench              # synthetic throughput (checks/sec, p50/p99)
npm run dev:engine         # live engine + local WS server
npm run dev:ui             # Vite dashboard (connects to the engine WS)
npm run backtest -- data/sample.ndjson
```

## Status (offline scaffolding)

CEX REST snapshots (`binance`, `coinbase`) are wired to public endpoints. DEX
venues (`jupiter`, `orca`, `raydium`) carry final `Exchange` shapes; the on-chain
pool reads / token-mint maps are stubbed until the laptop's real clients are
attached. Wiring those in does not touch the detector, simulator, or backtester.
