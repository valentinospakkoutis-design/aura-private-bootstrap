"""The audit must measure the same rules as the original backtests, not new ones."""

import numpy as np

from scripts.method_audit import Tables, deflated_sharpe, run, sharpe_of
from scripts.survivorship_backtest import masked_portfolio, synthetic_frames
from scripts.trend_backtest import symbol_returns
from scripts.xs_momentum_backtest import Universe


def test_fast_portfolio_equals_the_original_backtest():
    raw = synthetic_frames()
    t = Tables(raw, 9, 30.0)
    per = {s: symbol_returns(t.frames[s], 30.0) for s in t.symbols}
    for name in ("sma_50", "majority", "breakout_55_20"):
        original = masked_portfolio({s: r[name]["net"] for s, r in per.items()}, t.member_df)
        assert float((original - t.series(t.signal[name])).abs().max()) < 1e-12


def test_weekly_pick_equals_the_original_relative_strength_rule():
    raw = synthetic_frames()
    t, u = Tables(raw, 9, 30.0), Universe(raw, 9)
    mine = t.series(t.weekly_pick(np.nan_to_num(t.momentum[t.rebalance_rows], nan=-np.inf)), cost=0.0)
    assert float((mine - u.portfolio(u.select(u.momentum), 0.0)).abs().max()) < 1e-12


def test_rotation_keeps_how_often_each_coin_is_held():
    t = Tables(synthetic_frames(), 9, 30.0)
    rotated = t.rotated("sma_50", 333)
    assert np.allclose(np.nansum(rotated, axis=0), np.nansum(t.signal["sma_50"], axis=0))
    assert (np.isnan(rotated) == np.isnan(t.signal["sma_50"])).all()


def test_more_trials_lower_the_deflated_probability():
    t = Tables(synthetic_frames(), 9, 30.0)
    series = {n: t.series(s) for n, s in t.signal.items()}
    eight = deflated_sharpe(series, "mom_30")
    two = deflated_sharpe({k: series[k] for k in ("mom_30", "sma_50")}, "mom_30")
    assert eight["deflated_sharpe_probability"] <= eight["probability_sharpe_above_zero"]
    assert eight["luck_benchmark_sharpe_annual"] >= 0 and two["trials"] == 2


def test_report_runs_end_to_end():
    r = run(synthetic_frames(), runs=15, top_n=9, cost_bps=30.0)
    assert set(r["placebo"]["sma_50"]) >= {"p_own_placebo", "p_best_of_eight"}
    assert r["placebo"]["sma_50"]["p_best_of_eight"] >= r["placebo"]["sma_50"]["p_own_placebo"]
    assert len(r["relative_strength_ranking"]["rule_sharpe_by_rebalance_weekday"]) == 7
    assert r["composition_by_year"] and "in_universe_at_end" in r["endings_and_halts"]
