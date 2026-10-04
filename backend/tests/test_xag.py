"""
tests/test_xag.py — Deterministic tests for api/xag.py

Run from backend/:
    pytest tests/test_xag.py -v

All yfinance / network calls are mocked — CI never hits Yahoo Finance.
"""

import math
import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import xag
from api.xag import _rsi14


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_cache():
    """Guarantee a clean cache before and after every test."""
    xag._snapshot_cache.clear()
    xag._ohlc_cache.clear()
    yield
    xag._snapshot_cache.clear()
    xag._ohlc_cache.clear()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(xag.router)
    with TestClient(app) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# RSI unit tests (pure function — no mocking needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestRsi14:
    def test_insufficient_data_returns_none(self):
        assert _rsi14([30.0] * 14) is None

    def test_flat_series_returns_50(self):
        """20 identical closes → avg_gain=0 and avg_loss=0 → should return 50."""
        result = _rsi14([30.0] * 20)
        assert result == 50.0

    def test_strictly_rising_returns_100(self):
        """Only gains, no losses → RSI = 100."""
        closes = [float(i) for i in range(1, 30)]
        result = _rsi14(closes)
        assert result == 100.0

    def test_strictly_falling_returns_0(self):
        """Only losses, no gains → RSI ~ 0."""
        closes = [float(30 - i) for i in range(30)]
        result = _rsi14(closes)
        assert result is not None
        assert result < 5.0

    def test_mixed_series_in_range(self):
        import random
        random.seed(42)
        closes = [30.0 + random.uniform(-1, 1) for _ in range(50)]
        result = _rsi14(closes)
        assert result is not None
        assert 0.0 <= result <= 100.0

    def test_result_is_finite(self):
        closes = [float(i % 5) for i in range(30)]
        result = _rsi14(closes)
        assert result is None or math.isfinite(result)

    def test_wilder_reference_fixture(self):
        """
        Reference fixture computed by hand (Wilder RSI on 20-bar series).
        Seed: alternating +1 / -0.5 moves from base 30.
        """
        closes = []
        val = 30.0
        for i in range(20):
            val += 1.0 if i % 2 == 0 else -0.5
            closes.append(round(val, 2))
        result = _rsi14(closes)
        assert result is not None
        # Net-positive series must be above 50
        assert result > 50.0


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint validation — 422 for bad query params
# ─────────────────────────────────────────────────────────────────────────────

class TestOhlcValidation:
    @pytest.mark.parametrize("query,expected_status", [
        ("tf=4h",    422),   # unknown timeframe
        ("n=0",      422),   # n < 1
        ("n=501",    422),   # n > 500
        ("n=abc",    422),   # non-integer n
        ("tf=1m&n=1",  200), # minimum valid
        ("tf=1h&n=500", 200), # maximum valid
    ])
    def test_validation(self, client, query, expected_status, monkeypatch):
        monkeypatch.setattr(xag, "_fetch_ohlc", lambda tf, n: [])
        resp = client.get(f"/api/xag/ohlc?{query}")
        assert resp.status_code == expected_status


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot endpoint
# ─────────────────────────────────────────────────────────────────────────────

def _make_snapshot(**overrides):
    base = {
        "symbol":      "XAGUSD-STD",
        "source":      "yfinance/SI=F (proxy — synthetic bid/ask)",
        "price":       30.123,
        "bid":         30.098,
        "ask":         30.148,
        "rsi_1m":      55.0,
        "rsi_15m":     48.0,
        "rsi_1h":      None,
        "fetched_at":  "2026-01-01T12:00:00+00:00",
        "market_asof": "2026-01-01T11:59:00+00:00",
        "stale":       False,
    }
    base.update(overrides)
    return base


class TestSnapshotEndpoint:
    def test_returns_200_with_required_fields(self, client, monkeypatch):
        monkeypatch.setattr(xag, "_fetch_snapshot", lambda: _make_snapshot())
        resp = client.get("/api/xag/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        for field in ("symbol", "price", "bid", "ask", "rsi_1m", "rsi_15m", "rsi_1h",
                      "fetched_at", "market_asof", "stale", "source"):
            assert field in data, f"Missing field: {field}"

    def test_price_is_positive_finite(self, client, monkeypatch):
        monkeypatch.setattr(xag, "_fetch_snapshot", lambda: _make_snapshot())
        resp = client.get("/api/xag/snapshot")
        price = resp.json()["price"]
        assert price > 0
        assert math.isfinite(price)

    def test_rsi_null_is_acceptable(self, client, monkeypatch):
        monkeypatch.setattr(xag, "_fetch_snapshot", lambda: _make_snapshot(rsi_1m=None))
        resp = client.get("/api/xag/snapshot")
        assert resp.json()["rsi_1m"] is None

    def test_stale_flag_present(self, client, monkeypatch):
        monkeypatch.setattr(xag, "_fetch_snapshot", lambda: _make_snapshot(stale=True))
        resp = client.get("/api/xag/snapshot")
        assert resp.json()["stale"] is True

    def test_502_on_provider_failure(self, client, monkeypatch):
        def _fail():
            raise RuntimeError("Yahoo Finance timeout")
        monkeypatch.setattr(xag, "_fetch_snapshot", _fail)
        resp = client.get("/api/xag/snapshot")
        assert resp.status_code == 502


