"""
Tests for the Modular Strategy System.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.strategy_engine import (
    strategy_registry, StrategyRegistry, Strategy,
    MLTrendStrategy, SmartScoreStrategy, MomentumStrategy, MeanReversionStrategy,
)


def _market_data(trend=0.5, conf=90, pct=3.0, ml=True, ss=72, rsi=65, vol=60):
    return {
        "symbol": "BTCUSDC",
        "trend_score": trend,
        "confidence": conf,
        "price_change_percent": pct,
        "recommendation": "BUY" if pct > 0.5 else "SELL" if pct < -0.5 else "HOLD",
        "using_ml_model": ml,
        "smart_score": ss,
        "signals": {
            "rsi": {"score": rsi},
            "volume": {"score": vol},
            "news_sentiment": {"score": 55},
            "fear_greed": {"score": 50},
            "multi_timeframe": {"score": 65},
        },
    }


def test_strategy_interface():
    """All strategies must implement the interface."""
    for strat in [MLTrendStrategy(), SmartScoreStrategy(), MomentumStrategy(), MeanReversionStrategy()]:
        assert hasattr(strat, "generate_signal")
        assert hasattr(strat, "score")
        assert hasattr(strat, "explain")
        assert strat.name
        assert strat.description
    print("PASS: all strategies implement interface")


def test_ml_trend_buy():
    s = MLTrendStrategy()
    data = _market_data(trend=0.6, conf=92, ml=True)
    sig = s.generate_signal("BTCUSDC", data)
    assert sig["action"] == "BUY"
    assert sig["confidence"] > 0.5
    print(f"PASS: ml_trend BUY | conf={sig['confidence']:.2f}")


def test_ml_trend_no_model():
    s = MLTrendStrategy()
    data = _market_data(ml=False)
    sig = s.generate_signal("BTCUSDC", data)
    assert sig["action"] == "HOLD"
    print("PASS: ml_trend HOLD without ML model")


def test_smart_score_high():
    s = SmartScoreStrategy()
    data = _market_data(ss=82, pct=2.0)
    sig = s.generate_signal("BTCUSDC", data)
    assert sig["action"] == "BUY"
    print(f"PASS: smart_score BUY | ss=82")


def test_momentum_strong():
    s = MomentumStrategy()
    data = _market_data(trend=0.7, vol=70)
    sig = s.generate_signal("BTCUSDC", data)
    assert sig["action"] == "BUY"
    print(f"PASS: momentum BUY | trend=0.7, vol=70")


def test_momentum_weak():
    s = MomentumStrategy()
    data = _market_data(trend=0.1, vol=40)
    sig = s.generate_signal("BTCUSDC", data)
    assert sig["action"] == "HOLD"
    print("PASS: momentum HOLD (weak)")


def test_mean_reversion_oversold():
    s = MeanReversionStrategy()
    data = _market_data(rsi=15)
    sig = s.generate_signal("BTCUSDC", data)
    assert sig["action"] == "BUY"
    print("PASS: mean_reversion BUY (oversold)")


def test_mean_reversion_overbought():
    s = MeanReversionStrategy()
    data = _market_data(rsi=85)
    sig = s.generate_signal("BTCUSDC", data)
    assert sig["action"] == "SELL"
    print("PASS: mean_reversion SELL (overbought)")


def test_registry_has_all():
    strats = strategy_registry.list_all()
    names = {s["name"] for s in strats}
    assert "ml_trend" in names
    assert "smart_score" in names
    assert "momentum" in names
    assert "mean_reversion" in names
    print(f"PASS: registry has {len(strats)} strategies")


def test_evaluate_all():
    data = _market_data()
    results = strategy_registry.evaluate_all("BTCUSDC", data)
    assert len(results) == 4
    assert all("strategy" in r and "signal" in r and "score" in r for r in results)
    # Should be sorted by score descending
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    print(f"PASS: evaluate_all | scores={scores}")


def test_consensus():
    data = _market_data(trend=0.6, conf=92, ss=80, rsi=65, vol=70)
    c = strategy_registry.consensus("BTCUSDC", data)
    assert c["action"] in ("BUY", "SELL", "HOLD")
    assert 0 <= c["confidence"] <= 1
    assert c["strategy_count"] == 4
    assert "votes" in c
    print(f"PASS: consensus | action={c['action']}, conf={c['confidence']:.2f}, votes={c['votes']}")


def test_explain_returns_list():
    data = _market_data()
    for strat in [MLTrendStrategy(), SmartScoreStrategy(), MomentumStrategy(), MeanReversionStrategy()]:
        reasons = strat.explain("BTCUSDC", data)
        assert isinstance(reasons, list)
        assert all(isinstance(r, str) for r in reasons)
    print("PASS: all explain() return list of strings")


if __name__ == "__main__":
    test_strategy_interface()
    test_ml_trend_buy()
    test_ml_trend_no_model()
    test_smart_score_high()
    test_momentum_strong()
    test_momentum_weak()
    test_mean_reversion_oversold()
    test_mean_reversion_overbought()
    test_registry_has_all()
    test_evaluate_all()
    test_consensus()
    test_explain_returns_list()
    print(f"\nAll 12 tests passed!")
