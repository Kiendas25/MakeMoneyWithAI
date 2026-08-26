# Self-Evolving Crypto Trading Agent

An autonomous crypto-only trading agent that runs unattended, remembers what it
did, learns from it, and rewrites its own strategy over time.

Three things make it more than a bot with indicators:

| | |
|---|---|
| **Autonomous** | One loop: perceive → recall → decide → risk-check → act → record → evolve. It survives restarts, network outages and its own crashes, and holds a kill switch it cannot override. |
| **Two brains** | **Brain 1** is exact and episodic (SQLite ledger of candles, decisions, fills, trades, genomes, equity). **Brain 2** is semantic and associative (vector memory of lessons, searched by meaning). Recall changes the next order's size — memory that cannot change behaviour is decoration. |
| **Self-evolving** | A genetic algorithm breeds strategy genomes against the agent's own recent history, selects in-sample, and promotes to champion **only on out-of-sample evidence**. Reflection over past trades biases which genes mutate, so the search is informed rather than blind. |

Runs on the **standard library alone** — no numpy, no pandas, no framework.
`ccxt` is optional and only needed for live orders or non-Binance data.

> **This is research software that can lose money.** It defaults to paper
> trading. Live mode needs an explicit config flag *and* an environment
> confirmation string, and the profitability of any strategy it breeds is
> entirely unproven. Read the [Honest limits](#honest-limits) section before
> pointing it at real funds.

---

## Quickstart

```bash
cd self_evolving_trader

# 250 steps of the entire loop on deterministic synthetic data, no network
python3 -m crypto_agent demo --steps 400 --fresh

# the tests (71, stdlib unittest, ~9s)
python3 -m pytest tests -q
```

Then run it for real market data, still on paper money:

```bash
python3 -m crypto_agent --provider binance --symbol BTC/USDT --timeframe 1h run
```

On **Windows PowerShell**, use `python` and keep each command on one line (`\`
is not a line continuation there — the backtick `` ` `` is):

```powershell
git clone -b claude/self-evolving-crypto-agent-a9r543 https://github.com/Kiendas25/MakeMoneyWithAI.git
cd MakeMoneyWithAI\self_evolving_trader
python -m pytest tests -q
python -m crypto_agent --provider binance --symbol BTC/USDT --timeframe 5m --mode paper run --poll-seconds 20
```

If Binance answers `451`, the endpoint is geo-blocked where you are; switch
venue with `pip install ccxt` and
`--provider ccxt --exchange coinbase --symbol BTC/USD` (still paper — ccxt is
only fetching candles there).

It will fetch history, bootstrap a champion strategy, and trade a paper book
every hour, evolving as it goes. `Ctrl-C` stops it cleanly; starting it again
resumes mid-position from the two brains.

---

## The two brains

```
                       ┌──────────────────────────────────────────┐
   market data ───────▶│              TradingAgent                │
   (binance/ccxt/      │  perceive → recall → decide → risk → act  │
    synthetic)         └───────┬───────────────────────┬──────────┘
                               │ writes everything     │ asks "what does
                               ▼                       ▼  this remind me of?"
                ┌──────────────────────────┐  ┌─────────────────────────────┐
                │ BRAIN 1 — Hippocampus    │  │ BRAIN 2 — Cortex            │
                │ brain1_episodic.sqlite3  │  │ brain2_semantic.sqlite3     │
                │                          │  │                             │
                │ candles, decisions,      │  │ lessons as text + vectors,  │
                │ trades, fills, equity,   │  │ cosine recall, reinforcement│
                │ genomes, generations,    │  │ decay, pruning              │
                │ risk state, audit log    │  │                             │
                │                          │  │                             │
                │ exact · transactional    │  │ fuzzy · associative         │
                └───────────┬──────────────┘  └──────────────┬──────────────┘
                            │                                ▲
                            │   consolidation ("sleep"):     │
                            └── group episodes → distil ─────┘
                                lessons → write them back
```

**Why two.** They answer different questions. Brain 1 answers *"what happened at
14:00 on Tuesday"* — it is the ledger, and it must be exact, because position
size and risk limits are computed from it. Brain 2 answers *"what does this
situation remind me of"* — it is fuzzy on purpose, because no two market setups
are ever identical and an exact-match lookup would recall nothing. Fusing them
into one store would mean either a ledger you cannot search by meaning, or a
memory you cannot trust for accounting.

**How Brain 2 changes behaviour.** Before every entry the agent writes a
description of its own situation, recalls the most similar lessons, and turns
them into a `MemoryBias`:

- `size_mult` scales the order (0.4× … 1.5×) by the weighted average outcome of
  similar past situations,
- `veto_long` / `veto_short` block the trade outright — but only on real
  evidence: a materially negative average across **six or more** similar
  episodes, most of which lost,
- `gene_nudges` feed back into evolution, biasing which genes mutate next.

```
[2026-08-24 13:00] open:long   opened long 0.046713 at 41,584.76
                               (stop 39,346.91, target 46,955.58; x0.87 size from 4 memories)
[2026-08-25 10:00] veto:memory memory vetoed the entry — regime 'range_low_vol' long entries
                               lost money: 7 trades, avg -1.84%, win rate 29%
```

---

## Self-evolution

Every `evolve_every_steps` iterations the agent breeds a new generation against
its own recent history:

1. **Evaluate** each genome with a walk-forward split — fit window and a
   hold-out tail it never selects on.
2. **Select** by in-sample fitness: annualised Sharpe, shrunk toward zero by
   sample size, multiplied by a drawdown penalty, plus a return term.
3. **Breed** — tournament selection, uniform/blended crossover, gaussian creep
   mutation, elitism, and a diversity guard that rejects children too close in
   gene space to the existing population.
4. **Promote** only if the candidate beats the reigning champion
   **out-of-sample** by a margin, with enough hold-out trades and an acceptable
   drawdown. Churning the champion on noise is its own failure mode.
5. **Reflect** — summarise what the trades imply and write it to Brain 2 with
   `gene_hints` ("half the trades died on the stop → widen `stop_atr_mult`,
   shrink `risk_scale`"), which biases the next generation's mutations.

A genome is a flat vector of 25 bounded, typed genes — indicator lengths, the
weights of five signal modules (trend, MACD, breakout, mean-reversion, RSI),
entry/exit thresholds, and risk shape (ATR stop, target, trailing, time stop,
volatility ceiling). Every gene has hard bounds, so mutation can produce a bad
strategy but never an invalid one, and every genome describes itself in a line:

```
genome 917fe80c6cdc (gen 12, crossover): leans on meanrev 1.00, rsi 0.70, trend 0.10;
EMA 5/60, entry>0.35, stop 2.2ATR, tp 3.0ATR, long only
```

Reflection has two implementations: `heuristic` (default — explicit, auditable
rules over trade statistics, no network) and `llm` (asks Claude for hypotheses,
which are validated against the gene whitelist and bounds before anything is
trusted, and which fall back to the heuristic on any error).

---

## Autonomy and safety

The risk manager is the constitution evolution cannot mutate. All of its state
lives in Brain 1, so a halted agent stays halted across restarts:

| Guard | Default |
|---|---|
| Risk per trade (to the stop) | 1% of equity |
| Notional cap | 35% of equity |
| Daily loss limit | 4% — no new entries until the next market day |
| Drawdown kill switch | 20% from peak → halt, cleared only by `resume-risk` |
| Trades per day | 12 |
| Cooldown after a loss | 2 bars |
| Shorting | off |

Other properties that matter for running unattended:

- **Closed candles only.** A forming bar is never traded on.
- **One decision per bar.** Re-polling the same bar is a no-op.
- **Single instance.** A PID lockfile refuses a second agent on the same brains.
- **Network failures degrade, not crash.** `CachedProvider` serves the last
  known history out of Brain 1 when the exchange is unreachable.
- **Positions outlive promotions.** A position is always managed by the genome
  that opened it, so a mid-trade champion swap cannot move your stop.
- **Live trading is double-gated:** `mode=live` **and**
  `CRYPTO_AGENT_CONFIRM_LIVE=I_UNDERSTAND_THE_RISK`, plus API keys in the
  environment. Missing any of them raises rather than silently paper-trading —
  or silently live-trading.

---

## CLI

```bash
python3 -m crypto_agent demo --steps 400 --fresh   # offline end-to-end run
python3 -m crypto_agent run --steps 100            # autonomous loop
python3 -m crypto_agent dashboard --serve --open   # visual dashboard in a browser
python3 -m crypto_agent backtest                   # champion, in- vs out-of-sample
python3 -m crypto_agent evolve -g 5                # run generations now
python3 -m crypto_agent status                     # full state as JSON
python3 -m crypto_agent memory -q "downtrend high vol long"
python3 -m crypto_agent report                     # trades, evolution, events
python3 -m crypto_agent resume-risk                # clear a drawdown halt
```

The read-only commands (`status`, `report`, `memory`, `backtest`, `dashboard`)
adopt the config the agent last booted with, read from Brain 1 — so
`status` describes the agent that is actually running rather than falling back
to defaults. Explicit flags and `CRYPTO_AGENT_*` variables still override it,
and a stored `live` mode is never adopted by an inspection command.

## Dashboard

```bash
python3 -m crypto_agent dashboard --serve --open        # live, re-renders per request
python3 -m crypto_agent dashboard -o report.html        # or write a single file
```

Equity curve, price candles with entry/exit markers, best-vs-mean fitness per
generation, the champion's genes, Brain 2's lessons, the trade blotter, recent
decisions and the event log — one self-contained HTML file with inline SVG
charts. No JavaScript, no CDN, no dependencies, and it reads the brains without
touching the exchange, so it is safe to run while the agent trades.

Global flags: `--config`, `--data-dir`, `--symbol`, `--timeframe`, `--provider`,
`--exchange`, `--mode`, `--seed`, `--log-level`.

## Configuration

Precedence is **CLI flags > `--config` JSON > `CRYPTO_AGENT_*` env vars >
defaults**, and the resolved config is written into Brain 1 on every boot so any
run can be reproduced. See [`config.example.json`](config.example.json).

```bash
export CRYPTO_AGENT_SYMBOL=ETH/USDT
export CRYPTO_AGENT_RISK_PER_TRADE=0.005
python3 -m crypto_agent run
```

### Going live (only when you mean it)

```bash
pip install ccxt
export CRYPTO_AGENT_API_KEY=...  CRYPTO_AGENT_API_SECRET=...
export CRYPTO_AGENT_CONFIRM_LIVE=I_UNDERSTAND_THE_RISK
python3 -m crypto_agent --provider ccxt --exchange binance --mode live run
```

Paper-trade the same config for weeks first, and start with an amount you would
be relaxed about losing entirely.

## Layout

```
crypto_agent/
  agent.py              the autonomous loop
  config.py             typed, validated configuration
  core/types.py         candles, signals, positions, trades, fitness
  data/                 indicators (pure Python) + providers (synthetic/binance/ccxt/cached)
  brain/
    hippocampus.py      Brain 1 — episodic SQLite ledger
    cortex.py           Brain 2 — vector memory with decay and pruning
    embeddings.py       stable hashing embedder (no model, no network)
    memory.py           DualBrain: consolidation and decision-time advice
  strategy/
    genome.py           the evolvable parameter vector
    rules.py            one signal engine shared by live and backtest
    backtest.py         pessimistic event-driven simulator
  evolution/
    engine.py           GA with walk-forward promotion and diversity guard
    reflect.py          heuristic + optional Claude reflection → gene hints
  execution/
    broker.py           PaperBroker / CcxtBroker
    risk.py             limits, sizing, kill switch
tests/                  71 tests, stdlib unittest (pytest-compatible)
```

## Prior art this builds on

The wheels that were not reinvented, and the ideas that were borrowed:

- **[ccxt](https://github.com/ccxt/ccxt)** — the unified exchange API used for
  live orders and non-Binance market data (optional dependency).
- **[Freqtrade](https://github.com/freqtrade/freqtrade)** — the reference for
  strategy/risk separation, dry-run-first culture, and hyperopt-style parameter
  search with a hold-out.
- **[Jesse](https://github.com/jesse-ai/jesse)**,
  **[Backtrader](https://github.com/mementum/backtrader)**,
  **[vectorbt](https://github.com/polakowo/vectorbt)** — event-driven backtest
  structure and the metric set (Sharpe/Sortino/max-DD/exposure).
- **[Hummingbot](https://github.com/hummingbot/hummingbot)** — the case for
  hard, non-negotiable risk guards around an automated strategy.
- **[mem0](https://github.com/mem0ai/mem0)**,
  **[MemGPT/Letta](https://github.com/letta-ai/letta)**, and the
  *Generative Agents* (Park et al., 2023) memory-stream design — the split
  between an exact episodic store and a retrieved semantic one, with periodic
  reflection turning episodes into higher-level lessons. This project implements
  that pattern directly rather than depending on a framework, so the whole
  memory path stays dependency-free and inspectable.
- **[DEAP](https://github.com/DEAP/deap)** — standard GA vocabulary (tournament
  selection, elitism, uniform crossover, gaussian mutation).

## Honest limits

- **Evolution can only search what the genome expresses.** It tunes and
  recombines five classic signal families; it will not invent a new one.
- **A walk-forward hold-out reduces overfitting; it does not eliminate it.**
  Re-running evolution repeatedly on overlapping history erodes the hold-out's
  independence over time.
- **The synthetic provider is not a market.** It exists so the loop can be
  tested deterministically and offline. Any result produced against it says
  something about the *code*, nothing about the *strategy*.
- **No live-exchange verification was possible in this environment** — the
  sandbox blocks all exchange endpoints, so `BinancePublicProvider` and
  `CcxtBroker` are written to their documented APIs but have not been exercised
  against a real endpoint. Paper-trade them before trusting them.
- **Slippage and fees are modelled, not measured.** Real fills on thin books,
  during volatility, will be worse than the constant-basis-point assumption.
- **Past performance, synthetic or historical, does not predict future
  returns.** Nothing here is financial advice.
