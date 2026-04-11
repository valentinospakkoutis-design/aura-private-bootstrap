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
            "trail_pct": 2.0,              # trailing stop percentage
            "enabled": False,               # OFF by default
        }
        self.open_positions: Dict[str, dict] = {}
        self.closed_trades: List[dict] = []
        self.trade_log: List[dict] = []
        self.user_runtime: Dict[int, dict] = {}

    def _ensure_user_runtime(self, user_id: int) -> dict:
        if user_id not in self.user_runtime:
            self.user_runtime[user_id] = {
                "config": dict(self.config),
                "open_positions": {},
                "closed_trades": [],
                "trade_log": [],
                "total_auto_trades": 0,
                "last_run": None,
            }
        return self.user_runtime[user_id]

    def _load_user_context(self, user_id: int):
        ctx = self._ensure_user_runtime(user_id)
        self.config = dict(ctx["config"])
        self.open_positions = dict(ctx["open_positions"])
        self.closed_trades = list(ctx.get("closed_trades", []))
        self.trade_log = list(ctx["trade_log"])
        self.total_auto_trades = int(ctx["total_auto_trades"])
        self.last_run = ctx["last_run"]

    def _save_user_context(self, user_id: int):
        self.user_runtime[user_id] = {
            "config": dict(self.config),
            "open_positions": dict(self.open_positions),
            "closed_trades": list(self.closed_trades[-200:]),
            "trade_log": list(self.trade_log[-100:]),
            "total_auto_trades": int(self.total_auto_trades),
            "last_run": self.last_run,
        }

    def get_user_status(self, user_id: int) -> dict:
        ctx = self._ensure_user_runtime(user_id)
        return {
            "enabled": bool(ctx["config"].get("enabled", False)),
            "is_running": self.is_running,
            "config": ctx["config"],
            "open_positions_count": len(ctx["open_positions"]),
            "positions": list(ctx["open_positions"].values()),
            "closed_trades_count": len(ctx.get("closed_trades", [])),
            "total_auto_trades": int(ctx.get("total_auto_trades", 0)),
            "last_run": ctx.get("last_run"),
            "next_run_in_seconds": self.check_interval,
            "recent_log": list(ctx.get("trade_log", [])[-20:]),
        }

    def get_user_log(self, user_id: int, limit: int = 20) -> List[dict]:
        ctx = self._ensure_user_runtime(user_id)
        return list(ctx.get("trade_log", [])[-limit:])

    def get_user_positions(self, user_id: int) -> List[dict]:
        ctx = self._ensure_user_runtime(user_id)
        return list(ctx.get("open_positions", {}).values())

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

    def _calculate_position_size(self, price: float, confidence: float = 0.5, volatility: float = 0.3) -> float:
        """Calculate risk-adjusted quantity using the position sizing engine."""
        if price <= 0:
            return 0.0

        balance = self._get_available_balance()
        if balance <= 0:
            return 0.0

        try:
            from services.position_sizing import calculate_position_size, SizingInput
            exposure = sum(
                p.get("quantity", 0) * p.get("entry_price", 0)
                for p in self.open_positions.values()
            ) / balance if balance > 0 else 0

            result = calculate_position_size(SizingInput(
                account_balance=balance,
                signal_confidence=confidence,
                volatility=volatility,
                current_drawdown=0.0,  # TODO: track cumulative drawdown
                current_portfolio_exposure=min(1.0, exposure),
                price=price,
                user_risk_profile="moderate",
            ))

            # Respect the fixed order value cap from config
            max_notional = self.config["fixed_order_value_usd"]
            notional = min(result.recommended_notional, max_notional)
            quantity = notional / price if price > 0 else 0
            self._log_event("SIZING", f"Sized: ${notional:.2f} ({result.reasoning})")
            return round(quantity, 6)
        except Exception as e:
            # Fallback to fixed sizing
            logger.warning(f"[auto-trader] Position sizing failed, using fixed: {e}")
            position_value = self.config["fixed_order_value_usd"]
            if balance < position_value:
                return 0.0
            return round(position_value / price, 6)

    def _notify_user(self, user_id: Optional[int], title: str, body: str, data: Optional[dict] = None):
        try:
            if user_id is None:
                return
            from services.push_notifications import send_push_to_user_id
            send_push_to_user_id(int(user_id), title=title, body=body, data=data or {})
        except Exception:
            pass

    def _get_market_price(self, symbol: str) -> float:
        if not self.broker:
            return 0.0
        try:
            px = self.broker.get_symbol_price(symbol)
            return float(px or 0.0)
        except Exception:
            return 0.0

    def _estimate_equity_reference(self) -> float:
        balance = self._get_available_balance()
        exposure = 0.0
        for p in self.open_positions.values():
            qty = float(p.get("quantity") or 0.0)
            symbol = p.get("symbol")
            market_px = self._get_market_price(symbol) if symbol else 0.0
            if market_px <= 0:
                market_px = float(p.get("entry_price") or 0.0)
            exposure += qty * market_px
        total = balance + exposure
        return float(total if total > 0 else 10000.0)

    def _close_position(self, symbol: str, current_price: float, user_id: Optional[int], reason: str) -> Optional[dict]:
        position = self.open_positions.get(symbol)
        if not position or not self.broker or not self.broker.connected:
            return None

        side = "SELL" if position.get("side") == "BUY" else "BUY"
        quantity = float(position.get("quantity") or 0.0)
        if quantity <= 0:
            return None

        try:
            result = self.broker.place_live_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type="MARKET",
            )
            if "error" in result:
                self._log_event("CLOSE_FAILED", f"{symbol}: {result['error']}")
                return None

            exit_price = float(result.get("price") or current_price or 0.0)
            entry_price = float(position.get("entry_price") or 0.0)
            if position.get("side") == "BUY":
                pnl = (exit_price - entry_price) * quantity
            else:
                pnl = (entry_price - exit_price) * quantity

            closed_trade = {
                "symbol": symbol,
                "entry_side": position.get("side"),
                "exit_side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": round(pnl, 8),
                "reason": reason,
                "opened_at": position.get("opened_at"),
                "closed_at": datetime.utcnow().isoformat(),
                "order_id": result.get("order_id"),
            }
            self.closed_trades.append(closed_trade)
            self.open_positions.pop(symbol, None)

            self._log_event("POSITION_CLOSED", f"{symbol} closed ({reason}) PnL=${pnl:.2f}", closed_trade)
            self._notify_user(
                user_id,
                title="Position Closed",
                body=f"{symbol} closed by risk control ({reason}). PnL ${pnl:.2f}",
                data={"screen": "/auto-trading", "type": "position_closed", "symbol": symbol},
            )
            return closed_trade
        except Exception as e:
            self._log_event("CLOSE_ERROR", f"{symbol}: {type(e).__name__}: {e}")
            return None

    def _update_trailing_stops(self, user_id: Optional[int]):
        if not self.open_positions:
            return

        from services.trailing_stop import trailing_stop_service

        trail_pct = float(self.config.get("trail_pct", 2.0))
        for symbol, position in list(self.open_positions.items()):
            current_price = self._get_market_price(symbol)
            if current_price <= 0:
                continue

            new_stop, moved, move_dir = trailing_stop_service.update_stop(
                position,
                current_price=current_price,
                trail_pct=trail_pct,
            )
            if moved:
                position["trailing_stop"] = new_stop
                position["trailing_last_move"] = move_dir
                position["trailing_move_count"] = int(position.get("trailing_move_count") or 0) + 1
                self.open_positions[symbol] = position
                self._log_event("TRAILING_UPDATE", f"{symbol}: trailing stop moved to ${new_stop:.4f}")

            if trailing_stop_service.should_stop(position, current_price=current_price):
                self._close_position(symbol, current_price=current_price, user_id=user_id, reason="trailing_stop")

    def _check_circuit_breaker_pause(self, user_id: Optional[int]) -> bool:
        if user_id is None:
            return False
        from services.circuit_breaker import circuit_breaker_service
        state = circuit_breaker_service.get_state(int(user_id))
        if state.get("state") == "paused":
            self._log_event(
                "CIRCUIT_BREAKER_PAUSED",
                f"Auto trading paused: {state.get('reason')}",
                {
                    "resume_at": state.get("resume_at"),
                    "minutes_remaining": state.get("minutes_remaining"),
                },
            )
            return True
        return False

    def _evaluate_circuit_breaker(self, user_id: Optional[int]):
        if user_id is None:
            return
        from services.circuit_breaker import circuit_breaker_service

        result = circuit_breaker_service.evaluate_and_trip(
            int(user_id),
            closed_trades=self.closed_trades,
            equity_reference=self._estimate_equity_reference(),
        )
        if result.get("tripped"):
            reason = result.get("reason") or "Risk rule triggered"
            event = result.get("event") or {}
            self._log_event(
                "CIRCUIT_BREAKER_TRIPPED",
                reason,
                {
                    "rule_id": event.get("rule_id"),
                    "resume_at": event.get("resume_at"),
                },
            )
            self._notify_user(
                user_id,
                title="Circuit Breaker Activated",
                body=reason,
                data={"screen": "/auto-trading", "type": "circuit_breaker"},
            )

    def place_auto_order(self, prediction: dict, user_id: Optional[int] = None) -> Optional[dict]:
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
            try:
                from ai.trust_layer import verdict_from_auto_trader_skip
                verdict_from_auto_trader_skip(symbol, f"Confidence {confidence:.0%} < {self.config['confidence_threshold']:.0%}", confidence=confidence)
            except Exception:
                pass
            return None  # skip — confidence too low

        # ── Smart Score gate ─────────────────────────────────────
        from services.smart_score import smart_score_calculator
        score_result = smart_score_calculator.calculate_smart_score(symbol)
        smart_score = score_result.get("smart_score", 0)
        signals = score_result.get("signals", {})

        # Block trades during extreme fear
        fear_greed = signals.get("fear_greed", {}).get("score", 50)
        if fear_greed < 25:
            self._log_event("SKIP", f"{symbol}: extreme fear (F&G={fear_greed:.0f}), market too risky")
            try:
                from ai.trust_layer import verdict_from_auto_trader_skip
                verdict_from_auto_trader_skip(symbol, f"Extreme fear F&G={fear_greed:.0f}", confidence=confidence, fear_greed=fear_greed)
            except Exception:
                pass
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
            try:
                from ai.trust_layer import verdict_from_auto_trader_skip
                verdict_from_auto_trader_skip(symbol, f"Smart Score {smart_score:.0f} < {self.config['smart_score_threshold']}", confidence=confidence, smart_score=smart_score, fear_greed=fear_greed)
            except Exception:
                pass
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

        # ── Claude AI validation (only for high-confidence signals) ──
        claude_size_multiplier = 1.0
        if confidence >= 0.90:
            try:
                from services.claude_validator import validate_trade_signal
                ml_reasoning = (
                    f"Smart Score {smart_score:.0f}, F&G {fear_greed:.0f}, "
                    f"trend={prediction.get('trend_score', 0):+.2f}"
                )
                current_exposure = len(self.open_positions) / max(self.config["max_positions"], 1)
                validation = validate_trade_signal(
                    symbol=symbol,
                    action=side,
                    confidence=confidence,
                    current_price=price,
                    fear_greed=int(fear_greed),
                    portfolio_exposure=current_exposure,
                    reasoning=ml_reasoning,
                )
                logger.info(
                    f"[CLAUDE] {symbol} {side} -> {validation['decision']} | "
                    f"{validation.get('reasoning', '')[:80]}"
                )

                if validation["decision"] == "skip":
                    self._log_event("SKIP", f"{symbol}: Claude rejected — {validation.get('reasoning', '')[:100]}")
                    try:
                        from services.feed_engine import emit
                        emit(
                            event_type="trade_signal",
                            title=f"Claude: SKIP {symbol}",
                            body=validation.get("reasoning", "Signal rejected by AI validator"),
                            symbol=symbol,
                            severity="warning",
                            metadata={"source": "claude_validator", "decision": "skip"},
                        )
                    except Exception:
                        pass
                    return None

                if validation["decision"] == "reduce":
                    claude_size_multiplier = max(0.25, min(1.0, validation.get("size_multiplier", 0.5)))
                    self._log_event("REDUCE", f"{symbol}: Claude reduced size to {claude_size_multiplier:.0%}")

                try:
                    from services.feed_engine import emit
                    emit(
                        event_type="trade_signal",
                        title=f"Claude: {validation['decision'].upper()} {symbol}",
                        body=validation.get("reasoning", ""),
                        symbol=symbol,
                        severity="warning" if validation.get("risk_level") == "high" else "info",
                        metadata={"source": "claude_validator", "decision": validation["decision"]},
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"[Claude] Integration error (non-fatal): {e}")

        vol = abs(prediction.get("trend_score", 0.3)) if "trend_score" in prediction else 0.3
        quantity = self._calculate_position_size(price, confidence=confidence, volatility=vol)
        quantity *= claude_size_multiplier

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
                "trailing_stop": None,
                "trailing_last_move": "none",
                "trailing_move_count": 0,
                "confidence": confidence,
                "smart_score": smart_score,
                "smart_score_signals": signals,
                "order_id": result.get("order_id"),
                "opened_at": datetime.utcnow().isoformat(),
                "status": "open",
            }
            try:
                from services.trailing_stop import trailing_stop_service
                position["trailing_stop"] = trailing_stop_service.initialize_stop(
                    side=side,
                    entry_price=float(entry_price),
                    trail_pct=float(self.config.get("trail_pct", 2.0)),
                )
            except Exception:
                position["trailing_stop"] = round(stop_loss_price, 2)

            self.open_positions[symbol] = position

            self._log_event("ORDER_FILLED", f"{side} {quantity} {symbol} @ ${entry_price:.2f}", position)
            logger.info(f"[auto-trader] Position opened: {symbol} {side} @ ${entry_price:.2f}")

            # Push notification
            try:
                from services.push_notifications import notify_auto_trade
                if user_id is None:
                    notify_auto_trade(symbol, side, entry_price, confidence)
                else:
                    self._notify_user(
                        user_id,
                        title="Auto Trade",
                        body=f"AURA {side.lower()} {symbol} @ ${entry_price:,.2f} (confidence: {confidence:.0%})",
                        data={"screen": "/auto-trading", "type": "auto_trade", "symbol": symbol},
                    )
            except Exception:
                pass

            # AI feed event
            try:
                from services.feed_engine import emit_auto_trade
                emit_auto_trade(symbol, side, quantity, entry_price)
            except Exception:
                pass

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

    async def run_per_user(
        self,
        get_predictions_func: Callable,
        get_active_users_func: Callable,
        get_broker_for_user_func: Callable,
        get_user_config_func: Optional[Callable] = None,
    ):
        """Run isolated auto-trading cycles for all users with enabled autopilot."""
        self.is_running = True
        self._log_event("ENGINE_START", "Per-user auto trading engine started")
        logger.info("[auto-trader] Per-user engine started")

        while self.is_running:
            try:
                active_user_ids = get_active_users_func() or []

                for user_id in active_user_ids:
                    try:
                        uid = int(user_id)
                    except Exception:
                        continue

                    self._load_user_context(uid)

                    # Refresh config from persistent user settings if provided.
                    if get_user_config_func:
                        cfg = get_user_config_func(uid) or {}
                        self.config.update(cfg)

                    broker = get_broker_for_user_func(uid)
                    if not broker:
                        self._log_event("SKIP", f"user={uid}: no connected broker")
                        self._save_user_context(uid)
                        continue

                    self.broker = broker
                    self.last_run = datetime.utcnow().isoformat()

                    if not self.config.get("enabled", False):
                        self._save_user_context(uid)
                        continue

                    # Always maintain trailing stops on each scan before opening new positions.
                    self._update_trailing_stops(uid)
                    self._evaluate_circuit_breaker(uid)

                    # Circuit breaker pause prevents opening new auto-trades.
                    if self._check_circuit_breaker_pause(uid):
                        self._save_user_context(uid)
                        continue

                    predictions = await get_predictions_func(uid)
                    high_conf = [
                        p for p in predictions
                        if p.get("confidence", 0) >= self.config["confidence_threshold"]
                    ]

                    for prediction in high_conf:
                        result = self.place_auto_order(prediction, user_id=uid)
                        if result:
                            self.total_auto_trades += 1
                            self._evaluate_circuit_breaker(uid)

                    self._save_user_context(uid)

            except Exception as e:
                logger.error(f"[auto-trader] Per-user loop error: {e}")
                self._log_event("ERROR", f"Per-user loop error: {e}")

            await asyncio.sleep(self.check_interval)

        self.is_running = False
        self._log_event("ENGINE_STOP", "Per-user auto trading engine stopped")

    def stop(self):
        self.is_running = False


# Singleton instance
auto_trader = AutoTradingEngine()
