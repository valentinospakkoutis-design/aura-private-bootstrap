"""
Tests for the Explainable AI Decision Layer.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.decision_explanation import build_explanation, compute_confidence, DecisionExplanation


def _make_prediction(action="BUY", trend_score=0.5, confidence=90, price_change_pct=3.0,
                     strength="STRONG", using_ml=True, current_price=70000, predicted_price=72100):
    return {
        "symbol": "BTCUSDC",
        "asset_name": "Bitcoin",
        "asset_type": "crypto",
        "current_price": current_price,
        "predicted_price": predicted_price,
        "price_change": predicted_price - current_price,
        "price_change_percent": price_change_pct,
        "trend": "BULLISH" if trend_score > 0.3 else "BEARISH" if trend_score < -0.3 else "SIDEWAYS",
        "trend_score": trend_score,
        "confidence": confidence,
        "recommendation": action,
        "recommendation_strength": strength,
        "prediction_horizon_days": 7,
        "model_version": "xgboost_v1",
        "using_ml_model": using_ml,
    }


def _make_smart_score(rsi=65, volume=60, news=55, fear_greed=50, mtf=70, pred=80, score=72):
    return {
        "smart_score": score,
        "signals": {
            "rsi": {"score": rsi, "weight": 0.20},
            "volume": {"score": volume, "weight": 0.15},
            "news_sentiment": {"score": news, "weight": 0.15},
            "fear_greed": {"score": fear_greed, "weight": 0.10},
            "multi_timeframe": {"score": mtf, "weight": 0.15},
            "prediction": {"score": pred, "weight": 0.25},
        },
        "recommendation": "TRADE" if score > 75 else "WAIT",
    }


def test_buy_case():
    pred = _make_prediction(action="BUY", trend_score=0.6, confidence=92, price_change_pct=3.5, strength="STRONG")
    ss = _make_smart_score(rsi=70, volume=65, news=60, fear_greed=55, mtf=75, pred=85, score=78)
    exp = build_explanation(pred, ss)

    assert isinstance(exp, DecisionExplanation)
    assert exp.action == "BUY"
    assert exp.confidence_band in ("low", "medium", "high")
    assert exp.confidence_score > 0
    assert exp.market_regime == "bullish"
    assert len(exp.primary_reasons) > 0
    assert len(exp.why_not_opposite) > 0
    assert "stop loss" in exp.stop_loss_logic.lower() or "%" in exp.stop_loss_logic
    assert exp.audit_metadata["symbol"] == "BTCUSDC"
    print(f"BUY: conf={exp.confidence_score}, band={exp.confidence_band}, reasons={len(exp.primary_reasons)}")


def test_sell_case():
    pred = _make_prediction(action="SELL", trend_score=-0.7, confidence=88, price_change_pct=-4.0,
                            strength="STRONG", predicted_price=67200)
    ss = _make_smart_score(rsi=30, volume=40, news=35, fear_greed=20, mtf=15, pred=25, score=28)
    exp = build_explanation(pred, ss)

    assert exp.action == "SELL"
    assert exp.market_regime in ("bearish", "volatile")
    assert len(exp.primary_reasons) > 0
    assert any("negative" in r.lower() or "downward" in r.lower() for r in exp.why_not_opposite)
    print(f"SELL: conf={exp.confidence_score}, band={exp.confidence_band}, regime={exp.market_regime}")


def test_hold_case():
    pred = _make_prediction(action="HOLD", trend_score=0.1, confidence=72, price_change_pct=0.2,
                            strength="NEUTRAL", predicted_price=70140)
    ss = _make_smart_score(rsi=52, volume=48, news=50, fear_greed=45, mtf=50, pred=55, score=51)
    exp = build_explanation(pred, ss)

    assert exp.action == "HOLD"
    assert exp.market_regime == "sideways"
    assert "wait" in exp.expected_holding_profile.lower() or "no position" in exp.expected_holding_profile.lower()
    assert exp.why_not_wait[0].startswith("Action IS wait")
    print(f"HOLD: conf={exp.confidence_score}, band={exp.confidence_band}")


def test_no_trade_low_confidence():
    pred = _make_prediction(action="BUY", trend_score=0.15, confidence=68, price_change_pct=0.8,
                            strength="MODERATE", using_ml=False, predicted_price=70560)
    ss = _make_smart_score(rsi=48, volume=42, news=45, fear_greed=30, mtf=40, pred=50, score=43)
    exp = build_explanation(pred, ss)

    assert exp.confidence_band in ("low", "medium")
    assert any("simulated" in r.lower() or "no ml" in r.lower() for r in exp.risk_factors)
    print(f"LOW_CONF: conf={exp.confidence_score}, band={exp.confidence_band}, risks={exp.risk_factors}")


def test_confidence_computation():
    # High agreement, low volatility, strong trend
    c1 = compute_confidence(signal_agreement=0.8, volatility=0.2, trend_strength=0.7)
    assert c1["band"] == "high"
    assert c1["score"] > 0.6

    # No agreement, high volatility
    c2 = compute_confidence(signal_agreement=0.1, volatility=0.9, trend_strength=0.1)
    assert c2["band"] == "low"
    assert c2["score"] < 0.3

    # Medium case
    c3 = compute_confidence(signal_agreement=0.5, volatility=0.5, trend_strength=0.4)
    assert c3["band"] == "medium"

    print(f"Confidence: high={c1['score']}, low={c2['score']}, mid={c3['score']}")


def test_explanation_has_all_fields():
    pred = _make_prediction()
    ss = _make_smart_score()
    exp = build_explanation(pred, ss)
    d = exp.dict()

    required = [
        "action", "confidence_score", "confidence_band", "market_regime",
        "primary_reasons", "supporting_signals", "contradictory_signals",
        "risk_factors", "why_not_opposite", "why_not_wait",
        "stop_loss_logic", "take_profit_logic", "expected_holding_profile",
        "narrative_summary", "machine_summary", "audit_metadata",
    ]
    for field in required:
        assert field in d, f"Missing field: {field}"
        assert d[field] is not None, f"Field is None: {field}"

    print(f"All {len(required)} fields present and non-null")


if __name__ == "__main__":
    test_buy_case()
    test_sell_case()
    test_hold_case()
    test_no_trade_low_confidence()
    test_confidence_computation()
    test_explanation_has_all_fields()
    print("\nAll tests passed!")
