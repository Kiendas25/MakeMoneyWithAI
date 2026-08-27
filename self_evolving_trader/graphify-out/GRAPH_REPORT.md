# Graph Report - self_evolving_trader  (2026-08-27)

## Corpus Check
- 52 files · ~50,716 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1174 nodes · 2788 edges · 71 communities (58 shown, 13 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 176 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d476c7f4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- dashboard.py
- _candles_from_returns
- PaperBroker
- EvolutionEngine
- reflect.py
- test_regime_and_costs.py
- indicators.py
- Hippocampus
- TestTrailingStopLookahead
- TestDashboardPage
- backtest.py
- Signal
- test_divergence.py
- types.py
- cli.py
- TradingAgent
- DualBrain
- .make_broker
- cortex.py
- Broker
- CcxtBroker
- RiskManager
- make_agent
- make_config
- .cycle
- Cortex
- Self-Evolving Crypto Trading Agent
- obsidian.py
- TestRiskManager
- test_promotion_gate.py
- Lesson
- Genome
- _pid_alive
- HashingEmbedder
- Config
- min_edge_for
- Candle
- BacktestMetrics
- TestAgentEndToEnd
- TestDecisionReasons
- Correlation
- ReconcileReport
- SyntheticProvider
- _decision_bucket
- TestStoredConfigAdoption
- simulate
- TestCashIsNeverOverdrawn
- Position
- TestBacktest
- TestDashboardIntegration
- TestIndicators
- TestCorrelationWindow
- safe_name
- self-evolving-crypto-agent
- TestCheckEntryCorrelationCap
- MemoryBias
- TestMultiAssetBook
- TestResumeRebaselinesWatermarks
- Trade
- .__init__
- TestBackwardCompatibility
- Embedder
- TestCorrelatedExposureCapBinds
- _row_to_trade
- .distance
- .__init__

## God Nodes (most connected - your core abstractions)
1. `Config` - 148 edges
2. `DualBrain` - 102 edges
3. `Candle` - 73 edges
4. `Genome` - 59 edges
5. `Signal` - 57 edges
6. `TradingAgent` - 55 edges
7. `Hippocampus` - 50 edges
8. `Trade` - 39 edges
9. `RiskManager` - 39 edges
10. `Lesson` - 34 edges

## Surprising Connections (you probably didn't know these)
- `Coerce strings coming from env/JSON into the dataclass field type.` --rationale_for--> `_coerce()`  [EXTRACTED]
  crypto_agent/config.py → self_evolving_trader/crypto_agent/config.py
- `warmup_bars()` --uses--> `Genome`  [INFERRED]
  self_evolving_trader/crypto_agent/strategy/rules.py → self_evolving_trader/crypto_agent/strategy/genome.py
- `Start from a few hand-written archetypes, then fill with randoms. Pure random…` --rationale_for--> `seed_population()`  [EXTRACTED]
  crypto_agent/strategy/genome.py → self_evolving_trader/crypto_agent/strategy/genome.py
- `A coarse, human-readable label. Brain 2 groups its lessons by this, so it has…` --rationale_for--> `regime_at()`  [EXTRACTED]
  crypto_agent/strategy/rules.py → self_evolving_trader/crypto_agent/strategy/rules.py
- `Each module votes in [-1, 1]. Positive means "be long".` --rationale_for--> `module_scores()`  [EXTRACTED]
  crypto_agent/strategy/rules.py → self_evolving_trader/crypto_agent/strategy/rules.py

## Import Cycles
- None detected.

## Communities (71 total, 13 thin omitted)

### Community 0 - "dashboard.py"
Cohesion: 0.06
Nodes (52): _compare_symbol(), DivergenceReport, FillComparison, _mean_bps(), measure_divergence(), _pool(), Live-vs-backtest divergence for the champion genome. Nothing else in the agent…, The full comparison: one :class:`SymbolDivergence` per market, the pooled total… (+44 more)

### Community 1 - "_candles_from_returns"
Cohesion: 0.27
Nodes (6): _candles_from_returns(), Build a candle series whose closes follow the given log returns. ``skip_every``…, A caller must never mistake "unknown" for a genuine zero correlation., _returns(), TestClustering, TestPairwiseCorrelation

### Community 2 - "PaperBroker"
Cohesion: 0.12
Nodes (5): PaperBroker, Simulated fills, real bookkeeping., Units of the primary symbol - the single-symbol convenience view., Cash plus every holding marked to the prices given. Accepts a single price…, TestPaperBroker

### Community 3 - "EvolutionEngine"
Cohesion: 0.08
Nodes (23): BacktestResult, _as_markets(), _deflation_penalty(), Evaluation, EvolutionEngine, GenerationReport, Any, Random (+15 more)

### Community 4 - "reflect.py"
Cohesion: 0.16
Nodes (11): HeuristicReflector, LLMReflector, make_reflector(), Any, Reflection: turning outcomes into hypotheses. Consolidation (in…, Only real genes, only sane magnitudes. Applies to LLM output too., Optional Claude-powered reflection over the recent trade log., Rule-based post-mortem over recent trades. (+3 more)

### Community 5 - "test_regime_and_costs.py"
Cohesion: 0.12
Nodes (11): Fill gaps, clamp everything into range, enforce cross-gene sanity., Fill gaps, clamp everything into range, enforce cross-gene sanity., flat_candles(), genome_with(), The two gates that stop a genome trading a setup it cannot win. Both exist…, A range: no drift, small alternating moves, so slope stays near zero., An uptrend. Growth is compounded, not linear: `slope` normalises by the window…, TestCostFloor (+3 more)

### Community 6 - "indicators.py"
Cohesion: 0.17
Nodes (21): atr(), bollinger_z(), donchian_position(), ema(), last_valid(), macd_hist(), Technical indicators in pure Python. Each function takes a list of floats (or…, How many standard deviations price sits from its own mean. (+13 more)

### Community 7 - "Hippocampus"
Cohesion: 0.11
Nodes (5): Hippocampus, _now_ms(), Any, Durable, exact memory. Safe to share across threads., _row_to_genome()

### Community 8 - "TestTrailingStopLookahead"
Cohesion: 0.29
Nodes (5): _flat_frame(), A minimal Frame for exercising update_trailing_stop/exit_reason in isolation:…, BUG 2 regression: the stop must be tested against the level known before a bar…, On a constructed two-bar series, the buggy ordering manufactures a stop exit on…, TestTrailingStopLookahead

### Community 9 - "TestDashboardPage"
Cohesion: 0.12
Nodes (3): candles(), TestCharts, TestDashboardPage

### Community 10 - "backtest.py"
Cohesion: 0.14
Nodes (12): bars_per_year(), _aggregate_metrics(), compute_metrics(), Fold, Event-driven backtester. Deliberately pessimistic: fees on both sides, slippage…, One anchored walk-forward split: everything up to a point to fit on, and the…, Aggregate in-sample and out-of-sample results, plus the fold-by-fold detail…, Pool several fold results into one summary metric set. Trade counts sum… (+4 more)

### Community 11 - "Signal"
Cohesion: 0.14
Nodes (5): A strategy's opinion at one point in time., Signal, make_trade(), TestDualBrain, TestPortfolioRisk

### Community 12 - "test_divergence.py"
Cohesion: 0.11
Nodes (11): DivergenceTestCase, Tests for ``crypto_agent.analysis.divergence``. The two behavioural tests build…, No live trades at all - every entry the model would have taken was vetoed by…, The two scenarios must not collapse into the same generic text - this is the…, A risk veto is classified separately from a memory veto., A missed entry with no veto logged at all is neither a fill problem nor a…, Live fills that are worse than the model assumed, with every entry matched and…, TestBehaviouralDivergence (+3 more)

### Community 13 - "types.py"
Cohesion: 0.15
Nodes (18): The autonomous agent loop. One iteration is: perceive -> recall -> decide ->…, Brain 1 - episodic / structured memory (SQLite). This is the agent's ledger and…, The two brains, wired together. ``DualBrain`` is the only object the rest of…, Configuration for the autonomous agent. Precedence: explicit kwargs >…, Core value types shared by every layer of the agent. Everything here is plain…, timeframe_ms(), cluster_symbols(), How correlated two markets are, measured from their candle closes. The… (+10 more)

### Community 14 - "cli.py"
Cohesion: 0.22
Nodes (22): ArgumentParser, build_parser(), cmd_backtest(), cmd_dashboard(), cmd_demo(), cmd_evolve(), cmd_memory(), cmd_obsidian() (+14 more)

### Community 15 - "TradingAgent"
Cohesion: 0.13
Nodes (8): Any, Only fully closed bars. Acting on a forming candle is how a backtest that looks…, Fetch every symbol before deciding anything. Marking the book to market needs…, Sleep and dream: consolidate memories, then evolve., Run autonomously until stopped (or ``max_steps`` cycles). A cycle is one pass…, Trust the exchange over our own records before trading anything. A process that…, _release_lock(), TradingAgent

### Community 16 - "DualBrain"
Cohesion: 0.22
Nodes (5): DualBrain, Any, export_vault(), Mirror both brains into an Obsidian vault at ``vault_dir``. Read-only with…, TestExportVault

### Community 17 - ".make_broker"
Cohesion: 0.08
Nodes (16): BrokerOrderError, A live order was rejected, or its outcome could not be confirmed as a fill.…, RuntimeError, CcxtBrokerTestCase, Safety tests for CcxtBroker: order-quantity rounding, the live-mode gates, and…, ``TradingAgent.cycle()`` and ``status()`` always call ``equity()`` with a…, ``Fill.qty`` must always be what the exchange actually filled, never the…, A ``--top5``-style universe holds positions in more than one symbol.… (+8 more)

### Community 18 - "cortex.py"
Cohesion: 0.17
Nodes (10): hash_text(), Brain 2 - semantic / associative memory. Where Brain 1 answers "what happened…, Retrieve the memories most relevant to ``query``. Ranking blends three things:…, One recalled memory plus the scores that surfaced it., Recall, cosine(), pack(), Embeddings for Brain 2. The default embedder is a deterministic hashing… (+2 more)

### Community 19 - "Broker"
Cohesion: 0.12
Nodes (9): Fill, Broker, make_broker(), Protocol, Everything the agent actually calls on a broker. This declared only…, EmptyFillBroker, PartialFillBroker, A paper broker that fills only a fraction of what it is asked for. (+1 more)

### Community 20 - "CcxtBroker"
Cohesion: 0.09
Nodes (11): CcxtBroker, Any, Live exchange orders through ccxt. Opt-in, guarded, and audited. Keeps a…, Pull the exchange's LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL metadata once. Not every…, The exchange's LOT_SIZE increment for ``symbol``, or ``None`` when the market…, Round ``qty`` down to the venue's step size - never up, because rounding up can…, Read cash plus every tracked symbol's base-asset balance. This must cover the…, Cash plus every holding marked to the prices given. Accepts a single price… (+3 more)

### Community 21 - "RiskManager"
Cohesion: 0.12
Nodes (11): Any, Update the drawdown watermark and trip the kill switch if breached., Approve or refuse a new entry, sizing it within every active limit.…, None if the new position is fine; otherwise the refusal reason. A new entry is…, Cluster the given symbols by correlation, cached per bar in Brain 1. Five…, The trading day of a *market* timestamp. Deriving the day from the bar being…, Manual restart after a kill switch. Never called automatically - an agent that…, Best available estimate of current equity, for re-baselining on resume. Brain 1… (+3 more)

### Community 22 - "make_agent"
Cohesion: 0.18
Nodes (6): first_ts(), make_agent(), The half that did not sell is still real exposure., The partial-exit handling must not leave dust behind on a clean exit., TestEntryFollowsTheFill, TestExitFollowsTheFill

### Community 23 - "make_config"
Cohesion: 0.13
Nodes (9): first_ts(), make_config(), A halt must stop new risk, not imprison existing risk. An agent that cannot…, Caches keyed by bar timestamp would leave one dead row per bar., The bug this suite was written for: sizing rescaled past the cash clamp, so the…, Brain 1's positions and the broker's holdings are two records of the same fact;…, TestBookInvariants, TestKillSwitchDoesNotTrapPositions (+1 more)

### Community 24 - ".cycle"
Cohesion: 0.15
Nodes (9): CycleResult, _fmt_ts(), Manage an open position with the genome that opened it. A promotion mid-trade…, One decision on the primary symbol - the single-market view., Walk the whole universe once: perceive, then decide per symbol., What the agent decided about one symbol on one bar., Current exposure per market, in quote currency., One pass over the whole universe. (+1 more)

### Community 25 - "Cortex"
Cohesion: 0.17
Nodes (6): Cortex, _now_ms(), Any, Store a lesson. Re-learning the same text reinforces it instead of duplicating…, Forget the least useful memories once over capacity., Vector memory with decay, reinforcement and pruning.

### Community 26 - "Self-Evolving Crypto Trading Agent"
Cohesion: 0.10
Nodes (19): Autonomy and safety, CLI, Configuration, Dashboard, Going live (only when you mean it), Honest limits, Layout, Obsidian vault — reading the agent's mind (+11 more)

### Community 27 - "obsidian.py"
Cohesion: 0.18
Nodes (23): ExportReport, _frontmatter(), _index_note(), iter_note_paths(), _lesson_notes(), _lesson_symbol(), _market_notes(), _month() (+15 more)

### Community 29 - "test_promotion_gate.py"
Cohesion: 0.30
Nodes (3): evaluation(), The gate that stops a genome being crowned for fitting the fit window. From a…, TestGeneralisationGate

### Community 30 - "Lesson"
Cohesion: 0.23
Nodes (5): _group_lessons(), Turn recent raw episodes into generalisations. Triggered by new trades, but…, Lesson, A natural-language memory written into Brain 2., TestCortex

### Community 31 - "Genome"
Cohesion: 0.08
Nodes (16): Gene, Genome, Any, Random, The strategy genome - the thing that actually evolves. A genome is a flat,…, Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Uniform crossover; numeric genes may also blend. Which parent a gene picks… (+8 more)

### Community 32 - "_pid_alive"
Cohesion: 0.24
Nodes (6): _pid_alive(), _pid_alive_windows(), Is this PID still running? ``os.kill(pid, 0)`` is the POSIX idiom, but on…, The lockfile's liveness probe must never be able to kill anything., os.kill on Windows terminates; the probe must not go near it., TestProcessLiveness

### Community 33 - "HashingEmbedder"
Cohesion: 0.21
Nodes (5): HashingEmbedder, l2_normalize(), Stable bag-of-ngrams vectoriser using blake2b for bucket assignment., tokenize(), TestEmbeddings

### Community 34 - "Config"
Cohesion: 0.09
Nodes (13): _acquire_lock(), Refuse to run two agents against one set of brains., _coerce(), Config, Any, Path, Every symbol the agent trades, primary first, de-duplicated. One process…, Coerce strings coming from env/JSON into the dataclass field type. (+5 more)

### Community 35 - "min_edge_for"
Cohesion: 0.40
Nodes (5): min_edge_for(), Any, Fraction of notional a full open-and-close gives away to the venue., The cost floor a setup's target has to clear, from a config. Takes the config…, round_trip_cost()

### Community 36 - "Candle"
Cohesion: 0.14
Nodes (9): Candle, BinancePublicProvider, _dedupe(), Public klines endpoint. No API key, no dependencies, read-only., exit_price_for(), Where a given exit reason actually fills., Where a given exit reason actually fills., CorrelatedProvider (+1 more)

### Community 37 - "BacktestMetrics"
Cohesion: 0.31
Nodes (5): BacktestMetrics, fitness_score(), Risk-adjusted score used as the GA's selection pressure. Sharpe is the…, The pre-existing contract: fitness_score(metrics) with no other arguments must…, TestBenchmarkAwareFitness

### Community 38 - "TestAgentEndToEnd"
Cohesion: 0.13
Nodes (4): The whole loop on deterministic offline data., TestAgentEndToEnd, The full loop, three markets, deterministic offline data., TestAgentUniverse

### Community 39 - "TestDecisionReasons"
Cohesion: 0.24
Nodes (3): Tallying why the agent did or did not open anything. Twice in one session the…, signal(), TestDecisionReasons

### Community 40 - "Correlation"
Cohesion: 0.17
Nodes (11): align_closes(), Correlation, log_returns(), pearson(), Pearson correlation of log returns between two candle series, aligned on…, The result of measuring correlation between two return series. ``value`` is…, Pair up closes from two candle series by timestamp. The two series are not…, Bar-over-bar log returns; a non-positive close yields a 0.0 return rather than… (+3 more)

### Community 41 - "ReconcileReport"
Cohesion: 0.40
Nodes (3): Paper trading has no external venue to drift from - the local book *is* the…, What ``reconcile()`` found when it checked the local book against the source of…, ReconcileReport

### Community 42 - "SyntheticProvider"
Cohesion: 0.11
Nodes (11): Regime-switching geometric brownian motion with fat tails. Not a claim about…, SyntheticProvider, buy_and_hold(), The trivial "buy once and do nothing" strategy, priced the same way…, TestEvolutionAcrossMarkets, ramp_candles(), Tests for the buy-and-hold benchmark, anchored walk-forward folds, and the…, A deterministic price path with no wicks, so the arithmetic in a test can be… (+3 more)

### Community 43 - "_decision_bucket"
Cohesion: 0.27
Nodes (4): _decision_bucket(), Why the recent decisions went the way they did, most common first. Every…, Collapse one decision into a stable category. The action says what happened;…, TestDecisionBucket

### Community 44 - "TestStoredConfigAdoption"
Cohesion: 0.19
Nodes (6): Any, The config the agent last booted with, straight out of Brain 1., stored_config(), Inspection commands must describe the agent that actually ran., A stored live mode must not arm a read-only command., TestStoredConfigAdoption

### Community 45 - "simulate"
Cohesion: 0.11
Nodes (25): clamp(), simulate(), blended_score(), compute_frame(), exit_reason(), Frame, initial_stops(), module_scores() (+17 more)

### Community 46 - "TestCashIsNeverOverdrawn"
Cohesion: 0.22
Nodes (4): A spot book cannot spend money it does not have. position_size() fits the order…, What the broker will actually take out of cash: the slipped fill price plus the…, Selling short raises cash rather than spending it., TestCashIsNeverOverdrawn

### Community 48 - "TestBacktest"
Cohesion: 0.24
Nodes (4): position_size(), Risk-based sizing: lose ``risk_per_trade`` of equity if the stop hits. The same…, A decision at bar i must not change when future bars are appended., TestBacktest

### Community 49 - "TestDashboardIntegration"
Cohesion: 0.13
Nodes (8): make_candles(), Candles are cached and the model may well find entries in them, but with no…, The dashboard must render (and stay self-contained) whether or not there is…, A synthetic series with a slow, noisy oscillating drift - long enough to warm…, The archetype ``seed_population`` seeds first - reliably trades on the…, TestDashboardIntegration, TestGracefulDegradation, trend_follower_genome()

### Community 52 - "safe_name"
Cohesion: 0.24
Nodes (5): Turn a symbol or lesson title into a filename safe everywhere. ``BTC/USDT``…, ``safe_name`` plus a deterministic suffix when two inputs collide. Slugging is…, safe_name(), unique_name(), TestSafeName

### Community 60 - "MemoryBias"
Cohesion: 0.25
Nodes (4): _clamp(), MemoryBias, The query Brain 2 is searched with - deliberately written in the same…, What Brain 2 wants to change about the decision Brain 1's strategy made.

### Community 63 - "Trade"
Cohesion: 0.33
Nodes (4): A closed trade lands in both brains: the row in Brain 1, the story in Brain 2., A round trip, written to Brain 1 and distilled into Brain 2., Trade, make_trade()

### Community 64 - ".__init__"
Cohesion: 0.18
Nodes (7): CachedProvider, CcxtProvider, make_provider(), MarketDataProvider, Protocol, Any ccxt exchange. ``pip install ccxt`` to enable., Persist every candle in Brain 1 and survive network outages.

### Community 66 - "Embedder"
Cohesion: 0.40
Nodes (3): Path, Embedder, Protocol

## Knowledge Gaps
- **18 isolated node(s):** `self-evolving-crypto-agent`, `Quickstart`, `The two brains`, `Trading a universe`, `Self-evolution` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Config` to `dashboard.py`, `_candles_from_returns`, `PaperBroker`, `EvolutionEngine`, `test_regime_and_costs.py`, `TestDashboardPage`, `backtest.py`, `Signal`, `test_divergence.py`, `types.py`, `cli.py`, `TradingAgent`, `DualBrain`, `.make_broker`, `Broker`, `CcxtBroker`, `RiskManager`, `make_agent`, `make_config`, `obsidian.py`, `TestRiskManager`, `test_promotion_gate.py`, `Genome`, `HashingEmbedder`, `TestAgentEndToEnd`, `SyntheticProvider`, `TestStoredConfigAdoption`, `simulate`, `TestCashIsNeverOverdrawn`, `TestBacktest`, `TestDashboardIntegration`, `TestCorrelationWindow`, `TestCheckEntryCorrelationCap`, `TestMultiAssetBook`, `TestResumeRebaselinesWatermarks`, `Trade`, `.__init__`, `TestBackwardCompatibility`?**
  _High betweenness centrality (0.254) - this node is a cross-community bridge._
- **Why does `DualBrain` connect `DualBrain` to `dashboard.py`, `_candles_from_returns`, `PaperBroker`, `EvolutionEngine`, `Hippocampus`, `TestDashboardPage`, `Signal`, `test_divergence.py`, `types.py`, `cli.py`, `cortex.py`, `Cortex`, `TestRiskManager`, `test_promotion_gate.py`, `Lesson`, `HashingEmbedder`, `SyntheticProvider`, `TestStoredConfigAdoption`, `TestCashIsNeverOverdrawn`, `TestDashboardIntegration`, `TestCorrelationWindow`, `TestCheckEntryCorrelationCap`, `MemoryBias`, `TestMultiAssetBook`, `TestResumeRebaselinesWatermarks`, `Trade`, `.__init__`, `TestBackwardCompatibility`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `Candle` connect `Candle` to `dashboard.py`, `_candles_from_returns`, `EvolutionEngine`, `test_regime_and_costs.py`, `indicators.py`, `Hippocampus`, `TestTrailingStopLookahead`, `TestDashboardPage`, `backtest.py`, `Signal`, `test_divergence.py`, `types.py`, `TradingAgent`, `RiskManager`, `.cycle`, `Genome`, `Correlation`, `SyntheticProvider`, `simulate`, `TestDashboardIntegration`, `TestIndicators`, `TestCorrelationWindow`, `.__init__`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Are the 43 inferred relationships involving `Config` (e.g. with `_acquire_lock()` and `TradingAgent`) actually correct?**
  _`Config` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `DualBrain` (e.g. with `Cortex` and `Recall`) actually correct?**
  _`DualBrain` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Candle` (e.g. with `TestPairwiseCorrelation` and `CorrelatedProvider`) actually correct?**
  _`Candle` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Genome` (e.g. with `simulate()` and `walk_forward()`) actually correct?**
  _`Genome` has 18 INFERRED edges - model-reasoned connections that need verification._