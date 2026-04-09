"""
Tests for the Explainable AI Decision Layer v2.
Covers: BUY, SELL, HOLD, NO-TRADE, BLOCKED, confidence, reason codes,
improvement triggers, backward compatibility.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.decision_explanation import build_explanation, compute_confidence, DecisionExplanation
from ai.reason_codes import (
    ML_POSITIVE_FORECAST, ML_NEGATIVE_FORECAST, TREND_BULLISH, TREND_BEARISH,
    LOW_CONFIDENCE, SIGNAL_CONFLICT, NO_ML_CONFIRMATION, TREND_TOO_WEAK,
    MARKET_SIDEWAYS, SMART_SCORE_INSUFFICIENT, RISK_BLOCK,
    SIGNAL_ALIGNMENT_HIGH, STRONG_SIGNAL_STRENGTH,
    SMART_SCORE_ABOVE_THRESHOLD, PRICE_CHANGE_BELOW_THRESHOLD,
)


def _pred(action="BUY", trend=0.5, conf=90, pct=3.0, strength="STRONG",
          ml=True, price=70000, pred_price=72100):
    return {
        "symbol": "BTCUSDC", "asset_name": "Bitcoin", "asset_type": "crypto",
        "current_price": price, "predicted_price": pred_price,
        "price_change": pred_price - price, "price_change_percent": pct,
        "trend": "BULLISH" if trend > 0.3 else "BEARISH" if trend < -0.3 else "SIDEWAYS",
        "trend_score": trend, "confidence": conf,
        "recommendation": action, "recommendation_strength": strength,
        "prediction_horizon_days": 7, "model_version": "xgb_v1", "using_ml_model": ml,
    }


def _ss(rsi=65, vol=60, news=55, fg=50, mtf=70, pred=80, score=72):
    return {
        "smart_score": score,
        "signals": {
            "rsi": {"score": rsi, "weight": 0.20},
            "volume": {"score": vol, "weight": 0.15},
            "news_sentiment": {"score": news, "weight": 0.15},
            "fear_greed": {"score": fg, "weight": 0.10},
            "multi_timeframe": {"score": mtf, "weight": 0.15},
            "prediction": {"score": pred, "weight": 0.25},
        },
    }


def test_buy_with_high_confidence():
    exp = build_explanation(
        _pred(action="BUY", trend=0.6, conf=92, pct=3.5, strength="STRONG"),
        _ss(rsi=70, vol=65, news=60, fg=55, mtf=75, score=78),
    )
    assert exp.action == "BUY"
    assert exp.confidence_band == "high"
    assert ML_POSITIVE_FORECAST in exp.reason_codes
    assert TREND_BULLISH in exp.reason_codes
    assert STRONG_SIGNAL_STRENGTH in exp.reason_codes
    assert SMART_SCORE_ABOVE_THRESHOLD in exp.reason_codes
    assert len(exp.blocked_by) == 0
    assert len(exp.invalidation_conditions) > 0
    print(f"PASS: BUY high-conf | codes={len(exp.reason_codes)}")


def test_sell_with_bearish_signals():
    exp = build_explanation(
        _pred(action="SELL", trend=-0.7, conf=88, pct=-4.0, strength="STRONG", pred_price=67200),
        _ss(rsi=30, vol=40, news=35, fg=20, mtf=15, score=28),
    )
    assert exp.action == "SELL"
    assert exp.market_regime in ("bearish", "volatile")
    assert ML_NEGATIVE_FORECAST in exp.reason_codes
    assert TREND_BEARISH in exp.reason_codes
    assert len(exp.invalidation_conditions) > 0
    print(f"PASS: SELL bearish | regime={exp.market_regime}")


def test_hold_sideways():
    exp = build_explanation(
        _pred(action="HOLD", trend=0.1, conf=72, pct=0.2, strength="NEUTRAL", pred_price=70140),
        _ss(rsi=52, vol=48, news=50, fg=45, mtf=50, score=51),
    )
    assert exp.action in ("HOLD", "NO-TRADE")
    assert exp.market_regime == "sideways"
    assert MARKET_SIDEWAYS in exp.reason_codes
    assert TREND_TOO_WEAK in exp.reason_codes
    assert PRICE_CHANGE_BELOW_THRESHOLD in exp.reason_codes
    assert "wait" in exp.expected_holding_profile.lower()
    print(f"PASS: HOLD sideways | action={exp.action}")


def test_no_trade_low_confidence():
    exp = build_explanation(
        _pred(action="HOLD", trend=0.05, conf=60, pct=0.1, strength="NEUTRAL",
              ml=False, pred_price=70070),
        _ss(rsi=50, vol=48, news=48, fg=35, mtf=48, score=40),
    )
    assert exp.action == "NO-TRADE"
    assert LOW_CONFIDENCE in exp.reason_codes
    assert NO_ML_CONFIRMATION in exp.reason_codes
    assert len(exp.improvement_triggers) > 0
    triggers_text = " ".join(exp.improvement_triggers)
    assert "trend_score" in triggers_text or "Smart Score" in triggers_text
    print(f"PASS: NO-TRADE low-conf | triggers={len(exp.improvement_triggers)}")


def test_no_trade_conflicting_signals():
    exp = build_explanation(
        _pred(action="BUY", trend=0.15, conf=70, pct=0.8, strength="MODERATE",
              ml=False, pred_price=70560),
        _ss(rsi=48, vol=42, news=45, fg=30, mtf=40, score=43),
    )
    assert exp.action == "NO-TRADE"
    assert LOW_CONFIDENCE in exp.reason_codes
    assert SMART_SCORE_INSUFFICIENT in exp.reason_codes
    assert len(exp.contradictory_signals) > 0
    print(f"PASS: NO-TRADE conflict | contradictions={len(exp.contradictory_signals)}")


def test_blocked_by_risk():
    exp = build_explanation(
        _pred(action="BUY", trend=0.6, conf=92, pct=3.5, strength="STRONG"),
        _ss(rsi=70, vol=65, news=60, fg=55, mtf=75, score=78),
        risk_context={"blocked": True, "block_reason": "PORTFOLIO_EXPOSURE_LIMIT"},
    )
    assert exp.action == "BLOCKED"
    assert RISK_BLOCK in exp.reason_codes
    assert len(exp.blocked_by) > 0
    assert "PORTFOLIO_EXPOSURE_LIMIT" in exp.blocked_by
    print(f"PASS: BLOCKED by risk | blocked_by={exp.blocked_by}")


def test_size_reduced():
    exp = build_explanation(
        _pred(action="BUY", trend=0.5, conf=90, pct=3.0),
        _ss(rsi=65, vol=60, news=55, fg=50, mtf=65, score=72),
        risk_context={"size_factor": 0.5},
    )
    assert exp.action == "BUY"
    assert len(exp.sizing_adjustments) > 0
    assert "50%" in exp.sizing_adjustments[0]
    print(f"PASS: SIZE_REDUCED | adjustments={exp.sizing_adjustments}")


def test_confidence_computation():
    c1 = compute_confidence(0.8, 0.2, 0.7)
    assert c1["band"] == "high" and c1["score"] > 0.6

    c2 = compute_confidence(0.1, 0.9, 0.1)
    assert c2["band"] == "low" and c2["score"] < 0.3

    c3 = compute_confidence(0.5, 0.5, 0.4)
    assert c3["band"] == "medium"
    print(f"PASS: confidence | high={c1['score']}, low={c2['score']}, mid={c3['score']}")


def test_reason_codes_present():
    exp = build_explanation(
        _pred(action="BUY", trend=0.6, conf=92, pct=3.5, strength="STRONG"),
        _ss(rsi=70, vol=65, news=60, fg=55, mtf=75, score=78),
    )
    assert len(exp.reason_codes) >= 3
    for code in exp.reason_codes:
        assert isinstance(code, str) and code == code.upper()
    print(f"PASS: reason_codes | count={len(exp.reason_codes)}, first={exp.reason_codes[:3]}")


def test_backward_compatibility():
    exp = build_explanation(_pred(), _ss())
    d = exp.model_dump()
    v1_fields = [
        "action", "confidence_score", "confidence_band", "market_regime",
        "primary_reasons", "supporting_signals", "contradictory_signals",
        "risk_factors", "why_not_opposite", "why_not_wait",
        "stop_loss_logic", "take_profit_logic", "expected_holding_profile",
        "narrative_summary", "machine_summary", "audit_metadata",
    ]
    v2_fields = [
        "reason_codes", "blocked_by", "sizing_adjustments",
        "invalidation_conditions", "improvement_triggers",
    ]
    for f in v1_fields + v2_fields:
        assert f in d, f"Missing field: {f}"
    print(f"PASS: backward compat | all {len(v1_fields) + len(v2_fields)} fields present")


if __name__ == "__main__":
    test_buy_with_high_confidence()
    test_sell_with_bearish_signals()
    test_hold_sideways()
    test_no_trade_low_confidence()
    test_no_trade_conflicting_signals()
    test_blocked_by_risk()
    test_size_reduced()
    test_confidence_computation()
    test_reason_codes_present()
    test_backward_compatibility()
    print(f"\nAll 10 tests passed!")
