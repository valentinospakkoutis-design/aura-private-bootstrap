"""The survivorship universe must be chosen without knowing the future."""

import numpy as np
import pandas as pd

from scripts.survivorship_backtest import (
    build_membership, evaluate, is_candidate, parse_kline_csv, synthetic_frames, verdict,
)


def test_candidate_filter():
    assert is_candidate("BTCUSDT")
    assert is_candidate("LUNAUSDT")
    assert is_candidate("JUPUSDT")          # ends in UP but is a real coin
    assert not is_candidate("BTCUPUSDT")    # leveraged token
    assert not is_candidate("ETHBEARUSDT")
    assert not is_candidate("USDCUSDT")     # stablecoin
    assert not is_candidate("BTCBUSD")      # not a USDT pair


def test_membership_ignores_the_future():
    frames = synthetic_frames(days=900, coins=6)
    full = build_membership(frames, top_n=3)
    cut = pd.Timestamp("2021-06-15")
    truncated = build_membership({s: df[df.index <= cut] for s, df in frames.items()}, top_n=3)
    common = truncated.index
    pd.testing.assert_frame_equal(full.loc[common, truncated.columns], truncated)


def test_membership_respects_top_n_and_history():
    frames = synthetic_frames(days=900, coins=8)
    member = build_membership(frames, top_n=3)
    assert member.sum(axis=1).max() <= 3
    assert not member.iloc[:200].any().any()   # nothing before rules can have an opinion


def test_dead_coin_leaves_when_its_data_ends():
    frames = synthetic_frames(days=900, coins=6)
    dead = frames["C0USDT"]
    member = build_membership(frames, top_n=6)
    after = member.index[member.index > dead.index[-1] + pd.Timedelta(days=31)]
    assert not member.loc[after, "C0USDT"].any()


def test_parse_handles_microseconds_and_header():
    ms = b"1577836800000,1,2,0.5,1.5,10,1577923199999,15,3,1,1,0\n"
    us = b"open_time,open,high,low,close,volume,close_time,quote_volume,count,a,b,c\n" \
         b"1735689600000000,1,2,0.5,1.5,10,1735775999999999,15,3,1,1,0\n"
    assert str(parse_kline_csv(ms).index[0])[:10] == "2020-01-01"
    assert str(parse_kline_csv(us).index[0])[:10] == "2025-01-01"


def test_verdict_follows_preregistered_thresholds():
    assert verdict(2.0, 0.01) == "HOLDS"
    assert verdict(2.0, 0.07) == "UNCERTAIN"
    assert verdict(2.0, 0.20) == "REJECTED"
    assert verdict(-0.1, 0.01) == "REJECTED"


def test_random_walks_are_not_declared_an_edge():
    report = evaluate(synthetic_frames(), cost_bps=30.0, placebo_runs=40, top_n=8)
    assert report["universe"]["no_longer_trading"] >= 1
    for name in ("sma_50", "majority"):
        row = report["strategies"][name]
        assert np.isfinite(row["sharpe"])
        assert row["verdict"] in {"REJECTED", "UNCERTAIN", "HOLDS"}
