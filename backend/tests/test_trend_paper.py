"""The paper ledger must conserve money, never rewrite a day, and catch up missed days."""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.trend_paper import (
    STRATEGIES,
    Ledger,
    SqlStore,
    rebalance,
    run,
    signals_for_day,
    universe_for,
    step_strategy,
    summary,
)


def _ohlc(returns, start="2025-01-01", seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(returns))
    idx = pd.date_range(start, periods=len(close), freq="D")
    df = pd.DataFrame({"open": np.r_[100.0, close[:-1]], "close": close}, index=idx)
    spread = np.abs(rng.normal(0, 0.003, len(close)))
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + spread)
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - spread)
    return df[["open", "high", "low", "close"]]


@pytest.fixture
def store():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return SqlStore(sessionmaker(bind=engine))


@pytest.fixture
def frames():
    return {
        "UP": _ohlc(np.random.default_rng(1).normal(0.004, 0.02, 420), seed=1),
        "DOWN": _ohlc(np.random.default_rng(2).normal(-0.004, 0.02, 420), seed=2),
        "FLAT": _ohlc(np.random.default_rng(3).normal(0.0, 0.03, 420), seed=3),
    }


def test_rebalance_conserves_money_and_hits_targets():
    ledger = Ledger(cash=9000.0, positions={"A": 10.0})
    prices = {"A": 100.0, "B": 50.0}
    before = ledger.equity(prices)                      # 10,000
    trades = rebalance(ledger, prices, {"A": 0.0, "B": 0.5}, cost_bps=20)
    costs = sum(t.cost for t in trades)
    assert ledger.equity(prices) == pytest.approx(before - costs)
    assert "A" not in ledger.positions                  # flat signal -> sold
    assert ledger.positions["B"] * 50.0 == pytest.approx(before / 2 * 0.5)
    assert costs == pytest.approx((1000.0 + 2500.0) * 0.002)
    assert {t.symbol: t.side for t in trades} == {"A": "SELL", "B": "BUY"}


def test_position_without_a_bar_today_is_left_alone():
    ledger = Ledger(cash=5000.0, positions={"GONE": 3.0})
    trades = rebalance(ledger, {"A": 10.0}, {"A": 1.0}, cost_bps=20)
    assert ledger.positions["GONE"] == 3.0
    assert [t.symbol for t in trades] == ["A"]


def test_signals_use_only_bars_up_to_the_day(frames):
    day = frames["UP"].index[300]
    truncated = {s: df[df.index <= day] for s, df in frames.items()}
    for rule in STRATEGIES.values():
        assert signals_for_day(frames, day, rule) == signals_for_day(truncated, day, rule)


def test_first_run_starts_on_last_completed_day_and_is_idempotent(store, frames):
    today = (frames["UP"].index[-1] + pd.Timedelta(days=1)).date()
    first = run(store, frames, today)
    assert {s["strategy"] for s in first} == {n for n in STRATEGIES if universe_for(n, frames)}
    assert {s["as_of"] for s in first} == {str(frames["UP"].index[-1].date())}
    assert run(store, frames, today) == []              # same day again: nothing rewritten
    rows = {r["strategy"]: r for r in summary(store)}
    assert all(r["days"] == 1 for name, r in rows.items() if universe_for(name, frames))
    # always_long holds all three; the trend rules must not hold the falling asset
    assert rows["always_long"]["held"] == 3
    assert "DOWN" not in store.positions("majority") and "DOWN" not in store.positions("sma_50")
    assert "UP" in store.positions("majority")


def test_todays_forming_bar_is_never_used(store, frames):
    last = frames["UP"].index[-1]
    steps = run(store, frames, last.date())             # the last bar is "today": still forming
    assert {s["as_of"] for s in steps} == {str((last - pd.Timedelta(days=1)).date())}


def test_missed_days_are_caught_up_exactly_like_daily_runs(frames):
    def fresh():
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        return SqlStore(sessionmaker(bind=engine))

    days = list(frames["UP"].index[-6:])
    daily, lumped = fresh(), fresh()
    for d in days:                                      # ran every day
        run(daily, {s: df[df.index <= d] for s, df in frames.items()}, (d + pd.Timedelta(days=1)).date())
    first = days[0]                                     # ran once, then not again until the end
    run(lumped, {s: df[df.index <= first] for s, df in frames.items()}, (first + pd.Timedelta(days=1)).date())
    run(lumped, frames, (days[-1] + pd.Timedelta(days=1)).date())

    for strategy in (n for n in STRATEGIES if universe_for(n, frames)):
        a, b = daily.equity_history(strategy), lumped.equity_history(strategy)
        assert list(a["as_of"]) == list(b["as_of"]) and len(a) == 6
        assert np.allclose(a["equity"].astype(float), b["equity"].astype(float))
        assert daily.positions(strategy).keys() == lumped.positions(strategy).keys()


def test_recorded_day_cannot_be_overwritten(store, frames):
    day = frames["UP"].index[-1]
    assert step_strategy(store, "majority", frames, day, 10_000.0, 20.0) is not None
    assert step_strategy(store, "majority", frames, day, 10_000.0, 20.0) is None
    assert step_strategy(store, "majority", frames, day - pd.Timedelta(days=3), 10_000.0, 20.0) is None
    assert len(store.equity_history("majority")) == 1


