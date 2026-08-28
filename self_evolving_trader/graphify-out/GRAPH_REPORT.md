# Graph Report - self_evolving_trader  (2026-08-28)

## Corpus Check
- 52 files · ~51,715 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1188 nodes · 2828 edges · 74 communities (62 shown, 12 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 180 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `98890d08`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- dashboard.py
- test_correlation.py
- PaperBroker
- EvolutionEngine
- reflect.py
- genome_with
- TestIndicators
- Hippocampus
- TestTrailingStopLookahead
- TestCharts
- backtest.py
- make_trade
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
- TestStateAndStorage
- _make_eval
- Cortex
- Self-Evolving Crypto Trading Agent
- obsidian.py
- TestRiskManager
- TestGeneralisationGate
- Lesson
- Genome
- _pid_alive
- HashingEmbedder
- Config
- test_fills.py
- Candle
- .repair
- SyntheticProvider
- TestDecisionReasons
- Correlation
- FakeExchange
- walk_forward
- _decision_bucket
- test_dashboard_and_cli.py
- rules.py
- TestCashIsNeverOverdrawn
- Position
- simulate
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
- .__init__
- Signal
- Embedder
- make_config
- BrokerOrderError
- CcxtBrokerTestCase
- TestAgentEndToEnd
- TestAgentUniverse
- ._correlated_exposure_reason
- TestBreedRespectsAllowShortOnEveryPath

## God Nodes (most connected - your core abstractions)
1. `Config` - 154 edges
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

## Communities (74 total, 12 thin omitted)

### Community 0 - "dashboard.py"
Cohesion: 0.06
Nodes (52): _compare_symbol(), DivergenceReport, FillComparison, _mean_bps(), measure_divergence(), _pool(), Live-vs-backtest divergence for the champion genome. Nothing else in the agent…, The full comparison: one :class:`SymbolDivergence` per market, the pooled total… (+44 more)

### Community 1 - "test_correlation.py"
Cohesion: 0.24
Nodes (7): _candles_from_returns(), Correlation measurement, clustering, and the risk manager's cluster cap., Build a candle series whose closes follow the given log returns. ``skip_every``…, A caller must never mistake "unknown" for a genuine zero correlation., _returns(), TestClustering, TestPairwiseCorrelation

### Community 2 - "PaperBroker"
Cohesion: 0.06
Nodes (13): PaperBroker, Simulated fills, real bookkeeping., Units of the primary symbol - the single-symbol convenience view., Cash plus every holding marked to the prices given. Accepts a single price…, Paper trading has no external venue to drift from - the local book *is* the…, What ``reconcile()`` found when it checked the local book against the source of…, ReconcileReport, PartialFillBroker (+5 more)

### Community 3 - "EvolutionEngine"
Cohesion: 0.17
Nodes (8): Evaluation, EvolutionEngine, GenerationReport, Any, Score a genome across the whole universe. A strategy that only works on one…, Pull mutation bias out of Brain 2's reflections., Did the hold-out agree with the fit, or did the genome fit noise? A real edge…, Promote on out-of-sample evidence only, and only by a clear margin. Churning…

### Community 4 - "reflect.py"
Cohesion: 0.16
Nodes (11): HeuristicReflector, LLMReflector, make_reflector(), Any, Reflection: turning outcomes into hypotheses. Consolidation (in…, Only real genes, only sane magnitudes. Applies to LLM output too., Optional Claude-powered reflection over the recent trade log., Rule-based post-mortem over recent trades. (+3 more)

### Community 5 - "genome_with"
Cohesion: 0.15
Nodes (8): flat_candles(), genome_with(), A range: no drift, small alternating moves, so slope stays near zero., An uptrend. Growth is compounded, not linear: `slope` normalises by the window…, TestCostFloor, TestMeanReversionBias, TestRegimeGate, trending_candles()

### Community 7 - "Hippocampus"
Cohesion: 0.09
Nodes (8): Hippocampus, _now_ms(), Any, Path, Durable, exact memory. Safe to share across threads., _row_to_genome(), _row_to_trade(), Row

### Community 8 - "TestTrailingStopLookahead"
Cohesion: 0.29
Nodes (5): _flat_frame(), A minimal Frame for exercising update_trailing_stop/exit_reason in isolation:…, BUG 2 regression: the stop must be tested against the level known before a bar…, On a constructed two-bar series, the buggy ordering manufactures a stop exit on…, TestTrailingStopLookahead

### Community 10 - "backtest.py"
Cohesion: 0.13
Nodes (16): BacktestMetrics, bars_per_year(), fitness_score(), Risk-adjusted score used as the GA's selection pressure. Sharpe is the…, _aggregate_metrics(), buy_and_hold(), compute_metrics(), Event-driven backtester. Deliberately pessimistic: fees on both sides, slippage… (+8 more)

### Community 11 - "make_trade"
Cohesion: 0.15
Nodes (3): candles(), make_trade(), TestDualBrain

### Community 12 - "DivergenceTestCase"
Cohesion: 0.11
Nodes (10): DivergenceTestCase, No live trades at all - every entry the model would have taken was vetoed by…, The two scenarios must not collapse into the same generic text - this is the…, A risk veto is classified separately from a memory veto., A missed entry with no veto logged at all is neither a fill problem nor a…, Live fills that are worse than the model assumed, with every entry matched and…, TestBehaviouralDivergence, TestFillDivergence (+2 more)

### Community 13 - "types.py"
Cohesion: 0.12
Nodes (22): The autonomous agent loop. One iteration is: perceive -> recall -> decide ->…, Brain 1 - episodic / structured memory (SQLite). This is the agent's ledger and…, The two brains, wired together. ``DualBrain`` is the only object the rest of…, Configuration for the autonomous agent. Precedence: explicit kwargs >…, BacktestResult, Core value types shared by every layer of the agent. Everything here is plain…, timeframe_ms(), Market data providers. Three sources, one interface: * ``SyntheticProvider`` -… (+14 more)

### Community 14 - "cli.py"
Cohesion: 0.25
Nodes (20): cmd_backtest(), cmd_dashboard(), cmd_demo(), cmd_evolve(), cmd_memory(), cmd_obsidian(), cmd_report(), cmd_resume_risk() (+12 more)

### Community 15 - "TradingAgent"
Cohesion: 0.09
Nodes (16): CycleResult, _fmt_ts(), Any, Only fully closed bars. Acting on a forming candle is how a backtest that looks…, Fetch every symbol before deciding anything. Marking the book to market needs…, One decision on the primary symbol - the single-market view., Walk the whole universe once: perceive, then decide per symbol., Sleep and dream: consolidate memories, then evolve. (+8 more)

### Community 16 - "DualBrain"
Cohesion: 0.22
Nodes (5): DualBrain, Any, export_vault(), Mirror both brains into an Obsidian vault at ``vault_dir``. Read-only with…, TestExportVault

### Community 17 - ".make_broker"
Cohesion: 0.13
Nodes (5): ``TradingAgent.cycle()`` and ``status()`` always call ``equity()`` with a…, TestEquityAcceptsThePriceMapAgentActuallyPasses, TestLiveModeGates, TestQuantityRounding, TestReconcile

### Community 18 - "cortex.py"
Cohesion: 0.18
Nodes (11): hash_text(), _now_ms(), Brain 2 - semantic / associative memory. Where Brain 1 answers "what happened…, Store a lesson. Re-learning the same text reinforces it instead of duplicating…, Retrieve the memories most relevant to ``query``. Ranking blends three things:…, Forget the least useful memories once over capacity., cosine(), pack() (+3 more)

### Community 19 - "Broker"
Cohesion: 0.22
Nodes (3): Broker, Protocol, Everything the agent actually calls on a broker. This declared only…

### Community 20 - "CcxtBroker"
Cohesion: 0.17
Nodes (6): CcxtBroker, Any, Live exchange orders through ccxt. Opt-in, guarded, and audited. Keeps a…, The exchange's LOT_SIZE increment for ``symbol``, or ``None`` when the market…, Round ``qty`` down to the venue's step size - never up, because rounding up can…, Cash plus every holding marked to the prices given. Accepts a single price…

### Community 21 - "RiskManager"
Cohesion: 0.15
Nodes (9): Any, Update the drawdown watermark and trip the kill switch if breached., Approve or refuse a new entry, sizing it within every active limit.…, The trading day of a *market* timestamp. Deriving the day from the bar being…, Manual restart after a kill switch. Never called automatically - an agent that…, Best available estimate of current equity, for re-baselining on resume. Brain 1…, RiskDecision, RiskManager (+1 more)

### Community 22 - "make_agent"
Cohesion: 0.18
Nodes (6): first_ts(), make_agent(), The half that did not sell is still real exposure., The partial-exit handling must not leave dust behind on a clean exit., TestEntryFollowsTheFill, TestExitFollowsTheFill

### Community 23 - "TestStateAndStorage"
Cohesion: 0.18
Nodes (5): first_ts(), A halt must stop new risk, not imprison existing risk. An agent that cannot…, Caches keyed by bar timestamp would leave one dead row per bar., TestKillSwitchDoesNotTrapPositions, TestStateAndStorage

### Community 24 - "_make_eval"
Cohesion: 0.24
Nodes (6): _deflation_penalty(), How much to subtract from fitness for having already looked at this data…, _make_eval(), The champion's stored oos_fitness is deflated at its crowning trial count;…, Build an Evaluation with a known undeflated score, deflated at ``trials``.…, TestPromotionBarTracksTrials

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
Cohesion: 0.11
Nodes (7): Manage an open position with the genome that opened it. A promotion mid-trade…, Genome, Normalised gene-space distance, used to keep the population diverse., Normalised gene-space distance, used to keep the population diverse., ``roll < 0.4`` gated a choice of ``a if roll < 0.5 else b`` - since the gate…, TestCrossoverProvenance, TestGenome

### Community 32 - "_pid_alive"
Cohesion: 0.24
Nodes (6): _pid_alive(), _pid_alive_windows(), Is this PID still running? ``os.kill(pid, 0)`` is the POSIX idiom, but on…, The lockfile's liveness probe must never be able to kill anything., os.kill on Windows terminates; the probe must not go near it., TestProcessLiveness

### Community 33 - "HashingEmbedder"
Cohesion: 0.24
Nodes (5): HashingEmbedder, l2_normalize(), Stable bag-of-ngrams vectoriser using blake2b for bucket assignment., tokenize(), TestEmbeddings

### Community 34 - "Config"
Cohesion: 0.10
Nodes (11): _coerce(), Config, Any, Path, Every symbol the agent trades, primary first, de-duplicated. One process…, Coerce strings coming from env/JSON into the dataclass field type., Coerce strings coming from env/JSON into the dataclass field type., Every symbol the agent trades, primary first, de-duplicated. One process… (+3 more)

### Community 35 - "test_fills.py"
Cohesion: 0.47
Nodes (4): Fill, EmptyFillBroker, The local book must follow the fill, never the request. A live exchange rounds…, A broker whose order returns without filling anything at all.

### Community 36 - "Candle"
Cohesion: 0.15
Nodes (9): Candle, BinancePublicProvider, _dedupe(), Public klines endpoint. No API key, no dependencies, read-only., _as_markets(), Accept a symbol->candles map, or a bare series for the single-market case., History, CorrelatedProvider (+1 more)

### Community 37 - ".repair"
Cohesion: 0.12
Nodes (9): Gene, Any, Random, Fill gaps, clamp everything into range, enforce cross-gene sanity., Fill gaps, clamp everything into range, enforce cross-gene sanity., Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Gaussian creep on a random subset of genes. ``nudges`` is how Brain 2 reaches…, Uniform crossover; numeric genes may also blend. Which parent a gene picks… (+1 more)

### Community 38 - "SyntheticProvider"
Cohesion: 0.12
Nodes (4): Regime-switching geometric brownian motion with fat tails. Not a claim about…, SyntheticProvider, TestEvolutionAcrossMarkets, TestEvaluateAndDeflation

### Community 39 - "TestDecisionReasons"
Cohesion: 0.24
Nodes (3): Tallying why the agent did or did not open anything. Twice in one session the…, signal(), TestDecisionReasons

### Community 40 - "Correlation"
Cohesion: 0.19
Nodes (12): align_closes(), cluster_symbols(), Correlation, log_returns(), pearson(), How correlated two markets are, measured from their candle closes. The…, Pearson correlation of log returns between two candle series, aligned on…, Group symbols into clusters where any pair above ``threshold`` is linked. This… (+4 more)

### Community 41 - "FakeExchange"
Cohesion: 0.14
Nodes (5): Pull the exchange's LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL metadata once. Not every…, Read cash plus every tracked symbol's base-asset balance. This must cover the…, Re-fetch the real balance (and open orders) and make the local cache match it,…, FakeExchange, Just enough of ccxt's unified exchange interface for CcxtBroker.

### Community 42 - "walk_forward"
Cohesion: 0.20
Nodes (7): Fold, One anchored walk-forward split: everything up to a point to fit on, and the…, Aggregate in-sample and out-of-sample results, plus the fold-by-fold detail…, Anchored, multi-fold walk-forward evaluation. A single fixed hold-out at the…, walk_forward(), WalkForwardResult, TestAnchoredWalkForward

### Community 43 - "_decision_bucket"
Cohesion: 0.27
Nodes (4): _decision_bucket(), Why the recent decisions went the way they did, most common first. Every…, Collapse one decision into a stable category. The action says what happened;…, TestDecisionBucket

### Community 44 - "test_dashboard_and_cli.py"
Cohesion: 0.18
Nodes (7): ArgumentParser, build_parser(), The config the agent last booted with, straight out of Brain 1., stored_config(), Inspection commands must describe the agent that actually ran., A stored live mode must not arm a read-only command., TestStoredConfigAdoption

### Community 45 - "rules.py"
Cohesion: 0.06
Nodes (50): atr(), bollinger_z(), clamp(), donchian_position(), ema(), last_valid(), macd_hist(), Technical indicators in pure Python. Each function takes a list of floats (or… (+42 more)

### Community 46 - "TestCashIsNeverOverdrawn"
Cohesion: 0.22
Nodes (4): A spot book cannot spend money it does not have. position_size() fits the order…, What the broker will actually take out of cash: the slipped fill price plus the…, Selling short raises cash rather than spending it., TestCashIsNeverOverdrawn

### Community 47 - "Position"
Cohesion: 0.21
Nodes (5): _position_to_dict(), Position, exit_price_for(), Where a given exit reason actually fills., Where a given exit reason actually fills.

### Community 48 - "simulate"
Cohesion: 0.18
Nodes (10): position_size(), Risk-based sizing: lose ``risk_per_trade`` of equity if the stop hits. The same…, simulate(), Start from a few hand-written archetypes, then fill with randoms. Pure random…, Start from a few hand-written archetypes, then fill with randoms. Pure random…, seed_population(), A decision at bar i must not change when future bars are appended., TestBacktest (+2 more)

### Community 49 - "TestDashboardIntegration"
Cohesion: 0.13
Nodes (8): make_candles(), Candles are cached and the model may well find entries in them, but with no…, The dashboard must render (and stay self-contained) whether or not there is…, A synthetic series with a slow, noisy oscillating drift - long enough to warm…, The archetype ``seed_population`` seeds first - reliably trades on the…, TestDashboardIntegration, TestGracefulDegradation, trend_follower_genome()

### Community 50 - "TestCostHurdle"
Cohesion: 0.21
Nodes (5): _print_hurdle(), Any, How big the round trip is next to a typical bar, in this market. This is the…, Costs are fixed per trade; the move on offer scales with the bar. On a fast…, TestCostHurdle

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

### Community 65 - "Signal"
Cohesion: 0.16
Nodes (5): A strategy's opinion at one point in time., Signal, Every existing check_entry call signature must keep working unchanged., TestBackwardCompatibility, TestPortfolioRisk

### Community 66 - "Embedder"
Cohesion: 0.40
Nodes (3): Path, Embedder, Protocol

### Community 67 - "make_config"
Cohesion: 0.18
Nodes (6): make_config(), The cluster cap must actually hold in the live loop, not just in a unit test of…, The bug this suite was written for: sizing rescaled past the cash clamp, so the…, Brain 1's positions and the broker's holdings are two records of the same fact;…, TestBookInvariants, TestCorrelatedExposureCapBinds

### Community 68 - "BrokerOrderError"
Cohesion: 0.25
Nodes (6): _acquire_lock(), Refuse to run two agents against one set of brains., BrokerOrderError, A live order was rejected, or its outcome could not be confirmed as a fill.…, RuntimeError, TestOrderFailureHandling

### Community 69 - "CcxtBrokerTestCase"
Cohesion: 0.17
Nodes (6): CcxtBrokerTestCase, ``Fill.qty`` must always be what the exchange actually filled, never the…, A ``--top5``-style universe holds positions in more than one symbol.…, Base class that arms the live-mode gates and injects a fake ccxt., TestMultiSymbolReconcileKeepsEveryHolding, TestPartialFillReportsTruth

### Community 72 - "._correlated_exposure_reason"
Cohesion: 0.33
Nodes (4): None if the new position is fine; otherwise the refusal reason. A new entry is…, Cluster the given symbols by correlation, cached per bar in Brain 1. Five…, The cluster member `market` is most directly correlated with. A symbol only…, _strongest_partner()

## Knowledge Gaps
- **18 isolated node(s):** `self-evolving-crypto-agent`, `Quickstart`, `The two brains`, `Trading a universe`, `Self-evolution` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Config` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `genome_with`, `backtest.py`, `make_trade`, `DivergenceTestCase`, `types.py`, `cli.py`, `TradingAgent`, `DualBrain`, `.make_broker`, `RiskManager`, `make_agent`, `_make_eval`, `Cortex`, `obsidian.py`, `TestRiskManager`, `TestGeneralisationGate`, `test_fills.py`, `SyntheticProvider`, `TestDecisionReasons`, `FakeExchange`, `walk_forward`, `test_dashboard_and_cli.py`, `TestCashIsNeverOverdrawn`, `simulate`, `TestDashboardIntegration`, `TestCostHurdle`, `TestCorrelationWindow`, `TestCheckEntryCorrelationCap`, `TestDashboardPage`, `TestResumeRebaselinesWatermarks`, `Trade`, `.__init__`, `Signal`, `make_config`, `BrokerOrderError`, `CcxtBrokerTestCase`, `TestAgentEndToEnd`, `TestAgentUniverse`, `TestBreedRespectsAllowShortOnEveryPath`?**
  _High betweenness centrality (0.282) - this node is a cross-community bridge._
- **Why does `DualBrain` connect `DualBrain` to `dashboard.py`, `test_correlation.py`, `PaperBroker`, `Hippocampus`, `backtest.py`, `make_trade`, `DivergenceTestCase`, `types.py`, `cli.py`, `_make_eval`, `Cortex`, `TestRiskManager`, `TestGeneralisationGate`, `Lesson`, `HashingEmbedder`, `Config`, `SyntheticProvider`, `test_dashboard_and_cli.py`, `TestCashIsNeverOverdrawn`, `TestDashboardIntegration`, `TestCorrelationWindow`, `TestCheckEntryCorrelationCap`, `MemoryBias`, `TestDashboardPage`, `TestResumeRebaselinesWatermarks`, `Trade`, `.__init__`, `Signal`, `TestBreedRespectsAllowShortOnEveryPath`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Why does `Candle` connect `Candle` to `dashboard.py`, `test_correlation.py`, `genome_with`, `TestIndicators`, `Hippocampus`, `TestTrailingStopLookahead`, `backtest.py`, `make_trade`, `types.py`, `TradingAgent`, `RiskManager`, `SyntheticProvider`, `TestDecisionReasons`, `Correlation`, `walk_forward`, `test_dashboard_and_cli.py`, `rules.py`, `Position`, `simulate`, `TestDashboardIntegration`, `TestCostHurdle`, `TestCorrelationWindow`, `.__init__`, `._correlated_exposure_reason`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 45 inferred relationships involving `Config` (e.g. with `_acquire_lock()` and `TradingAgent`) actually correct?**
  _`Config` has 45 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `DualBrain` (e.g. with `Cortex` and `Recall`) actually correct?**
  _`DualBrain` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `Candle` (e.g. with `TestPairwiseCorrelation` and `CorrelatedProvider`) actually correct?**
  _`Candle` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Genome` (e.g. with `simulate()` and `walk_forward()`) actually correct?**
  _`Genome` has 18 INFERRED edges - model-reasoned connections that need verification._