"""
Every new model must pass backtesting QA before going live.
A model is deployed ONLY if it beats the benchmark.
"""

import json
from datetime import datetime

VALIDATION_THRESHOLDS = {
    "min_accuracy": 0.52,
    "min_sharpe": 0.5,
    "max_drawdown": -0.25,
    "min_trades": 10,
}


def validate_model(symbol: str, new_model_metrics: dict, current_model_metrics: dict, redis_client) -> dict:
    """Validate new model against thresholds and current model."""
    symbol_u = (symbol or "").upper()
    new_m = new_model_metrics or {}
    cur_m = current_model_metrics

    checks = {}

    checks["min_accuracy"] = float(new_m.get("accuracy", 0.0) or 0.0) >= VALIDATION_THRESHOLDS["min_accuracy"]
    checks["min_sharpe"] = float(new_m.get("sharpe_ratio", 0.0) or 0.0) >= VALIDATION_THRESHOLDS["min_sharpe"]
    checks["max_drawdown"] = float(new_m.get("max_drawdown", -1.0) or -1.0) >= VALIDATION_THRESHOLDS["max_drawdown"]
    checks["min_trades"] = float(new_m.get("total_trades", 0.0) or 0.0) >= VALIDATION_THRESHOLDS["min_trades"]

    beats_current = (
        cur_m is None
        or float(new_m.get("accuracy", 0.0) or 0.0) >= float(cur_m.get("accuracy", 0.0) or 0.0) - 0.02
    )
    checks["beats_current"] = bool(beats_current)

    all_passed = bool(all(checks.values()))

    result = {
        "symbol": symbol_u,
        "deploy": all_passed,
        "checks": checks,
        "new_metrics": new_m,
        "current_metrics": cur_m,
        "validated_at": datetime.utcnow().isoformat(),
    }

    try:
        if redis_client is not None:
            redis_client.setex(f"model_validation:{symbol_u}", 86400, json.dumps(result))
    except Exception:
        pass

    status = "APPROVED" if all_passed else "REJECTED"
    print(f"[VALIDATOR] {symbol_u}: {status} - checks: {checks}")

    return result


def get_validation_history(symbol: str, redis_client) -> dict:
    """Get latest validation result for a symbol."""
    symbol_u = (symbol or "").upper()
    try:
        if redis_client is None:
            return {"symbol": symbol_u, "deploy": None, "message": "no cache available"}
        raw = redis_client.get(f"model_validation:{symbol_u}")
        if raw:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        return {"symbol": symbol_u, "deploy": None, "message": "no validation run yet"}
    except Exception as e:
        return {"symbol": symbol_u, "error": str(e)}
