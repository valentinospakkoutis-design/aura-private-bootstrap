"""
Strategy Simulation Engine for AURA.
Runs historical backtests against AI predictions and risk controls.

DISCLAIMER: Simulation results do NOT guarantee real-world performance.
Past performance, even simulated, is not indicative of future results.
Market conditions, slippage, fees, and execution differ in live trading.
"""

import logging
import math
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "SIMULATION DISCLAIMER: These results are hypothetical and do NOT represent real trading. "
    "Simulated performance does not account for all real-world factors including slippage, "
    "partial fills, exchange outages, and market impact. Past simulated results are NOT "
    "indicative of future performance. Use at your own risk."
)

# ── Strategy definitions ────────────────────────────────────────
STRATEGIES = {
    "ai_follow": {
        "label": "AI Follow",
        "description": "Follow AI BUY/SELL signals when confidence exceeds threshold",
        "default_confidence": 0.70,
    },
    "conservative_ai": {
        "label": "Conservative AI",
        "description": "Only act on STRONG signals with high smart score",
        "default_confidence": 0.90,
    },
    "buy_and_hold": {
        "label": "Buy & Hold",
        "description": "Buy at start, hold until end (benchmark)",
        "default_confidence": 0.0,
    },
}


def run_simulation(
    strategy: str,
    symbols: List[str],
    timeframe_days: int = 30,
    initial_capital: float = 10000.0,
    confidence_threshold: Optional[float] = None,
    stop_loss_pct: float = 0.03,
    take_profit_pct: float = 0.05,
    max_positions: int = 3,
    position_size_pct: float = 5.0,
) -> Dict:
    """
    Run a strategy simulation.

    Returns PnL, drawdown, trade list, risk metrics, and disclaimer.
    """
    if strategy not in STRATEGIES:
        return {"error": f"Unknown strategy. Available: {list(STRATEGIES.keys())}"}

    if not symbols:
        return {"error": "At least one symbol required"}

    if initial_capital <= 0:
        return {"error": "Initial capital must be positive"}

    if timeframe_days < 1 or timeframe_days > 365:
        return {"error": "Timeframe must be 1-365 days"}

    strat_def = STRATEGIES[strategy]
    conf_threshold = confidence_threshold if confidence_threshold is not None else strat_def["default_confidence"]

    # ── Fetch predictions for each symbol ───────────────────────
    try:
        from ai.asset_predictor import asset_predictor
    except ImportError:
        return {"error": "Asset predictor not available"}

    predictions = {}
    for sym in symbols:
        sym = sym.upper()
        pred = asset_predictor.predict_price(sym, days=min(timeframe_days, 7))
        if "error" not in pred:
            predictions[sym] = pred

    if not predictions:
        return {"error": "No valid predictions available for the given symbols"}

    # ── Simulate trades ─────────────────────────────────────────
    capital = initial_capital
    peak_capital = initial_capital
    max_drawdown = 0.0
    trades = []
    open_positions: Dict[str, dict] = {}
    daily_returns = []

    for sym, pred in predictions.items():
        action = pred.get("recommendation", "HOLD")
        confidence = pred.get("confidence", 0) / 100  # normalize to 0-1
        current_price = pred.get("current_price", 0)
        predicted_price = pred.get("predicted_price", 0)
        trend_score = pred.get("trend_score", 0)

        if current_price <= 0:
            continue

        # ── Buy & Hold strategy ─────────────────────────────────
        if strategy == "buy_and_hold":
            if len(open_positions) < max_positions:
                alloc = capital * (position_size_pct / 100)
                qty = alloc / current_price
                if qty > 0 and alloc > 1:
                    pnl = (predicted_price - current_price) * qty
                    pnl_pct = (predicted_price - current_price) / current_price * 100

                    trades.append({
                        "symbol": sym,
                        "side": "BUY",
                        "entry_price": round(current_price, 2),
                        "exit_price": round(predicted_price, 2),
                        "quantity": round(qty, 6),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "confidence": round(confidence, 3),
                        "reason": "Buy & Hold allocation",
                    })
                    capital += pnl
                    daily_returns.append(pnl_pct / max(timeframe_days, 1))
            continue

        # ── AI-based strategies ─────────────────────────────────
        if confidence < conf_threshold:
            trades.append({
                "symbol": sym,
                "side": "SKIP",
                "entry_price": round(current_price, 2),
                "exit_price": None,
                "quantity": 0,
                "pnl": 0,
                "pnl_pct": 0,
                "confidence": round(confidence, 3),
                "reason": f"Confidence {confidence:.0%} < threshold {conf_threshold:.0%}",
            })
            continue

        if action not in ("BUY", "SELL"):
            trades.append({
                "symbol": sym,
                "side": "HOLD",
                "entry_price": round(current_price, 2),
                "exit_price": None,
                "quantity": 0,
                "pnl": 0,
                "pnl_pct": 0,
                "confidence": round(confidence, 3),
                "reason": "No directional signal",
            })
            continue

        if len(open_positions) >= max_positions:
            continue

        # Conservative AI: additional smart score check
        if strategy == "conservative_ai" and abs(trend_score) < 0.3:
            trades.append({
                "symbol": sym,
                "side": "SKIP",
                "entry_price": round(current_price, 2),
                "exit_price": None,
                "quantity": 0,
                "pnl": 0,
                "pnl_pct": 0,
                "confidence": round(confidence, 3),
                "reason": f"Trend too weak ({trend_score:+.2f}) for conservative strategy",
            })
            continue

        # Calculate position
        alloc = capital * (position_size_pct / 100)
        qty = alloc / current_price
        if qty <= 0 or alloc < 1:
            continue

        # Simulate exit based on predicted price
        price_change = (predicted_price - current_price) / current_price

        if action == "BUY":
            # Check SL/TP
            if price_change <= -stop_loss_pct:
                exit_price = current_price * (1 - stop_loss_pct)
                pnl = -alloc * stop_loss_pct
                exit_reason = "Stop loss hit"
            elif price_change >= take_profit_pct:
                exit_price = current_price * (1 + take_profit_pct)
                pnl = alloc * take_profit_pct
                exit_reason = "Take profit hit"
            else:
                exit_price = predicted_price
                pnl = (predicted_price - current_price) * qty
                exit_reason = "Exit at predicted price"
        else:  # SELL
            if price_change >= stop_loss_pct:
                exit_price = current_price * (1 + stop_loss_pct)
                pnl = -alloc * stop_loss_pct
                exit_reason = "Stop loss hit"
            elif price_change <= -take_profit_pct:
                exit_price = current_price * (1 - take_profit_pct)
                pnl = alloc * take_profit_pct
                exit_reason = "Take profit hit"
            else:
                exit_price = predicted_price
                pnl = (current_price - predicted_price) * qty
                exit_reason = "Exit at predicted price"

        pnl_pct = (pnl / alloc * 100) if alloc > 0 else 0

        trades.append({
            "symbol": sym,
            "side": action,
            "entry_price": round(current_price, 2),
            "exit_price": round(exit_price, 2),
            "quantity": round(qty, 6),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "confidence": round(confidence, 3),
            "reason": exit_reason,
        })

        capital += pnl
        daily_returns.append(pnl_pct / max(timeframe_days, 1))

        # Track drawdown
        peak_capital = max(peak_capital, capital)
        current_drawdown = (peak_capital - capital) / peak_capital if peak_capital > 0 else 0
        max_drawdown = max(max_drawdown, current_drawdown)

    # ── Calculate risk metrics ──────────────────────────────────
    total_pnl = capital - initial_capital
    total_pnl_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0

    executed_trades = [t for t in trades if t["side"] not in ("SKIP", "HOLD")]
    winning_trades = [t for t in executed_trades if t["pnl"] > 0]
    losing_trades = [t for t in executed_trades if t["pnl"] < 0]

    win_rate = len(winning_trades) / len(executed_trades) * 100 if executed_trades else 0
    avg_win = sum(t["pnl"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t["pnl"] for t in losing_trades) / len(losing_trades) if losing_trades else 0
    profit_factor = abs(sum(t["pnl"] for t in winning_trades) / sum(t["pnl"] for t in losing_trades)) if losing_trades and sum(t["pnl"] for t in losing_trades) != 0 else float("inf")

    # Sharpe ratio (simplified)
    if daily_returns and len(daily_returns) > 1:
        mean_ret = sum(daily_returns) / len(daily_returns)
        std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1))
        sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0
    else:
        sharpe = 0

    return {
        "strategy": strategy,
        "strategy_label": strat_def["label"],
        "timeframe_days": timeframe_days,
        "initial_capital": initial_capital,
        "final_capital": round(capital, 2),
        "pnl": round(total_pnl, 2),
        "pnl_pct": round(total_pnl_pct, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "total_trades": len(executed_trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "skipped_trades": len([t for t in trades if t["side"] == "SKIP"]),
        "win_rate_pct": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else None,
        "confidence_threshold": conf_threshold,
        "stop_loss_pct": stop_loss_pct * 100,
        "take_profit_pct": take_profit_pct * 100,
        "trades": trades,
        "disclaimer": DISCLAIMER,
        "simulated_at": datetime.utcnow().isoformat(),
    }