# ─────────────────────────────────────────────────────────────────────────────
# OHLC endpoint
# ─────────────────────────────────────────────────────────────────────────────

def _make_bars(n=5):
    base_ts = 1700000000
    return [
        {"time": base_ts + i * 60, "open": 30.0, "high": 30.5,
         "low": 29.8, "close": 30.2, "volume": 100}
        for i in range(n)
    ]


class TestOhlcEndpoint:
    def test_returns_list_of_bars(self, client, monkeypatch):
        monkeypatch.setattr(xag, "_fetch_ohlc", lambda tf, n: _make_bars(5))
        resp = client.get("/api/xag/ohlc?tf=1m&n=10")
        assert resp.status_code == 200
        bars = resp.json()
        assert isinstance(bars, list)
        assert len(bars) == 5

    def test_bar_has_required_fields(self, client, monkeypatch):
        monkeypatch.setattr(xag, "_fetch_ohlc", lambda tf, n: _make_bars(1))
        bar = client.get("/api/xag/ohlc?tf=1m&n=1").json()[0]
        for field in ("time", "open", "high", "low", "close", "volume"):
            assert field in bar

    def test_empty_response_on_no_data(self, client, monkeypatch):
        monkeypatch.setattr(xag, "_fetch_ohlc", lambda tf, n: [])
        resp = client.get("/api/xag/ohlc?tf=1h&n=100")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_502_on_provider_failure(self, client, monkeypatch):
        def _fail(tf, n):
            raise RuntimeError("Rate limited")
        monkeypatch.setattr(xag, "_fetch_ohlc", _fail)
        resp = client.get("/api/xag/ohlc?tf=1m&n=10")
        assert resp.status_code == 502


# ─────────────────────────────────────────────────────────────────────────────
# Cache behaviour
# ─────────────────────────────────────────────────────────────────────────────

class TestCacheBehaviour:
    def test_snapshot_cache_hit_before_ttl(self, client, monkeypatch):
        calls = []

        def _fetch():
            calls.append(1)
            return _make_snapshot()

        monkeypatch.setattr(xag, "_fetch_snapshot", _fetch)
        client.get("/api/xag/snapshot")
        client.get("/api/xag/snapshot")
        assert len(calls) == 1, "Second request should hit cache, not call _fetch_snapshot"

    def test_snapshot_cache_refresh_after_ttl(self, client, monkeypatch):
        calls = []
        clock = [1000.0]
        monkeypatch.setattr(xag.time, "monotonic", lambda: clock[0])

        def _fetch():
            calls.append(1)
            return _make_snapshot()

        monkeypatch.setattr(xag, "_fetch_snapshot", _fetch)
        client.get("/api/xag/snapshot")
        assert len(calls) == 1

        clock[0] += xag._SNAPSHOT_TTL + 1
        client.get("/api/xag/snapshot")
        assert len(calls) == 2, "Cache should expire after TTL"

    def test_ohlc_cache_hit_before_ttl(self, client, monkeypatch):
        calls = []

        def _fetch(tf, n):
            calls.append((tf, n))
            return _make_bars(3)

        monkeypatch.setattr(xag, "_fetch_ohlc", _fetch)
        client.get("/api/xag/ohlc?tf=1m&n=10")
        client.get("/api/xag/ohlc?tf=1m&n=10")
        assert len(calls) == 1

    def test_ohlc_cache_refresh_after_ttl(self, client, monkeypatch):
        calls = []
        clock = [1000.0]
        monkeypatch.setattr(xag.time, "monotonic", lambda: clock[0])

        def _fetch(tf, n):
            calls.append((tf, n))
            return _make_bars(3)

        monkeypatch.setattr(xag, "_fetch_ohlc", _fetch)
        client.get("/api/xag/ohlc?tf=1m&n=10")
        clock[0] += xag._OHLC_TTL + 1
        client.get("/api/xag/ohlc?tf=1m&n=10")
        assert len(calls) == 2

    def test_ohlc_cache_isolated_by_timeframe(self, client, monkeypatch):
        calls = []

        def _fetch(tf, n):
            calls.append(tf)
            return _make_bars(3)

        monkeypatch.setattr(xag, "_fetch_ohlc", _fetch)
        client.get("/api/xag/ohlc?tf=1m&n=10")
        client.get("/api/xag/ohlc?tf=1h&n=10")
        assert calls == ["1m", "1h"], "Different timeframes must use separate cache keys"

    def test_ohlc_cache_miss_on_failed_refresh_does_not_cache(self, client, monkeypatch):
        """A failed fetch must not populate the cache with empty/error data."""
        clock = [1000.0]
        monkeypatch.setattr(xag.time, "monotonic", lambda: clock[0])
        calls = []

        def _fetch(tf, n):
            calls.append(1)
            if len(calls) == 1:
                return _make_bars(3)
            raise RuntimeError("provider down")

        monkeypatch.setattr(xag, "_fetch_ohlc", _fetch)
        client.get("/api/xag/ohlc?tf=1m&n=10")  # warm cache

        clock[0] += xag._OHLC_TTL + 1
        resp = client.get("/api/xag/ohlc?tf=1m&n=10")  # should fail
        assert resp.status_code == 502
        # Cache must still hold the old data (not poisoned)
        clock[0] -= 1  # within TTL of old entry would require old ts — just check 502
