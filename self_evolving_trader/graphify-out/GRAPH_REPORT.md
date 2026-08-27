# Graph Report - self_evolving_trader  (2026-08-27)

## Corpus Check
- 52 files · ~51,489 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1186 nodes · 2822 edges · 71 communities (59 shown, 12 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 180 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a8b40296`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- dashboard.py
- test_correlation.py
- PaperBroker
- EvolutionEngine
- reflect.py
- test_regime_and_costs.py
- indicators.py
- Hippocampus
- Position
- TestCharts
- backtest.py
- Signal
- DivergenceTestCase
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
- test_invariants.py
- _make_eval
- Cortex
- Self-Evolving Crypto Trading Agent
- obsidian.py
- TestRiskManager
- TestGeneralisationGate
- Lesson
- Genome
- agent.py
- HashingEmbedder
- Config
- broker.py
- Candle
- .load
- SyntheticProvider
- TestDecisionReasons
- Correlation
- ReconcileReport
- buy_and_hold
- _decision_bucket
- TestStoredConfigAdoption
- rules.py
- TestCashIsNeverOverdrawn
- Any
- seed_population
- TestDashboardIntegration
- TestCostHurdle
- TestCorrelationWindow
- safe_name
- self-evolving-crypto-agent
- TestCheckEntryCorrelationCap
- MemoryBias
- TestDashboardPage
- TestResumeRebaselinesWatermarks
- Trade
- providers.py
- TestBackwardCompatibility
- Embedder
- CorrelatedProvider
- BrokerOrderError
- _print_hurdle
- .symbol_list

## God Nodes (most connected - your core abstractions)
1. `Config` - 153 edges
2. `DualBrain` - 102 edges
3. `Candle` - 76 edges
4. `Genome` - 59 edges
5. `Signal` - 57 edges
6. `TradingAgent` - 55 edges
7. `Hippocampus` - 52 edges
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

## Communities (71 total, 12 thin omitted)

### Community 0 - "dashboard.py"
Cohesion: 0.06
Nodes (52): _compare_symbol(), DivergenceReport, FillComparison, _mean_bps(), measure_divergence(), _pool(), Live-vs-backtest divergence for the champion genome. Nothing else in the agent…, The full comparison: one :class:`SymbolDivergence` per market, the pooled total… (+44 more)

### Community 1 - "test_correlation.py"
Cohesion: 0.24
Nodes (7): _candles_from_returns(), Correlation measurement, clustering, and the risk manager's cluster cap., Build a candle series whose closes follow the given log returns. ``skip_every``…, A caller must never mistake "unknown" for a genuine zero correlation., _returns(), TestClustering, TestPairwiseCorrelation

### Community 2 - "PaperBroker"
Cohesion: 0.08
Nodes (8): PaperBroker, Simulated fills, real bookkeeping., Units of the primary symbol - the single-symbol convenience view., Cash plus every holding marked to the prices given. Accepts a single price…, Paper trading has no external venue to drift from - the local book *is* the…, TestPaperBroker, A brain written before the universe existed keeps its position., TestMultiAssetBook

### Community 3 - "EvolutionEngine"
Cohesion: 0.15
Nodes (9): Evaluation, EvolutionEngine, GenerationReport, Any, Random, Score a genome across the whole universe. A strategy that only works on one…, Pull mutation bias out of Brain 2's reflections., Did the hold-out agree with the fit, or did the genome fit noise? A real edge… (+1 more)

### Community 4 - "reflect.py"
Cohesion: 0.16
Nodes (11): HeuristicReflector, LLMReflector, make_reflector(), Any, Reflection: turning outcomes into hypotheses. Consolidation (in…, Only real genes, only sane magnitudes. Applies to LLM output too., Optional Claude-powered reflection over the recent trade log., Rule-based post-mortem over recent trades. (+3 more)

### Community 5 - "test_regime_and_costs.py"
Cohesion: 0.12
Nodes (11): Fill gaps, clamp everything into range, enforce cross-gene sanity., Fill gaps, clamp everything into range, enforce cross-gene sanity., flat_candles(), genome_with(), The two gates that stop a genome trading a setup it cannot win. Both exist…, A range: no drift, small alternating moves, so slope stays near zero., An uptrend. Growth is compounded, not linear: `slope` normalises by the window…, TestCostFloor (+3 more)

### Community 6 - "indicators.py"
Cohesion: 0.09
Nodes (24): atr(), bollinger_z(), donchian_position(), ema(), last_valid(), macd_hist(), Technical indicators in pure Python. Each function takes a list of floats (or…, How many standard deviations price sits from its own mean. (+16 more)

### Community 7 - "Hippocampus"
Cohesion: 0.10
Nodes (5): Hippocampus, Path, Durable, exact memory. Safe to share across threads., _row_to_trade(), Row

### Community 8 - "Position"
Cohesion: 0.16
Nodes (9): Position, exit_price_for(), Where a given exit reason actually fills., Where a given exit reason actually fills., _flat_frame(), A minimal Frame for exercising update_trailing_stop/exit_reason in isolation:…, BUG 2 regression: the stop must be tested against the level known before a bar…, On a constructed two-bar series, the buggy ordering manufactures a stop exit on… (+1 more)

### Community 10 - "backtest.py"
Cohesion: 0.10
Nodes (23): BacktestMetrics, BacktestResult, fitness_score(), Risk-adjusted score used as the GA's selection pressure. Sharpe is the…, The evolution engine. A steady-state genetic algorithm over strategy genomes,…, _aggregate_metrics(), compute_metrics(), Fold (+15 more)

### Community 11 - "Signal"
Cohesion: 0.15
Nodes (5): A strategy's opinion at one point in time., Signal, make_trade(), TestDualBrain, TestPortfolioRisk

### Community 12 - "DivergenceTestCase"
Cohesion: 0.11
Nodes (10): DivergenceTestCase, No live trades at all - every entry the model would have taken was vetoed by…, The two scenarios must not collapse into the same generic text - this is the…, A risk veto is classified separately from a memory veto., A missed entry with no veto logged at all is neither a fill problem nor a…, Live fills that are worse than the model assumed, with every entry matched and…, TestBehaviouralDivergence, TestFillDivergence (+2 more)

### Community 13 - "types.py"
Cohesion: 0.22
Nodes (10): Brain 1 - episodic / structured memory (SQLite). This is the agent's ledger and…, The two brains, wired together. ``DualBrain`` is the only object the rest of…, Configuration for the autonomous agent. Precedence: explicit kwargs >…, bars_per_year(), Core value types shared by every layer of the agent. Everything here is plain…, timeframe_ms(), Risk manager - the part that is allowed to say no. Evolution optimises for…, Tests for ``crypto_agent.analysis.divergence``. The two behavioural tests build… (+2 more)

### Community 14 - "cli.py"
Cohesion: 0.22
Nodes (22): ArgumentParser, build_parser(), cmd_backtest(), cmd_dashboard(), cmd_demo(), cmd_evolve(), cmd_memory(), cmd_obsidian() (+14 more)

### Community 15 - "TradingAgent"
Cohesion: 0.08
Nodes (17): CycleResult, _fmt_ts(), Any, Only fully closed bars. Acting on a forming candle is how a backtest that looks…, Fetch every symbol before deciding anything. Marking the book to market needs…, One decision on the primary symbol - the single-market view., Walk the whole universe once: perceive, then decide per symbol., Sleep and dream: consolidate memories, then evolve. (+9 more)

### Community 16 - "DualBrain"
Cohesion: 0.22
Nodes (5): DualBrain, Any, export_vault(), Mirror both brains into an Obsidian vault at ``vault_dir``. Read-only with…, TestExportVault

### Community 17 - ".make_broker"
Cohesion: 0.09
Nodes (9): CcxtBrokerTestCase, ``TradingAgent.cycle()`` and ``status()`` always call ``equity()`` with a…, ``Fill.qty`` must always be what the exchange actually filled, never the…, Base class that arms the live-mode gates and injects a fake ccxt., TestEquityAcceptsThePriceMapAgentActuallyPasses, TestLiveModeGates, TestPartialFillReportsTruth, TestQuantityRounding (+1 more)

### Community 18 - "cortex.py"
Cohesion: 0.18
Nodes (11): hash_text(), _now_ms(), Brain 2 - semantic / associative memory. Where Brain 1 answers "what happened…, Store a lesson. Re-learning the same text reinforces it instead of duplicating…, Retrieve the memories most relevant to ``query``. Ranking blends three things:…, Forget the least useful memories once over capacity., cosine(), pack() (+3 more)

### Community 19 - "Broker"
Cohesion: 0.18
Nodes (4): Broker, make_broker(), Protocol, Everything the agent actually calls on a broker. This declared only…

### Community 20 - "CcxtBroker"
Cohesion: 0.09
Nodes (11): CcxtBroker, Any, Live exchange orders through ccxt. Opt-in, guarded, and audited. Keeps a…, Pull the exchange's LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL metadata once. Not every…, The exchange's LOT_SIZE increment for ``symbol``, or ``None`` when the market…, Round ``qty`` down to the venue's step size - never up, because rounding up can…, Read cash plus every tracked symbol's base-asset balance. This must cover the…, Cash plus every holding marked to the prices given. Accepts a single price… (+3 more)

### Community 21 - "RiskManager"
Cohesion: 0.14
Nodes (9): Any, Update the drawdown watermark and trip the kill switch if breached., Approve or refuse a new entry, sizing it within every active limit.…, The trading day of a *market* timestamp. Deriving the day from the bar being…, Manual restart after a kill switch. Never called automatically - an agent that…, Best available estimate of current equity, for re-baselining on resume. Brain 1…, RiskDecision, RiskManager (+1 more)

### Community 22 - "make_agent"
Cohesion: 0.18
Nodes (6): first_ts(), make_agent(), The half that did not sell is still real exposure., The partial-exit handling must not leave dust behind on a clean exit., TestEntryFollowsTheFill, TestExitFollowsTheFill

### Community 23 - "test_invariants.py"
Cohesion: 0.13
Nodes (10): first_ts(), make_config(), Properties that must hold over a long run, not just on one call. These are the…, A halt must stop new risk, not imprison existing risk. An agent that cannot…, Caches keyed by bar timestamp would leave one dead row per bar., The bug this suite was written for: sizing rescaled past the cash clamp, so the…, Brain 1's positions and the broker's holdings are two records of the same fact;…, TestBookInvariants (+2 more)

### Community 24 - "_make_eval"
Cohesion: 0.15
Nodes (8): _deflation_penalty(), How much to subtract from fitness for having already looked at this data…, _make_eval(), The champion's stored oos_fitness is deflated at its crowning trial count;…, Every other path in ``breed`` (seed_population, crossover+mutate) clamps…, Build an Evaluation with a known undeflated score, deflated at ``trials``.…, TestBreedRespectsAllowShortOnEveryPath, TestPromotionBarTracksTrials

### Community 25 - "Cortex"
Cohesion: 0.16
Nodes (5): Cortex, Any, One recalled memory plus the scores that surfaced it., Vector memory with decay, reinforcement and pruning., Recall

### Community 26 - "Self-Evolving Crypto Trading Agent"
Cohesion: 0.10
Nodes (19): Autonomy and safety, CLI, Configuration, Dashboard, Going live (only when you mean it), Honest limits, Layout, Obsidian vault — reading the agent's mind (+11 more)

### Community 27 - "obsidian.py"
Cohesion: 0.18
Nodes (23): ExportReport, _frontmatter(), _index_note(), iter_note_paths(), _lesson_notes(), _lesson_symbol(), _market_notes(), _month() (+15 more)

### Community 30 - "Lesson"
Cohesion: 0.23
Nodes (5): _group_lessons(), Turn recent raw episodes into generalisations. Triggered by new trades, but…, Lesson, A natural-language memory written into Brain 2., TestCortex

### Community 31 - "Genome"
Cohesion: 0.08
Nodes (14): Manage an open position with the genome that opened it. A promotion mid-trade…, Gene, Genome, Any, Random, Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Uniform crossover; numeric genes may also blend. Which parent a gene picks… (+6 more)

### Community 32 - "agent.py"
Cohesion: 0.17
Nodes (9): _acquire_lock(), _pid_alive(), _pid_alive_windows(), The autonomous agent loop. One iteration is: perceive -> recall -> decide ->…, Refuse to run two agents against one set of brains., Is this PID still running? ``os.kill(pid, 0)`` is the POSIX idiom, but on…, The lockfile's liveness probe must never be able to kill anything., os.kill on Windows terminates; the probe must not go near it. (+1 more)

### Community 33 - "HashingEmbedder"
Cohesion: 0.24
Nodes (5): HashingEmbedder, l2_normalize(), Stable bag-of-ngrams vectoriser using blake2b for bucket assignment., tokenize(), TestEmbeddings

### Community 34 - "Config"
Cohesion: 0.11
Nodes (9): Config, Path, position_size(), Risk-based sizing: lose ``risk_per_trade`` of equity if the stop hits. The same…, Safety tests for CcxtBroker: order-quantity rounding, the live-mode gates, and…, A ``--top5``-style universe holds positions in more than one symbol.…, TestMultiSymbolReconcileKeepsEveryHolding, TestPaperBrokerReconcile (+1 more)

### Community 35 - "broker.py"
Cohesion: 0.23
Nodes (7): Fill, Order execution. ``PaperBroker`` is the default and simulates fills with the…, EmptyFillBroker, PartialFillBroker, The local book must follow the fill, never the request. A live exchange rounds…, A paper broker that fills only a fraction of what it is asked for., A broker whose order returns without filling anything at all.

### Community 36 - "Candle"
Cohesion: 0.29
Nodes (4): Candle, BinancePublicProvider, _dedupe(), Public klines endpoint. No API key, no dependencies, read-only.

### Community 37 - ".load"
Cohesion: 0.31
Nodes (5): _coerce(), Any, Coerce strings coming from env/JSON into the dataclass field type., Coerce strings coming from env/JSON into the dataclass field type., TestConfig

### Community 38 - "SyntheticProvider"
Cohesion: 0.06
Nodes (11): Regime-switching geometric brownian motion with fat tails. Not a claim about…, SyntheticProvider, _as_markets(), Accept a symbol->candles map, or a bare series for the single-market case., History, The whole loop on deterministic offline data., TestAgentEndToEnd, The full loop, three markets, deterministic offline data. (+3 more)

### Community 39 - "TestDecisionReasons"
Cohesion: 0.24
Nodes (3): Tallying why the agent did or did not open anything. Twice in one session the…, signal(), TestDecisionReasons

### Community 40 - "Correlation"
Cohesion: 0.13
Nodes (16): align_closes(), cluster_symbols(), Correlation, log_returns(), pearson(), How correlated two markets are, measured from their candle closes. The…, Pearson correlation of log returns between two candle series, aligned on…, Group symbols into clusters where any pair above ``threshold`` is linked. This… (+8 more)

### Community 42 - "buy_and_hold"
Cohesion: 0.31
Nodes (6): buy_and_hold(), The trivial "buy once and do nothing" strategy, priced the same way…, ramp_candles(), A deterministic price path with no wicks, so the arithmetic in a test can be…, BUG 1 regression: pricing the benchmark over the full candle range (rather than…, TestBuyAndHold

### Community 43 - "_decision_bucket"
Cohesion: 0.27
Nodes (4): _decision_bucket(), Why the recent decisions went the way they did, most common first. Every…, Collapse one decision into a stable category. The action says what happened;…, TestDecisionBucket

### Community 44 - "TestStoredConfigAdoption"
Cohesion: 0.21
Nodes (5): The config the agent last booted with, straight out of Brain 1., stored_config(), Inspection commands must describe the agent that actually ran., A stored live mode must not arm a read-only command., TestStoredConfigAdoption

### Community 45 - "rules.py"
Cohesion: 0.09
Nodes (28): clamp(), blended_score(), exit_reason(), Frame, initial_stops(), min_edge_for(), module_scores(), Any (+20 more)

### Community 46 - "TestCashIsNeverOverdrawn"
Cohesion: 0.22
Nodes (4): A spot book cannot spend money it does not have. position_size() fits the order…, What the broker will actually take out of cash: the slipped fill price plus the…, Selling short raises cash rather than spending it., TestCashIsNeverOverdrawn

### Community 47 - "Any"
Cohesion: 0.16
Nodes (4): _now_ms(), _position_to_dict(), Any, _row_to_genome()

### Community 48 - "seed_population"
Cohesion: 0.19
Nodes (6): Start from a few hand-written archetypes, then fill with randoms. Pure random…, Start from a few hand-written archetypes, then fill with randoms. Pure random…, seed_population(), A decision at bar i must not change when future bars are appended., TestBacktest, trending_candles()

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

### Community 64 - "providers.py"
Cohesion: 0.21
Nodes (8): CachedProvider, CcxtProvider, make_provider(), MarketDataProvider, Protocol, Market data providers. Three sources, one interface: * ``SyntheticProvider`` -…, Any ccxt exchange. ``pip install ccxt`` to enable., Persist every candle in Brain 1 and survive network outages.

### Community 66 - "Embedder"
Cohesion: 0.40
Nodes (3): Path, Embedder, Protocol

### Community 67 - "CorrelatedProvider"
Cohesion: 0.22
Nodes (4): CorrelatedProvider, Markets that move together, the way real majors do. The synthetic provider…, The cluster cap must actually hold in the live loop, not just in a unit test of…, TestCorrelatedExposureCapBinds

### Community 68 - "BrokerOrderError"
Cohesion: 0.33
Nodes (4): BrokerOrderError, A live order was rejected, or its outcome could not be confirmed as a fill.…, RuntimeError, TestOrderFailureHandling

### Community 69 - "_print_hurdle"
Cohesion: 0.50
Nodes (3): _print_hurdle(), Any, How big the round trip is next to a typical bar, in this market. This is the…

## Knowledge Gaps
- **18 isolated node(s):** `self-evolving-crypto-agent`, `Quickstart`, `The two brains`, `Trading a universe`, `Self-evolution` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Config` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `EvolutionEngine`, `test_regime_and_costs.py`, `backtest.py`, `Signal`, `DivergenceTestCase`, `types.py`, `cli.py`, `TradingAgent`, `DualBrain`, `.make_broker`, `Broker`, `CcxtBroker`, `RiskManager`, `make_agent`, `test_invariants.py`, `_make_eval`, `Cortex`, `obsidian.py`, `TestRiskManager`, `TestGeneralisationGate`, `agent.py`, `broker.py`, `.load`, `SyntheticProvider`, `TestDecisionReasons`, `buy_and_hold`, `TestStoredConfigAdoption`, `TestCashIsNeverOverdrawn`, `seed_population`, `TestDashboardIntegration`, `TestCostHurdle`, `TestCorrelationWindow`, `TestCheckEntryCorrelationCap`, `TestDashboardPage`, `TestResumeRebaselinesWatermarks`, `Trade`, `TestBackwardCompatibility`, `_print_hurdle`, `.symbol_list`?**
  _High betweenness centrality (0.281) - this node is a cross-community bridge._
- **Why does `DualBrain` connect `DualBrain` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `EvolutionEngine`, `Hippocampus`, `backtest.py`, `Signal`, `DivergenceTestCase`, `types.py`, `cli.py`, `TradingAgent`, `Broker`, `_make_eval`, `Cortex`, `TestRiskManager`, `TestGeneralisationGate`, `Lesson`, `agent.py`, `HashingEmbedder`, `SyntheticProvider`, `TestStoredConfigAdoption`, `TestCashIsNeverOverdrawn`, `seed_population`, `TestDashboardIntegration`, `TestCorrelationWindow`, `TestCheckEntryCorrelationCap`, `MemoryBias`, `TestDashboardPage`, `TestResumeRebaselinesWatermarks`, `Trade`, `TestBackwardCompatibility`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `Candle` connect `Candle` to `dashboard.py`, `test_correlation.py`, `test_regime_and_costs.py`, `indicators.py`, `Hippocampus`, `Position`, `TestCharts`, `backtest.py`, `Signal`, `types.py`, `TradingAgent`, `RiskManager`, `test_invariants.py`, `agent.py`, `SyntheticProvider`, `TestDecisionReasons`, `Correlation`, `buy_and_hold`, `rules.py`, `seed_population`, `TestDashboardIntegration`, `TestCostHurdle`, `TestCorrelationWindow`, `providers.py`, `CorrelatedProvider`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 45 inferred relationships involving `Config` (e.g. with `_acquire_lock()` and `TradingAgent`) actually correct?**
  _`Config` has 45 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `DualBrain` (e.g. with `Cortex` and `Recall`) actually correct?**
  _`DualBrain` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `Candle` (e.g. with `TestPairwiseCorrelation` and `CorrelatedProvider`) actually correct?**
  _`Candle` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Genome` (e.g. with `simulate()` and `walk_forward()`) actually correct?**
  _`Genome` has 18 INFERRED edges - model-reasoned connections that need verification._