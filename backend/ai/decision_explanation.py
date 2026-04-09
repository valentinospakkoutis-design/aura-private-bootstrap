"""
Explainable AI Decision Layer for AURA (v2)
Produces structured, auditable explanations for every trading decision.
All reasoning is derived from real signals — never fabricated.

Supports first-class: BUY, SELL, HOLD, NO-TRADE, BLOCKED, REDUCED states.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel

from ai.reason_codes import (
    ML_POSITIVE_FORECAST, ML_NEGATIVE_FORECAST,
    TREND_BULLISH, TREND_BEARISH,
    SMART_SCORE_ABOVE_THRESHOLD, SMART_SCORE_BELOW_THRESHOLD,
    SIGNAL_ALIGNMENT_HIGH, RSI_SUPPORTS_DIRECTION,
    VOLUME_CONFIRMS_MOVE, NEWS_SENTIMENT_FAVORABLE,
    MTF_TREND_ALIGNED, STRONG_SIGNAL_STRENGTH,
    LOW_CONFIDENCE, SIGNAL_CONFLICT, NO_ML_CONFIRMATION,
    TREND_TOO_WEAK, MARKET_SIDEWAYS, VOLATILITY_TOO_HIGH,
    RISK_BLOCK, WAIT_FOR_CONFIRMATION,
    SMART_SCORE_INSUFFICIENT, FEAR_GREED_EXTREME,
    PRICE_CHANGE_BELOW_THRESHOLD,
    SIZE_REDUCED_BY_VOLATILITY, SIZE_REDUCED_BY_RISK,
    THRESHOLDS,
)


class DecisionExplanation(BaseModel):
    """Structured explanation for a trading decision."""
    # ── Core (v1) ───────────────────────────────────────────────
    action: str
    confidence_score: float
    confidence_band: str
    market_regime: str
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

    # ── Extended (v2) ───────────────────────────────────────────
    reason_codes: List[str] = []
    blocked_by: List[str] = []
    sizing_adjustments: List[str] = []
    invalidation_conditions: List[str] = []
    improvement_triggers: List[str] = []


def compute_confidence(
    signal_agreement: float,
    volatility: float,
    trend_strength: float,
) -> dict:
    """
    Deterministic confidence scoring.
    signal_agreement: 0-1, volatility: 0-1, trend_strength: 0-1
    """
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
    risk_context: Optional[Dict] = None,
) -> DecisionExplanation:
    """
    Build a structured decision explanation from real data.
    risk_context: optional dict with keys like
        {"blocked": bool, "block_reason": str, "size_factor": float, ...}
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
    symbol = prediction.get("symbol", "")

    signals = smart_score.get("signals", {}) if smart_score else {}
    ss_value = smart_score.get("smart_score", 50) if smart_score else 50
    rsi_score = signals.get("rsi", {}).get("score", 50)
    volume_score = signals.get("volume", {}).get("score", 50)
    news_score = signals.get("news_sentiment", {}).get("score", 50)
    fear_greed = signals.get("fear_greed", {}).get("score", 50)
    mtf_score = signals.get("multi_timeframe", {}).get("score", 50)

    risk_ctx = risk_context or {}
    volatility = abs(trend_score)

    # ── Market regime ───────────────────────────────────────────
    if volatility > THRESHOLDS["volatility_high"]:
        market_regime = "volatile"
    elif trend_score > THRESHOLDS["trend_score_directional"]:
        market_regime = "bullish"
    elif trend_score < -THRESHOLDS["trend_score_directional"]:
        market_regime = "bearish"
    else:
        market_regime = "sideways"

    # ── Signal agreement ────────────────────────────────────────
    agreement_signals = []
    contradictory = []
    reason_codes = []

    if action == "BUY":
        if rsi_score > 55:
            agreement_signals.append("rsi")
            reason_codes.append(RSI_SUPPORTS_DIRECTION)
        else:
            contradictory.append(f"RSI score weak ({rsi_score:.0f}/100)")
        if volume_score > 55:
            agreement_signals.append("volume")
            reason_codes.append(VOLUME_CONFIRMS_MOVE)
        if news_score > 55:
            agreement_signals.append("news")
            reason_codes.append(NEWS_SENTIMENT_FAVORABLE)
        else:
            contradictory.append(f"News sentiment neutral/negative ({news_score:.0f}/100)")
        if mtf_score > 55:
            agreement_signals.append("multi_timeframe")
            reason_codes.append(MTF_TREND_ALIGNED)
        else:
            contradictory.append(f"Multi-timeframe not confirming ({mtf_score:.0f}/100)")
        if fear_greed > 40:
            agreement_signals.append("fear_greed")
        else:
            contradictory.append(f"Market fear high (F&G={fear_greed:.0f})")
    elif action == "SELL":
        if rsi_score < 45:
            agreement_signals.append("rsi")
            reason_codes.append(RSI_SUPPORTS_DIRECTION)
        else:
            contradictory.append(f"RSI not overbought ({rsi_score:.0f}/100)")
        if volume_score < 45: agreement_signals.append("volume")
        if news_score < 45: agreement_signals.append("news")
        if mtf_score < 45:
            agreement_signals.append("multi_timeframe")
            reason_codes.append(MTF_TREND_ALIGNED)
        if fear_greed < 40: agreement_signals.append("fear_greed")
    else:
        contradictory.append("No clear directional consensus")
        reason_codes.append(SIGNAL_CONFLICT)

    total_checked = 5
    signal_agreement = len(agreement_signals) / total_checked

    conf = compute_confidence(
        signal_agreement=signal_agreement,
        volatility=min(1.0, volatility),
        trend_strength=min(1.0, abs(trend_score)),
    )

    # ── Reason codes from inputs ────────────────────────────────
    if using_ml and price_change_pct > 0:
        reason_codes.append(ML_POSITIVE_FORECAST)
    elif using_ml and price_change_pct < 0:
        reason_codes.append(ML_NEGATIVE_FORECAST)
    if not using_ml:
        reason_codes.append(NO_ML_CONFIRMATION)

    if trend_score > THRESHOLDS["trend_score_directional"]:
        reason_codes.append(TREND_BULLISH)
    elif trend_score < -THRESHOLDS["trend_score_directional"]:
        reason_codes.append(TREND_BEARISH)
    else:
        reason_codes.append(TREND_TOO_WEAK)

    if ss_value >= THRESHOLDS["smart_score_min"]:
        reason_codes.append(SMART_SCORE_ABOVE_THRESHOLD)
    else:
        reason_codes.append(SMART_SCORE_INSUFFICIENT)

    if signal_agreement >= THRESHOLDS["signal_agreement_high"]:
        reason_codes.append(SIGNAL_ALIGNMENT_HIGH)

    if strength == "STRONG":
        reason_codes.append(STRONG_SIGNAL_STRENGTH)

    if conf["band"] == "low":
        reason_codes.append(LOW_CONFIDENCE)

    if market_regime == "sideways":
        reason_codes.append(MARKET_SIDEWAYS)

    if volatility > THRESHOLDS["volatility_high"]:
        reason_codes.append(VOLATILITY_TOO_HIGH)

    if fear_greed < THRESHOLDS["fear_greed_min"]:
        reason_codes.append(FEAR_GREED_EXTREME)

    if abs(price_change_pct) < THRESHOLDS["price_change_buy"]:
        reason_codes.append(PRICE_CHANGE_BELOW_THRESHOLD)

    # ── Determine effective action (upgrade HOLD to NO-TRADE) ───
    effective_action = action
    if action == "HOLD" and conf["band"] == "low":
        effective_action = "NO-TRADE"
    if action in ("BUY", "SELL") and conf["band"] == "low" and signal_agreement < 0.4:
        effective_action = "NO-TRADE"

    # ── Blocked / Reduced (from risk context) ───────────────────
    blocked_by = []
    sizing_adjustments = []

    if risk_ctx.get("blocked"):
        effective_action = "BLOCKED"
        blocked_by.append(risk_ctx.get("block_reason", RISK_BLOCK))
        reason_codes.append(RISK_BLOCK)

    if risk_ctx.get("position_limit_hit"):
        blocked_by.append("Max concurrent positions reached")
        reason_codes.append("PORTFOLIO_EXPOSURE_LIMIT")

    if risk_ctx.get("symbol_already_open"):
        blocked_by.append("Position already open for this symbol")
        reason_codes.append("SYMBOL_EXPOSURE_LIMIT")

    size_factor = risk_ctx.get("size_factor", 1.0)
    if 0 < size_factor < 1.0:
        effective_action = action  # keep directional, but note reduction
        if volatility > 0.5:
            sizing_adjustments.append(f"Size reduced to {size_factor:.0%} due to high volatility")
            reason_codes.append(SIZE_REDUCED_BY_VOLATILITY)
        else:
            sizing_adjustments.append(f"Size reduced to {size_factor:.0%} by risk engine")
            reason_codes.append(SIZE_REDUCED_BY_RISK)

    # ── Primary reasons ─────────────────────────────────────────
    primary_reasons = []
    if using_ml:
        primary_reasons.append(f"ML model predicts {price_change_pct:+.1f}% price change")
    if abs(trend_score) > THRESHOLDS["trend_score_directional"]:
        primary_reasons.append(f"Trend score {trend_score:+.2f} indicates {trend.lower()} momentum")
    if ss_value >= THRESHOLDS["smart_score_min"] and effective_action == "BUY":
        primary_reasons.append(f"Smart Score {ss_value:.0f}/100 exceeds {THRESHOLDS['smart_score_min']} threshold")
    if strength == "STRONG":
        primary_reasons.append(f"Signal strength is STRONG ({abs(price_change_pct):.1f}% expected)")
    if effective_action == "NO-TRADE":
        primary_reasons.append("No trade: insufficient confidence or signal alignment")
    if effective_action == "BLOCKED":
        primary_reasons.append(f"Trade blocked: {', '.join(blocked_by)}")
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
    if fear_greed < THRESHOLDS["fear_greed_min"]:
        risk_factors.append(f"Extreme market fear (F&G={fear_greed:.0f}, threshold={THRESHOLDS['fear_greed_min']})")
    if fear_greed > 80:
        risk_factors.append("Extreme greed — correction risk elevated")
    if volatility > 0.6:
        risk_factors.append(f"High volatility (|trend_score|={abs(trend_score):.2f})")
    if not using_ml:
        risk_factors.append("No ML model available — prediction is simulated")
    if conf["band"] == "low":
        risk_factors.append("Low confidence — signals disagree")
    if len(contradictory) > 2:
        risk_factors.append(f"{len(contradictory)} contradictory signals detected")

    # ── Why not opposite / why not wait ─────────────────────────
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
        why_not_opposite.append(f"BUY/SELL rejected: price change too small ({abs(price_change_pct):.1f}% < {THRESHOLDS['price_change_buy']}% threshold)")

    why_not_wait = []
    if strength == "STRONG":
        why_not_wait.append(f"Signal is STRONG — waiting may miss the move ({abs(price_change_pct):.1f}%)")
    if ss_value > 80:
        why_not_wait.append(f"Smart Score {ss_value:.0f} indicates high-probability setup")
    if effective_action in ("HOLD", "NO-TRADE"):
        why_not_wait = ["Action IS wait — no compelling entry/exit detected"]

    # ── Improvement triggers (counterfactuals) ──────────────────
    improvement_triggers = []
    if effective_action in ("HOLD", "NO-TRADE"):
        if abs(trend_score) < THRESHOLDS["trend_score_directional"]:
            needed = THRESHOLDS["trend_score_directional"]
            improvement_triggers.append(
                f"Becomes BUY if trend_score > +{needed} (currently {trend_score:+.2f})"
            )
            improvement_triggers.append(
                f"Becomes SELL if trend_score < -{needed} (currently {trend_score:+.2f})"
            )
        if ss_value < THRESHOLDS["smart_score_min"]:
            improvement_triggers.append(
                f"Becomes tradable if Smart Score >= {THRESHOLDS['smart_score_min']} (currently {ss_value:.0f})"
            )
        if conf["band"] == "low":
            improvement_triggers.append(
                f"Confidence improves if signal agreement > {THRESHOLDS['signal_agreement_high']:.0%} (currently {signal_agreement:.0%})"
            )
        if not using_ml:
            improvement_triggers.append("ML model training would enable data-driven forecasts")
        if abs(price_change_pct) < THRESHOLDS["price_change_buy"]:
            improvement_triggers.append(
                f"Directional signal requires price forecast > {THRESHOLDS['price_change_buy']}% (currently {abs(price_change_pct):.1f}%)"
            )

    if effective_action == "BLOCKED":
        if risk_ctx.get("position_limit_hit"):
            improvement_triggers.append(f"Close an existing position to free a slot (max={THRESHOLDS['max_positions']})")
        if risk_ctx.get("symbol_already_open"):
            improvement_triggers.append("Close existing position in this symbol first")

    if effective_action in ("BUY", "SELL") and conf["band"] != "high":
        if signal_agreement < THRESHOLDS["signal_agreement_high"]:
            improvement_triggers.append(
                f"Confidence upgrades to HIGH if {int(THRESHOLDS['signal_agreement_high'] * 5)}/5 signals align (currently {len(agreement_signals)}/5)"
            )

    # ── Invalidation conditions ─────────────────────────────────
    invalidation_conditions = []
    if effective_action == "BUY":
        invalidation_conditions.append(f"Invalidated if trend_score drops below -{THRESHOLDS['trend_score_directional']}")
        invalidation_conditions.append(f"Invalidated if Fear & Greed drops below {THRESHOLDS['fear_greed_min']}")
        invalidation_conditions.append(f"Invalidated if Smart Score drops below {THRESHOLDS['smart_score_min']}")
    elif effective_action == "SELL":
        invalidation_conditions.append(f"Invalidated if trend_score rises above +{THRESHOLDS['trend_score_directional']}")
        invalidation_conditions.append(f"Invalidated if Smart Score rises above {THRESHOLDS['smart_score_min']}")

    # ── SL/TP logic ─────────────────────────────────────────────
    sl_pct = THRESHOLDS["stop_loss_pct"]
    tp_pct = THRESHOLDS["take_profit_pct"]
    if current_price > 0 and effective_action in ("BUY", "SELL"):
        if effective_action == "BUY":
            sl_price = current_price * (1 - sl_pct / 100)
            tp_price = current_price * (1 + tp_pct / 100)
        else:
            sl_price = current_price * (1 + sl_pct / 100)
            tp_price = current_price * (1 - tp_pct / 100)
        stop_loss_logic = f"{sl_pct}% stop loss at ${sl_price:,.2f}"
        take_profit_logic = f"{tp_pct}% take profit at ${tp_price:,.2f} — R:R 1:{tp_pct / sl_pct:.1f}"
    else:
        stop_loss_logic = "N/A — no position"
        take_profit_logic = "N/A — no position"

    # ── Holding profile ─────────────────────────────────────────
    if effective_action in ("HOLD", "NO-TRADE", "BLOCKED"):
        expected_holding = "No position — wait for clearer signal"
    elif strength == "STRONG":
        expected_holding = "Short-term (1-3 days) — strong momentum expected"
    else:
        expected_holding = "Medium-term (3-7 days) — moderate trend developing"

    # ── Narratives ──────────────────────────────────────────────
    narrative = (
        f"{symbol}: {effective_action} signal with {conf['band']} confidence ({conf['score']:.0%}). "
        f"{'ML model' if using_ml else 'Simulation'} predicts {price_change_pct:+.1f}% over 7 days in a {market_regime} market. "
        f"Smart Score: {ss_value:.0f}/100. "
        f"{len(agreement_signals)}/{total_checked} signals agree. "
    )
    if effective_action == "NO-TRADE":
        narrative += "No trade: conditions insufficient. "
    elif effective_action == "BLOCKED":
        narrative += f"Blocked by: {', '.join(blocked_by)}. "
    elif conf["band"] == "high":
        narrative += "Setup looks favorable."
    elif conf["band"] == "low":
        narrative += "Proceed with caution."
    else:
        narrative += "Monitor closely."

    machine = (
        f"action={effective_action}|conf={conf['score']}|band={conf['band']}|regime={market_regime}"
        f"|trend={trend_score:+.3f}|ss={ss_value:.1f}"
        f"|agree={len(agreement_signals)}/{total_checked}|ml={using_ml}"
        f"|codes={','.join(reason_codes[:5])}"
    )

    return DecisionExplanation(
        action=effective_action,
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
        reason_codes=reason_codes,
        blocked_by=blocked_by,
        sizing_adjustments=sizing_adjustments,
        invalidation_conditions=invalidation_conditions,
        improvement_triggers=improvement_triggers,
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
            "effective_action": effective_action,
            "original_action": action,
            "reason_code_count": len(reason_codes),
            "blocked": len(blocked_by) > 0,
            "size_adjusted": len(sizing_adjustments) > 0,
        },
    )
