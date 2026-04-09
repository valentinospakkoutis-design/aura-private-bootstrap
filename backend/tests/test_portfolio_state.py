"""
Tests for Portfolio State & Awareness Engine.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.portfolio_state import assess_portfolio, CONCENTRATION_LIMITS


def test_empty_portfolio():
    """Empty portfolio should be low risk."""
    result = assess_portfolio(positions=[], account_balance=10000)
    assert result.portfolio_risk_score < 10
    assert result.total_exposure_usd == 0
    assert result.adjustment_recommendation == "ok"
    assert result.size_factor == 1.0
    print(f"PASS: empty | risk={result.portfolio_risk_score}")


def test_single_position():
    """Single small position should be ok."""
    result = assess_portfolio(
        positions=[{"symbol": "BTCUSDC", "amount": 0.001, "value_usdc": 70}],
        account_balance=10000,
    )
    assert result.portfolio_risk_score < 20
    assert result.adjustment_recommendation == "ok"
    assert result.exposure_by_symbol.get("BTC", 0) == 70
    assert result.exposure_by_class.get("crypto", 0) == 70
    print(f"PASS: single | risk={result.portfolio_risk_score}, BTC=${result.exposure_by_symbol.get('BTC')}")


def test_symbol_concentration_warning():
    """30% in one symbol should trigger warning."""
    result = assess_portfolio(
        positions=[{"symbol": "BTCUSDC", "amount": 0.04, "value_usdc": 3000}],
        account_balance=10000,
    )
    assert any("SYMBOL_CONCENTRATION" in w for w in result.concentration_warnings)
    assert result.portfolio_risk_score >= 20
    print(f"PASS: sym concentration | warnings={result.concentration_warnings}")


def test_class_concentration():
    """70% in crypto should trigger class warning."""
    result = assess_portfolio(
        positions=[
            {"symbol": "BTCUSDC", "amount": 0.03, "value_usdc": 2000},
            {"symbol": "ETHUSDC", "amount": 1.0, "value_usdc": 2500},
            {"symbol": "SOLUSDC", "amount": 20, "value_usdc": 2500},
        ],
        account_balance=10000,
    )
    assert any("CLASS_CONCENTRATION" in w or "CLASS_WARNING" in w for w in result.concentration_warnings)
    assert result.exposure_by_class_pct.get("crypto", 0) >= 60
    print(f"PASS: class concentration | crypto={result.exposure_by_class_pct.get('crypto')}%")


def test_correlated_exposure():
    """Heavy BTC+ETH should flag correlated exposure."""
    result = assess_portfolio(
        positions=[
            {"symbol": "BTCUSDC", "amount": 0.04, "value_usdc": 3000},
            {"symbol": "ETHUSDC", "amount": 1.5, "value_usdc": 3000},
        ],
        account_balance=10000,
    )
    assert result.correlated_exposure.get("large_cap_crypto", 0) > 0
    assert any("CORRELATED" in w for w in result.concentration_warnings)
    print(f"PASS: correlated | large_cap={result.correlated_exposure.get('large_cap_crypto')}")


def test_proposed_trade_blocked():
    """Proposed trade that would exceed symbol limit should block."""
    result = assess_portfolio(
        positions=[{"symbol": "BTCUSDC", "amount": 0.03, "value_usdc": 2400}],
        account_balance=10000,
        proposed_symbol="BTCUSDC",
        proposed_value=200,
    )
    # BTC would be 2400+200=2600 = 26% > 25% limit
    assert result.adjustment_recommendation == "block"
    assert result.size_factor == 0.0
    print(f"PASS: proposed blocked | risk={result.portfolio_risk_score}")


def test_diversified_portfolio_ok():
    """Well diversified portfolio should be ok."""
    result = assess_portfolio(
        positions=[
            {"symbol": "BTCUSDC", "amount": 0.001, "value_usdc": 100},
            {"symbol": "AAPL", "amount": 0.5, "value_usdc": 100},
            {"symbol": "XAUUSDC", "amount": 0.05, "value_usdc": 100},
        ],
        account_balance=10000,
    )
    assert result.adjustment_recommendation == "ok"
    assert len(result.concentration_warnings) == 0
    assert len(result.exposure_by_class) >= 2
    print(f"PASS: diversified | risk={result.portfolio_risk_score}, classes={list(result.exposure_by_class.keys())}")


def test_high_risk_reduces_size():
    """High risk score should reduce size factor."""
    result = assess_portfolio(
        positions=[
            {"symbol": "BTCUSDC", "amount": 0.03, "value_usdc": 2000},
            {"symbol": "ETHUSDC", "amount": 1.0, "value_usdc": 2000},
            {"symbol": "SOLUSDC", "amount": 20, "value_usdc": 1500},
        ],
        account_balance=10000,
    )
    assert result.size_factor < 1.0
    assert result.adjustment_recommendation in ("reduce", "block")
    print(f"PASS: high risk reduces | factor={result.size_factor}, adj={result.adjustment_recommendation}")


if __name__ == "__main__":
    test_empty_portfolio()
    test_single_position()
    test_symbol_concentration_warning()
    test_class_concentration()
    test_correlated_exposure()
    test_proposed_trade_blocked()
    test_diversified_portfolio_ok()
    test_high_risk_reduces_size()
    print(f"\nAll 8 tests passed!")
