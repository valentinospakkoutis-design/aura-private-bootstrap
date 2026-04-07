"""
Sentiment Shadow Mode — Phase 3
Simulates what confidence adjustments WOULD be made by sentiment data,
but does NOT apply them. Logs hypothetical results for validation.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def simulate_sentiment_adjustment(
    symbol: str,
    action: str,
    original_confidence: float,
    sentiment_score: float,
    sentiment_label: str,
) -> Dict:
    """
    Simulate what a sentiment adjustment WOULD do.
    Returns the hypothetical result — does NOT modify anything.

    Adjustment logic (hypothetical):
    - Strong positive sentiment (>70) + BUY → confidence boosted by 5%
    - Strong negative sentiment (<30) + SELL → confidence boosted by 5%
    - Sentiment contradicts action → confidence reduced by 5%
    - Neutral sentiment (30-70) → no change
    """
    adjustment = 0.0
    reason = "neutral_sentiment"

    if sentiment_score > 70:
        if action.upper() == "BUY":
            adjustment = 0.05
            reason = "positive_sentiment_confirms_buy"
        elif action.upper() == "SELL":
            adjustment = -0.05
            reason = "positive_sentiment_contradicts_sell"
    elif sentiment_score < 30:
        if action.upper() == "SELL":
            adjustment = 0.05
            reason = "negative_sentiment_confirms_sell"
        elif action.upper() == "BUY":
            adjustment = -0.05
            reason = "negative_sentiment_contradicts_buy"

    adjusted_confidence = max(0.0, min(1.0, original_confidence + adjustment))

    result = {
        "symbol": symbol,
        "action": action,
        "original_confidence": round(original_confidence, 4),
        "sentiment_score": round(sentiment_score, 1),
        "sentiment_label": sentiment_label,
        "adjustment": round(adjustment, 4),
        "adjusted_confidence": round(adjusted_confidence, 4),
        "reason": reason,
        "applied": False,  # Shadow mode — never applied
    }

    logger.info(
        f"[SHADOW] {symbol} {action}: conf {original_confidence:.3f} → "
        f"{adjusted_confidence:.3f} (sentiment={sentiment_score:.0f} {sentiment_label}, "
        f"adj={adjustment:+.3f}, reason={reason})"
    )

    return result


def run_shadow_on_predictions(predictions: list) -> list:
    """
    Run shadow simulation on a batch of predictions.
    Returns list of shadow results for logging/analysis.
    Requires ENABLE_SENTIMENT_SHADOW flag — caller must check.
    """
    from services.sentiment_scheduler import get_cached_sentiment

    shadow_results = []
    for pred in predictions:
        symbol = pred.get("symbol", "")
        action = pred.get("action", "hold")
        confidence = pred.get("confidence", 0.5)

        sentiment = get_cached_sentiment(symbol)
        score = sentiment.get("score", 50.0)
        label = sentiment.get("label", "neutral")

        result = simulate_sentiment_adjustment(
            symbol=symbol,
            action=action,
            original_confidence=confidence,
            sentiment_score=score,
            sentiment_label=label,
        )
        shadow_results.append(result)

    return shadow_results
