"""
Trend signal: hold an asset only while it is in an established uptrend.

Pure functions over daily OHLC — no network, no database, no engine state — so
the backtest (scripts.trend_backtest) and anything that trades on the signal
use exactly the same code.

The rules are fixed and have no fitted parameters. The tradeable signal is the
majority vote of all of them, so no single rule is hand-picked after seeing
which one backtested best.

Every function is causal: the value for a day uses only that day and earlier.
A signal formed at a close is acted on afterwards, never on the same bar.
"""

from typing import Callable, Dict

import numpy as np
import pandas as pd

TARGET_DAILY_VOL = 0.01   # size each position to ~1% daily volatility
VOL_WINDOW = 20
MAX_WEIGHT = 1.0          # never lever a single position above 100%

Rule = Callable[[pd.DataFrame], pd.Series]


def rule_sma(n: int) -> Rule:
    """Hold while the close is above its n-day average."""
    def f(df: pd.DataFrame) -> pd.Series:
        sma = df["close"].rolling(n).mean()
        return (df["close"] > sma).astype(float).where(sma.notna())
    return f


def rule_momentum(n: int) -> Rule:
    """Hold while the n-day return is positive (time-series momentum)."""
    def f(df: pd.DataFrame) -> pd.Series:
        past = df["close"].pct_change(n)
        return (past > 0).astype(float).where(past.notna())
    return f


def rule_breakout(entry: int, exit_: int) -> Rule:
    """Enter on a new `entry`-day high, leave on a new `exit_`-day low (Donchian)."""
    def f(df: pd.DataFrame) -> pd.Series:
        upper = df["high"].rolling(entry).max().shift(1)
        lower = df["low"].rolling(exit_).min().shift(1)
        close = df["close"].values
        up, lo = upper.values, lower.values
        out = np.full(len(df), np.nan)
        held = 0.0
        for i in range(len(df)):
            if np.isnan(up[i]) or np.isnan(lo[i]):
                continue
            if held == 0.0 and close[i] > up[i]:
                held = 1.0
            elif held == 1.0 and close[i] < lo[i]:
                held = 0.0
            out[i] = held
        return pd.Series(out, index=df.index)
    return f


BASE_RULES: Dict[str, Rule] = {
    "sma_50": rule_sma(50),
    "sma_100": rule_sma(100),
    "sma_200": rule_sma(200),
    "mom_30": rule_momentum(30),
    "mom_90": rule_momentum(90),
    "mom_180": rule_momentum(180),
    "breakout_55_20": rule_breakout(55, 20),
}

# Days of history needed before every rule has an opinion.
MIN_HISTORY_DAYS = 201


def rule_votes(df: pd.DataFrame) -> pd.DataFrame:
    """One column per base rule: 1.0 hold, 0.0 flat, NaN not enough history yet."""
    return pd.DataFrame({name: rule(df) for name, rule in BASE_RULES.items()})


def majority_signal(df: pd.DataFrame) -> pd.Series:
    """Hold when more than half of ALL base rules say hold.

    Undefined (NaN) until every rule has enough history, so a young listing is
    never traded on a partial vote.
    """
    votes = rule_votes(df)
    complete = votes.notna().all(axis=1)
    held = (votes.sum(axis=1) > len(BASE_RULES) / 2.0).astype(float)
    return held.where(complete)


def vol_weight(returns: pd.Series) -> pd.Series:
    """Position size from trailing volatility: calmer asset, larger position."""
    vol = returns.rolling(VOL_WINDOW).std()
    return (TARGET_DAILY_VOL / vol).clip(upper=MAX_WEIGHT).where(vol > 0)


def current_view(df: pd.DataFrame) -> Dict:
    """What the signal says as of the last completed bar in `df`."""
    if df is None or len(df) < MIN_HISTORY_DAYS:
        return {"ready": False, "reason": f"needs {MIN_HISTORY_DAYS} daily bars",
                "bars": 0 if df is None else int(len(df))}
    votes = rule_votes(df).iloc[-1]
    if votes.isna().any():
        return {"ready": False, "reason": "incomplete history for some rules", "bars": int(len(df))}
    hold = bool(votes.sum() > len(BASE_RULES) / 2.0)
    weight = vol_weight(df["close"].pct_change()).iloc[-1]
    weight = 0.0 if pd.isna(weight) else float(weight)
    return {
        "ready": True,
        "as_of": str(df.index[-1])[:10],
        "close": float(df["close"].iloc[-1]),
        "hold": hold,
        "votes_for": int(votes.sum()),
        "votes_total": len(BASE_RULES),
        "rules": {name: bool(v) for name, v in votes.items()},
        "target_weight": round(weight if hold else 0.0, 4),
        "weight_if_held": round(weight, 4),
    }
