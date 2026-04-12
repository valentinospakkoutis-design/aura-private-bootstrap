"""
Multi-model ensemble predictor.

Base weights:
- XGBoost: 60%
- Random Forest: 40%

RL is a confirmation signal (bonus), not a base weight.
"""

import logging
from typing import Dict, Optional

from ai.asset_predictor import asset_predictor
from ml.rl_agent import get_rl_prediction

logger = logging.getLogger(__name__)


def _normalize_action(action: Optional[str]) -> str:
    a = str(action or "HOLD").upper()
    if a in ("BUY", "SELL", "HOLD"):
        return a
    return "HOLD"


def _extract_base_confidences(pred: Dict) -> tuple[float, float]:
    ensemble = pred.get("ensemble") if isinstance(pred, dict) else {}
    if not isinstance(ensemble, dict):
        ensemble = {}

    xgb = ensemble.get("xgboost")
    rf = ensemble.get("random_forest")

    # Fall back to overall confidence if sidecar values are missing.
    overall = float(pred.get("confidence", 0.0) or 0.0)
    overall = overall / 100.0 if overall > 1.0 else overall
    overall = max(0.0, min(1.0, overall))

    xgb_conf = float(xgb) if xgb is not None else overall
    rf_conf = float(rf) if rf is not None else overall

    return max(0.0, min(1.0, xgb_conf)), max(0.0, min(1.0, rf_conf))


def get_ensemble_prediction(symbol: str, features: Optional[Dict] = None) -> Dict:
    """
    Combined prediction from all models:
    - XGBoost (60% weight)
    - RandomForest (40% weight)
    - RL Agent confirmation bonus (+5% when it agrees)
    """
    symbol_u = (symbol or "").upper()
    try:
        pred = asset_predictor.predict_price(symbol_u, days=7)
        if not isinstance(pred, dict) or pred.get("error"):
            raise ValueError(pred.get("error") if isinstance(pred, dict) else "invalid prediction response")

        base_action = _normalize_action(pred.get("recommendation"))
        xgb_conf, rf_conf = _extract_base_confidences(pred)
        base_confidence = xgb_conf * 0.6 + rf_conf * 0.4

        rl_pred = None
        rl_action = None
        rl_agrees = False
        confidence_boost = 0.0

        try:
            rl_pred = get_rl_prediction(symbol_u)
            if rl_pred:
                rl_action = _normalize_action(rl_pred.get("action"))
                rl_agrees = rl_action == base_action
                confidence_boost = 0.05 if rl_agrees else 0.0
        except Exception as rl_err:
            logger.warning("[RL_CONSENSUS] RL fetch failed for %s: %s", symbol_u, rl_err)

        final_confidence = min(1.0, max(0.0, base_confidence + confidence_boost))

        logger.info(
            "[RL_CONSENSUS] %s: XGB=%.0f%% RF=%.0f%% RL=%s %s",
            symbol_u,
            xgb_conf * 100.0,
            rf_conf * 100.0,
            rl_action or "NONE",
            "✅" if rl_agrees else "❌",
        )

        return {
            "symbol": symbol_u,
            "action": base_action,
            "confidence": round(final_confidence, 4),
            "xgb_confidence": round(xgb_conf, 4),
            "rf_confidence": round(rf_conf, 4),
            "rl_action": rl_action,
            "rl_agrees": rl_agrees,
            "consensus": rl_agrees,
            "raw": {
                "asset_predictor": pred,
                "rl": rl_pred,
            },
        }
    except Exception as e:
        logger.exception("[RL_CONSENSUS] failed for %s", symbol_u)
        return {
            "symbol": symbol_u,
            "action": "HOLD",
            "confidence": 0.0,
            "xgb_confidence": 0.0,
            "rf_confidence": 0.0,
            "rl_action": None,
            "rl_agrees": False,
            "consensus": False,
            "error": str(e),
        }
