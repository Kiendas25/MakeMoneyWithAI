"""Order execution.

``PaperBroker`` is the default and simulates fills with the same fee and
slippage assumptions the backtester uses, keeping its balance in Brain 1 so a
restart resumes the same book.

``CcxtBroker`` places real orders. It refuses to initialise unless the config
says ``mode=live`` *and* the operator has set ``CRYPTO_AGENT_CONFIRM_LIVE`` to
the exact confirmation string, because "it started trading my actual money
because a config default flipped" is not a recoverable mistake.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Mapping, Optional, Protocol

from ..config import Config
from ..core.types import Fill
from ..brain.hippocampus import Hippocampus

log = logging.getLogger(__name__)

LIVE_CONFIRMATION_ENV = "CRYPTO_AGENT_CONFIRM_LIVE"
LIVE_CONFIRMATION_VALUE = "I_UNDERSTAND_THE_RISK"
BROKER_STATE_KEY = "broker.state"


class Broker(Protocol):
    name: str

    def market_order(self, side: str, qty: float, price: float, ts: int,
                     symbol: Optional[str] = None) -> Fill:
        ...

    @property
    def cash(self) -> float:
        ...


class PaperBroker:
    """Simulated fills, real bookkeeping."""

    name = "paper"

    def __init__(self, cfg: Config, brain: Hippocampus) -> None:
        self.cfg = cfg
        self.brain = brain
        state = brain.get_state(BROKER_STATE_KEY) or {}
        self._cash = float(state.get("cash", cfg.start_cash))
        self._holdings: Dict[str, float] = {
            str(k): float(v) for k, v in (state.get("holdings") or {}).items()
        }
        if "qty" in state and not self._holdings:  # book from the single-symbol era
            legacy = float(state["qty"])
            if legacy:
                self._holdings[cfg.symbol] = legacy

    # ------------------------------------------------------------------
    @property
    def cash(self) -> float:
        return self._cash

    @property
    def holdings(self) -> Dict[str, float]:
        return dict(self._holdings)

    @property
    def qty(self) -> float:
        """Units of the primary symbol - the single-symbol convenience view."""
        return self.qty_of(self.cfg.symbol)

    def qty_of(self, symbol: str) -> float:
        return self._holdings.get(symbol, 0.0)

    def equity(self, price: float | Mapping[str, float]) -> float:
        """Cash plus every holding marked to the prices given.

        Accepts a single price (primary symbol) or a symbol->price mapping, so
        callers that only track one market keep working.
        """
        if isinstance(price, Mapping):
            return self._cash + sum(
                qty * float(price.get(sym, 0.0)) for sym, qty in self._holdings.items()
            )
        return self._cash + self.qty_of(self.cfg.symbol) * float(price)

    def _persist(self) -> None:
        self.brain.set_state(
            BROKER_STATE_KEY, {"cash": self._cash, "holdings": self._holdings}
        )

    def market_order(self, side: str, qty: float, price: float, ts: int,
                     symbol: Optional[str] = None) -> Fill:
        if qty <= 0:
            raise ValueError("qty must be positive")
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        market = symbol or self.cfg.symbol
        slip = self.cfg.slippage_bps / 10_000.0
        fill_price = price * (1 + slip) if side == "buy" else price * (1 - slip)
        notional = qty * fill_price
        fee = notional * (self.cfg.fee_bps / 10_000.0)
        signed = qty if side == "buy" else -qty
        self._cash -= signed * fill_price + fee
        held = self._holdings.get(market, 0.0) + signed
        if abs(held) < 1e-12:
            self._holdings.pop(market, None)
        else:
            self._holdings[market] = held
        self._persist()
        fill = Fill(ts=ts, side=side, qty=qty, price=fill_price, fee=fee)
        self.brain.log_event(
            "fill",
            f"paper {side} {qty:.6f} {market} @ {fill_price:.2f} (fee {fee:.4f})",
            {"cash": self._cash, "holdings": self._holdings},
        )
        return fill

    def reset(self) -> None:
        self._cash = self.cfg.start_cash
        self._holdings = {}
        self._persist()


class CcxtBroker:
    """Live exchange orders through ccxt. Opt-in, guarded, and audited."""

    name = "ccxt"

    def __init__(self, cfg: Config, brain: Hippocampus) -> None:
        if cfg.mode != "live":
            raise RuntimeError("CcxtBroker requires mode='live'")
        if os.environ.get(LIVE_CONFIRMATION_ENV) != LIVE_CONFIRMATION_VALUE:
            raise RuntimeError(
                f"live trading is disabled: set {LIVE_CONFIRMATION_ENV}={LIVE_CONFIRMATION_VALUE} "
                "to confirm you accept the risk of real orders"
            )
        try:
            import ccxt  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional path
            raise ImportError("live trading needs ccxt: pip install ccxt") from exc

        api_key = os.environ.get("CRYPTO_AGENT_API_KEY")
        secret = os.environ.get("CRYPTO_AGENT_API_SECRET")
        if not api_key or not secret:
            raise RuntimeError(
                "set CRYPTO_AGENT_API_KEY and CRYPTO_AGENT_API_SECRET for live trading"
            )
        self.cfg = cfg
        self.brain = brain
        self.exchange = getattr(ccxt, cfg.exchange)(
            {
                "apiKey": api_key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )
        password = os.environ.get("CRYPTO_AGENT_API_PASSWORD")
        if password:
            self.exchange.password = password
        self.quote = cfg.symbol.split("/")[-1]
        self.base = cfg.symbol.split("/")[0]
        brain.log_event("broker", f"live ccxt broker armed on {cfg.exchange}", level="WARNING")

    @property
    def cash(self) -> float:
        balance = self.exchange.fetch_balance()
        return float(balance.get("free", {}).get(self.quote, 0.0))

    @property
    def qty(self) -> float:
        balance = self.exchange.fetch_balance()
        return float(balance.get("free", {}).get(self.base, 0.0))

    def equity(self, price: float) -> float:
        return self.cash + self.qty * price

    def market_order(self, side: str, qty: float, price: float, ts: int) -> Fill:
        if qty <= 0:
            raise ValueError("qty must be positive")
        order = self.exchange.create_order(self.cfg.symbol, "market", side, qty)
        filled_price = float(order.get("average") or order.get("price") or price)
        fee_info = order.get("fee") or {}
        fee = float(fee_info.get("cost") or qty * filled_price * self.cfg.fee_bps / 10_000.0)
        self.brain.log_event(
            "fill",
            f"live {side} {qty} {self.cfg.symbol} @ {filled_price}",
            {"order_id": order.get("id"), "status": order.get("status")},
            level="WARNING",
        )
        return Fill(ts=ts, side=side, qty=float(order.get("filled") or qty), price=filled_price, fee=fee)


def make_broker(cfg: Config, brain: Hippocampus) -> Broker:
    if cfg.mode == "live":
        return CcxtBroker(cfg, brain)
    return PaperBroker(cfg, brain)
