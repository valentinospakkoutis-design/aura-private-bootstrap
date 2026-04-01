"""
Auto Trading Engine for AURA
Monitors AI predictions and places orders automatically when confidence is high.
DISABLED by default — user must explicitly enable from the UI.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List, Callable

logger = logging.getLogger(__name__)


class AutoTradingEngine:
    def __init__(self):
        self.is_running = False
        self.broker = None  # BinanceAPI instance
        self.check_interval = 300  # check every 5 minutes
        self.config = {
            "confidence_threshold": 0.90,   # only trade >= 90% confidence
            "position_size_pct": 0.05,      # 5% of portfolio per trade
            "stop_loss_pct": 0.03,          # 3% stop loss
            "max_positions": 5,             # max concurrent positions
            "max_order_value_usd": 100.0,   # hard safety limit per order
            "enabled": False,               # OFF by default
        }
        self.open_positions: Dict[str, dict] = {}
        self.trade_log: List[dict] = []

    def set_broker(self, broker):
        """Set the BinanceAPI broker instance."""
        self.broker = broker
        logger.info("[auto-trader] Broker set")

    def enable(self):
        if not self.broker:
            raise ValueError("No broker connected")
        self.config["enabled"] = True
        self._log_event("AUTO_TRADING_ENABLED", "Auto trading enabled by user")
        logger.info("[auto-trader] AUTO TRADING ENABLED")

    def disable(self):
        self.config["enabled"] = False
        self._log_event("AUTO_TRADING_DISABLED", "Auto trading disabled by user")
        logger.info("[auto-trader] Auto trading DISABLED")

    def get_status(self) -> dict:
        return {
            "enabled": self.config["enabled"],
            "is_running": self.is_running,
            "config": self.config,
            "open_positions_count": len(self.open_positions),
            "positions": list(self.open_positions.values()),
            "recent_log": self.trade_log[-20:],
        }

    def _log_event(self, event_type: str, message: str, data: dict = None):
        entry = {
            "type": event_type,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.trade_log.append(entry)
        # Keep only last 100 entries
        if len(self.trade_log) > 100:
            self.trade_log = self.trade_log[-100:]

    def _get_available_balance(self) -> float:
        """Get available stablecoin balance (USDC or USDT)"""
        try:
            account = self.broker.get_account_balance()
            # Try USDC first
            if isinstance(account, dict) and "balances" in account:
                for balance in account["balances"]:
                    if balance["asset"] == "USDC":
                        return float(balance["free"])
                # Fallback to USDT if USDC not found
                for balance in account["balances"]:
                    if balance["asset"] == "USDT":
                        return float(balance["free"])
            else:
                return account.get("available_balance", 0)
        except Exception as e:
            logger.error(f"[auto-trader] Failed to get balance: {e}")
            return 0.0

    def get_trading_symbol(self, asset_symbol: str) -> str:
        """Try USDC pair first, fallback to USDT pair."""
        usdc_symbol = asset_symbol.replace("USDT", "USDC")
        try:
            self.broker.client.get_symbol_ticker(symbol=usdc_symbol)
            return usdc_symbol  # USDC pair exists
        except Exception:
            return asset_symbol  # fallback to USDT pair

    def _calculate_position_size(self, price: float) -> float:
        """Calculate quantity based on position_size_pct of portfolio."""
        balance = self._get_available_balance()
        position_value = balance * self.config["position_size_pct"]

        # Hard safety limit
        if position_value > self.config["max_order_value_usd"]:
            position_value = self.config["max_order_value_usd"]

        if price <= 0:
            return 0.0
        quantity = position_value / price
        return round(quantity, 6)

    def place_auto_order(self, prediction: dict) -> Optional[dict]:
        """Place an automated order based on a prediction. Returns position dict or None."""
        symbol = prediction.get("symbol", "")
        action = prediction.get("action", "")
        price = prediction.get("price", 0)
        target_price = prediction.get("targetPrice", 0)
        confidence = prediction.get("confidence", 0)

        # ── Safety checks ────────────────────────────────────────
        if not self.config["enabled"]:
            return None

        if not self.broker or not self.broker.connected:
            self._log_event("SKIP", f"{symbol}: broker not connected")
            return None

        if confidence < self.config["confidence_threshold"]:
            return None  # silent skip — most predictions won't pass

        if len(self.open_positions) >= self.config["max_positions"]:
            self._log_event("SKIP", f"{symbol}: max positions reached ({self.config['max_positions']})")
            return None

        if symbol in self.open_positions:
            return None  # already have position

        if action not in ("buy", "sell"):
            return None

        if price <= 0:
            self._log_event("SKIP", f"{symbol}: invalid price {price}")
            return None

        side = "BUY" if action == "buy" else "SELL"
        quantity = self._calculate_position_size(price)

        if quantity <= 0:
            self._log_event("SKIP", f"{symbol}: insufficient balance for position")
            return None

        # Final safety: check order value
        order_value = quantity * price
        if order_value > self.config["max_order_value_usd"]:
            self._log_event("BLOCKED", f"{symbol}: order value ${order_value:.2f} exceeds limit ${self.config['max_order_value_usd']:.0f}")
            return None

        # ── Place order ──────────────────────────────────────────
        try:
            self._log_event("ORDER_ATTEMPT", f"{side} {quantity} {symbol} @ ~${price:.2f} (confidence {confidence:.0%})")
            logger.info(f"[auto-trader] Placing {side} {symbol} qty={quantity} confidence={confidence:.0%}")

            result = self.broker.place_live_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type="MARKET",
            )

            if "error" in result:
                self._log_event("ORDER_FAILED", f"{symbol}: {result['error']}", result)
                logger.error(f"[auto-trader] Order failed for {symbol}: {result['error']}")
                return None

            entry_price = result.get("price") or price
            stop_loss_price = (
                entry_price * (1 - self.config["stop_loss_pct"])
                if side == "BUY"
                else entry_price * (1 + self.config["stop_loss_pct"])
            )

            position = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                "target_price": target_price,
                "stop_loss": round(stop_loss_price, 2),
                "confidence": confidence,
                "order_id": result.get("order_id"),
                "opened_at": datetime.utcnow().isoformat(),
                "status": "open",
            }
            self.open_positions[symbol] = position

            self._log_event("ORDER_FILLED", f"{side} {quantity} {symbol} @ ${entry_price:.2f}", position)
            logger.info(f"[auto-trader] Position opened: {symbol} {side} @ ${entry_price:.2f}")
            return position

        except Exception as e:
            self._log_event("ORDER_ERROR", f"{symbol}: {type(e).__name__}: {e}")
            logger.error(f"[auto-trader] Error placing order for {symbol}: {e}")
            return None

    async def run(self, get_predictions_func: Callable):
        """Main loop — checks predictions every check_interval seconds."""
        self.is_running = True
        self._log_event("ENGINE_START", "Auto trading engine started (disabled by default)")
        logger.info("[auto-trader] Engine started (disabled by default)")

        while self.is_running:
            try:
                if self.config["enabled"] and self.broker and self.broker.connected:
                    predictions = await get_predictions_func()
                    high_conf = [
                        p for p in predictions
                        if p.get("confidence", 0) >= self.config["confidence_threshold"]
                    ]
                    if high_conf:
                        self._log_event("SCAN", f"Found {len(high_conf)} high-confidence predictions")
                    for prediction in high_conf:
                        self.place_auto_order(prediction)
            except Exception as e:
                logger.error(f"[auto-trader] Loop error: {e}")
                self._log_event("ERROR", f"Loop error: {e}")

            await asyncio.sleep(self.check_interval)

        self.is_running = False
        self._log_event("ENGINE_STOP", "Auto trading engine stopped")

    def stop(self):
        self.is_running = False


# Singleton instance
auto_trader = AutoTradingEngine()
