"""
Tests for Autopilot Mode Configuration.
Verifies mode changes affect engine behavior.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.autopilot_config import (
    AUTOPILOT_MODES, VALID_MODES, apply_mode, get_current_mode,
    get_mode_config, get_all_modes,
)


class MockAutoTrader:
    """Minimal mock of AutoTradingEngine for testing."""
    def __init__(self):
        self.config = {
            "confidence_threshold": 0.90,
            "smart_score_threshold": 75,
            "fixed_order_value_usd": 10.0,
            "max_order_value_usd": 100.0,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.05,
            "max_positions": 3,
            "enabled": False,
        }
        self.check_interval = 60


def test_safe_mode_is_stricter():
    """Safe mode should have higher confidence threshold and fewer positions."""
    safe = AUTOPILOT_MODES["safe"]["engine_config"]
    balanced = AUTOPILOT_MODES["balanced"]["engine_config"]
    assert safe["confidence_threshold"] > balanced["confidence_threshold"]
    assert safe["max_positions"] < balanced["max_positions"]
    assert safe["fixed_order_value_usd"] < balanced["fixed_order_value_usd"]
    print(f"PASS: safe stricter | conf={safe['confidence_threshold']} > {balanced['confidence_threshold']}")


def test_aggressive_mode_is_looser():
    """Aggressive mode should have lower thresholds and more positions."""
    aggressive = AUTOPILOT_MODES["aggressive"]["engine_config"]
    balanced = AUTOPILOT_MODES["balanced"]["engine_config"]
    assert aggressive["confidence_threshold"] < balanced["confidence_threshold"]
    assert aggressive["max_positions"] > balanced["max_positions"]
    assert aggressive["fixed_order_value_usd"] > balanced["fixed_order_value_usd"]
    print(f"PASS: aggressive looser | conf={aggressive['confidence_threshold']} < {balanced['confidence_threshold']}")


def test_apply_mode_changes_engine():
    """Applying a mode should update engine config."""
    trader = MockAutoTrader()
    result = apply_mode("safe", trader)
    assert "error" not in result
    assert trader.config["confidence_threshold"] == 0.95
    assert trader.config["max_positions"] == 2
    assert trader.check_interval == 120
    print(f"PASS: apply safe | conf={trader.config['confidence_threshold']}, interval={trader.check_interval}")


def test_apply_aggressive_then_safe():
    """Switching modes should fully replace config."""
    trader = MockAutoTrader()
    apply_mode("aggressive", trader)
    assert trader.config["confidence_threshold"] == 0.80
    assert trader.config["max_positions"] == 5

    apply_mode("safe", trader)
    assert trader.config["confidence_threshold"] == 0.95
    assert trader.config["max_positions"] == 2
    print("PASS: mode switch | aggressive -> safe correctly replaces config")


def test_invalid_mode_rejected():
    """Invalid mode should return error."""
    trader = MockAutoTrader()
    result = apply_mode("yolo", trader)
    assert "error" in result
    print(f"PASS: invalid mode | error='{result['error']}'")


def test_check_intervals_differ():
    """Each mode should have different check intervals."""
    safe_int = AUTOPILOT_MODES["safe"]["check_interval"]
    bal_int = AUTOPILOT_MODES["balanced"]["check_interval"]
    aggr_int = AUTOPILOT_MODES["aggressive"]["check_interval"]
    assert safe_int > bal_int > aggr_int
    print(f"PASS: intervals | safe={safe_int}s > bal={bal_int}s > aggr={aggr_int}s")


def test_allowed_strategies_differ():
    """Aggressive allows more strategies than safe."""
    safe_strats = AUTOPILOT_MODES["safe"]["allowed_strategies"]
    aggr_strats = AUTOPILOT_MODES["aggressive"]["allowed_strategies"]
    assert len(aggr_strats) > len(safe_strats)
    assert "futures_long" not in safe_strats
    assert "futures_long" in aggr_strats
    print(f"PASS: strategies | safe={safe_strats} vs aggr={aggr_strats}")


def test_get_all_modes():
    """Should return summary for all modes."""
    modes = get_all_modes()
    assert len(modes) == 3
    for name in ("safe", "balanced", "aggressive"):
        assert name in modes
        assert "label" in modes[name]
        assert "confidence_threshold" in modes[name]
    print(f"PASS: all modes | {list(modes.keys())}")


def test_current_mode_tracking():
    """get_current_mode should track apply_mode calls."""
    trader = MockAutoTrader()
    apply_mode("aggressive", trader)
    assert get_current_mode() == "aggressive"
    apply_mode("safe", trader)
    assert get_current_mode() == "safe"
    print("PASS: mode tracking | aggressive -> safe tracked")


if __name__ == "__main__":
    test_safe_mode_is_stricter()
    test_aggressive_mode_is_looser()
    test_apply_mode_changes_engine()
    test_apply_aggressive_then_safe()
    test_invalid_mode_rejected()
    test_check_intervals_differ()
    test_allowed_strategies_differ()
    test_get_all_modes()
    test_current_mode_tracking()
    print(f"\nAll 9 tests passed!")
