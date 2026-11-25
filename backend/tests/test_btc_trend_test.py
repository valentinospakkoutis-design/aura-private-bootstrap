"""BTC trend test: fixed thresholds, no look-ahead, same sizing as the paper ledger."""

import numpy as np
import pandas as pd
import pytest

import services.trend_paper as tp
from scripts.btc_trend_test import TARGET_ANNUAL_VOL, decide, every_shift_placebo, run, sized_returns
from scripts.survivorship_backtest import synthetic_frames
from scripts.trend_backtest import RULES


def test_verdict_needs_both_conditions():
    assert decide(3.0, 2.4, 0.01) == "DISTINGUISHABLE"
    assert decide(3.0, 1.9, 0.01) == "NOT DISTINGUISHABLE"      # economic size not shown
    assert decide(3.0, 2.4, 0.20) == "NOT DISTINGUISHABLE"      # timing not shown
    assert decide(-1.0, 2.4, 0.01) == "NOT DISTINGUISHABLE"
    assert decide(3.0, 2.4) == "DISTINGUISHABLE"                # question 2 has no placebo


def test_backtest_and_paper_ledger_use_the_same_target():
    assert TARGET_ANNUAL_VOL == tp.BTC_TARGET_ANNUAL_VOL
    assert tp.SPECS["btc_voltarget_trend50"].rule is tp.BASE_RULES["sma_50"]


def test_todays_position_does_not_depend_on_todays_price():
    df = synthetic_frames()["C1USDT"]
    signal = RULES["sma_50"](df)
    base = sized_returns(df, signal, 30.0)
    shocked = df.copy()
    day = df.index[900]
    shocked.loc[day, "close"] *= 1.5
    after = sized_returns(shocked, RULES["sma_50"](shocked), 30.0)
    assert after.loc[day, "position"] == pytest.approx(base.loc[day, "position"])


def test_placebo_uses_every_shift_and_p_is_a_probability():
    df = synthetic_frames()["C1USDT"].iloc[:500]
    signal = RULES["sma_50"](df)
    out = every_shift_placebo(df, signal, df.index[100:], 30.0)
    assert out["shifts"] == int(signal.notna().sum()) - 1
    assert 0 < out["p_value"] <= 1


def test_report_end_to_end_on_noise():
    quick = lambda df, sig, window, cost: {"actual_sharpe": 0.0, "shifts": 1, "shifted_mean": 0.0,  # noqa: E731
                                           "shifted_95th": 0.0, "p_value": 0.5}
    r = run(synthetic_frames(), 30.0, 9, "C1USDT", placebo=quick)
    assert r["question_1"]["verdict"] == "NOT DISTINGUISHABLE"
    assert r["lines"]["btc_voltarget"]["annual_vol_pct"] == pytest.approx(10.0, abs=2.5)
    assert r["pairwise_correlation_by_year"]
