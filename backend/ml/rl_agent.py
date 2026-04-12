"""
RL Agent access layer.

Cache-first strategy:
1) Read today's cached action from rl_predictions.
2) Fallback to live model inference via rl_trader.get_rl_prediction.
"""

import logging
import os
import sys
from datetime import date
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def get_rl_prediction(symbol: str) -> Optional[Dict]:
    """Get RL prediction for symbol with DB cache-first and live fallback."""
    symbol_u = (symbol or "").upper()
    if not symbol_u:
        return None

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from database.connection import SessionLocal
        from database.models import RLPrediction

        db = SessionLocal()
        try:
            today = date.today()
            row = db.query(RLPrediction).filter(
                RLPrediction.symbol == symbol_u,
                RLPrediction.date == today,
            ).order_by(RLPrediction.predicted_at.desc()).first()

            if row is not None:
                action = str(row.action or "HOLD").upper()
                confidence = float(row.confidence or 0.6)
                return {
                    "symbol": symbol_u,
                    "action": action,
                    "confidence": round(confidence, 3),
                    "date": str(today),
                    "source": "rl_predictions_cache",
                    "agent_version": getattr(row, "agent_version", "v1.0"),
                }
        finally:
            db.close()
    except Exception as e:
        logger.debug("[RL_AGENT] cache lookup failed for %s: %s", symbol_u, e)

    try:
        from ml.rl_trader import get_rl_prediction as _get_live_prediction

        live = _get_live_prediction(symbol_u)
        if live:
            live["source"] = "rl_live_model"
        return live
    except Exception as e:
        logger.warning("[RL_AGENT] live prediction failed for %s: %s", symbol_u, e)
        return None
