# Graph Report - self_evolving_trader  (2026-08-27)

## Corpus Check
- 49 files · ~47,264 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1088 nodes · 2599 edges · 70 communities (54 shown, 16 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 168 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `52027093`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- dashboard.py
- test_correlation.py
- PaperBroker
- EvolutionEngine
- reflect.py
- Any
- indicators.py
- Hippocampus
- simulate
- test_dashboard_and_cli.py
- walk_forward
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
- Genome
- _pid_alive
- HashingEmbedder
- Config
- TestBackwardCompatibility
- Candle
- engine.py
- TestAgentEndToEnd
- TestAgentUniverse
- Correlation
- FakeExchange
- TestCorrelationWindow
- TestMultiSymbolReconcileKeepsEveryHolding
- _as_markets
- TestCashIsNeverOverdrawn
- BrokerOrderError
- TestCorrelatedExposureCapBinds
- TestStateAndStorage
- TestDashboardIntegration
- TestIndicators
- TestResumeRebaselinesWatermarks
- safe_name
- self-evolving-crypto-agent
- test_evolution_fixes.py
- MemoryBias
- .closed_candles
- .remember
- Trade
- CachedProvider
- TestPortfolioRisk
- TestKillSwitchDoesNotTrapPositions
- .__init__
- .snapshot
- RiskDecision

## God Nodes (most connected - your core abstractions)
1. `Config` - 141 edges
2. `DualBrain` - 98 edges
3. `Candle` - 70 edges
4. `TradingAgent` - 55 edges
5. `Signal` - 55 edges
6. `Genome` - 54 edges
7. `Hippocampus` - 46 edges
8. `Trade` - 39 edges
9. `RiskManager` - 39 edges
10. `Lesson` - 34 edges

## Surprising Connections (you probably didn't know these)
- `TestBookInvariants` --uses--> `TradingAgent`  [INFERRED]
  tests/test_invariants.py → crypto_agent/agent.py
- `TestCorrelatedExposureCapBinds` --uses--> `TradingAgent`  [INFERRED]
  tests/test_invariants.py → crypto_agent/agent.py
- `TestKillSwitchDoesNotTrapPositions` --uses--> `TradingAgent`  [INFERRED]
  tests/test_invariants.py → crypto_agent/agent.py
- `TestStateAndStorage` --uses--> `TradingAgent`  [INFERRED]
  tests/test_invariants.py → crypto_agent/agent.py
- `TestAgentEndToEnd` --uses--> `TradingAgent`  [INFERRED]
  tests/test_risk_and_agent.py → crypto_agent/agent.py

## Import Cycles
- None detected.

## Communities (70 total, 16 thin omitted)

### Community 0 - "dashboard.py"
Cohesion: 0.06
Nodes (52): _compare_symbol(), DivergenceReport, FillComparison, _mean_bps(), measure_divergence(), _pool(), Live-vs-backtest divergence for the champion genome. Nothing else in the agent…, The full comparison: one :class:`SymbolDivergence` per market, the pooled total… (+44 more)

### Community 1 - "test_correlation.py"
Cohesion: 0.15
Nodes (9): _candles_from_returns(), Correlation measurement, clustering, and the risk manager's cluster cap., Cached per bar, but under one key - a key per bar would leak a kv row on every…, Build a candle series whose closes follow the given log returns. ``skip_every``…, A caller must never mistake "unknown" for a genuine zero correlation., _returns(), TestCheckEntryCorrelationCap, TestClustering (+1 more)

### Community 2 - "PaperBroker"
Cohesion: 0.07
Nodes (10): PaperBroker, Simulated fills, real bookkeeping., Units of the primary symbol - the single-symbol convenience view., Cash plus every holding marked to the prices given. Accepts a single price…, Paper trading has no external venue to drift from - the local book *is* the…, PartialFillBroker, A paper broker that fills only a fraction of what it is asked for., TestPaperBroker (+2 more)

### Community 3 - "EvolutionEngine"
Cohesion: 0.18
Nodes (7): Evaluation, EvolutionEngine, GenerationReport, Any, Score a genome across the whole universe. A strategy that only works on one…, Pull mutation bias out of Brain 2's reflections., Promote on out-of-sample evidence only, and only by a clear margin. Churning…

### Community 4 - "reflect.py"
Cohesion: 0.09
Nodes (15): HeuristicReflector, LLMReflector, make_reflector(), Any, Reflection: turning outcomes into hypotheses. Consolidation (in…, Only real genes, only sane magnitudes. Applies to LLM output too., Optional Claude-powered reflection over the recent trade log., Rule-based post-mortem over recent trades. (+7 more)

### Community 5 - "Any"
Cohesion: 0.14
Nodes (6): Gene, Any, Random, Fill gaps, clamp everything into range, enforce cross-gene sanity., Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Uniform crossover; numeric genes may also blend. Which parent a gene picks…

### Community 6 - "indicators.py"
Cohesion: 0.19
Nodes (22): atr(), bollinger_z(), donchian_position(), ema(), last_valid(), macd_hist(), Technical indicators in pure Python. Each function takes a list of floats (or…, How many standard deviations price sits from its own mean. (+14 more)

### Community 7 - "Hippocampus"
Cohesion: 0.09
Nodes (8): Hippocampus, _now_ms(), Any, Path, Durable, exact memory. Safe to share across threads., _row_to_genome(), _row_to_trade(), Row

### Community 8 - "simulate"
Cohesion: 0.10
Nodes (26): Position, clamp(), simulate(), blended_score(), exit_price_for(), exit_reason(), Frame, initial_stops() (+18 more)

### Community 9 - "test_dashboard_and_cli.py"
Cohesion: 0.13
Nodes (3): candles(), TestCharts, TestDashboardPage

### Community 10 - "walk_forward"
Cohesion: 0.22
Nodes (7): Fold, One anchored walk-forward split: everything up to a point to fit on, and the…, Aggregate in-sample and out-of-sample results, plus the fold-by-fold detail…, Anchored, multi-fold walk-forward evaluation. A single fixed hold-out at the…, walk_forward(), WalkForwardResult, TestAnchoredWalkForward

### Community 11 - "Signal"
Cohesion: 0.15
Nodes (8): _position_to_dict(), Brain 1 - episodic / structured memory (SQLite). This is the agent's ledger and…, The two brains, wired together. ``DualBrain`` is the only object the rest of…, A strategy's opinion at one point in time., Signal, make_trade(), TestDualBrain, Regression tests for the risk-manager resume() kill switch and the…

### Community 12 - "DivergenceTestCase"
Cohesion: 0.11
Nodes (10): DivergenceTestCase, No live trades at all - every entry the model would have taken was vetoed by…, The two scenarios must not collapse into the same generic text - this is the…, A risk veto is classified separately from a memory veto., A missed entry with no veto logged at all is neither a fill problem nor a…, Live fills that are worse than the model assumed, with every entry matched and…, TestBehaviouralDivergence, TestFillDivergence (+2 more)

### Community 13 - "agent.py"
Cohesion: 0.15
Nodes (15): The autonomous agent loop. One iteration is: perceive -> recall -> decide ->…, Configuration for the autonomous agent. Precedence: explicit kwargs >…, Fill, timeframe_ms(), make_provider(), Market data providers. Three sources, one interface: * ``SyntheticProvider`` -…, Regime-switching geometric brownian motion with fat tails. Not a claim about…, SyntheticProvider (+7 more)

### Community 14 - "cli.py"
Cohesion: 0.12
Nodes (26): ArgumentParser, build_parser(), cmd_backtest(), cmd_dashboard(), cmd_demo(), cmd_evolve(), cmd_memory(), cmd_obsidian() (+18 more)

### Community 15 - "TradingAgent"
Cohesion: 0.16
Nodes (6): Any, Sleep and dream: consolidate memories, then evolve., Run autonomously until stopped (or ``max_steps`` cycles). A cycle is one pass…, Trust the exchange over our own records before trading anything. A process that…, _release_lock(), TradingAgent

### Community 16 - "DualBrain"
Cohesion: 0.23
Nodes (6): DualBrain, Any, export_vault(), Mirror both brains into an Obsidian vault at ``vault_dir``. Read-only with…, make_trade(), TestExportVault

### Community 17 - ".make_broker"
Cohesion: 0.18
Nodes (3): TestLiveModeGates, TestQuantityRounding, TestReconcile

### Community 18 - "cortex.py"
Cohesion: 0.20
Nodes (9): Brain 2 - semantic / associative memory. Where Brain 1 answers "what happened…, Retrieve the memories most relevant to ``query``. Ranking blends three things:…, cosine(), Embedder, pack(), Protocol, Embeddings for Brain 2. The default embedder is a deterministic hashing…, Cosine similarity; inputs are expected to be L2-normalised already. (+1 more)

### Community 19 - "types.py"
Cohesion: 0.23
Nodes (7): bars_per_year(), Core value types shared by every layer of the agent. Everything here is plain…, compute_metrics(), Event-driven backtester. Deliberately pessimistic: fees on both sides, slippage…, The strategy genome - the thing that actually evolves. A genome is a flat,…, Tests for ``crypto_agent.analysis.divergence``. The two behavioural tests build…, Tests for the buy-and-hold benchmark, anchored walk-forward folds, and the…

### Community 20 - "CcxtBroker"
Cohesion: 0.17
Nodes (6): CcxtBroker, Any, Live exchange orders through ccxt. Opt-in, guarded, and audited. Keeps a…, The exchange's LOT_SIZE increment for ``symbol``, or ``None`` when the market…, Round ``qty`` down to the venue's step size - never up, because rounding up can…, Cash plus every holding marked to the prices given. Accepts a single price…

### Community 21 - "RiskManager"
Cohesion: 0.24
Nodes (5): Update the drawdown watermark and trip the kill switch if breached., Approve or refuse a new entry, sizing it within every active limit.…, Manual restart after a kill switch. Never called automatically - an agent that…, Best available estimate of current equity, for re-baselining on resume. Brain 1…, RiskManager

### Community 22 - "make_agent"
Cohesion: 0.18
Nodes (6): first_ts(), make_agent(), The half that did not sell is still real exposure., The partial-exit handling must not leave dust behind on a clean exit., TestEntryFollowsTheFill, TestExitFollowsTheFill

### Community 23 - "make_config"
Cohesion: 0.22
Nodes (6): first_ts(), make_config(), Caches keyed by bar timestamp would leave one dead row per bar., The bug this suite was written for: sizing rescaled past the cash clamp, so the…, Brain 1's positions and the broker's holdings are two records of the same fact;…, TestBookInvariants

### Community 24 - ".cycle"
Cohesion: 0.13
Nodes (10): CycleResult, _fmt_ts(), Manage an open position with the genome that opened it. A promotion mid-trade…, One decision on the primary symbol - the single-market view., Walk the whole universe once: perceive, then decide per symbol., What the agent decided about one symbol on one bar., Current exposure per market, in quote currency., One pass over the whole universe. (+2 more)

### Community 25 - "Cortex"
Cohesion: 0.19
Nodes (5): Cortex, Any, One recalled memory plus the scores that surfaced it., Vector memory with decay, reinforcement and pruning., Recall

### Community 26 - "Self-Evolving Crypto Trading Agent"
Cohesion: 0.12
Nodes (16): Autonomy and safety, CLI, Configuration, Dashboard, Going live (only when you mean it), Honest limits, Layout, Obsidian vault — reading the agent's mind (+8 more)

### Community 27 - "obsidian.py"
Cohesion: 0.21
Nodes (21): ExportReport, _frontmatter(), _index_note(), iter_note_paths(), _lesson_notes(), _lesson_symbol(), _market_notes(), _month() (+13 more)

### Community 29 - "test_live_safety.py"
Cohesion: 0.16
Nodes (7): CcxtBrokerTestCase, Safety tests for CcxtBroker: order-quantity rounding, the live-mode gates, and…, ``TradingAgent.cycle()`` and ``status()`` always call ``equity()`` with a…, ``Fill.qty`` must always be what the exchange actually filled, never the…, Base class that arms the live-mode gates and injects a fake ccxt., TestEquityAcceptsThePriceMapAgentActuallyPasses, TestPartialFillReportsTruth

### Community 30 - "Lesson"
Cohesion: 0.23
Nodes (5): _group_lessons(), Turn recent raw episodes into generalisations. Triggered by new trades, but…, Lesson, A natural-language memory written into Brain 2., TestCortex

### Community 31 - "Genome"
Cohesion: 0.12
Nodes (6): Genome, Normalised gene-space distance, used to keep the population diverse., warmup_bars(), ``roll < 0.4`` gated a choice of ``a if roll < 0.5 else b`` - since the gate…, TestCrossoverProvenance, TestGenome

### Community 32 - "_pid_alive"
Cohesion: 0.20
Nodes (8): _acquire_lock(), _pid_alive(), _pid_alive_windows(), Refuse to run two agents against one set of brains., Is this PID still running? ``os.kill(pid, 0)`` is the POSIX idiom, but on…, The lockfile's liveness probe must never be able to kill anything., os.kill on Windows terminates; the probe must not go near it., TestProcessLiveness

### Community 33 - "HashingEmbedder"
Cohesion: 0.17
Nodes (6): Path, HashingEmbedder, l2_normalize(), Stable bag-of-ngrams vectoriser using blake2b for bucket assignment., tokenize(), TestEmbeddings

### Community 34 - "Config"
Cohesion: 0.05
Nodes (23): _coerce(), Config, Any, Path, Coerce strings coming from env/JSON into the dataclass field type., Every symbol the agent trades, primary first, de-duplicated. One process…, buy_and_hold(), position_size() (+15 more)

### Community 36 - "Candle"
Cohesion: 0.13
Nodes (8): Candle, BinancePublicProvider, CcxtProvider, _dedupe(), Public klines endpoint. No API key, no dependencies, read-only., Any ccxt exchange. ``pip install ccxt`` to enable., CorrelatedProvider, Markets that move together, the way real majors do. The synthetic provider…

### Community 37 - "engine.py"
Cohesion: 0.18
Nodes (10): BacktestMetrics, BacktestResult, fitness_score(), Risk-adjusted score used as the GA's selection pressure. Sharpe is the…, Random, The evolution engine. A steady-state genetic algorithm over strategy genomes,…, _aggregate_metrics(), Pool several fold results into one summary metric set. Trade counts sum… (+2 more)

### Community 40 - "Correlation"
Cohesion: 0.13
Nodes (16): align_closes(), cluster_symbols(), Correlation, log_returns(), pearson(), How correlated two markets are, measured from their candle closes. The…, Pearson correlation of log returns between two candle series, aligned on…, Group symbols into clusters where any pair above ``threshold`` is linked. This… (+8 more)

### Community 41 - "FakeExchange"
Cohesion: 0.12
Nodes (7): Pull the exchange's LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL metadata once. Not every…, Read cash plus every tracked symbol's base-asset balance. This must cover the…, Re-fetch the real balance (and open orders) and make the local cache match it,…, What ``reconcile()`` found when it checked the local book against the source of…, ReconcileReport, FakeExchange, Just enough of ccxt's unified exchange interface for CcxtBroker.

### Community 43 - "TestMultiSymbolReconcileKeepsEveryHolding"
Cohesion: 0.22
Nodes (3): A ``--top5``-style universe holds positions in more than one symbol.…, TestMultiSymbolReconcileKeepsEveryHolding, TestPaperBrokerReconcile

### Community 44 - "_as_markets"
Cohesion: 0.50
Nodes (3): _as_markets(), Accept a symbol->candles map, or a bare series for the single-market case., History

### Community 45 - "TestCashIsNeverOverdrawn"
Cohesion: 0.22
Nodes (4): A spot book cannot spend money it does not have. position_size() fits the order…, What the broker will actually take out of cash: the slipped fill price plus the…, Selling short raises cash rather than spending it., TestCashIsNeverOverdrawn

### Community 46 - "BrokerOrderError"
Cohesion: 0.33
Nodes (4): BrokerOrderError, A live order was rejected, or its outcome could not be confirmed as a fill.…, RuntimeError, TestOrderFailureHandling

### Community 49 - "TestDashboardIntegration"
Cohesion: 0.13
Nodes (8): make_candles(), Candles are cached and the model may well find entries in them, but with no…, The dashboard must render (and stay self-contained) whether or not there is…, A synthetic series with a slow, noisy oscillating drift - long enough to warm…, The archetype ``seed_population`` seeds first - reliably trades on the…, TestDashboardIntegration, TestGracefulDegradation, trend_follower_genome()

### Community 52 - "safe_name"
Cohesion: 0.24
Nodes (5): Turn a symbol or lesson title into a filename safe everywhere. ``BTC/USDT``…, ``safe_name`` plus a deterministic suffix when two inputs collide. Slugging is…, safe_name(), unique_name(), TestSafeName

### Community 59 - "test_evolution_fixes.py"
Cohesion: 0.15
Nodes (9): _deflation_penalty(), How much to subtract from fitness for having already looked at this data…, _make_eval(), Regression tests for three genetic-algorithm correctness bugs. Each test embeds…, The champion's stored oos_fitness is deflated at its crowning trial count;…, Every other path in ``breed`` (seed_population, crossover+mutate) clamps…, Build an Evaluation with a known undeflated score, deflated at ``trials``.…, TestBreedRespectsAllowShortOnEveryPath (+1 more)

### Community 60 - "MemoryBias"
Cohesion: 0.25
Nodes (4): _clamp(), MemoryBias, The query Brain 2 is searched with - deliberately written in the same…, What Brain 2 wants to change about the decision Brain 1's strategy made.

### Community 62 - ".remember"
Cohesion: 0.33
Nodes (4): hash_text(), _now_ms(), Store a lesson. Re-learning the same text reinforces it instead of duplicating…, Forget the least useful memories once over capacity.

### Community 63 - "Trade"
Cohesion: 0.29
Nodes (5): A closed trade lands in both brains: the row in Brain 1, the story in Brain 2., Every market worth a note: configured, traded, or currently held., _symbol_universe(), A round trip, written to Brain 1 and distilled into Brain 2., Trade

### Community 64 - "CachedProvider"
Cohesion: 0.29
Nodes (4): CachedProvider, MarketDataProvider, Protocol, Persist every candle in Brain 1 and survive network outages.

## Knowledge Gaps
- **15 isolated node(s):** `self-evolving-crypto-agent`, `Quickstart`, `The two brains`, `Trading a universe`, `Self-evolution` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Config` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `reflect.py`, `simulate`, `test_dashboard_and_cli.py`, `walk_forward`, `Signal`, `DivergenceTestCase`, `agent.py`, `cli.py`, `TradingAgent`, `DualBrain`, `.make_broker`, `types.py`, `make_agent`, `make_config`, `.cycle`, `obsidian.py`, `TestRiskManager`, `test_live_safety.py`, `_pid_alive`, `HashingEmbedder`, `TestBackwardCompatibility`, `engine.py`, `TestAgentEndToEnd`, `TestAgentUniverse`, `FakeExchange`, `TestCorrelationWindow`, `TestMultiSymbolReconcileKeepsEveryHolding`, `TestCashIsNeverOverdrawn`, `TestDashboardIntegration`, `TestResumeRebaselinesWatermarks`, `test_evolution_fixes.py`, `Trade`, `TestPortfolioRisk`, `.__init__`?**
  _High betweenness centrality (0.285) - this node is a cross-community bridge._
- **Why does `DualBrain` connect `DualBrain` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `reflect.py`, `Hippocampus`, `test_dashboard_and_cli.py`, `Signal`, `DivergenceTestCase`, `agent.py`, `cli.py`, `types.py`, `.cycle`, `Cortex`, `TestRiskManager`, `Lesson`, `HashingEmbedder`, `Config`, `TestBackwardCompatibility`, `Candle`, `engine.py`, `TestCorrelationWindow`, `TestCashIsNeverOverdrawn`, `TestDashboardIntegration`, `TestResumeRebaselinesWatermarks`, `test_evolution_fixes.py`, `MemoryBias`, `Trade`, `TestPortfolioRisk`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `Candle` connect `Candle` to `dashboard.py`, `test_correlation.py`, `indicators.py`, `Hippocampus`, `simulate`, `test_dashboard_and_cli.py`, `walk_forward`, `Signal`, `agent.py`, `TradingAgent`, `types.py`, `RiskManager`, `.cycle`, `Config`, `engine.py`, `Correlation`, `TestCorrelationWindow`, `_as_markets`, `TestDashboardIntegration`, `TestIndicators`, `.closed_candles`, `CachedProvider`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Are the 41 inferred relationships involving `Config` (e.g. with `_acquire_lock()` and `TradingAgent`) actually correct?**
  _`Config` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `DualBrain` (e.g. with `Cortex` and `Recall`) actually correct?**
  _`DualBrain` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Candle` (e.g. with `TestPairwiseCorrelation` and `CorrelatedProvider`) actually correct?**
  _`Candle` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `TradingAgent` (e.g. with `Config` and `_replay_clock()`) actually correct?**
  _`TradingAgent` has 8 INFERRED edges - model-reasoned connections that need verification._