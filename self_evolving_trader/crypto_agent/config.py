"""Configuration for the autonomous agent.

Precedence: explicit kwargs > environment > JSON config file > defaults.

A deployed agent is typically started from one JSON file baked into its
image or checkout, with the environment used for per-deployment overrides
(secrets, host-specific tuning) layered on top without editing that file -
so environment intentionally beats the file, and only an explicit keyword
argument (e.g. from a test or a CLI flag) beats the environment.
Every field is deliberately boring and inspectable; the agent writes the
resolved config into Brain 1 on every boot so a run can be reproduced.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

ENV_PREFIX = "CRYPTO_AGENT_"


@dataclass
class Config:
    # --- market ---
    symbol: str = "BTC/USDT"  # primary; `symbols` widens the universe
    symbols: str = ""  # comma-separated, e.g. "BTC/USDT,ETH/USDT,SOL/USDT"
    timeframe: str = "1h"
    provider: str = "synthetic"  # synthetic | binance | ccxt
    exchange: str = "binance"  # used when provider == ccxt
    history_bars: int = 1500

    # --- runtime ---
    mode: str = "paper"  # paper | live
    poll_seconds: float = 60.0
    data_dir: str = "./agent_data"
    seed: int = 7
    log_level: str = "INFO"

    # --- accounting ---
    start_cash: float = 10_000.0
    fee_bps: float = 10.0  # 0.10% taker, per side
    slippage_bps: float = 5.0

    # --- risk ---
    risk_per_trade: float = 0.01  # fraction of equity risked to the stop
    max_position_pct: float = 0.35  # notional cap as a fraction of equity
    max_daily_loss_pct: float = 0.04
    max_drawdown_pct: float = 0.20  # kill switch, persisted across restarts
    max_trades_per_day: int = 12
    max_open_positions: int = 3  # across the whole universe
    max_correlated_exposure_pct: float = 0.5  # cap on notional in one correlated cluster
    correlation_window: int = 200  # bars of returns used to measure correlation
    correlation_threshold: float = 0.7  # above this, two markets count as one bet
    cooldown_bars_after_loss: int = 2
    min_notional: float = 10.0
    # A take-profit has to clear the round trip by this multiple or the setup
    # is refused. Not a gene: clearing your own costs is physics, not taste,
    # and evolution should not get to breed strategies that cannot.
    min_edge_multiple: float = 1.5
    allow_short: bool = False  # spot-style default; genomes may still want it

    # --- evolution ---
    population_size: int = 24
    elite_count: int = 3
    mutation_rate: float = 0.25
    mutation_scale: float = 0.25
    tournament_size: int = 3
    evolve_every_steps: int = 24
    generations_per_cycle: int = 2
    oos_bars: int = 400  # walk-forward hold-out at the tail of history
    promotion_margin: float = 0.05  # champion must be beaten by this much
    benchmark_weight: float = 0.6  # how much fitness is judged against buy-and-hold
    walk_forward_folds: int = 3  # rolling fit/hold-out splits per evaluation
    trials_penalty: bool = True  # deflate fitness by how often the data was reused
    min_trades_for_promotion: int = 3

    # --- memory ---
    consolidate_every_steps: int = 12
    recall_k: int = 6
    memory_dim: int = 256
    max_memories: int = 5000
    memory_half_life_days: float = 30.0

    # --- reflection ---
    reflector: str = "heuristic"  # heuristic | llm
    llm_model: str = "claude-sonnet-5"

    # ------------------------------------------------------------------
    @property
    def symbol_list(self) -> List[str]:
        """Every symbol the agent trades, primary first, de-duplicated.

        One process covering several coins beats one process per coin: the
        portfolio-level risk limits actually see the whole book, and Brain 2's
        lessons are shared, so what the agent learns about high-volatility
        downtrends on one coin informs the next entry on another.
        """
        out: List[str] = []
        for raw in [self.symbol, *self.symbols.split(",")]:
            name = raw.strip().upper()
            if name and name not in out:
                out.append(name)
        return out

    @property
    def root(self) -> Path:
        return Path(self.data_dir).expanduser().resolve()

    @property
    def hippocampus_path(self) -> Path:
        return self.root / "brain1_episodic.sqlite3"

    @property
    def cortex_path(self) -> Path:
        return self.root / "brain2_semantic.sqlite3"

    @property
    def lock_path(self) -> Path:
        return self.root / "agent.lock"

    def ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: Optional[str] = None, **overrides: Any) -> "Config":
        values: Dict[str, Any] = {}
        if path:
            values.update(json.loads(Path(path).expanduser().read_text()))
        values.update(cls._from_env())
        values.update({k: v for k, v in overrides.items() if v is not None})
        known = {f.name: f for f in fields(cls)}
        unknown = sorted(set(values) - set(known))
        if unknown:
            raise ValueError(f"unknown config keys: {', '.join(unknown)}")
        coerced = {name: _coerce(known[name].type, val) for name, val in values.items()}
        cfg = cls(**coerced)
        cfg.validate()
        return cfg

    @staticmethod
    def _from_env() -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        names = {f.name for f in fields(Config)}
        for key, raw in os.environ.items():
            if not key.startswith(ENV_PREFIX):
                continue
            name = key[len(ENV_PREFIX):].lower()
            if name in names:
                out[name] = raw
        return out

    def validate(self) -> None:
        from .core.types import timeframe_ms  # local import to avoid cycles

        timeframe_ms(self.timeframe)
        if self.mode not in ("paper", "live"):
            raise ValueError("mode must be 'paper' or 'live'")
        if self.provider not in ("synthetic", "binance", "ccxt"):
            raise ValueError("provider must be 'synthetic', 'binance' or 'ccxt'")
        if self.reflector not in ("heuristic", "llm"):
            raise ValueError("reflector must be 'heuristic' or 'llm'")
        if not 0 < self.risk_per_trade <= 0.25:
            raise ValueError("risk_per_trade must be in (0, 0.25]")
        if not 0 < self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be in (0, 1]")
        if not 0 < self.max_drawdown_pct <= 1.0:
            raise ValueError("max_drawdown_pct must be in (0, 1]")
        if self.population_size < 4:
            raise ValueError("population_size must be >= 4")
        if self.elite_count >= self.population_size:
            raise ValueError("elite_count must be < population_size")
        if self.start_cash <= 0:
            raise ValueError("start_cash must be positive")
        if self.history_bars <= self.oos_bars + 100:
            raise ValueError("history_bars must exceed oos_bars by at least 100")
        if not 0 < self.max_correlated_exposure_pct <= 1.0:
            raise ValueError("max_correlated_exposure_pct must be in (0, 1]")
        if not 0 <= self.correlation_threshold <= 1.0:
            raise ValueError("correlation_threshold must be in [0, 1]")
        if self.correlation_window < 2:
            raise ValueError("correlation_window must be at least 2 bars")
        if self.walk_forward_folds < 1:
            raise ValueError("walk_forward_folds must be at least 1")
        if not 0 <= self.benchmark_weight <= 1.0:
            raise ValueError("benchmark_weight must be in [0, 1]")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1")
        if self.min_edge_multiple < 0:
            raise ValueError("min_edge_multiple must not be negative")
        for name in self.symbol_list:
            if "/" not in name:
                raise ValueError(f"symbol {name!r} must look like BASE/QUOTE, e.g. BTC/USDT")


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _coerce(type_hint: Any, value: Any) -> Any:
    """Coerce strings coming from env/JSON into the dataclass field type."""
    if not isinstance(value, str):
        return value
    hint = type_hint if isinstance(type_hint, str) else getattr(type_hint, "__name__", "str")
    if hint == "bool":
        low = value.strip().lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise ValueError(f"cannot read {value!r} as a boolean")
    if hint == "int":
        return int(value)
    if hint == "float":
        return float(value)
    return value
