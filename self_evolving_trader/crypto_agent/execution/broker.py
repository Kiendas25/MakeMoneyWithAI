"""Order execution.

``PaperBroker`` is the default and simulates fills with the same fee and
slippage assumptions the backtester uses, keeping its balance in Brain 1 so a
restart resumes the same book.

``CcxtBroker`` places real orders. It refuses to initialise unless the config
says ``mode=live`` *and* the operator has set ``CRYPTO_AGENT_CONFIRM_LIVE`` to
the exact confirmation string, because "it started trading my actual money
because a config default flipped" is not a recoverable mistake. Before it
will place an order it loads the exchange's market metadata and rounds the
requested quantity down to the venue's step size, because exchanges reject an
unrounded amount outright rather than rounding it for you - and both brokers
expose a ``reconcile()`` that re-checks the local book against the source of
truth, since a crash mid-order or a partial fill otherwise leaves every
downstream risk calculation silently wrong.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, Tuple

from ..config import Config
from ..core.types import Fill
from ..brain.hippocampus import Hippocampus

log = logging.getLogger(__name__)

LIVE_CONFIRMATION_ENV = "CRYPTO_AGENT_CONFIRM_LIVE"
LIVE_CONFIRMATION_VALUE = "I_UNDERSTAND_THE_RISK"
BROKER_STATE_KEY = "broker.state"


class BrokerOrderError(RuntimeError):
    """A live order was rejected, or its outcome could not be confirmed as a fill.

    Callers must treat this as "assume nothing filled" - the whole point is
    that a caller can catch a real problem instead of being handed back a
    ``Fill`` for money that never actually moved.
    """


@dataclass
class ReconcileReport:
    """What ``reconcile()`` found when it checked the local book against the
    source of truth.

    ``corrected`` maps a field name (e.g. ``"cash"`` or ``"holdings:BTC/USDT"``)
    to a ``(local, truth)`` pair for everything that had drifted and was
    overwritten with the true value; an empty dict means the local book
    already agreed. Both brokers return this same shape so a caller never has
    to special-case which one it is holding.
    """

    broker: str
    corrected: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    open_orders: int = 0

    @property
    def clean(self) -> bool:
        return not self.corrected


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

    def reconcile(self) -> ReconcileReport:
        """Paper trading has no external venue to drift from - the local
        book *is* the source of truth - so this is a cheap no-op that still
        returns the report shape ``CcxtBroker.reconcile()`` does, so a caller
        holding either broker can call it unconditionally.
        """
        return ReconcileReport(broker=self.name)


class CcxtBroker:
    """Live exchange orders through ccxt. Opt-in, guarded, and audited.

    Keeps a locally cached ``cash``/``holdings`` view - updated optimistically
    from each order's response, exactly like ``PaperBroker`` - rather than
    re-fetching the balance on every read. That is what makes ``reconcile()``
    meaningful: the cache is exactly the thing that can drift from the
    exchange if the process dies mid-order or a fill turns out partial, and
    ``reconcile()`` is what notices and fixes it.
    """

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
        self.markets: Dict[str, Any] = {}
        self._load_markets()
        self._cash, self._holdings = self._fetch_live_book()
        brain.log_event("broker", f"live ccxt broker armed on {cfg.exchange}", level="WARNING")

    # -- market metadata -------------------------------------------------
    def _load_markets(self) -> None:
        """Pull the exchange's LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL metadata once.

        Not every ccxt exchange object exposes ``load_markets`` the same way
        in tests or degraded environments, so this is defensive: a failure
        here must not stop the broker from constructing, it just means
        rounding later falls back to the config's ``min_notional`` and an
        unrounded quantity.
        """
        load = getattr(self.exchange, "load_markets", None)
        if load is not None:
            try:
                load()
            except Exception as exc:  # a slow/broken exchange must not crash construction
                self.brain.log_event(
                    "broker", f"load_markets failed on {self.cfg.exchange}: {exc}",
                    {"error": str(exc)}, level="WARNING",
                )
        self.markets = getattr(self.exchange, "markets", None) or {}

    def _market(self, symbol: str) -> Dict[str, Any]:
        return self.markets.get(symbol) or {}

    def _step_size(self, symbol: str) -> Optional[float]:
        """The exchange's LOT_SIZE increment for ``symbol``, or ``None`` when
        the market metadata does not say so - the caller then leaves the
        quantity as given, besides the min-notional check.
        """
        limits = self._market(symbol).get("limits") or {}
        amount_limits = limits.get("amount") or {}
        for key in ("step", "min"):  # not every exchange names the step the same way
            raw = amount_limits.get(key)
            if not raw:
                continue
            try:
                step = float(raw)
            except (TypeError, ValueError):
                continue
            if step > 0:
                return step
        precision = (self._market(symbol).get("precision") or {}).get("amount")
        if precision is None:
            return None
        try:
            precision = float(precision)
        except (TypeError, ValueError):
            return None
        if precision <= 0:
            return None
        # ccxt reports amount precision either as a decimal-place count (the
        # common "DECIMAL_PLACES" convention, e.g. 6) or as the tick size
        # itself (the "TICK_SIZE" convention, e.g. 0.000001); a value under 1
        # can only be the latter, so treat it as an already-usable step.
        if precision < 1:
            return precision
        return 10 ** (-int(precision))

    def _min_notional(self, symbol: str) -> float:
        cost_min = ((self._market(symbol).get("limits") or {}).get("cost") or {}).get("min")
        if cost_min:
            try:
                value = float(cost_min)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                return value
        return float(self.cfg.min_notional)

    def _round_amount_down(self, symbol: str, qty: float) -> float:
        """Round ``qty`` down to the venue's step size - never up, because
        rounding up can push an order past the risk budget or the available
        balance, and an exchange rejects an unrounded amount rather than
        rounding it for us.
        """
        step = self._step_size(symbol)
        rounded = qty
        if step:
            # +epsilon so a quantity that is already an exact multiple of the
            # step isn't knocked down a full step by ordinary float error.
            steps = math.floor(qty / step + 1e-9)
            rounded = steps * step
        to_precision = getattr(self.exchange, "amount_to_precision", None)
        if to_precision is not None:
            try:
                formatted = float(to_precision(symbol, rounded))
            except Exception as exc:  # a badly-behaved exchange stub must not block trading
                log.warning("amount_to_precision failed for %s: %s", symbol, exc)
            else:
                # amount_to_precision may only reformat the string, never hand
                # back more coin than we already floored to.
                if formatted <= rounded + 1e-12:
                    rounded = formatted
        return max(rounded, 0.0)

    # -- balances ----------------------------------------------------------
    def _fetch_live_book(self) -> Tuple[float, Dict[str, float]]:
        balance = self.exchange.fetch_balance()
        free = balance.get("free", {}) or {}
        cash = float(free.get(self.quote, 0.0))
        base_qty = float(free.get(self.base, 0.0))
        holdings = {self.cfg.symbol: base_qty} if abs(base_qty) > 1e-12 else {}
        return cash, holdings

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def holdings(self) -> Dict[str, float]:
        return dict(self._holdings)

    @property
    def qty(self) -> float:
        return self._holdings.get(self.cfg.symbol, 0.0)

    def equity(self, price: float) -> float:
        return self._cash + self.qty * price

    # -- orders --------------------------------------------------------
    def market_order(self, side: str, qty: float, price: float, ts: int,
                     symbol: Optional[str] = None) -> Fill:
        if qty <= 0:
            raise ValueError("qty must be positive")
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        market_symbol = symbol or self.cfg.symbol
        rounded_qty = self._round_amount_down(market_symbol, qty)
        if rounded_qty <= 0:
            raise BrokerOrderError(
                f"quantity {qty} rounds down to 0 at {market_symbol}'s exchange step size"
            )
        notional = rounded_qty * price
        min_notional = self._min_notional(market_symbol)
        if notional < min_notional:
            raise BrokerOrderError(
                f"order notional {notional:.8f} {self.quote} for {market_symbol} is below the "
                f"exchange minimum of {min_notional:.8f} {self.quote} after rounding down to "
                "step size - refusing to place it rather than risk a silent reject"
            )

        try:
            order = self.exchange.create_order(market_symbol, "market", side, rounded_qty)
        except Exception as exc:  # the exchange call itself failed - nothing filled
            self.brain.log_event(
                "order_failed", f"live {side} {rounded_qty} {market_symbol} rejected: {exc}",
                {"side": side, "qty": rounded_qty, "symbol": market_symbol, "error": str(exc)},
                level="WARNING",
            )
            raise BrokerOrderError(f"live order failed: {exc}") from exc

        status = order.get("status")
        filled = float(order.get("filled") or 0.0)
        if filled <= 0 or status in ("canceled", "cancelled", "rejected", "expired"):
            # ccxt's status vocabulary is exchange-dependent, so this only
            # trusts an explicit failure state or a zero fill - anything else
            # is treated as filled, but never silently as more than reported.
            self.brain.log_event(
                "order_incomplete",
                f"live {side} {rounded_qty} {market_symbol} did not fill: status={status}",
                {"order_id": order.get("id"), "status": status, "filled": filled},
                level="WARNING",
            )
            raise BrokerOrderError(
                f"order did not fill (status={status!r}, filled={filled}); "
                "reconcile() before assuming anything about the account's real state"
            )

        filled_price = float(order.get("average") or order.get("price") or price)
        fee_info = order.get("fee") or {}
        fee = float(fee_info.get("cost") or filled * filled_price * self.cfg.fee_bps / 10_000.0)

        signed = filled if side == "buy" else -filled
        self._cash -= signed * filled_price + fee
        held = self._holdings.get(market_symbol, 0.0) + signed
        if abs(held) < 1e-12:
            self._holdings.pop(market_symbol, None)
        else:
            self._holdings[market_symbol] = held

        self.brain.log_event(
            "fill",
            f"live {side} {filled} {market_symbol} @ {filled_price}",
            {"order_id": order.get("id"), "status": status},
            level="WARNING",
        )
        return Fill(ts=ts, side=side, qty=filled, price=filled_price, fee=fee)

    # -- reconciliation --------------------------------------------------
    def reconcile(self) -> ReconcileReport:
        """Re-fetch the real balance (and open orders) and make the local
        cache match it, logging anything that had drifted.

        This is what catches a crash mid-order or a partial fill: the local
        cache is only ever updated optimistically from an order's response,
        so if the process died between placing an order and recording its
        fill - or the fill was only partial - this is what notices before
        risk math runs on stale numbers.
        """
        try:
            live_cash, live_holdings = self._fetch_live_book()
        except Exception as exc:  # network/exchange trouble must not crash reconciliation
            self.brain.log_event(
                "reconcile_failed",
                f"could not fetch live balance from {self.cfg.exchange}: {exc}",
                {"error": str(exc)}, level="WARNING",
            )
            return ReconcileReport(broker=self.name, open_orders=-1)

        corrected: Dict[str, Tuple[float, float]] = {}
        if abs(live_cash - self._cash) > 1e-9:
            corrected["cash"] = (self._cash, live_cash)
        for sym in {self.cfg.symbol, *self._holdings.keys(), *live_holdings.keys()}:
            local_qty = self._holdings.get(sym, 0.0)
            live_qty = live_holdings.get(sym, 0.0)
            if abs(local_qty - live_qty) > 1e-9:
                corrected[f"holdings:{sym}"] = (local_qty, live_qty)

        self._cash, self._holdings = live_cash, live_holdings

        open_orders = 0
        fetch_open = getattr(self.exchange, "fetch_open_orders", None)
        if fetch_open is not None:
            try:
                open_orders = len(fetch_open(self.cfg.symbol) or [])
            except Exception as exc:  # optional signal only - never fatal
                self.brain.log_event(
                    "reconcile_open_orders_failed", str(exc), {"error": str(exc)}, level="WARNING"
                )

        if corrected:
            self.brain.log_event(
                "reconcile",
                f"local book drifted from {self.cfg.exchange} on {sorted(corrected)}",
                {"corrected": {k: list(v) for k, v in corrected.items()}},
                level="WARNING",
            )
        return ReconcileReport(broker=self.name, corrected=corrected, open_orders=open_orders)


def make_broker(cfg: Config, brain: Hippocampus) -> Broker:
    if cfg.mode == "live":
        return CcxtBroker(cfg, brain)
    return PaperBroker(cfg, brain)
