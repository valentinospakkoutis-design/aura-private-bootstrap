"""Relative strength: the weekly pick must not see the future."""

import numpy as np
import pandas as pd

from scripts.survivorship_backtest import synthetic_frames
from scripts.xs_momentum_backtest import HOLD_FRACTION, Universe, evaluate


def test_selection_ignores_the_future():
    frames = synthetic_frames(days=900, coins=9)
    full = Universe(frames, top_n=9).select(Universe(frames, top_n=9).momentum)
    cut = pd.Timestamp("2021-09-10")
    short_u = Universe({s: df[df.index <= cut] for s, df in frames.items()}, top_n=9)
    short = short_u.select(short_u.momentum)
    pd.testing.assert_frame_equal(full.loc[short.index, short.columns], short)


def test_holds_a_third_and_only_universe_members():
    u = Universe(synthetic_frames(days=900, coins=9), top_n=9)
    held = u.select(u.momentum)
    for day in u.rebalance_days[5:]:
        eligible = int((u.member.loc[day] & u.momentum.loc[day].notna()).sum())
        if eligible:
            assert int(held.loc[day].sum()) == max(1, int(round(eligible * HOLD_FRACTION)))
            assert not held.loc[day][~u.member.loc[day]].any()


def test_top_and_bottom_do_not_overlap_and_random_is_reproducible():
    u = Universe(synthetic_frames(days=900, coins=9), top_n=9)
    top, bottom = u.select(u.momentum), u.select(u.momentum, bottom=True)
    assert float((top * bottom).values.sum()) == 0.0
    a = u.select(None, np.random.default_rng(1))
    b = u.select(None, np.random.default_rng(1))
    pd.testing.assert_frame_equal(a, b)


def test_report_has_a_verdict_from_the_fixed_thresholds():
    r = evaluate(synthetic_frames(), cost_bps=30.0, runs=20, top_n=9)
    assert r["verdict"] in {"HOLDS", "UNCERTAIN", "REJECTED"}
    assert r["with_trend"]["adds_to_trend"] in {True, False}
    if r["verdict"] != "HOLDS":
        assert r["with_trend"]["adds_to_trend"] is False