def test_equity_moves_with_prices_between_days(store, frames):
    d1, d2 = frames["UP"].index[-2], frames["UP"].index[-1]
    step_strategy(store, "always_long", frames, d1, 10_000.0, 0.0)
    held = store.positions("always_long")
    expected = store.load_ledger("always_long", 0).cash + sum(
        p["quantity"] * float(frames[s].loc[d2, "close"]) for s, p in held.items())
    out = step_strategy(store, "always_long", frames, d2, 10_000.0, 0.0)
    assert out["equity_before_costs"] == pytest.approx(expected)


# ── BTC benchmark lines and the spread measurement (added 25 Nov 2026) ────────

import services.trend_paper as tp
from services.trend_signal import annual_vol_weight


@pytest.fixture
def frames_with_btc(frames):
    out = dict(frames)
    out["BTCUSDC"] = _ohlc(np.random.default_rng(9).normal(0.001, 0.03, 420), seed=9)
    return out


def test_annual_vol_weight_aims_at_the_target_and_never_levers():
    rng = np.random.default_rng(4)
    wild = pd.Series(rng.normal(0, 0.04, 800))          # ~76% a year
    calm = pd.Series(rng.normal(0, 0.001, 800))         # ~2% a year
    w = annual_vol_weight(wild, 0.10)
    realised = float((w.shift(1) * wild).std() * np.sqrt(365))
    assert realised == pytest.approx(0.10, rel=0.15)
    assert float(annual_vol_weight(calm, 0.10).max()) == 1.0    # capped: no leverage


def test_btc_lines_hold_only_btc_within_the_cap(store, frames_with_btc):
    today = (frames_with_btc["UP"].index[-1] + pd.Timedelta(days=1)).date()
    run(store, frames_with_btc, today)
    rows = {r["strategy"]: r for r in summary(store)}
    assert set(store.positions("btc_voltarget")) == {"BTCUSDC"}
    assert set(store.positions("btc_voltarget_trend50")) <= {"BTCUSDC"}
    assert rows["btc_voltarget"]["universe"] == 1
    assert 0 < rows["btc_voltarget"]["exposure_pct"] <= 100.0
    assert rows["btc_voltarget_trend50"]["exposure_pct"] <= rows["btc_voltarget"]["exposure_pct"] + 1e-9


def test_adding_the_btc_lines_changes_nothing_in_the_original_three(frames_with_btc, monkeypatch):
    def fresh():
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        return SqlStore(sessionmaker(bind=engine))

    def play(store):
        for d in frames_with_btc["UP"].index[-8:]:
            run(store, {s: df[df.index <= d] for s, df in frames_with_btc.items()},
                (d + pd.Timedelta(days=1)).date())
        return store

    with_btc = play(fresh())
    originals = ("sma_50", "majority", "always_long")
    monkeypatch.setattr(tp, "SPECS", {k: tp.SPECS[k] for k in originals})
    monkeypatch.setattr(tp, "STRATEGIES", {k: tp.STRATEGIES[k] for k in originals})
    without = play(fresh())
    for name in originals:
        a, b = with_btc.equity_history(name), without.equity_history(name)
        assert list(a["as_of"]) == list(b["as_of"]) and len(a) == 8
        assert (a["equity"].astype(float).values == b["equity"].astype(float).values).all()
        assert with_btc.positions(name) == without.positions(name)


def test_a_line_added_later_starts_on_its_own_day(frames_with_btc, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    store = SqlStore(sessionmaker(bind=engine))
    days = frames_with_btc["UP"].index[-5:]
    full_specs, full_strategies = dict(tp.SPECS), dict(tp.STRATEGIES)
    originals = ("sma_50", "majority", "always_long")
    monkeypatch.setattr(tp, "SPECS", {k: full_specs[k] for k in originals})
    monkeypatch.setattr(tp, "STRATEGIES", {k: full_strategies[k] for k in originals})
    for d in days[:3]:
        run(store, {s: df[df.index <= d] for s, df in frames_with_btc.items()}, (d + pd.Timedelta(days=1)).date())
    monkeypatch.setattr(tp, "SPECS", full_specs)
    monkeypatch.setattr(tp, "STRATEGIES", full_strategies)
    for d in days[3:]:
        run(store, {s: df[df.index <= d] for s, df in frames_with_btc.items()}, (d + pd.Timedelta(days=1)).date())
    assert len(store.equity_history("sma_50")) == 5
    btc = store.equity_history("btc_voltarget")
    assert list(btc["as_of"]) == [str(d.date()) for d in days[3:]]      # no back-filled history


def test_spreads_are_stored_and_summarised_without_touching_ledgers(store, frames_with_btc):
    today = (frames_with_btc["UP"].index[-1] + pd.Timedelta(days=1)).date()
    run(store, frames_with_btc, today)
    before = store.equity_history("sma_50")
    saved = store.save_spreads("2026-11-25T00:10:00+00:00", {
        "BTCUSDC": {"bid": 99.99, "ask": 100.01}, "BTCUSDT": {"bid": 99.995, "ask": 100.005},
        "ETHUSDC": {"bid": 49.95, "ask": 50.05}, "BADUSDC": {"bid": 0.0, "ask": 1.0},
    }, after_close=True)
    assert saved == 3                                   # the zero bid is dropped
    rows = {r["quote"]: r for r in tp.spread_summary(store)}
    assert rows["USDC"]["btc_half_spread_bps"] == pytest.approx(1.0, abs=0.01)
    assert rows["USDT"]["btc_half_spread_bps"] == pytest.approx(0.5, abs=0.01)
    assert rows["USDC"]["worst_symbol"] == "ETHUSDC"
    assert store.equity_history("sma_50").equals(before)
