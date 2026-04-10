"""
Claude AI Validation Layer for AURA Auto Trading.
Called ONLY when XGBoost confidence > 90% — not on every scan.

Uses claude-haiku-4-5-20251001 (fast + cheap) with 10s timeout.
Graceful degradation: if API key missing or call fails, proceeds normally.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def _get_client():
    """Lazy-init Anthropic client. Returns None if no API key."""
    if not _ANTHROPIC_KEY:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=_ANTHROPIC_KEY, timeout=10.0)
    except Exception as e:
        logger.warning(f"[Claude] Failed to init client: {e}")
        return None


def validate_trade_signal(
    symbol: str,
    action: str,
    confidence: float,
    current_price: float,
    fear_greed: int,
    portfolio_exposure: float,
    reasoning: str,
) -> dict:
    """
    Asks Claude to validate a high-confidence trade signal.
    Returns: { decision, confidence_adjustment, size_multiplier, reasoning, risk_level }
    """
    client = _get_client()
    if not client:
        return _default_execute("No API key")

    try:
        prompt = f"""You are a professional trading risk manager for AURA.

Current signal:
- Symbol: {symbol}
- Action: {action}
- ML Confidence: {confidence:.1%}
- Current Price: ${current_price:,.2f}
- Fear & Greed Index: {fear_greed}/100
- Portfolio Exposure: {portfolio_exposure:.1%}
- ML Reasoning: {reasoning}

Based on this data, should AURA execute this trade?

Respond ONLY with valid JSON:
{{
  "decision": "execute" | "skip" | "reduce",
  "confidence_adjustment": -0.2 to +0.1,
  "size_multiplier": 0.25 to 1.0,
  "reasoning": "brief explanation in Greek",
  "risk_level": "low" | "medium" | "high"
}}

Rules:
- "execute": signal is strong, proceed normally
- "reduce": signal ok but reduce position size
- "skip": too risky, do not trade
- Fear & Greed < 20: always skip unless very strong signal
- Portfolio exposure > 40%: always reduce
- Never suggest trades against strong market trends"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()
        result = json.loads(response_text)

        # Validate required fields
        if result.get("decision") not in ("execute", "skip", "reduce"):
            result["decision"] = "execute"
        result.setdefault("confidence_adjustment", 0)
        result.setdefault("size_multiplier", 1.0)
        result.setdefault("reasoning", "")
        result.setdefault("risk_level", "medium")

        logger.info(
            f"[Claude] {symbol} {action} -> {result['decision']} | "
            f"size={result['size_multiplier']} | {result['reasoning'][:80]}"
        )
        return result

    except Exception as e:
        logger.warning(f"[Claude] Validation failed: {e}, proceeding with original signal")
        return _default_execute(str(e))


def validate_close_position(
    symbol: str,
    side: str,
    entry_price: float,
    current_price: float,
    pnl_pct: float,
    holding_hours: float,
    fear_greed: int,
) -> dict:
    """
    Asks Claude whether to close an open position.
    Returns: { decision, partial_size, reasoning, urgency }
    """
    client = _get_client()
    if not client:
        return {"decision": "hold", "partial_size": 1.0, "reasoning": "No API key", "urgency": "low"}

    try:
        pnl_direction = "profit" if pnl_pct > 0 else "loss"

        prompt = f"""You are a professional trading risk manager for AURA.

Open position:
- Symbol: {symbol}
- Position: {side}
- Entry Price: ${entry_price:,.2f}
- Current Price: ${current_price:,.2f}
- P/L: {pnl_pct:+.2f}% ({pnl_direction})
- Holding: {holding_hours:.1f} hours
- Fear & Greed: {fear_greed}/100

Should AURA close this position now?

Respond ONLY with valid JSON:
{{
  "decision": "close" | "hold" | "partial_close",
  "partial_size": 0.25 to 1.0,
  "reasoning": "brief explanation in Greek",
  "urgency": "low" | "medium" | "high"
}}

Rules:
- P/L > +5%: consider closing to secure profits
- P/L < -3%: close immediately to limit losses
- Fear & Greed < 15: close risky positions
- Holding > 48h: reassess if still valid"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()
        result = json.loads(response_text)

        if result.get("decision") not in ("close", "hold", "partial_close"):
            result["decision"] = "hold"
        result.setdefault("partial_size", 1.0)
        result.setdefault("reasoning", "")
        result.setdefault("urgency", "low")

        logger.info(f"[Claude] Close {symbol} -> {result['decision']} | {result['reasoning'][:80]}")
        return result

    except Exception as e:
        logger.warning(f"[Claude] Close validation failed: {e}")
        return {"decision": "hold", "partial_size": 1.0, "reasoning": f"Claude unavailable: {e}", "urgency": "low"}


def _default_execute(reason: str) -> dict:
    return {
        "decision": "execute",
        "confidence_adjustment": 0,
        "size_multiplier": 1.0,
        "reasoning": f"Claude unavailable ({reason}), using ML signal",
        "risk_level": "medium",
    }
