"""
Online learning: RL agent updates itself from real trade outcomes.
Called after completed auto-trades (fire-and-forget).
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


async def record_trade_outcome(
    symbol: str,
    action: str,
    entry_price: float,
    exit_price: float,
    confidence: float,
    redis_client,
    db_session=None,
):
    """
    Record trade outcome and compute reward for RL agent.
    Stores in rl_trade_outcomes for periodic retraining.
    """
    symbol_u = (symbol or "").upper()
    action_u = (action or "HOLD").upper()
    ep = _to_float(entry_price, 0.0)
    xp = _to_float(exit_price, 0.0)
    conf = _to_float(confidence, 0.0)

    if ep <= 0 or xp <= 0 or not symbol_u:
        return

    pnl_pct = (xp - ep) / ep
    if action_u == "SELL":
        pnl_pct = -pnl_pct

    if pnl_pct > 0.01:
        reward = 1.0
    elif pnl_pct > 0:
        reward = 0.3
    elif pnl_pct > -0.01:
        reward = -0.3
    else:
        reward = -1.0

    try:
        if db_session is not None:
            from sqlalchemy import text

            db_session.execute(
                text(
                    """
                    INSERT INTO rl_trade_outcomes
                    (symbol, action, entry_price, exit_price, pnl_pct, reward, confidence, recorded_at)
                    VALUES (:symbol, :action, :entry_price, :exit_price, :pnl_pct, :reward, :confidence, :recorded_at)
                    """
                ),
                {
                    "symbol": symbol_u,
                    "action": action_u,
                    "entry_price": ep,
                    "exit_price": xp,
                    "pnl_pct": pnl_pct,
                    "reward": reward,
                    "confidence": conf,
                    "recorded_at": datetime.utcnow(),
                },
            )
            db_session.commit()
        else:
            from database.connection import SessionLocal
            from sqlalchemy import text

            db = SessionLocal()
            try:
                db.execute(
                    text(
                        """
                        INSERT INTO rl_trade_outcomes
                        (symbol, action, entry_price, exit_price, pnl_pct, reward, confidence, recorded_at)
                        VALUES (:symbol, :action, :entry_price, :exit_price, :pnl_pct, :reward, :confidence, :recorded_at)
                        """
                    ),
                    {
                        "symbol": symbol_u,
                        "action": action_u,
                        "entry_price": ep,
                        "exit_price": xp,
                        "pnl_pct": pnl_pct,
                        "reward": reward,
                        "confidence": conf,
                        "recorded_at": datetime.utcnow(),
                    },
                )
                db.commit()
            finally:
                db.close()

        print(f"[RL_ONLINE] {symbol_u} {action_u}: PnL={pnl_pct:.2%} Reward={reward}")

        if redis_client is not None:
            payload = {
                "reward": reward,
                "pnl_pct": round(pnl_pct, 4),
                "action": action_u,
                "ts": datetime.utcnow().isoformat(),
            }
            redis_client.lpush(f"rl_rewards:{symbol_u}", json.dumps(payload))
            redis_client.ltrim(f"rl_rewards:{symbol_u}", 0, 99)
            redis_client.expire(f"rl_rewards:{symbol_u}", 7 * 86400)
    except Exception as e:
        print(f"[RL_ONLINE] Error recording outcome: {e}")


async def get_symbol_performance(symbol: str, redis_client) -> Dict[str, Any]:
    """Get recent RL performance for a symbol from Redis cache."""
    symbol_u = (symbol or "").upper()
    try:
        if redis_client is None:
            return {"symbol": symbol_u, "trades": 0, "avg_reward": 0.0}

        raw = redis_client.lrange(f"rl_rewards:{symbol_u}", 0, 19)
        if not raw:
            return {"symbol": symbol_u, "trades": 0, "avg_reward": 0.0}

        rewards = []
        for r in raw:
            if isinstance(r, bytes):
                r = r.decode("utf-8")
            rewards.append(float(json.loads(r).get("reward", 0.0)))

        avg_reward = sum(rewards) / len(rewards) if rewards else 0.0
        positive = sum(1 for r in rewards if r > 0)

        return {
            "symbol": symbol_u,
            "trades": len(rewards),
            "avg_reward": round(avg_reward, 3),
            "win_rate": round((positive / len(rewards)) if rewards else 0.0, 3),
            "trend": "improving" if avg_reward > 0.2 else "stable" if avg_reward > -0.2 else "degrading",
        }
    except Exception as e:
        return {"symbol": symbol_u, "trades": 0, "avg_reward": 0.0, "error": str(e)}
