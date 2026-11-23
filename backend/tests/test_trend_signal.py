"""The trend signal must be causal, and the majority vote must not favour any rule."""

import numpy as np
import pandas as pd
import pytest

from services.trend_signal import (
    BASE_RULES,
    MAX_WEIGHT,
    MIN_HISTORY_DAYS,
    current_view,
    majority_signal,
    rule_votes,
    vol_weight,
)


def _ohlc(returns, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(returns))
    idx = pd.date_range("2020-01-01", periods=len(close), freq="D")
    df = pd.DataFrame({"open": np.r_[100.0, close[:-1]], "close": close}, index=idx)
    spread = np.abs(rng.normal(0, 0.003, len(close)))
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + spread)
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - spread)
    return df[["open", "high", "low", "close"]]


@pytest.fixture
def noisy():
    return _ohlc(np.random.default_rng(1).normal(0.0005, 0.03, 600))


def test_signal_never_uses_future_bars(noisy):
    """A value computed with only the past must equal the value computed with the full history."""
    full_votes = rule_votes(noisy)
    full_majority = majority_signal(noisy)
    for cut in (250, 333, 480, 599):
        past = noisy.iloc[:cut]
        pd.testing.assert_series_equal(rule_votes(past).iloc[-1], full_votes.iloc[cut - 1], check_names=False)
        a, b = majority_signal(past).iloc[-1], full_majority.iloc[cut - 1]
        assert (np.isnan(a) and np.isnan(b)) or a == b


def test_majority_is_undefined_until_every_rule_can_vote(noisy):
    signal = majority_signal(noisy)
    assert signal.iloc[: MIN_HISTORY_DAYS - 2].isna().all()
    assert signal.iloc[MIN_HISTORY_DAYS:].notna().all()
    assert set(signal.dropna().unique()) <= {0.0, 1.0}


def test_majority_needs_more_than_half_of_all_rules(noisy):
    votes = rule_votes(noisy).dropna()
    signal = majority_signal(noisy).loc[votes.index]
    assert ((votes.sum(axis=1) > len(BASE_RULES) / 2) == (signal == 1.0)).all()


def test_steady_uptrend_is_held_and_steady_downtrend_is_not():
    up = _ohlc(np.full(400, 0.004))
    down = _ohlc(np.full(400, -0.004))
    assert majority_signal(up).iloc[-1] == 1.0
    assert majority_signal(down).iloc[-1] == 0.0


def test_vol_weight_is_capped_and_shrinks_with_volatility():
    calm = pd.Series(np.random.default_rng(2).normal(0, 0.002, 200))
    wild = pd.Series(np.random.default_rng(2).normal(0, 0.08, 200))
    assert vol_weight(calm).iloc[-1] == MAX_WEIGHT
    assert 0 < vol_weight(wild).iloc[-1] < 0.25


def test_current_view_reports_no_position_when_flat_or_not_ready():
    assert current_view(_ohlc(np.full(100, 0.004)))["ready"] is False
    assert current_view(None)["ready"] is False
    down = current_view(_ohlc(np.full(400, -0.004)))
    assert down["ready"] and down["hold"] is False and down["target_weight"] == 0.0
    up = current_view(_ohlc(np.random.default_rng(3).normal(0.004, 0.01, 400)))
    assert up["hold"] is True and 0 < up["target_weight"] <= MAX_WEIGHT
    assert up["votes_total"] == len(BASE_RULES)
