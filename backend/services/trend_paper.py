"""
Paper ledger for the trend strategies — a forward test, outside the trading engine.

Each strategy gets its own virtual capital and is stepped once per completed
daily bar, using exactly the rule and sizing code the backtest uses
(services.trend_signal). The point is to collect results on data that did not
exist when the rules were chosen, and to compare them with the backtest.

Conventions, identical to scripts.trend_backtest so the two are comparable:
  * the signal is formed on a completed daily close and traded at that close;
  * every symbol with a ready signal gets an equal slice of equity, scaled by
    its volatility weight, and is rebalanced to that target every day;
  * a cost in basis points is charged on every unit of notional traded.

Trading at the close is an assumption a paper ledger can afford and a real
account cannot; the gap between the two is one of the things being measured.

Nothing here places orders, talks to a broker or touches engine state. The
only side effect is writing the four `trend_paper_*` tables.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Optional

import pandas as pd

from services.trend_signal import (
    BASE_RULES,
    MIN_HISTORY_DAYS,
    majority_signal,
    vol_weight,
)

INITIAL_CAPITAL = 10_000.0
# Exchange fee (~10 bps) plus an allowance for slippage. Applied to every strategy.
PAPER_COST_BPS = 20.0

# The two candidates run side by side so the choice between them is made on new
# data, not on the backtest. "always_long" holds everything with the same sizing:
# it is the yardstick, not a candidate.
STRATEGIES: Dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "sma_50": BASE_RULES["sma_50"],
    "majority": majority_signal,
    "always_long": lambda df: pd.Series(1.0, index=df.index),
}


# ── Pure ledger arithmetic ─────────────────────────────────────────────────────

@dataclass
class Ledger:
    cash: float
    positions: Dict[str, float] = field(default_factory=dict)   # symbol -> quantity

    def equity(self, prices: Dict[str, float]) -> float:
        return self.cash + sum(q * prices[s] for s, q in self.positions.items() if s in prices)


@dataclass
class Trade:
    symbol: str
    side: str
    quantity: float
    price: float
    notional: float
    cost: float


def rebalance(ledger: Ledger, prices: Dict[str, float], target_weights: Dict[str, float],
              cost_bps: float) -> List[Trade]:
    """Move `ledger` to the target weights at `prices`, charging costs. Mutates the ledger.

    `target_weights` maps each symbol in today's universe to its weight within
    its own equal slice of equity (0 when the signal is flat). A held symbol
    that is missing from today's universe has no bar for the day, so it is left
    exactly as it is rather than traded at a stale price.
    """
    equity = ledger.equity(prices)
    slice_value = equity / len(target_weights) if target_weights else 0.0
    rate = cost_bps / 10000.0
    trades: List[Trade] = []

    for symbol in sorted(target_weights):
        price = prices.get(symbol)
        if not price or price <= 0:
            continue
        current_qty = ledger.positions.get(symbol, 0.0)
        target_qty = slice_value * target_weights.get(symbol, 0.0) / price
        delta = target_qty - current_qty
        notional = abs(delta) * price
        if notional < 1e-9:
            continue
        cost = notional * rate
        ledger.cash -= delta * price + cost
        if abs(target_qty) < 1e-12:
            ledger.positions.pop(symbol, None)
        else:
            ledger.positions[symbol] = target_qty
        trades.append(Trade(symbol, "BUY" if delta > 0 else "SELL", abs(delta), price, notional, cost))
    return trades


# ── Signals for one day ────────────────────────────────────────────────────────

def signals_for_day(frames: Dict[str, pd.DataFrame], as_of: pd.Timestamp,
                    rule: Callable[[pd.DataFrame], pd.Series]) -> Dict[str, Dict]:
    """Per symbol: close, hold flag and volatility weight using bars up to `as_of` only."""
    out: Dict[str, Dict] = {}
    for symbol, df in frames.items():
        past = df[df.index <= as_of]
        if len(past) < MIN_HISTORY_DAYS or past.index[-1] != as_of:
            continue   # not enough history, or no bar for this day
        hold = rule(past).iloc[-1]
        weight = vol_weight(past["close"].pct_change()).iloc[-1]
        if pd.isna(hold) or pd.isna(weight):
            continue
        out[symbol] = {"close": float(past["close"].iloc[-1]), "hold": bool(hold > 0),
                       "weight": float(weight)}
    return out


# ── Storage ────────────────────────────────────────────────────────────────────

_DDL = [
    """CREATE TABLE IF NOT EXISTS trend_paper_equity (
        strategy TEXT NOT NULL, as_of TEXT NOT NULL, equity FLOAT NOT NULL, cash FLOAT NOT NULL,
        exposure FLOAT NOT NULL, held INTEGER NOT NULL, universe INTEGER NOT NULL,
        costs FLOAT NOT NULL, daily_return FLOAT, recorded_at TEXT NOT NULL,
        PRIMARY KEY (strategy, as_of))""",
    """CREATE TABLE IF NOT EXISTS trend_paper_positions (
        strategy TEXT NOT NULL, symbol TEXT NOT NULL, quantity FLOAT NOT NULL, price FLOAT NOT NULL,
        PRIMARY KEY (strategy, symbol))""",
    """CREATE TABLE IF NOT EXISTS trend_paper_trades (
        strategy TEXT NOT NULL, as_of TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
        quantity FLOAT NOT NULL, price FLOAT NOT NULL, notional FLOAT NOT NULL, cost FLOAT NOT NULL,
        PRIMARY KEY (strategy, as_of, symbol))""",
    """CREATE TABLE IF NOT EXISTS trend_paper_signals (
        strategy TEXT NOT NULL, as_of TEXT NOT NULL, symbol TEXT NOT NULL, hold INTEGER NOT NULL,
        weight FLOAT NOT NULL, close FLOAT NOT NULL,
        PRIMARY KEY (strategy, as_of, symbol))""",
]


class SqlStore:
    """Persists the ledger. Each day for a strategy is written in one transaction."""

    def __init__(self, session_factory):
        self._session_factory = session_factory
        from sqlalchemy import text
        self._text = text
        with self._session_factory() as db:
            for ddl in _DDL:
                db.execute(text(ddl))
            db.commit()

    def last_day(self, strategy: str) -> Optional[Dict]:
        with self._session_factory() as db:
            row = db.execute(self._text(
                "SELECT as_of, equity, cash FROM trend_paper_equity "
                "WHERE strategy = :s ORDER BY as_of DESC LIMIT 1"), {"s": strategy}).first()
        return None if row is None else {"as_of": row[0], "equity": float(row[1]), "cash": float(row[2])}

    def load_ledger(self, strategy: str, default_cash: float) -> Ledger:
        last = self.last_day(strategy)
        with self._session_factory() as db:
            rows = db.execute(self._text(
                "SELECT symbol, quantity FROM trend_paper_positions WHERE strategy = :s"),
                {"s": strategy}).all()
        return Ledger(cash=last["cash"] if last else default_cash,
                      positions={r[0]: float(r[1]) for r in rows})

    def save_day(self, strategy: str, as_of: str, ledger: Ledger, prices: Dict[str, float],
                 trades: List[Trade], signals: Dict[str, Dict], daily_return: Optional[float]) -> None:
        equity = ledger.equity(prices)
        exposure = (equity - ledger.cash) / equity if equity else 0.0
        t = self._text
        with self._session_factory() as db:
            db.execute(t(
                "INSERT INTO trend_paper_equity (strategy, as_of, equity, cash, exposure, held, universe, "
                "costs, daily_return, recorded_at) VALUES (:s, :d, :e, :c, :x, :h, :u, :k, :r, :t)"),
                {"s": strategy, "d": as_of, "e": equity, "c": ledger.cash, "x": exposure,
                 "h": len(ledger.positions), "u": len(signals), "k": sum(tr.cost for tr in trades),
                 "r": daily_return, "t": datetime.now(timezone.utc).isoformat()})
            db.execute(t("DELETE FROM trend_paper_positions WHERE strategy = :s"), {"s": strategy})
            for symbol, qty in ledger.positions.items():
                db.execute(t("INSERT INTO trend_paper_positions (strategy, symbol, quantity, price) "
                             "VALUES (:s, :y, :q, :p)"),
                           {"s": strategy, "y": symbol, "q": qty, "p": prices.get(symbol, 0.0)})
            for tr in trades:
                db.execute(t("INSERT INTO trend_paper_trades (strategy, as_of, symbol, side, quantity, "
                             "price, notional, cost) VALUES (:s, :d, :y, :side, :q, :p, :n, :k)"),
                           {"s": strategy, "d": as_of, "y": tr.symbol, "side": tr.side, "q": tr.quantity,
                            "p": tr.price, "n": tr.notional, "k": tr.cost})
            for symbol, sig in signals.items():
                db.execute(t("INSERT INTO trend_paper_signals (strategy, as_of, symbol, hold, weight, close) "
                             "VALUES (:s, :d, :y, :h, :w, :c)"),
                           {"s": strategy, "d": as_of, "y": symbol, "h": int(sig["hold"]),
                            "w": sig["weight"], "c": sig["close"]})
            db.commit()   # equity row has a primary key: a repeated day fails as a whole

    def equity_history(self, strategy: str) -> pd.DataFrame:
        with self._session_factory() as db:
            rows = db.execute(self._text(
                "SELECT as_of, equity, exposure, held, universe, costs, daily_return "
                "FROM trend_paper_equity WHERE strategy = :s ORDER BY as_of"), {"s": strategy}).all()
        return pd.DataFrame(rows, columns=["as_of", "equity", "exposure", "held", "universe",
                                           "costs", "daily_return"])

    def trade_count(self, strategy: str) -> int:
        with self._session_factory() as db:
            return int(db.execute(self._text(
                "SELECT COUNT(*) FROM trend_paper_trades WHERE strategy = :s"), {"s": strategy}).scalar() or 0)

    def positions(self, strategy: str) -> Dict[str, Dict]:
        with self._session_factory() as db:
            rows = db.execute(self._text(
                "SELECT symbol, quantity, price FROM trend_paper_positions WHERE strategy = :s "
                "ORDER BY symbol"), {"s": strategy}).all()
        return {r[0]: {"quantity": float(r[1]), "price": float(r[2])} for r in rows}


# ── Daily run ──────────────────────────────────────────────────────────────────

def completed_days(frames: Dict[str, pd.DataFrame], today_utc: date) -> List[pd.Timestamp]:
    """Every bar date present in the data that is strictly before today (UTC)."""
    cutoff = pd.Timestamp(today_utc)
    days = set()
    for df in frames.values():
        days.update(d for d in df.index if d < cutoff)
    return sorted(days)


def step_strategy(store: SqlStore, strategy: str, frames: Dict[str, pd.DataFrame],
                  as_of: pd.Timestamp, capital: float, cost_bps: float) -> Optional[Dict]:
    """Advance one strategy by one completed day. Returns a summary, or None if skipped."""
    day = str(as_of.date())
    last = store.last_day(strategy)
    if last and last["as_of"] >= day:
        return None   # already recorded — never rewrite history

    signals = signals_for_day(frames, as_of, STRATEGIES[strategy])
    if not signals:
        return None   # no symbol has a completed bar for this day

    ledger = store.load_ledger(strategy, capital)
    prices = {s: sig["close"] for s, sig in signals.items()}
    for symbol in ledger.positions:   # held but not priced today: carry the last known close
        if symbol not in prices and symbol in frames:
            past = frames[symbol][frames[symbol].index <= as_of]
            if len(past):
                prices[symbol] = float(past["close"].iloc[-1])

    equity_before = ledger.equity(prices)
    targets = {s: (sig["weight"] if sig["hold"] else 0.0) for s, sig in signals.items()}
    trades = rebalance(ledger, prices, targets, cost_bps)
    equity_after = ledger.equity(prices)
    daily_return = (equity_after / last["equity"] - 1.0) if last and last["equity"] else None

    store.save_day(strategy, day, ledger, prices, trades, signals, daily_return)
    return {"strategy": strategy, "as_of": day, "equity": equity_after,
            "equity_before_costs": equity_before, "trades": len(trades),
            "held": len(ledger.positions), "universe": len(signals)}


def run(store: SqlStore, frames: Dict[str, pd.DataFrame], today_utc: date,
        capital: float = INITIAL_CAPITAL, cost_bps: float = PAPER_COST_BPS) -> List[Dict]:
    """Bring every strategy up to the last completed day.

    A new strategy starts on the most recent completed day. An existing one is
    stepped through every completed day it has not recorded yet, in order, so a
    missed run is caught up exactly instead of skipped.
    """
    days = completed_days(frames, today_utc)
    if not days:
        return []
    results: List[Dict] = []
    for strategy in STRATEGIES:
        last = store.last_day(strategy)
        pending = [d for d in days if str(d.date()) > last["as_of"]] if last else days[-1:]
        for as_of in pending:
            summary = step_strategy(store, strategy, frames, as_of, capital, cost_bps)
            if summary:
                results.append(summary)
    return results


def summary(store: SqlStore, capital: float = INITIAL_CAPITAL) -> List[Dict]:
    out = []
    for strategy in STRATEGIES:
        hist = store.equity_history(strategy)
        if hist.empty:
            out.append({"strategy": strategy, "days": 0})
            continue
        equity = hist["equity"].astype(float)
        out.append({
            "strategy": strategy,
            "start": hist["as_of"].iloc[0],
            "as_of": hist["as_of"].iloc[-1],
            "days": int(len(hist)),
            "equity": round(float(equity.iloc[-1]), 2),
            "total_return_pct": round((float(equity.iloc[-1]) / capital - 1.0) * 100, 2),
            "max_drawdown_pct": round(float((equity / equity.cummax() - 1.0).min()) * 100, 2),
            "exposure_pct": round(float(hist["exposure"].iloc[-1]) * 100, 1),
            "held": int(hist["held"].iloc[-1]),
            "universe": int(hist["universe"].iloc[-1]),
            "costs_total": round(float(hist["costs"].sum()), 2),
            "trades": store.trade_count(strategy),
        })
    return out
