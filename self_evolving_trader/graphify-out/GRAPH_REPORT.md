# Graph Report - self_evolving_trader  (2026-08-27)

## Corpus Check
- 50 files · ~48,779 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1131 nodes · 2678 edges · 67 communities (56 shown, 11 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 170 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e5d9f782`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- dashboard.py
- test_correlation.py
- PaperBroker
- EvolutionEngine
- test_risk_and_agent.py
- genome_with
- indicators.py
- Hippocampus
- Position
- TestCharts
- backtest.py
- Signal
- DivergenceTestCase
- agent.py
- cli.py
- TradingAgent
- DualBrain
- .make_broker
- cortex.py
- types.py
- CcxtBroker
- RiskManager
- make_agent
- make_config
- .cycle
- Cortex
- Self-Evolving Crypto Trading Agent
- obsidian.py
- TestRiskManager
- test_live_safety.py
- Lesson
- .random
- _pid_alive
- test_memory.py
- Config
- Genome
- Candle
- test_walkforward.py
- TestAgentEndToEnd
- TestAgentUniverse
- Correlation
- FakeExchange
- SyntheticProvider
- TestMultiSymbolReconcileKeepsEveryHolding
- test_dashboard_and_cli.py
- Frame
- TestFillDivergence
- .load
- Any
- TestDashboardIntegration
- TestIndicators
- TestDashboardPage
- safe_name
- self-evolving-crypto-agent
- TestCheckEntryCorrelationCap
- MemoryBias
- Recall
- .remember
- Trade
- providers.py
- TestEquityAcceptsThePriceMapAgentActuallyPasses
- TestKillSwitchDoesNotTrapPositions

## God Nodes (most connected - your core abstractions)
1. `Config` - 145 edges
2. `DualBrain` - 98 edges
3. `Candle` - 73 edges
4. `Genome` - 57 edges
5. `TradingAgent` - 55 edges
6. `Signal` - 55 edges
7. `Hippocampus` - 46 edges
8. `Trade` - 39 edges
9. `RiskManager` - 39 edges
10. `Lesson` - 34 edges

## Surprising Connections (you probably didn't know these)
- `Coerce strings coming from env/JSON into the dataclass field type.` --rationale_for--> `_coerce()`  [EXTRACTED]
  crypto_agent/config.py → self_evolving_trader/crypto_agent/config.py
- `Start from a few hand-written archetypes, then fill with randoms. Pure random…` --rationale_for--> `seed_population()`  [EXTRACTED]
  crypto_agent/strategy/genome.py → self_evolving_trader/crypto_agent/strategy/genome.py
- `A coarse, human-readable label. Brain 2 groups its lessons by this, so it has…` --rationale_for--> `regime_at()`  [EXTRACTED]
  crypto_agent/strategy/rules.py → self_evolving_trader/crypto_agent/strategy/rules.py
- `Each module votes in [-1, 1]. Positive means "be long".` --rationale_for--> `module_scores()`  [EXTRACTED]
  crypto_agent/strategy/rules.py → self_evolving_trader/crypto_agent/strategy/rules.py
- `Ratchet the stop toward price using bar ``i``'s close; never loosen it. The…` --rationale_for--> `update_trailing_stop()`  [EXTRACTED]
  crypto_agent/strategy/rules.py → self_evolving_trader/crypto_agent/strategy/rules.py

## Import Cycles
- None detected.

## Communities (67 total, 11 thin omitted)

### Community 0 - "dashboard.py"
Cohesion: 0.06
Nodes (51): _compare_symbol(), DivergenceReport, FillComparison, _mean_bps(), measure_divergence(), _pool(), The full comparison: one :class:`SymbolDivergence` per market, the pooled total…, Re-simulate the current champion over the window it actually traded and compare… (+43 more)

### Community 1 - "test_correlation.py"
Cohesion: 0.24
Nodes (7): _candles_from_returns(), Correlation measurement, clustering, and the risk manager's cluster cap., Build a candle series whose closes follow the given log returns. ``skip_every``…, A caller must never mistake "unknown" for a genuine zero correlation., _returns(), TestClustering, TestPairwiseCorrelation

### Community 2 - "PaperBroker"
Cohesion: 0.05
Nodes (16): Fill, Broker, PaperBroker, Protocol, Simulated fills, real bookkeeping., Units of the primary symbol - the single-symbol convenience view., Cash plus every holding marked to the prices given. Accepts a single price…, Paper trading has no external venue to drift from - the local book *is* the… (+8 more)

### Community 3 - "EvolutionEngine"
Cohesion: 0.10
Nodes (15): _deflation_penalty(), Evaluation, EvolutionEngine, Any, Random, Score a genome across the whole universe. A strategy that only works on one…, Pull mutation bias out of Brain 2's reflections., Promote on out-of-sample evidence only, and only by a clear margin. Churning… (+7 more)

### Community 4 - "test_risk_and_agent.py"
Cohesion: 0.15
Nodes (11): HeuristicReflector, LLMReflector, make_reflector(), Any, Reflection: turning outcomes into hypotheses. Consolidation (in…, Only real genes, only sane magnitudes. Applies to LLM output too., Optional Claude-powered reflection over the recent trade log., Rule-based post-mortem over recent trades. (+3 more)

### Community 5 - "genome_with"
Cohesion: 0.09
Nodes (12): Gene, Any, Fill gaps, clamp everything into range, enforce cross-gene sanity., Fill gaps, clamp everything into range, enforce cross-gene sanity., flat_candles(), genome_with(), A range: no drift, small alternating moves, so slope stays near zero., An uptrend. Growth is compounded, not linear: `slope` normalises by the window… (+4 more)

### Community 6 - "indicators.py"
Cohesion: 0.17
Nodes (22): atr(), bollinger_z(), donchian_position(), ema(), last_valid(), macd_hist(), Technical indicators in pure Python. Each function takes a list of floats (or…, How many standard deviations price sits from its own mean. (+14 more)

### Community 7 - "Hippocampus"
Cohesion: 0.10
Nodes (4): Hippocampus, _now_ms(), Path, Durable, exact memory. Safe to share across threads.

### Community 8 - "Position"
Cohesion: 0.15
Nodes (10): _position_to_dict(), Position, exit_price_for(), Where a given exit reason actually fills., Where a given exit reason actually fills., _flat_frame(), A minimal Frame for exercising update_trailing_stop/exit_reason in isolation:…, BUG 2 regression: the stop must be tested against the level known before a bar… (+2 more)

### Community 10 - "backtest.py"
Cohesion: 0.16
Nodes (11): BacktestResult, _aggregate_metrics(), Fold, Event-driven backtester. Deliberately pessimistic: fees on both sides, slippage…, One anchored walk-forward split: everything up to a point to fit on, and the…, Aggregate in-sample and out-of-sample results, plus the fold-by-fold detail…, Pool several fold results into one summary metric set. Trade counts sum…, Anchored, multi-fold walk-forward evaluation. A single fixed hold-out at the… (+3 more)

### Community 11 - "Signal"
Cohesion: 0.14
Nodes (5): A strategy's opinion at one point in time., Signal, make_trade(), TestDualBrain, TestPortfolioRisk

### Community 12 - "DivergenceTestCase"
Cohesion: 0.22
Nodes (5): DivergenceTestCase, A risk veto is classified separately from a memory veto., A missed entry with no veto logged at all is neither a fill problem nor a…, TestRiskVeto, TestUnexplainedGap

### Community 13 - "agent.py"
Cohesion: 0.12
Nodes (17): The autonomous agent loop. One iteration is: perceive -> recall -> decide ->…, Live-vs-backtest divergence for the champion genome. Nothing else in the agent…, The two brains, wired together. ``DualBrain`` is the only object the rest of…, Configuration for the autonomous agent. Precedence: explicit kwargs >…, _as_markets(), GenerationReport, The evolution engine. A steady-state genetic algorithm over strategy genomes,…, Accept a symbol->candles map, or a bare series for the single-market case. (+9 more)

### Community 14 - "cli.py"
Cohesion: 0.27
Nodes (18): cmd_backtest(), cmd_dashboard(), cmd_demo(), cmd_evolve(), cmd_memory(), cmd_obsidian(), cmd_report(), cmd_resume_risk() (+10 more)

### Community 15 - "TradingAgent"
Cohesion: 0.12
Nodes (8): Any, Sleep and dream: consolidate memories, then evolve., Run autonomously until stopped (or ``max_steps`` cycles). A cycle is one pass…, Trust the exchange over our own records before trading anything. A process that…, _release_lock(), TradingAgent, The cluster cap must actually hold in the live loop, not just in a unit test of…, TestCorrelatedExposureCapBinds

### Community 16 - "DualBrain"
Cohesion: 0.21
Nodes (6): DualBrain, Any, export_vault(), Mirror both brains into an Obsidian vault at ``vault_dir``. Read-only with…, make_trade(), TestExportVault

### Community 17 - ".make_broker"
Cohesion: 0.18
Nodes (3): TestLiveModeGates, TestQuantityRounding, TestReconcile

### Community 18 - "cortex.py"
Cohesion: 0.21
Nodes (8): Brain 2 - semantic / associative memory. Where Brain 1 answers "what happened…, Embedder, l2_normalize(), pack(), Protocol, Embeddings for Brain 2. The default embedder is a deterministic hashing…, tokenize(), unpack()

### Community 19 - "types.py"
Cohesion: 0.23
Nodes (7): Brain 1 - episodic / structured memory (SQLite). This is the agent's ledger and…, bars_per_year(), Core value types shared by every layer of the agent. Everything here is plain…, timeframe_ms(), Risk manager - the part that is allowed to say no. Evolution optimises for…, Properties that must hold over a long run, not just on one call. These are the…, Regression tests for the risk-manager resume() kill switch and the…

### Community 20 - "CcxtBroker"
Cohesion: 0.12
Nodes (8): CcxtBroker, Any, Live exchange orders through ccxt. Opt-in, guarded, and audited. Keeps a…, Pull the exchange's LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL metadata once. Not every…, The exchange's LOT_SIZE increment for ``symbol``, or ``None`` when the market…, Round ``qty`` down to the venue's step size - never up, because rounding up can…, Read cash plus every tracked symbol's base-asset balance. This must cover the…, Cash plus every holding marked to the prices given. Accepts a single price…

### Community 21 - "RiskManager"
Cohesion: 0.05
Nodes (21): Any, Update the drawdown watermark and trip the kill switch if breached., Approve or refuse a new entry, sizing it within every active limit.…, None if the new position is fine; otherwise the refusal reason. A new entry is…, Cluster the given symbols by correlation, cached per bar in Brain 1. Five…, The trading day of a *market* timestamp. Deriving the day from the bar being…, Manual restart after a kill switch. Never called automatically - an agent that…, Best available estimate of current equity, for re-baselining on resume. Brain 1… (+13 more)

### Community 22 - "make_agent"
Cohesion: 0.18
Nodes (6): first_ts(), make_agent(), The half that did not sell is still real exposure., The partial-exit handling must not leave dust behind on a clean exit., TestEntryFollowsTheFill, TestExitFollowsTheFill

### Community 23 - "make_config"
Cohesion: 0.16
Nodes (7): first_ts(), make_config(), Caches keyed by bar timestamp would leave one dead row per bar., The bug this suite was written for: sizing rescaled past the cash clamp, so the…, Brain 1's positions and the broker's holdings are two records of the same fact;…, TestBookInvariants, TestStateAndStorage

### Community 24 - ".cycle"
Cohesion: 0.17
Nodes (8): CycleResult, _fmt_ts(), One decision on the primary symbol - the single-market view., Walk the whole universe once: perceive, then decide per symbol., What the agent decided about one symbol on one bar., Current exposure per market, in quote currency., One pass over the whole universe., StepResult

### Community 25 - "Cortex"
Cohesion: 0.19
Nodes (4): Cortex, Any, Path, Vector memory with decay, reinforcement and pruning.

### Community 26 - "Self-Evolving Crypto Trading Agent"
Cohesion: 0.11
Nodes (17): Autonomy and safety, CLI, Configuration, Dashboard, Going live (only when you mean it), Honest limits, Layout, Obsidian vault — reading the agent's mind (+9 more)

### Community 27 - "obsidian.py"
Cohesion: 0.18
Nodes (23): ExportReport, _frontmatter(), _index_note(), iter_note_paths(), _lesson_notes(), _lesson_symbol(), _market_notes(), _month() (+15 more)

### Community 29 - "test_live_safety.py"
Cohesion: 0.16
Nodes (9): BrokerOrderError, A live order was rejected, or its outcome could not be confirmed as a fill.…, RuntimeError, CcxtBrokerTestCase, Safety tests for CcxtBroker: order-quantity rounding, the live-mode gates, and…, ``Fill.qty`` must always be what the exchange actually filled, never the…, Base class that arms the live-mode gates and injects a fake ccxt., TestOrderFailureHandling (+1 more)

### Community 30 - "Lesson"
Cohesion: 0.21
Nodes (5): _group_lessons(), Turn recent raw episodes into generalisations. Triggered by new trades, but…, Lesson, A natural-language memory written into Brain 2., TestCortex

### Community 31 - ".random"
Cohesion: 0.10
Nodes (9): Manage an open position with the genome that opened it. A promotion mid-trade…, Random, Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Uniform crossover; numeric genes may also blend. Which parent a gene picks…, Uniform crossover; numeric genes may also blend. Which parent a gene picks…, ``roll < 0.4`` gated a choice of ``a if roll < 0.5 else b`` - since the gate…, TestCrossoverProvenance (+1 more)

### Community 32 - "_pid_alive"
Cohesion: 0.20
Nodes (8): _acquire_lock(), _pid_alive(), _pid_alive_windows(), Refuse to run two agents against one set of brains., Is this PID still running? ``os.kill(pid, 0)`` is the POSIX idiom, but on…, The lockfile's liveness probe must never be able to kill anything., os.kill on Windows terminates; the probe must not go near it., TestProcessLiveness

### Community 33 - "test_memory.py"
Cohesion: 0.29
Nodes (5): cosine(), HashingEmbedder, Stable bag-of-ngrams vectoriser using blake2b for bucket assignment., Cosine similarity; inputs are expected to be L2-normalised already., TestEmbeddings

### Community 34 - "Config"
Cohesion: 0.14
Nodes (10): Config, Path, Every symbol the agent trades, primary first, de-duplicated. One process…, Every symbol the agent trades, primary first, de-duplicated. One process…, position_size(), Risk-based sizing: lose ``risk_per_trade`` of equity if the stop hits. The same…, simulate(), TestBacktest (+2 more)

### Community 35 - "Genome"
Cohesion: 0.10
Nodes (19): clamp(), Genome, Normalised gene-space distance, used to keep the population diverse., Normalised gene-space distance, used to keep the population diverse., blended_score(), initial_stops(), min_edge_for(), module_scores() (+11 more)

### Community 36 - "Candle"
Cohesion: 0.14
Nodes (8): Only fully closed bars. Acting on a forming candle is how a backtest that looks…, Fetch every symbol before deciding anything. Marking the book to market needs…, Candle, BinancePublicProvider, _dedupe(), Public klines endpoint. No API key, no dependencies, read-only., CorrelatedProvider, Markets that move together, the way real majors do. The synthetic provider…

### Community 37 - "test_walkforward.py"
Cohesion: 0.16
Nodes (13): BacktestMetrics, fitness_score(), Risk-adjusted score used as the GA's selection pressure. Sharpe is the…, buy_and_hold(), compute_metrics(), The trivial "buy once and do nothing" strategy, priced the same way…, ramp_candles(), Tests for the buy-and-hold benchmark, anchored walk-forward folds, and the… (+5 more)

### Community 40 - "Correlation"
Cohesion: 0.16
Nodes (14): align_closes(), cluster_symbols(), Correlation, log_returns(), pearson(), How correlated two markets are, measured from their candle closes. The…, Pearson correlation of log returns between two candle series, aligned on…, Group symbols into clusters where any pair above ``threshold`` is linked. This… (+6 more)

### Community 41 - "FakeExchange"
Cohesion: 0.17
Nodes (5): Re-fetch the real balance (and open orders) and make the local cache match it,…, What ``reconcile()`` found when it checked the local book against the source of…, ReconcileReport, FakeExchange, Just enough of ccxt's unified exchange interface for CcxtBroker.

### Community 42 - "SyntheticProvider"
Cohesion: 0.10
Nodes (8): Regime-switching geometric brownian motion with fat tails. Not a claim about…, SyntheticProvider, Start from a few hand-written archetypes, then fill with randoms. Pure random…, Start from a few hand-written archetypes, then fill with randoms. Pure random…, seed_population(), A decision at bar i must not change when future bars are appended., TestEvolutionAcrossMarkets, TestEvaluateAndDeflation

### Community 43 - "TestMultiSymbolReconcileKeepsEveryHolding"
Cohesion: 0.22
Nodes (3): A ``--top5``-style universe holds positions in more than one symbol.…, TestMultiSymbolReconcileKeepsEveryHolding, TestPaperBrokerReconcile

### Community 44 - "test_dashboard_and_cli.py"
Cohesion: 0.16
Nodes (8): ArgumentParser, build_parser(), Any, The config the agent last booted with, straight out of Brain 1., stored_config(), Inspection commands must describe the agent that actually ran., A stored live mode must not arm a read-only command., TestStoredConfigAdoption

### Community 45 - "Frame"
Cohesion: 0.15
Nodes (13): exit_reason(), Frame, Ratchet the stop toward price using bar ``i``'s close; never loosen it. The…, Why this position should close now, or ``None`` to hold. Checked against the…, Ratchet the stop toward price using bar ``i``'s close; never loosen it. The…, All indicator series a genome needs, computed once over the history., Why this position should close now, or ``None`` to hold. Checked against the…, A coarse, human-readable label. Brain 2 groups its lessons by this, so it has… (+5 more)

### Community 46 - "TestFillDivergence"
Cohesion: 0.17
Nodes (5): No live trades at all - every entry the model would have taken was vetoed by…, The two scenarios must not collapse into the same generic text - this is the…, Live fills that are worse than the model assumed, with every entry matched and…, TestBehaviouralDivergence, TestFillDivergence

### Community 47 - ".load"
Cohesion: 0.24
Nodes (5): _coerce(), Any, Coerce strings coming from env/JSON into the dataclass field type., Coerce strings coming from env/JSON into the dataclass field type., TestConfig

### Community 49 - "TestDashboardIntegration"
Cohesion: 0.13
Nodes (8): make_candles(), Candles are cached and the model may well find entries in them, but with no…, The dashboard must render (and stay self-contained) whether or not there is…, A synthetic series with a slow, noisy oscillating drift - long enough to warm…, The archetype ``seed_population`` seeds first - reliably trades on the…, TestDashboardIntegration, TestGracefulDegradation, trend_follower_genome()

### Community 52 - "safe_name"
Cohesion: 0.24
Nodes (5): Turn a symbol or lesson title into a filename safe everywhere. ``BTC/USDT``…, ``safe_name`` plus a deterministic suffix when two inputs collide. Slugging is…, safe_name(), unique_name(), TestSafeName

### Community 60 - "MemoryBias"
Cohesion: 0.25
Nodes (4): _clamp(), MemoryBias, The query Brain 2 is searched with - deliberately written in the same…, What Brain 2 wants to change about the decision Brain 1's strategy made.

### Community 61 - "Recall"
Cohesion: 0.33
Nodes (3): Retrieve the memories most relevant to ``query``. Ranking blends three things:…, One recalled memory plus the scores that surfaced it., Recall

### Community 62 - ".remember"
Cohesion: 0.33
Nodes (4): hash_text(), _now_ms(), Store a lesson. Re-learning the same text reinforces it instead of duplicating…, Forget the least useful memories once over capacity.

### Community 63 - "Trade"
Cohesion: 0.28
Nodes (5): _row_to_trade(), A closed trade lands in both brains: the row in Brain 1, the story in Brain 2., A round trip, written to Brain 1 and distilled into Brain 2., Trade, Row

### Community 64 - "providers.py"
Cohesion: 0.21
Nodes (8): CachedProvider, CcxtProvider, make_provider(), MarketDataProvider, Protocol, Market data providers. Three sources, one interface: * ``SyntheticProvider`` -…, Any ccxt exchange. ``pip install ccxt`` to enable., Persist every candle in Brain 1 and survive network outages.

## Knowledge Gaps
- **16 isolated node(s):** `self-evolving-crypto-agent`, `Quickstart`, `The two brains`, `Trading a universe`, `Self-evolution` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Config` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `EvolutionEngine`, `test_risk_and_agent.py`, `genome_with`, `backtest.py`, `Signal`, `DivergenceTestCase`, `agent.py`, `cli.py`, `TradingAgent`, `DualBrain`, `.make_broker`, `types.py`, `CcxtBroker`, `RiskManager`, `make_agent`, `make_config`, `Cortex`, `obsidian.py`, `TestRiskManager`, `test_live_safety.py`, `_pid_alive`, `test_memory.py`, `Genome`, `test_walkforward.py`, `TestAgentEndToEnd`, `TestAgentUniverse`, `FakeExchange`, `SyntheticProvider`, `TestMultiSymbolReconcileKeepsEveryHolding`, `test_dashboard_and_cli.py`, `.load`, `TestDashboardIntegration`, `TestDashboardPage`, `TestCheckEntryCorrelationCap`?**
  _High betweenness centrality (0.281) - this node is a cross-community bridge._
- **Why does `DualBrain` connect `DualBrain` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `EvolutionEngine`, `test_risk_and_agent.py`, `Hippocampus`, `Signal`, `DivergenceTestCase`, `agent.py`, `cli.py`, `types.py`, `RiskManager`, `Cortex`, `TestRiskManager`, `Lesson`, `test_memory.py`, `test_walkforward.py`, `SyntheticProvider`, `test_dashboard_and_cli.py`, `TestDashboardIntegration`, `TestDashboardPage`, `TestCheckEntryCorrelationCap`, `MemoryBias`, `Recall`, `Trade`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `Genome` connect `Genome` to `dashboard.py`, `Config`, `EvolutionEngine`, `genome_with`, `indicators.py`, `SyntheticProvider`, `backtest.py`, `agent.py`, `cli.py`, `TradingAgent`, `Frame`, `.cycle`, `.random`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `Config` (e.g. with `_acquire_lock()` and `TradingAgent`) actually correct?**
  _`Config` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `DualBrain` (e.g. with `Cortex` and `Recall`) actually correct?**
  _`DualBrain` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Candle` (e.g. with `TestPairwiseCorrelation` and `CorrelatedProvider`) actually correct?**
  _`Candle` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `Genome` (e.g. with `simulate()` and `walk_forward()`) actually correct?**
  _`Genome` has 17 INFERRED edges - model-reasoned connections that need verification._