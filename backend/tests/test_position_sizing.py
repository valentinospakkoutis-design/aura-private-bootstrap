"""
Tests for the Position Sizing Engine.
Covers: multipliers, safety caps, decisions (execute/reduce/block).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.position_sizing import calculate_position_size, SizingInput, RISK_PROFILES, SAFETY_CAPS


def _inp(**overrides):
    defaults = {
        "account_balance": 10000,
        "signal_confidence": 0.7,
        "volatility": 0.3,
        "current_drawdown": 0.0,
        "current_portfolio_exposure": 0.0,
        "price": 70000,
        "user_risk_profile": "moderate",
        "symbol": "BTCUSDC",
        "existing_symbol_exposure_usd": 0.0,
    }
    defaults.update(overrides)
    return SizingInput(**defaults)


# ── Multiplier tests ────────────────────────────────────────────

def test_high_volatility_smaller_size():
    low_vol = calculate_position_size(_inp(volatility=0.1))
    high_vol = calculate_position_size(_inp(volatility=0.9))
    assert high_vol.recommended_notional < low_vol.recommended_notional
    print(f"PASS: vol | low_vol=${low_vol.recommended_notional:.2f} > high_vol=${high_vol.recommended_notional:.2f}")


def test_high_confidence_bigger_size():
    low_conf = calculate_position_size(_inp(signal_confidence=0.3))
    high_conf = calculate_position_size(_inp(signal_confidence=0.9))
    assert high_conf.recommended_notional > low_conf.recommended_notional
    print(f"PASS: conf | high=${high_conf.recommended_notional:.2f} > low=${low_conf.recommended_notional:.2f}")


def test_high_drawdown_reduced_size():
    no_dd = calculate_position_size(_inp(current_drawdown=0.0))
    severe_dd = calculate_position_size(_inp(current_drawdown=0.2))
    assert severe_dd.recommended_notional < no_dd.recommended_notional
    assert severe_dd.drawdown_multiplier == 0.25
    print(f"PASS: drawdown | none=${no_dd.recommended_notional:.2f} > severe=${severe_dd.recommended_notional:.2f}")


# ── Safety cap tests ────────────────────────────────────────────

def test_absolute_max_exposure():
    """No trade can exceed $1000 absolute cap."""
    result = calculate_position_size(_inp(
        account_balance=1000000, signal_confidence=0.99, volatility=0.01,
    ))
    assert result.recommended_notional <= SAFETY_CAPS["absolute_max_exposure_usd"]
    assert any("ABSOLUTE_MAX_CAP" in a for a in result.cap_adjustments)
    assert result.decision in ("execute", "reduce")
    print(f"PASS: abs cap | ${result.recommended_notional:.2f} <= ${SAFETY_CAPS['absolute_max_exposure_usd']:.0f}")


def test_per_symbol_cap():
    """Existing + new exposure in one symbol capped at $500."""
    result = calculate_position_size(_inp(
        existing_symbol_exposure_usd=450, account_balance=50000,
    ))
    sym_max = SAFETY_CAPS["per_symbol_max_usd"]
    assert result.recommended_notional <= (sym_max - 450) + 0.01
    assert any("SYMBOL_CAP" in a for a in result.cap_adjustments)
    print(f"PASS: sym cap | ${result.recommended_notional:.2f} + $450 <= ${sym_max:.0f}")


def test_per_symbol_cap_blocks_when_full():
    """Symbol at max -> trade blocked."""
    result = calculate_position_size(_inp(
        existing_symbol_exposure_usd=500,
    ))
    assert result.decision == "block"
    assert result.recommended_notional == 0
    assert any("BLOCK" in a for a in result.cap_adjustments)
    print(f"PASS: sym full -> BLOCK | adjustments={result.cap_adjustments}")


def test_portfolio_exposure_cap():
    """Already at 24% with 25% max -> heavily capped."""
    result = calculate_position_size(_inp(current_portfolio_exposure=0.24))
    max_remaining = 10000 * (0.25 - 0.24)
    assert result.recommended_notional <= max_remaining + 0.01
    assert result.exposure_cap_applied
    print(f"PASS: portfolio cap | ${result.recommended_notional:.2f} <= ${max_remaining:.2f}")


def test_portfolio_exposure_blocks_when_full():
    """Portfolio at max -> trade blocked."""
    result = calculate_position_size(_inp(current_portfolio_exposure=0.25))
    assert result.decision == "block"
    assert result.recommended_notional == 0
    print(f"PASS: portfolio full -> BLOCK")


# ── Decision tests ──────────────────────────────────────────────

def test_execute_decision():
    """Normal trade with no caps -> execute."""
    result = calculate_position_size(_inp())
    assert result.decision == "execute"
    assert result.recommended_notional > 0
    assert len(result.cap_adjustments) == 0
    print(f"PASS: execute | ${result.recommended_notional:.2f}")


def test_reduce_decision():
    """Trade significantly reduced by caps -> reduce."""
    result = calculate_position_size(_inp(
        account_balance=100000, signal_confidence=0.99, volatility=0.01,
        # Abs cap will cut from ~$2300 to $1000 = ~56% reduction
    ))
    assert result.decision == "reduce"
    assert len(result.cap_adjustments) > 0
    print(f"PASS: reduce | ${result.recommended_notional:.2f} | caps={result.cap_adjustments}")


def test_block_zero_balance():
    """Zero balance -> block."""
    result = calculate_position_size(_inp(account_balance=0))
    assert result.decision == "block"
    assert result.recommended_notional == 0
    print("PASS: zero balance -> BLOCK")


# ── Profile & field tests ───────────────────────────────────────

def test_conservative_vs_aggressive():
    cons = calculate_position_size(_inp(user_risk_profile="conservative"))
    aggr = calculate_position_size(_inp(user_risk_profile="aggressive"))
    assert aggr.recommended_notional > cons.recommended_notional
    print(f"PASS: profiles | cons=${cons.recommended_notional:.2f} < aggr=${aggr.recommended_notional:.2f}")


def test_all_fields_present():
    result = calculate_position_size(_inp())
    assert result.recommended_notional >= 0
    assert result.quantity >= 0
    assert result.decision in ("execute", "reduce", "block")
    assert isinstance(result.cap_adjustments, list)
    assert len(result.reasoning) > 0
    print(f"PASS: all fields | decision={result.decision}")


if __name__ == "__main__":
    test_high_volatility_smaller_size()
    test_high_confidence_bigger_size()
    test_high_drawdown_reduced_size()
    test_absolute_max_exposure()
    test_per_symbol_cap()
    test_per_symbol_cap_blocks_when_full()
    test_portfolio_exposure_cap()
    test_portfolio_exposure_blocks_when_full()
    test_execute_decision()
    test_reduce_decision()
    test_block_zero_balance()
    test_conservative_vs_aggressive()
    test_all_fields_present()
    print(f"\nAll 13 tests passed!")
