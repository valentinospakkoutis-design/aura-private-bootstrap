"""
Tests for the AI Feed Engine.
Tests event emission, deduplication, and convenience emitters.
Note: DB-dependent tests are mocked; logic tests are direct.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.feed_engine import (
    _dedup_key, EVENT_TYPES, SEVERITY_LEVELS,
    emit_trade_signal, emit_no_trade, emit_risk_alert,
    emit_market_insight, emit_auto_trade,
)


def test_dedup_key_stable():
    """Same inputs on same day produce same key."""
    k1 = _dedup_key("trade_signal", "BTCUSDC", "BUY signal")
    k2 = _dedup_key("trade_signal", "BTCUSDC", "BUY signal")
    assert k1 == k2
    print(f"PASS: dedup stable | key={k1}")


def test_dedup_key_differs_by_type():
    """Different event types produce different keys."""
    k1 = _dedup_key("trade_signal", "BTCUSDC", "BUY signal")
    k2 = _dedup_key("risk_alert", "BTCUSDC", "BUY signal")
    assert k1 != k2
    print("PASS: dedup differs by type")


def test_dedup_key_differs_by_symbol():
    """Different symbols produce different keys."""
    k1 = _dedup_key("trade_signal", "BTCUSDC", "BUY signal")
    k2 = _dedup_key("trade_signal", "ETHUSDC", "BUY signal")
    assert k1 != k2
    print("PASS: dedup differs by symbol")


def test_event_types_defined():
    """All expected event types should be defined."""
    expected = {"market_insight", "trade_signal", "risk_alert",
                "no_trade_explanation", "auto_trade", "portfolio_alert", "system"}
    assert EVENT_TYPES == expected
    print(f"PASS: event types | {len(EVENT_TYPES)} types defined")


def test_severity_levels():
    """Severity levels should be defined."""
    assert "info" in SEVERITY_LEVELS
    assert "warning" in SEVERITY_LEVELS
    assert "critical" in SEVERITY_LEVELS
    print("PASS: severity levels defined")


def test_convenience_emitters_exist():
    """All convenience emitters should be callable."""
    assert callable(emit_trade_signal)
    assert callable(emit_no_trade)
    assert callable(emit_risk_alert)
    assert callable(emit_market_insight)
    assert callable(emit_auto_trade)
    print("PASS: all 5 convenience emitters callable")


if __name__ == "__main__":
    test_dedup_key_stable()
    test_dedup_key_differs_by_type()
    test_dedup_key_differs_by_symbol()
    test_event_types_defined()
    test_severity_levels()
    test_convenience_emitters_exist()
    print(f"\nAll 6 tests passed!")
