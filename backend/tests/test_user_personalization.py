"""
Tests for User Personalization.
Verifies different risk profiles produce different sizing/decisions.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.position_sizing import calculate_position_size, SizingInput
from services.user_personalization import PROFILE_PARAMS, VALID_PROFILES


def _inp(profile="moderate", **overrides):
    defaults = {
        "account_balance": 10000,
        "signal_confidence": 0.7,
        "volatility": 0.3,
        "current_drawdown": 0.0,
        "current_portfolio_exposure": 0.0,
        "price": 70000,
        "user_risk_profile": profile,
        "symbol": "BTCUSDC",
        "existing_symbol_exposure_usd": 0.0,
    }
    defaults.update(overrides)
    return SizingInput(**defaults)


def test_conservative_smaller_than_aggressive():
    """Conservative user gets smaller positions than aggressive."""
    cons = calculate_position_size(_inp("conservative"))
    aggr = calculate_position_size(_inp("aggressive"))
    assert aggr.recommended_notional > cons.recommended_notional
    assert aggr.base_risk_pct > cons.base_risk_pct
    print(f"PASS: cons=${cons.recommended_notional:.2f} < aggr=${aggr.recommended_notional:.2f}")


def test_conservative_higher_confidence_needed():
    """Conservative profile has higher confidence threshold."""
    cons_params = PROFILE_PARAMS["conservative"]
    aggr_params = PROFILE_PARAMS["aggressive"]
    assert cons_params["confidence_threshold"] > aggr_params["confidence_threshold"]
    print(f"PASS: cons threshold={cons_params['confidence_threshold']} > aggr={aggr_params['confidence_threshold']}")


def test_aggressive_more_positions():
    """Aggressive profile allows more concurrent positions."""
    cons_params = PROFILE_PARAMS["conservative"]
    aggr_params = PROFILE_PARAMS["aggressive"]
    assert aggr_params["max_positions"] > cons_params["max_positions"]
    print(f"PASS: cons positions={cons_params['max_positions']} < aggr={aggr_params['max_positions']}")


def test_all_profiles_valid():
    """All defined profiles map to valid sizing profiles."""
    for name in VALID_PROFILES:
        result = calculate_position_size(_inp(name))
        assert result.recommended_notional >= 0
        assert result.decision in ("execute", "reduce", "block")
    print(f"PASS: all {len(VALID_PROFILES)} profiles produce valid results")


def test_low_confidence_conservative_blocks():
    """Conservative with very low confidence should produce tiny/blocked trade."""
    result = calculate_position_size(_inp("conservative", signal_confidence=0.2, volatility=0.8))
    assert result.recommended_notional < 30  # Very small
    print(f"PASS: cons+low_conf=${result.recommended_notional:.2f} (very small)")


def test_high_confidence_aggressive_larger():
    """Aggressive with high confidence should produce larger trade."""
    result = calculate_position_size(_inp("aggressive", signal_confidence=0.95, volatility=0.1))
    # Aggressive base=4%, high conf=1.15x, low vol=0.93x = ~4.28% = $428
    assert result.recommended_notional > 300
    print(f"PASS: aggr+high_conf=${result.recommended_notional:.2f} (large)")


def test_profile_affects_sizing_proportionally():
    """Moving from conservative -> moderate -> aggressive should increase size monotonically."""
    cons = calculate_position_size(_inp("conservative")).recommended_notional
    mod = calculate_position_size(_inp("moderate")).recommended_notional
    aggr = calculate_position_size(_inp("aggressive")).recommended_notional
    assert cons < mod < aggr
    print(f"PASS: monotonic | cons=${cons:.2f} < mod=${mod:.2f} < aggr=${aggr:.2f}")


if __name__ == "__main__":
    test_conservative_smaller_than_aggressive()
    test_conservative_higher_confidence_needed()
    test_aggressive_more_positions()
    test_all_profiles_valid()
    test_low_confidence_conservative_blocks()
    test_high_confidence_aggressive_larger()
    test_profile_affects_sizing_proportionally()
    print(f"\nAll 7 tests passed!")
