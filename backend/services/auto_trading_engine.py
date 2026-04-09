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

# Only USDC crypto pairs are allowed for auto trading.
# Metals (XAU, XAG, XPT, XPD) are excluded — no USDC pairs on Binance for Cyprus.
# Removed: MANAUSDC, MATICUSDC, FTMUSDC, EOSUSDC (delisted from Binance)
# MATIC rebranded to POL
ALLOWED_AUTO_TRADE_SYMBOLS = {
    "BTCUSDC", "ETHUSDC", "BNBUSDC", "ADAUSDC", "SOLUSDC",
    "XRPUSDC", "DOTUSDC", "POLUSDC", "LINKUSDC", "AVAXUSDC",
    "SHIBUSDC", "DOGEUSDC", "TRXUSDC", "LTCUSDC", "BCHUSDC",
    "ETCUSDC", "XLMUSDC", "ALGOUSDC", "ATOMUSDC", "NEARUSDC",
    "ICPUSDC", "FILUSDC", "AAVEUSDC",
    "UNIUSDC", "SANDUSDC", "AXSUSDC", "THETAUSDC",
}


class AutoTradingEngine:
    def __init__(self):
        self.is_running = False
        self.broker = None  # BinanceAPI instance
        self.check_interval = 60  # check every 60 seconds
        self.last_run = None
        self.total_auto_trades = 0
        self.config = {
            "confidence_threshold": 0.90,   # only trade >= 90% confidence
            "fixed_order_value_usd": 10.0,  # fixed $10 USDC per trade
            "stop_loss_pct": 0.03,          # 3% stop loss
            "take_profit_pct": 0.05,        # 5% take profit
            "max_positions": 3,             # max 3 concurrent positions
            "max_order_value_usd": 100.0,   # hard safety limit per order
            "smart_score_threshold": 75,    # only trade when Smart Score > 75
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
        from services.live_trading import live_trading_service
        return {
            "enabled": self.config["enabled"],
            "is_running": self.is_running,
            "mode": live_trading_service.trading_mode,
            "config": self.config,
            "open_positions_count": len(self.open_positions),
            "positions": list(self.open_positions.values()),
            "total_auto_trades": self.total_auto_trades,
            "last_run": self.last_run,
            "next_run_in_seconds": self.check_interval,
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
        """Get available USDC balance"""
        try:
            account = self.broker.get_account_balance()
            if isinstance(account, dict) and "balances" in account:
                for balance in account["balances"]:
                    if balance["asset"] == "USDC":
                        return float(balance["free"])
            else:
                return account.get("available_balance", 0)
        except Exception as e:
            logger.error(f"[auto-trader] Failed to get balance: {e}")
            return 0.0

    def get_trading_symbol(self, asset_symbol: str) -> str:
        """Ensure symbol uses USDC pair."""
        if asset_symbol.endswith("USDT"):
            return asset_symbol[:-4] + "USDC"
        return asset_symbol

    def _calculate_position_size(self, price: float) -> float:
        """Calculate quantity for a fixed $10 USDC order."""
        if price <= 0:
            return 0.0

        position_value = self.config["fixed_order_value_usd"]

        # Verify we have enough balance
        balance = self._get_available_balance()
        if balance < position_value:
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

        # Only trade allowed USDC crypto pairs
        trading_symbol = self.get_trading_symbol(symbol)
        if trading_symbol not in ALLOWED_AUTO_TRADE_SYMBOLS:
            self._log_event("SKIP", f"{symbol}: not in allowed auto-trade symbols")
            return None
        symbol = trading_symbol

        if not self.broker or not self.broker.connected:
            self._log_event("SKIP", f"{symbol}: broker not connected")
            return None

        if confidence < self.config["confidence_threshold"]:
            return None  # silent skip — most predictions won't pass

        # ── Smart Score gate ─────────────────────────────────────
        from services.smart_score import smart_score_calculator
        score_result = smart_score_calculator.calculate_smart_score(symbol)
        smart_score = score_result.get("smart_score", 0)
        signals = score_result.get("signals", {})

        # Block trades during extreme fear
        fear_greed = signals.get("fear_greed", {}).get("score", 50)
        if fear_greed < 25:
            self._log_event("SKIP", f"{symbol}: extreme fear (F&G={fear_greed:.0f}), market too risky")
            return None

        if smart_score < self.config["smart_score_threshold"]:
            self._log_event("SKIP",
                f"{symbol}: Smart Score {smart_score:.1f} < {self.config['smart_score_threshold']} "
                f"[news={signals.get('news_sentiment',{}).get('score',0):.0f} "
                f"F&G={fear_greed:.0f} "
                f"RSI={signals.get('rsi',{}).get('score',0):.0f} "
                f"vol={signals.get('volume',{}).get('score',0):.0f} "
                f"MTF={signals.get('multi_timeframe',{}).get('score',0):.0f} "
                f"pred={signals.get('prediction',{}).get('score',0):.0f}]")
            return None

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

        # ── Kill switch check ────────────────────────────────────
        import os
        if os.getenv("ALLOW_LIVE_TRADING", "false").lower() not in ("true", "1", "yes"):
            self._log_event("BLOCKED", f"{symbol}: ALLOW_LIVE_TRADING is disabled")
            return None

        # ── Place order ──────────────────────────────────────────
        try:
            import uuid
            client_order_id = f"AURA_AUTO_{uuid.uuid4().hex[:16]}"

            self._log_event("ORDER_ATTEMPT",
                f"{side} {quantity} {symbol} @ ~${price:.2f} "
                f"(confidence {confidence:.0%}, Smart Score {smart_score:.1f}, coid={client_order_id})")
            logger.info(f"[auto-trader] Placing {side} {symbol} qty={quantity} "
                f"confidence={confidence:.0%} smart_score={smart_score:.1f} coid={client_order_id}")

            result = self.broker.place_live_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type="MARKET",
                client_order_id=client_order_id,
            )

            # Persistent audit log
            try:
                from main import _log_live_order_audit
                _log_live_order_audit(
                    source="auto_trader", symbol=symbol, side=side,
                    quantity=quantity, price=price, client_order_id=client_order_id,
                    status="filled" if "error" not in result else "failed",
                    broker_order_id=result.get("order_id"),
                    error_message=result.get("error"),
                )
            except Exception:
                pass  # Audit failure must not block trading

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
                "smart_score": smart_score,
                "smart_score_signals": signals,
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
        from services.smart_score import smart_score_calculator
        self.is_running = True
        self._log_event("ENGINE_START", "Auto trading engine started (disabled by default)")
        logger.info("[auto-trader] Engine started (disabled by default)")

        while self.is_running:
            try:
                if self.config["enabled"] and self.broker and self.broker.connected:
                    self.last_run = datetime.utcnow().isoformat()
                    predictions = await get_predictions_func()
                    high_conf = [
                        p for p in predictions
                        if p.get("confidence", 0) >= self.config["confidence_threshold"]
                    ]
                    if high_conf:
                        score_previews = []
                        for p in high_conf[:5]:
                            sym = self.get_trading_symbol(p.get("symbol", ""))
                            ss = smart_score_calculator.calculate_smart_score(sym)
                            score_previews.append(f"{sym}={ss['smart_score']:.0f}")
                        self._log_event("SCAN",
                            f"Found {len(high_conf)} high-confidence predictions | "
                            f"Smart Scores: {', '.join(score_previews)}")
                    for prediction in high_conf:
                        result = self.place_auto_order(prediction)
                        if result:
                            self.total_auto_trades += 1
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
