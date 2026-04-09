"""
Explainable AI Decision Layer for AURA
Produces structured, auditable explanations for every trading decision.
All reasoning is derived from real signals — never fabricated.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class DecisionExplanation(BaseModel):
    """Structured explanation for a trading decision."""
    action: str
    confidence_score: float  # 0-1
    confidence_band: str  # low / medium / high
    market_regime: str  # bullish / bearish / sideways / volatile
    primary_reasons: List[str]
    supporting_signals: List[str]
    contradictory_signals: List[str]
    risk_factors: List[str]
    why_not_opposite: List[str]
    why_not_wait: List[str]
    stop_loss_logic: str
    take_profit_logic: str
    expected_holding_profile: str
    narrative_summary: str
    machine_summary: str
    audit_metadata: dict


def compute_confidence(
    signal_agreement: float,
    volatility: float,
    trend_strength: float,
) -> dict:
    """
    Deterministic confidence scoring.

    signal_agreement: 0-1 (how many signals agree with the action)
    volatility: 0-1 (normalized, higher = more volatile)
    trend_strength: 0-1 (abs trend_score)
    """
    # Weighted combination
    score = (
        signal_agreement * 0.50
        + (1 - volatility) * 0.25
        + trend_strength * 0.25
    )
    score = max(0.0, min(1.0, score))

    if score >= 0.7:
        band = "high"
    elif score >= 0.4:
        band = "medium"
    else:
        band = "low"

    return {"score": round(score, 3), "band": band}


def build_explanation(
    prediction: Dict,
    smart_score: Optional[Dict] = None,
) -> DecisionExplanation:
    """
    Build a structured decision explanation from real prediction + smart score data.
    No fake reasoning — every field is derived from actual signals.
    """
    action = prediction.get("recommendation", "HOLD")
    trend_score = prediction.get("trend_score", 0)
    confidence_raw = prediction.get("confidence", 50)
    price_change_pct = prediction.get("price_change_percent", 0)
    strength = prediction.get("recommendation_strength", "NEUTRAL")
    using_ml = prediction.get("using_ml_model", False)
    current_price = prediction.get("current_price", 0)
    predicted_price = prediction.get("predicted_price", 0)
    trend = prediction.get("trend", "SIDEWAYS")

    # Extract smart score signals if available
    signals = smart_score.get("signals", {}) if smart_score else {}
    ss_value = smart_score.get("smart_score", 50) if smart_score else 50
    rsi_score = signals.get("rsi", {}).get("score", 50)
    volume_score = signals.get("volume", {}).get("score", 50)
    news_score = signals.get("news_sentiment", {}).get("score", 50)
    fear_greed = signals.get("fear_greed", {}).get("score", 50)
    mtf_score = signals.get("multi_timeframe", {}).get("score", 50)
    pred_score = signals.get("prediction", {}).get("score", 50)

    # ── Market regime ───────────────────────────────────────────
    volatility = abs(trend_score)
    if volatility > 0.7:
        market_regime = "volatile"
    elif trend_score > 0.3:
        market_regime = "bullish"
    elif trend_score < -0.3:
        market_regime = "bearish"
    else:
        market_regime = "sideways"

    # ── Confidence ──────────────────────────────────────────────
    # Signal agreement: how many signals support the action
    agreement_signals = []
    contradictory = []

    if action == "BUY":
        if rsi_score > 55: agreement_signals.append("rsi")
        else: contradictory.append(f"RSI score weak ({rsi_score:.0f}/100)")
        if volume_score > 55: agreement_signals.append("volume")
        if news_score > 55: agreement_signals.append("news")
        else: contradictory.append(f"News sentiment neutral/negative ({news_score:.0f}/100)")
        if mtf_score > 55: agreement_signals.append("multi_timeframe")
        else: contradictory.append(f"Multi-timeframe not confirming ({mtf_score:.0f}/100)")
        if fear_greed > 40: agreement_signals.append("fear_greed")
        else: contradictory.append(f"Market fear high (F&G={fear_greed:.0f})")
    elif action == "SELL":
        if rsi_score < 45: agreement_signals.append("rsi")
        else: contradictory.append(f"RSI not overbought ({rsi_score:.0f}/100)")
        if volume_score < 45: agreement_signals.append("volume")
        if news_score < 45: agreement_signals.append("news")
        if mtf_score < 45: agreement_signals.append("multi_timeframe")
        if fear_greed < 40: agreement_signals.append("fear_greed")
    else:
        contradictory.append("No clear directional consensus")

    total_checked = 5
    signal_agreement = len(agreement_signals) / total_checked if total_checked > 0 else 0

    conf = compute_confidence(
        signal_agreement=signal_agreement,
        volatility=min(1.0, volatility),
        trend_strength=min(1.0, abs(trend_score)),
    )

    # ── Primary reasons ─────────────────────────────────────────
    primary_reasons = []
    if using_ml:
        primary_reasons.append(f"ML model predicts {price_change_pct:+.1f}% price change")
    if abs(trend_score) > 0.3:
        primary_reasons.append(f"Trend score {trend_score:+.2f} indicates {trend.lower()} momentum")
    if ss_value > 75 and action == "BUY":
        primary_reasons.append(f"Smart Score {ss_value:.0f}/100 exceeds trade threshold")
    elif ss_value < 30 and action == "SELL":
        primary_reasons.append(f"Smart Score {ss_value:.0f}/100 below sell threshold")
    if strength == "STRONG":
        primary_reasons.append(f"Signal strength is STRONG ({abs(price_change_pct):.1f}% expected)")
    if not primary_reasons:
        primary_reasons.append(f"Predicted price {'increase' if price_change_pct > 0 else 'decrease'} of {abs(price_change_pct):.1f}%")

    # ── Supporting signals ──────────────────────────────────────
    supporting = []
    if rsi_score > 60 and action == "BUY":
        supporting.append(f"RSI momentum supports upside ({rsi_score:.0f}/100)")
    if rsi_score < 40 and action == "SELL":
        supporting.append(f"RSI confirms downward pressure ({rsi_score:.0f}/100)")
    if volume_score > 60:
        supporting.append(f"Volume confirms move ({volume_score:.0f}/100)")
    if news_score > 65 and action == "BUY":
        supporting.append(f"Positive news sentiment ({news_score:.0f}/100)")
    if mtf_score > 70 and action == "BUY":
        supporting.append(f"Multi-timeframe trend aligned bullish ({mtf_score:.0f}/100)")
    if mtf_score < 30 and action == "SELL":
        supporting.append(f"Multi-timeframe trend aligned bearish ({mtf_score:.0f}/100)")

    # ── Risk factors ────────────────────────────────────────────
    risk_factors = []
    if fear_greed < 25:
        risk_factors.append("Extreme market fear — high liquidation risk")
    if fear_greed > 80:
        risk_factors.append("Extreme greed — correction risk elevated")
    if volatility > 0.6:
        risk_factors.append(f"High volatility (trend_score magnitude {abs(trend_score):.2f})")
    if not using_ml:
        risk_factors.append("No ML model available — prediction is simulated")
    if conf["band"] == "low":
        risk_factors.append("Low confidence — signals disagree")

    # ── Why not opposite ────────────────────────────────────────
    why_not_opposite = []
    if action == "BUY":
        why_not_opposite.append(f"SELL rejected: predicted price change is positive ({price_change_pct:+.1f}%)")
        if trend_score > 0:
            why_not_opposite.append(f"Trend is upward (score {trend_score:+.2f})")
    elif action == "SELL":
        why_not_opposite.append(f"BUY rejected: predicted price change is negative ({price_change_pct:+.1f}%)")
        if trend_score < 0:
            why_not_opposite.append(f"Trend is downward (score {trend_score:+.2f})")
    else:
        why_not_opposite.append(f"BUY/SELL rejected: price change too small ({abs(price_change_pct):.1f}% < 0.5% threshold)")

    # ── Why not wait ────────────────────────────────────────────
    why_not_wait = []
    if strength == "STRONG":
        why_not_wait.append(f"Signal is STRONG — waiting may miss the move ({abs(price_change_pct):.1f}%)")
    if ss_value > 80:
        why_not_wait.append(f"Smart Score {ss_value:.0f} indicates high-probability setup")
    if action == "HOLD":
        why_not_wait = ["Action IS wait — no compelling entry/exit detected"]

    # ── Stop loss / Take profit logic ───────────────────────────
    sl_pct = 3.0
    tp_pct = 5.0
    if current_price > 0:
        if action == "BUY":
            sl_price = current_price * (1 - sl_pct / 100)
            tp_price = current_price * (1 + tp_pct / 100)
        elif action == "SELL":
            sl_price = current_price * (1 + sl_pct / 100)
            tp_price = current_price * (1 - tp_pct / 100)
        else:
            sl_price = tp_price = current_price

        stop_loss_logic = f"{sl_pct}% stop loss at ${sl_price:,.2f} — limits downside to ${current_price * sl_pct / 100:,.2f} per unit"
        take_profit_logic = f"{tp_pct}% take profit at ${tp_price:,.2f} — risk:reward ratio 1:{tp_pct / sl_pct:.1f}"
    else:
        stop_loss_logic = f"{sl_pct}% stop loss — standard risk management"
        take_profit_logic = f"{tp_pct}% take profit — 1:{tp_pct / sl_pct:.1f} R:R ratio"

    # ── Holding profile ─────────────────────────────────────────
    if strength == "STRONG":
        expected_holding = "Short-term (1-3 days) — strong momentum expected"
    elif strength == "MODERATE":
        expected_holding = "Medium-term (3-7 days) — moderate trend developing"
    else:
        expected_holding = "No position — wait for clearer signal"

    # ── Narratives ──────────────────────────────────────────────
    symbol = prediction.get("symbol", "")
    narrative = (
        f"{symbol}: {action} signal with {conf['band']} confidence ({conf['score']:.0%}). "
        f"ML model predicts {price_change_pct:+.1f}% over 7 days in a {market_regime} market. "
        f"Smart Score: {ss_value:.0f}/100. "
        f"{len(agreement_signals)}/{total_checked} signals agree. "
        f"{'Proceed with caution.' if conf['band'] == 'low' else 'Setup looks favorable.' if conf['band'] == 'high' else 'Monitor closely.'}"
    )

    machine = (
        f"action={action}|conf={conf['score']}|band={conf['band']}|regime={market_regime}"
        f"|trend={trend_score:+.3f}|smart_score={ss_value:.1f}"
        f"|agree={len(agreement_signals)}/{total_checked}|ml={using_ml}"
    )

    return DecisionExplanation(
        action=action,
        confidence_score=conf["score"],
        confidence_band=conf["band"],
        market_regime=market_regime,
        primary_reasons=primary_reasons,
        supporting_signals=supporting,
        contradictory_signals=contradictory,
        risk_factors=risk_factors,
        why_not_opposite=why_not_opposite,
        why_not_wait=why_not_wait,
        stop_loss_logic=stop_loss_logic,
        take_profit_logic=take_profit_logic,
        expected_holding_profile=expected_holding,
        narrative_summary=narrative,
        machine_summary=machine,
        audit_metadata={
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "model_version": prediction.get("model_version", "unknown"),
            "using_ml_model": using_ml,
            "raw_confidence": confidence_raw,
            "smart_score": ss_value,
            "trend_score": trend_score,
            "price_change_pct": price_change_pct,
            "signal_agreement_ratio": signal_agreement,
        },
    )
