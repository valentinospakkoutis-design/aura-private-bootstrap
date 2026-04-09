"""
Tests for the AURA Trust Layer.
Verifies standardized verdicts across all systems.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.trust_layer import (
    TrustVerdict,
    verdict_from_auto_trader_skip,
    verdict_from_sizing,
    verdict_from_portfolio,
)
from ai.reason_codes import (
    LOW_CONFIDENCE, SMART_SCORE_INSUFFICIENT, FEAR_GREED_EXTREME,
    SYMBOL_EXPOSURE_LIMIT, PORTFOLIO_EXPOSURE_LIMIT, RISK_BLOCK,
    SIZE_REDUCED_BY_RISK,
)


def test_verdict_structure():
    """TrustVerdict should have all required fields."""
    v = TrustVerdict(
        action="SKIP", reason_codes=["LOW_CONFIDENCE"],
        explanation="test", source="test",
    )
    d = v.to_dict()
    for field in ("action", "reason_codes", "explanation", "blocked_by",
                   "sizing_adjustments", "improvement_triggers", "source", "timestamp"):
        assert field in d
    print("PASS: verdict structure")


def test_auto_trader_skip_low_confidence():
    """Low confidence skip should produce correct reason codes."""
    v = verdict_from_auto_trader_skip("BTCUSDC", "Conf too low", confidence=0.75)
    assert v.action == "SKIP"
    assert LOW_CONFIDENCE in v.reason_codes
    assert len(v.improvement_triggers) > 0
    assert "source" in v.to_dict()
    print(f"PASS: auto skip low conf | codes={v.reason_codes}")


def test_auto_trader_skip_smart_score():
    """Low smart score skip should include SMART_SCORE_INSUFFICIENT."""
    v = verdict_from_auto_trader_skip("ETHUSDC", "SS too low", confidence=0.92, smart_score=60)
    assert SMART_SCORE_INSUFFICIENT in v.reason_codes
    assert any("Smart Score" in t for t in v.improvement_triggers)
    print(f"PASS: auto skip SS | codes={v.reason_codes}")


def test_auto_trader_skip_fear():
    """Extreme fear skip should include FEAR_GREED_EXTREME."""
    v = verdict_from_auto_trader_skip("SOLUSDC", "Fear", confidence=0.92, fear_greed=15)
    assert FEAR_GREED_EXTREME in v.reason_codes
    print(f"PASS: auto skip fear | codes={v.reason_codes}")


def test_sizing_block():
    """Sizing block should produce RISK_BLOCK."""
    v = verdict_from_sizing("BTCUSDC", "block", ["BLOCK: symbol exposure at $500 cap"], 0)
    assert v.action == "BLOCK"
    assert RISK_BLOCK in v.reason_codes
    assert len(v.blocked_by) > 0
    print(f"PASS: sizing block | blocked_by={v.blocked_by}")


def test_sizing_reduce():
    """Sizing reduce should produce sizing adjustments."""
    v = verdict_from_sizing("BTCUSDC", "reduce",
        ["ABSOLUTE_MAX_CAP: $2000 reduced to $1000 hard limit"], 1000)
    assert v.action == "REDUCE"
    assert SIZE_REDUCED_BY_RISK in v.reason_codes
    assert len(v.sizing_adjustments) > 0
    print(f"PASS: sizing reduce | adjustments={v.sizing_adjustments}")


def test_portfolio_block():
    """High portfolio risk should produce block verdict."""
    v = verdict_from_portfolio("BTCUSDC", 75, "block",
        ["SYMBOL_CONCENTRATION: BTC at 30%"], 0.0)
    assert v.action == "BLOCK"
    assert RISK_BLOCK in v.reason_codes
    assert SYMBOL_EXPOSURE_LIMIT in v.reason_codes
    assert len(v.improvement_triggers) > 0
    print(f"PASS: portfolio block | codes={v.reason_codes}")


def test_portfolio_reduce():
    """Moderate risk should produce reduce verdict."""
    v = verdict_from_portfolio("ETHUSDC", 45, "reduce",
        ["CLASS_CONCENTRATION: crypto at 65%"], 0.6)
    assert v.action == "REDUCE"
    assert PORTFOLIO_EXPOSURE_LIMIT in v.reason_codes
    print(f"PASS: portfolio reduce | codes={v.reason_codes}")


if __name__ == "__main__":
    test_verdict_structure()
    test_auto_trader_skip_low_confidence()
    test_auto_trader_skip_smart_score()
    test_auto_trader_skip_fear()
    test_sizing_block()
    test_sizing_reduce()
    test_portfolio_block()
    test_portfolio_reduce()
    print(f"\nAll 8 tests passed!")
