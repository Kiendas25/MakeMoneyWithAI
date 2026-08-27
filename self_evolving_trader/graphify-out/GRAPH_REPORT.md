# Graph Report - self_evolving_trader  (2026-08-27)

## Corpus Check
- 49 files · ~46,985 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1084 nodes · 2584 edges · 62 communities (49 shown, 13 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 168 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `108124eb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- dashboard.py
- test_correlation.py
- PaperBroker
- EvolutionEngine
- Trade
- Genome
- indicators.py
- Hippocampus
- rules.py
- TestDashboardPage
- backtest.py
- Signal
- DivergenceTestCase
- types.py
- cli.py
- TradingAgent
- DualBrain
- .make_broker
- test_memory.py
- simulate
- CcxtBroker
- RiskManager
- make_agent
- make_config
- .cycle
- Cortex
- Self-Evolving Crypto Trading Agent
- TestCharts
- TestRiskManager
- test_live_safety.py
- Lesson
- .random
- _pid_alive
- HashingEmbedder
- Config
- TestBackwardCompatibility
- Candle
- BacktestMetrics
- TestAgentEndToEnd
- TestAgentUniverse
- Position
- FakeExchange
- TestCorrelationWindow
- TestMultiSymbolReconcileKeepsEveryHolding
- TestEvolutionAcrossMarkets
- TestCashIsNeverOverdrawn
- BrokerOrderError
- CorrelatedProvider
- TestStateAndStorage
- TestEvaluateAndDeflation
- Embedder
- TestResumeRebaselinesWatermarks
- HeuristicReflector
- self-evolving-crypto-agent
- TestPromotionBarTracksTrials
- TestBreedRespectsAllowShortOnEveryPath
- .closed_candles

## God Nodes (most connected - your core abstractions)
1. `Config` - 141 edges
2. `DualBrain` - 96 edges
3. `Candle` - 70 edges
4. `TradingAgent` - 55 edges
5. `Signal` - 55 edges
6. `Genome` - 54 edges
7. `Hippocampus` - 46 edges
8. `RiskManager` - 39 edges
9. `Trade` - 38 edges
10. `Lesson` - 33 edges

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

## Communities (62 total, 13 thin omitted)

### Community 0 - "dashboard.py"
Cohesion: 0.07
Nodes (45): _compare_symbol(), DivergenceReport, FillComparison, _mean_bps(), measure_divergence(), _pool(), The full comparison: one :class:`SymbolDivergence` per market, the pooled total…, Re-simulate the current champion over the window it actually traded and compare… (+37 more)

### Community 1 - "test_correlation.py"
Cohesion: 0.08
Nodes (23): align_closes(), cluster_symbols(), Correlation, log_returns(), pearson(), How correlated two markets are, measured from their candle closes. The…, Pearson correlation of log returns between two candle series, aligned on…, Group symbols into clusters where any pair above ``threshold`` is linked. This… (+15 more)

### Community 2 - "PaperBroker"
Cohesion: 0.05
Nodes (14): Broker, make_broker(), PaperBroker, Protocol, Simulated fills, real bookkeeping., Units of the primary symbol - the single-symbol convenience view., Cash plus every holding marked to the prices given. Accepts a single price…, Paper trading has no external venue to drift from - the local book *is* the… (+6 more)

### Community 3 - "EvolutionEngine"
Cohesion: 0.16
Nodes (6): EvolutionEngine, GenerationReport, Any, Random, Pull mutation bias out of Brain 2's reflections., Promote on out-of-sample evidence only, and only by a clear margin. Churning…

### Community 4 - "Trade"
Cohesion: 0.13
Nodes (12): _row_to_trade(), A closed trade lands in both brains: the row in Brain 1, the story in Brain 2., A round trip, written to Brain 1 and distilled into Brain 2., Trade, LLMReflector, make_reflector(), Any, Reflection: turning outcomes into hypotheses. Consolidation (in… (+4 more)

### Community 5 - "Genome"
Cohesion: 0.12
Nodes (8): Gene, Genome, Any, Random, Fill gaps, clamp everything into range, enforce cross-gene sanity., Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Uniform crossover; numeric genes may also blend. Which parent a gene picks…, Normalised gene-space distance, used to keep the population diverse.

### Community 6 - "indicators.py"
Cohesion: 0.09
Nodes (24): atr(), bollinger_z(), donchian_position(), ema(), last_valid(), macd_hist(), Technical indicators in pure Python. Each function takes a list of floats (or…, How many standard deviations price sits from its own mean. (+16 more)

### Community 7 - "Hippocampus"
Cohesion: 0.10
Nodes (7): Hippocampus, _now_ms(), Any, Path, Durable, exact memory. Safe to share across threads., _row_to_genome(), Row

### Community 8 - "rules.py"
Cohesion: 0.15
Nodes (18): clamp(), blended_score(), exit_reason(), Frame, initial_stops(), module_scores(), Turning a genome plus price history into a decision. One rule engine serves…, Ratchet the stop toward price using bar ``i``'s close; never loosen it. The… (+10 more)

### Community 10 - "backtest.py"
Cohesion: 0.11
Nodes (18): bars_per_year(), _aggregate_metrics(), buy_and_hold(), compute_metrics(), Fold, Event-driven backtester. Deliberately pessimistic: fees on both sides, slippage…, The trivial "buy once and do nothing" strategy, priced the same way…, One anchored walk-forward split: everything up to a point to fit on, and the… (+10 more)

### Community 11 - "Signal"
Cohesion: 0.14
Nodes (5): A strategy's opinion at one point in time., Signal, make_trade(), TestDualBrain, TestPortfolioRisk

### Community 12 - "DivergenceTestCase"
Cohesion: 0.11
Nodes (10): DivergenceTestCase, No live trades at all - every entry the model would have taken was vetoed by…, The two scenarios must not collapse into the same generic text - this is the…, A risk veto is classified separately from a memory veto., A missed entry with no veto logged at all is neither a fill problem nor a…, Live fills that are worse than the model assumed, with every entry matched and…, TestBehaviouralDivergence, TestFillDivergence (+2 more)

### Community 13 - "types.py"
Cohesion: 0.11
Nodes (24): The autonomous agent loop. One iteration is: perceive -> recall -> decide ->…, Live-vs-backtest divergence for the champion genome. Nothing else in the agent…, The two brains, wired together. ``DualBrain`` is the only object the rest of…, Configuration for the autonomous agent. Precedence: explicit kwargs >…, BacktestResult, Fill, Core value types shared by every layer of the agent. Everything here is plain…, _deflation_penalty() (+16 more)

### Community 14 - "cli.py"
Cohesion: 0.09
Nodes (32): ArgumentParser, build_parser(), cmd_backtest(), cmd_dashboard(), cmd_demo(), cmd_evolve(), cmd_memory(), cmd_obsidian() (+24 more)

### Community 15 - "TradingAgent"
Cohesion: 0.15
Nodes (7): Any, Sleep and dream: consolidate memories, then evolve., Run autonomously until stopped (or ``max_steps`` cycles). A cycle is one pass…, Trust the exchange over our own records before trading anything. A process that…, _release_lock(), TradingAgent, A self-evolving, autonomous crypto trading agent with two brains. Public…

### Community 16 - "DualBrain"
Cohesion: 0.05
Nodes (44): _clamp(), DualBrain, MemoryBias, Any, The query Brain 2 is searched with - deliberately written in the same…, What Brain 2 wants to change about the decision Brain 1's strategy made., export_vault(), ExportReport (+36 more)

### Community 17 - ".make_broker"
Cohesion: 0.18
Nodes (3): TestLiveModeGates, TestQuantityRounding, TestReconcile

### Community 18 - "test_memory.py"
Cohesion: 0.18
Nodes (11): hash_text(), _now_ms(), Brain 2 - semantic / associative memory. Where Brain 1 answers "what happened…, Store a lesson. Re-learning the same text reinforces it instead of duplicating…, Retrieve the memories most relevant to ``query``. Ranking blends three things:…, Forget the least useful memories once over capacity., cosine(), pack() (+3 more)

### Community 19 - "simulate"
Cohesion: 0.18
Nodes (9): position_size(), Risk-based sizing: lose ``risk_per_trade`` of equity if the stop hits. The same…, simulate(), Start from a few hand-written archetypes, then fill with randoms. Pure random…, seed_population(), A decision at bar i must not change when future bars are appended., TestBacktest, trending_candles() (+1 more)

### Community 20 - "CcxtBroker"
Cohesion: 0.17
Nodes (6): CcxtBroker, Any, Live exchange orders through ccxt. Opt-in, guarded, and audited. Keeps a…, The exchange's LOT_SIZE increment for ``symbol``, or ``None`` when the market…, Round ``qty`` down to the venue's step size - never up, because rounding up can…, Cash plus every holding marked to the prices given. Accepts a single price…

### Community 21 - "RiskManager"
Cohesion: 0.12
Nodes (11): Any, Update the drawdown watermark and trip the kill switch if breached., Approve or refuse a new entry, sizing it within every active limit.…, None if the new position is fine; otherwise the refusal reason. A new entry is…, Cluster the given symbols by correlation, cached per bar in Brain 1. Five…, The trading day of a *market* timestamp. Deriving the day from the bar being…, Manual restart after a kill switch. Never called automatically - an agent that…, Best available estimate of current equity, for re-baselining on resume. Brain 1… (+3 more)

### Community 22 - "make_agent"
Cohesion: 0.18
Nodes (6): first_ts(), make_agent(), The half that did not sell is still real exposure., The partial-exit handling must not leave dust behind on a clean exit., TestEntryFollowsTheFill, TestExitFollowsTheFill

### Community 23 - "make_config"
Cohesion: 0.31
Nodes (4): make_config(), The bug this suite was written for: sizing rescaled past the cash clamp, so the…, Brain 1's positions and the broker's holdings are two records of the same fact;…, TestBookInvariants

### Community 24 - ".cycle"
Cohesion: 0.15
Nodes (9): CycleResult, _fmt_ts(), Manage an open position with the genome that opened it. A promotion mid-trade…, One decision on the primary symbol - the single-market view., Walk the whole universe once: perceive, then decide per symbol., What the agent decided about one symbol on one bar., Current exposure per market, in quote currency., One pass over the whole universe. (+1 more)

### Community 25 - "Cortex"
Cohesion: 0.16
Nodes (5): Cortex, Any, One recalled memory plus the scores that surfaced it., Vector memory with decay, reinforcement and pruning., Recall

### Community 26 - "Self-Evolving Crypto Trading Agent"
Cohesion: 0.12
Nodes (16): Autonomy and safety, CLI, Configuration, Dashboard, Going live (only when you mean it), Honest limits, Layout, Obsidian vault — reading the agent's mind (+8 more)

### Community 29 - "test_live_safety.py"
Cohesion: 0.16
Nodes (7): CcxtBrokerTestCase, Safety tests for CcxtBroker: order-quantity rounding, the live-mode gates, and…, ``TradingAgent.cycle()`` and ``status()`` always call ``equity()`` with a…, ``Fill.qty`` must always be what the exchange actually filled, never the…, Base class that arms the live-mode gates and injects a fake ccxt., TestEquityAcceptsThePriceMapAgentActuallyPasses, TestPartialFillReportsTruth

### Community 30 - "Lesson"
Cohesion: 0.23
Nodes (5): _group_lessons(), Turn recent raw episodes into generalisations. Triggered by new trades, but…, Lesson, A natural-language memory written into Brain 2., TestCortex

### Community 31 - ".random"
Cohesion: 0.15
Nodes (3): ``roll < 0.4`` gated a choice of ``a if roll < 0.5 else b`` - since the gate…, TestCrossoverProvenance, TestGenome

### Community 32 - "_pid_alive"
Cohesion: 0.20
Nodes (8): _acquire_lock(), _pid_alive(), _pid_alive_windows(), Refuse to run two agents against one set of brains., Is this PID still running? ``os.kill(pid, 0)`` is the POSIX idiom, but on…, The lockfile's liveness probe must never be able to kill anything., os.kill on Windows terminates; the probe must not go near it., TestProcessLiveness

### Community 33 - "HashingEmbedder"
Cohesion: 0.24
Nodes (5): HashingEmbedder, l2_normalize(), Stable bag-of-ngrams vectoriser using blake2b for bucket assignment., tokenize(), TestEmbeddings

### Community 34 - "Config"
Cohesion: 0.13
Nodes (8): _coerce(), Config, Any, Path, Coerce strings coming from env/JSON into the dataclass field type., Every symbol the agent trades, primary first, de-duplicated. One process…, TestConfig, TestSymbolList

### Community 36 - "Candle"
Cohesion: 0.10
Nodes (16): Candle, timeframe_ms(), BinancePublicProvider, CachedProvider, CcxtProvider, _dedupe(), make_provider(), MarketDataProvider (+8 more)

### Community 37 - "BacktestMetrics"
Cohesion: 0.31
Nodes (5): BacktestMetrics, fitness_score(), Risk-adjusted score used as the GA's selection pressure. Sharpe is the…, The pre-existing contract: fitness_score(metrics) with no other arguments must…, TestBenchmarkAwareFitness

### Community 40 - "Position"
Cohesion: 0.15
Nodes (10): _position_to_dict(), Brain 1 - episodic / structured memory (SQLite). This is the agent's ledger and…, Position, exit_price_for(), Where a given exit reason actually fills., _flat_frame(), A minimal Frame for exercising update_trailing_stop/exit_reason in isolation:…, BUG 2 regression: the stop must be tested against the level known before a bar… (+2 more)

### Community 41 - "FakeExchange"
Cohesion: 0.12
Nodes (7): Pull the exchange's LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL metadata once. Not every…, Read cash plus every tracked symbol's base-asset balance. This must cover the…, Re-fetch the real balance (and open orders) and make the local cache match it,…, What ``reconcile()`` found when it checked the local book against the source of…, ReconcileReport, FakeExchange, Just enough of ccxt's unified exchange interface for CcxtBroker.

### Community 43 - "TestMultiSymbolReconcileKeepsEveryHolding"
Cohesion: 0.22
Nodes (3): A ``--top5``-style universe holds positions in more than one symbol.…, TestMultiSymbolReconcileKeepsEveryHolding, TestPaperBrokerReconcile

### Community 44 - "TestEvolutionAcrossMarkets"
Cohesion: 0.22
Nodes (4): _as_markets(), Accept a symbol->candles map, or a bare series for the single-market case., History, TestEvolutionAcrossMarkets

### Community 45 - "TestCashIsNeverOverdrawn"
Cohesion: 0.22
Nodes (4): A spot book cannot spend money it does not have. position_size() fits the order…, What the broker will actually take out of cash: the slipped fill price plus the…, Selling short raises cash rather than spending it., TestCashIsNeverOverdrawn

### Community 46 - "BrokerOrderError"
Cohesion: 0.33
Nodes (4): BrokerOrderError, A live order was rejected, or its outcome could not be confirmed as a fill.…, RuntimeError, TestOrderFailureHandling

### Community 47 - "CorrelatedProvider"
Cohesion: 0.22
Nodes (4): CorrelatedProvider, Markets that move together, the way real majors do. The synthetic provider…, The cluster cap must actually hold in the live loop, not just in a unit test of…, TestCorrelatedExposureCapBinds

### Community 48 - "TestStateAndStorage"
Cohesion: 0.18
Nodes (5): first_ts(), A halt must stop new risk, not imprison existing risk. An agent that cannot…, Caches keyed by bar timestamp would leave one dead row per bar., TestKillSwitchDoesNotTrapPositions, TestStateAndStorage

### Community 50 - "Embedder"
Cohesion: 0.40
Nodes (3): Path, Embedder, Protocol

### Community 52 - "HeuristicReflector"
Cohesion: 0.47
Nodes (3): HeuristicReflector, Rule-based post-mortem over recent trades., TestReflector

## Knowledge Gaps
- **15 isolated node(s):** `self-evolving-crypto-agent`, `Quickstart`, `The two brains`, `Trading a universe`, `Self-evolution` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Config` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `EvolutionEngine`, `TestDashboardPage`, `backtest.py`, `Signal`, `DivergenceTestCase`, `types.py`, `cli.py`, `TradingAgent`, `DualBrain`, `.make_broker`, `test_memory.py`, `simulate`, `RiskManager`, `make_agent`, `make_config`, `Cortex`, `TestRiskManager`, `test_live_safety.py`, `_pid_alive`, `TestBackwardCompatibility`, `Candle`, `TestAgentEndToEnd`, `TestAgentUniverse`, `FakeExchange`, `TestCorrelationWindow`, `TestMultiSymbolReconcileKeepsEveryHolding`, `TestEvolutionAcrossMarkets`, `TestCashIsNeverOverdrawn`, `TestEvaluateAndDeflation`, `TestResumeRebaselinesWatermarks`, `TestPromotionBarTracksTrials`, `TestBreedRespectsAllowShortOnEveryPath`?**
  _High betweenness centrality (0.274) - this node is a cross-community bridge._
- **Why does `Candle` connect `Candle` to `dashboard.py`, `test_correlation.py`, `indicators.py`, `Hippocampus`, `rules.py`, `backtest.py`, `Signal`, `types.py`, `cli.py`, `TradingAgent`, `DualBrain`, `test_memory.py`, `simulate`, `RiskManager`, `.cycle`, `TestCharts`, `Position`, `TestCorrelationWindow`, `TestEvolutionAcrossMarkets`, `CorrelatedProvider`, `.closed_candles`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `DualBrain` connect `DualBrain` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `EvolutionEngine`, `Trade`, `Hippocampus`, `TestDashboardPage`, `backtest.py`, `Signal`, `DivergenceTestCase`, `types.py`, `cli.py`, `TradingAgent`, `test_memory.py`, `Cortex`, `TestRiskManager`, `Lesson`, `HashingEmbedder`, `TestBackwardCompatibility`, `TestCorrelationWindow`, `TestEvolutionAcrossMarkets`, `TestCashIsNeverOverdrawn`, `TestEvaluateAndDeflation`, `TestResumeRebaselinesWatermarks`, `TestPromotionBarTracksTrials`, `TestBreedRespectsAllowShortOnEveryPath`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Are the 41 inferred relationships involving `Config` (e.g. with `_acquire_lock()` and `TradingAgent`) actually correct?**
  _`Config` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `DualBrain` (e.g. with `Cortex` and `Recall`) actually correct?**
  _`DualBrain` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Candle` (e.g. with `TestPairwiseCorrelation` and `CorrelatedProvider`) actually correct?**
  _`Candle` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `TradingAgent` (e.g. with `Config` and `_replay_clock()`) actually correct?**
  _`TradingAgent` has 8 INFERRED edges - model-reasoned connections that need verification._