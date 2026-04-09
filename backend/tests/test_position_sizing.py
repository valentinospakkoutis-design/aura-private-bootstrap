"""
Tests for the Position Sizing Engine.
Covers: volatility scaling, confidence scaling, drawdown reduction,
exposure caps, per-trade caps, risk profiles.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.position_sizing import calculate_position_size, SizingInput, RISK_PROFILES


def _inp(**overrides):
    defaults = {
        "account_balance": 10000,
        "signal_confidence": 0.7,
        "volatility": 0.3,
        "current_drawdown": 0.0,
        "current_portfolio_exposure": 0.0,
        "price": 70000,
        "user_risk_profile": "moderate",
    }
    defaults.update(overrides)
    return SizingInput(**defaults)


def test_high_volatility_smaller_size():
    """High volatility should produce smaller position."""
    low_vol = calculate_position_size(_inp(volatility=0.1))
    high_vol = calculate_position_size(_inp(volatility=0.9))

    assert high_vol.recommended_notional < low_vol.recommended_notional
    assert high_vol.volatility_multiplier < low_vol.volatility_multiplier
    print(f"PASS: vol scaling | low_vol=${low_vol.recommended_notional:.2f} > high_vol=${high_vol.recommended_notional:.2f}")


def test_high_confidence_bigger_size():
    """High confidence should produce larger position."""
    low_conf = calculate_position_size(_inp(signal_confidence=0.3))
    high_conf = calculate_position_size(_inp(signal_confidence=0.9))

    assert high_conf.recommended_notional > low_conf.recommended_notional
    assert high_conf.confidence_multiplier > low_conf.confidence_multiplier
    print(f"PASS: conf scaling | high=${high_conf.recommended_notional:.2f} > low=${low_conf.recommended_notional:.2f}")


def test_high_drawdown_reduced_size():
    """Drawdown should reduce position size."""
    no_dd = calculate_position_size(_inp(current_drawdown=0.0))
    severe_dd = calculate_position_size(_inp(current_drawdown=0.2))

    assert severe_dd.recommended_notional < no_dd.recommended_notional
    assert severe_dd.drawdown_multiplier < no_dd.drawdown_multiplier
    assert severe_dd.drawdown_multiplier == 0.25  # severe: 25%
    print(f"PASS: drawdown | none=${no_dd.recommended_notional:.2f} > severe=${severe_dd.recommended_notional:.2f}")


def test_per_trade_cap():
    """Position should not exceed per-trade max %."""
    # Very high confidence + low vol = tries to be big
    result = calculate_position_size(_inp(
        signal_confidence=0.99, volatility=0.01, account_balance=100000
    ))
    max_pct = RISK_PROFILES["moderate"]["max_per_trade_pct"]
    max_notional = 100000 * max_pct / 100
    assert result.recommended_notional <= max_notional + 0.01
    print(f"PASS: per-trade cap | ${result.recommended_notional:.2f} <= ${max_notional:.2f}")


def test_portfolio_exposure_cap():
    """Position should respect portfolio exposure limit."""
    # Already 24% exposed with 25% max
    result = calculate_position_size(_inp(current_portfolio_exposure=0.24))
    max_remaining = 10000 * (0.25 - 0.24)  # $100 remaining capacity
    assert result.recommended_notional <= max_remaining + 0.01
    assert result.exposure_cap_applied
    print(f"PASS: exposure cap | ${result.recommended_notional:.2f} <= ${max_remaining:.2f}")


def test_conservative_vs_aggressive():
    """Aggressive profile should size larger than conservative."""
    cons = calculate_position_size(_inp(user_risk_profile="conservative"))
    aggr = calculate_position_size(_inp(user_risk_profile="aggressive"))

    assert aggr.recommended_notional > cons.recommended_notional
    assert aggr.base_risk_pct > cons.base_risk_pct
    print(f"PASS: profiles | conservative=${cons.recommended_notional:.2f} < aggressive=${aggr.recommended_notional:.2f}")


def test_zero_balance():
    """Zero balance should produce zero sizing."""
    result = calculate_position_size(_inp(account_balance=0))
    assert result.recommended_notional == 0
    assert result.quantity == 0
    print("PASS: zero balance -> $0.00")


def test_output_has_all_fields():
    """Result should have all expected fields."""
    result = calculate_position_size(_inp())
    assert result.recommended_notional >= 0
    assert result.quantity >= 0
    assert 0 < result.confidence_multiplier <= 1.5
    assert 0 < result.volatility_multiplier <= 1.0
    assert 0 < result.drawdown_multiplier <= 1.0
    assert len(result.reasoning) > 0
    print(f"PASS: all fields | reasoning='{result.reasoning[:60]}...'")


if __name__ == "__main__":
    test_high_volatility_smaller_size()
    test_high_confidence_bigger_size()
    test_high_drawdown_reduced_size()
    test_per_trade_cap()
    test_portfolio_exposure_cap()
    test_conservative_vs_aggressive()
    test_zero_balance()
    test_output_has_all_fields()
    print(f"\nAll 8 tests passed!")
