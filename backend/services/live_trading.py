"""
Live Trading Service
Handles real order execution with risk management and safety checks
"""

import logging
import os
from typing import Any, Dict, Optional, List
from datetime import datetime

from fastapi import HTTPException

from ops.kill_switch import kill_switch_manager
from ops.observability import runtime_monitor
from services.execution import (
    ExecutionConfigurationError,
    ExecutionRequest,
    RealExecutionEngine,
    ValidationContext,
    build_broker_client,
    validate_execution_provider_or_raise,
)
from services.risk_governor import risk_governor_service
from services.execution.startup_checks import startup_checker

logger = logging.getLogger(__name__)


class LiveTradingService:
    """
    Service for managing live trading
    Includes risk management, position sizing, and safety checks
    """
    
    def __init__(self):
        self.trading_mode = "paper"  # "paper" or "live"
        self.kill_switch_active = False
        self.risk_settings = {
            "max_position_size_percent": 10.0,  # Max 10% of portfolio per position
            "max_daily_loss_percent": 5.0,  # Max 5% daily loss
            "stop_loss_percent": 2.0,  # 2% stop loss
            "take_profit_percent": 5.0,  # 5% take profit
            "max_open_positions": 5,  # Max 5 open positions
            "require_confirmation": True  # Require user confirmation
        }
        self.daily_stats = {
            "date": datetime.now().date().isoformat(),
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "daily_loss": 0.0
        }
        self.execution_engine = RealExecutionEngine()

    @staticmethod
    def _is_truthy(value: str) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def is_kill_switch_active(self) -> bool:
        if self._is_truthy(os.getenv("AURA_KILL_SWITCH_ACTIVE", "false")):
            return True
        status = kill_switch_manager.status()
        return bool(status.get("global_active"))

    def execution_provider(self) -> str:
        return os.getenv("EXECUTION_PROVIDER", "stub").strip().lower()

    def allow_live_trading(self) -> bool:
        return self._is_truthy(os.getenv("ALLOW_LIVE_TRADING", "false"))

    def validate_execution_configuration(self) -> None:
        validate_execution_provider_or_raise(
            provider=self.execution_provider(),
            trading_mode=os.getenv("TRADING_MODE", self.trading_mode),
            allow_live_trading=self.allow_live_trading(),
        )

    def is_live_startup_required(self) -> bool:
        return startup_checker.is_live_mode()

    def validate_live_startup_preconditions(self) -> None:
        provider = self.execution_provider()
        self.validate_execution_configuration()
        startup_checker.validate_live_requirements(provider=provider)

    def set_kill_switch(
        self,
        active: bool,
        *,
        actor: str = "system",
        scope: str = "global",
        value: Optional[str] = None,
        reason: Optional[str] = None,
        emergency: bool = False,
        cancel_open_orders: bool = False,
    ) -> Dict:
        if active:
            return kill_switch_manager.activate(
                actor=actor,
                scope=scope,
                value=value,
                reason=reason,
                emergency=emergency,
                cancel_open_orders=cancel_open_orders,
            )
        return kill_switch_manager.deactivate(actor=actor, scope=scope, value=value, reason=reason)

    def get_kill_switch_status(self) -> Dict:
        return kill_switch_manager.status()

    @staticmethod
    def _extract_portfolio_value(balance: Dict[str, Any]) -> float:
        if not isinstance(balance, dict):
            return 0.0
        for field in ("total_balance", "equity", "portfolio_value", "balance"):
            value = balance.get(field)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return 0.0

    @staticmethod
    def _allowed_symbols_from_broker(adapter: Any) -> List[str]:
        if hasattr(adapter, "get_supported_symbols"):
            try:
                symbols = adapter.get_supported_symbols()
                if isinstance(symbols, list):
                    return [str(item).upper() for item in symbols]
            except Exception:
                return []

        configured = os.getenv("ALLOWED_LIVE_SYMBOLS", "")
        if not configured.strip():
            return []
        return [item.strip().upper() for item in configured.split(",") if item.strip()]
    
    def set_trading_mode(self, mode: str) -> Dict:
        """Set trading mode (paper or live)"""
        if mode not in ["paper", "live"]:
            return {"error": "Invalid mode. Must be 'paper' or 'live'"}
        
        self.trading_mode = mode
        return {
            "status": "success",
            "mode": mode,
            "message": f"Trading mode set to {mode}",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_trading_mode(self) -> Dict:
        """Get current trading mode"""
        return {
            "mode": self.trading_mode,
            "is_live": self.trading_mode == "live",
            "risk_settings": self.risk_settings,
            "daily_stats": self.daily_stats,
            "timestamp": datetime.now().isoformat()
        }
    
    def update_risk_settings(self, settings: Dict) -> Dict:
        """Update risk management settings"""
        for key, value in settings.items():
            if key in self.risk_settings:
                self.risk_settings[key] = value
        
        return {
            "status": "updated",
            "risk_settings": self.risk_settings,
            "timestamp": datetime.now().isoformat()
        }
    
    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        portfolio_value: float,
        current_positions: List[Dict],
        stop_loss_price: Optional[float] = None,
    ) -> Dict:
        """
        Validate order before execution
        Checks risk limits, position sizing, etc.
        """
        errors = []
        warnings = []
        
        # Check position size
        order_value = quantity * price
        position_size_percent = (order_value / portfolio_value * 100) if portfolio_value > 0 else 0
        
        if position_size_percent > self.risk_settings["max_position_size_percent"]:
            errors.append(
                f"Position size ({position_size_percent:.2f}%) exceeds maximum "
                f"({self.risk_settings['max_position_size_percent']}%)"
            )
        
        # Check daily loss limit
        if self.daily_stats["daily_loss"] < -abs(self.risk_settings["max_daily_loss_percent"] * portfolio_value / 100):
            errors.append("Daily loss limit reached. Trading paused.")
        
        # Check max open positions
        if len(current_positions) >= self.risk_settings["max_open_positions"]:
            errors.append(
                f"Maximum open positions ({self.risk_settings['max_open_positions']}) reached"
            )
        
        # Check if already have position in this symbol
        existing_position = next(
            (p for p in current_positions if p.get("symbol") == symbol),
            None
        )
        if existing_position and side == "BUY":
            warnings.append(f"Already have position in {symbol}")
        
        # Warnings for large orders
        if position_size_percent > 5.0:
            warnings.append("Large position size. Consider reducing.")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "position_size_percent": position_size_percent,
            "order_value": order_value,
            "portfolio_value": portfolio_value,
            "stop_loss_price": stop_loss_price,
            "requires_confirmation": self.risk_settings["require_confirmation"] and len(warnings) > 0
        }
    
    def calculate_position_size(
        self,
        symbol: str,
        side: str,
        price: float,
        portfolio_value: float,
        risk_percent: Optional[float] = None
    ) -> Dict:
        """
        Calculate optimal position size based on risk management
        """
        if risk_percent is None:
            risk_percent = self.risk_settings["max_position_size_percent"]
        
        max_position_value = portfolio_value * (risk_percent / 100)
        max_quantity = max_position_value / price
        
        # Apply stop loss calculation
        stop_loss_price = price * (1 - self.risk_settings["stop_loss_percent"] / 100) if side == "BUY" else price * (1 + self.risk_settings["stop_loss_percent"] / 100)
        risk_per_trade = abs(price - stop_loss_price) * max_quantity
        
        return {
            "recommended_quantity": max_quantity,
            "max_position_value": max_position_value,
            "risk_per_trade": risk_per_trade,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": price * (1 + self.risk_settings["take_profit_percent"] / 100) if side == "BUY" else price * (1 - self.risk_settings["take_profit_percent"] / 100),
            "risk_percent": risk_percent
        }
    
    def execute_live_order(
        self,
        broker: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        validation_result: Optional[Dict] = None,
        idempotency_key: Optional[str] = None,
        user_email: Optional[str] = None,
        user_roles: Optional[List[str]] = None,
        broker_adapter: Optional[Any] = None,
        price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        idempotency_reserved: bool = False,
    ) -> Dict:
        """
        Execute live order (real money)
        This would call the actual broker API
        """
        if validation_result is None:
            return {
                "error": "Order validation is required before execution.",
            }

        if not validation_result.get("valid", False):
            runtime_monitor.record_validation_failure(symbol=symbol)
            return {
                "error": "Order validation failed",
                "errors": validation_result.get("errors", [])
            }

        if not idempotency_key:
            return {"error": "Idempotency key is required for live execution."}
        if not user_email:
            return {"error": "Authenticated user context required for live execution."}
        if broker_adapter is None:
            return {"error": "Broker adapter is required for live execution."}
        if price is None:
            return {"error": "Explicit price is required for live execution."}

        try:
            can_execute, block_reason = risk_governor_service.can_execute(mode="live", symbol=symbol)
            if not can_execute:
                return {
                    "error": "Risk governor blocked new execution",
                    "error_code": block_reason or "RISK_GOVERNOR_BLOCK",
                    "status_code": 503,
                    "details": {"error": block_reason or "RISK_GOVERNOR_BLOCK"},
                }

            strategy = None
            if isinstance(validation_result, dict):
                strategy_value = validation_result.get("strategy")
                strategy = str(strategy_value) if strategy_value else None

            blocked, blocked_reason = kill_switch_manager.is_blocked(symbol=symbol, strategy=strategy)
            if blocked:
                return {
                    "error": "Kill switch is active for this execution scope",
                    "error_code": blocked_reason,
                    "status_code": 503,
                    "details": {"error": blocked_reason},
                }

            provider = self.execution_provider()
            live_requested = self.trading_mode == "live"
            validate_execution_provider_or_raise(
                provider=provider,
                trading_mode=self.trading_mode,
                allow_live_trading=self.allow_live_trading() or live_requested,
            )

            broker_client = build_broker_client(
                provider=provider,
                broker_name=broker,
                adapter=broker_adapter,
                trading_mode=self.trading_mode,
                allow_live_trading=self.allow_live_trading() or live_requested,
            )
            balance = broker_client.get_balance()
            portfolio_value = self._extract_portfolio_value(balance)

            execution_request = ExecutionRequest(
                broker=broker,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=float(price),
                stop_loss_price=stop_loss_price,
                idempotency_key=idempotency_key,
                user_email=user_email,
            )

            context = ValidationContext(
                user_roles=user_roles or [],
                allowed_symbols=self._allowed_symbols_from_broker(broker_adapter),
                portfolio_value=portfolio_value,
                max_position_size_percent=float(self.risk_settings["max_position_size_percent"]),
                max_daily_loss_percent=float(self.risk_settings["max_daily_loss_percent"]),
                current_daily_loss=float(self.daily_stats.get("daily_loss", 0.0)),
                stop_loss_required=bool(self.risk_settings.get("require_confirmation", False)),
                trading_mode=self.trading_mode,
                env_trading_mode=os.getenv("TRADING_MODE", self.trading_mode),
                allow_live_trading=self.allow_live_trading(),
                kill_switch_active=self.is_kill_switch_active(),
                idempotency_reserved=idempotency_reserved,
            )

            result = self.execution_engine.execute_order(
                request=execution_request,
                context=context,
                broker_client=broker_client,
            )
            self.daily_stats["total_trades"] += 1
            result["mode"] = "live"
            result["timestamp"] = datetime.now().isoformat()

            latest_balance = broker_client.get_balance()
            latest_equity = self._extract_portfolio_value(latest_balance)
            try:
                risk_governor_service.update_pnl(
                    mode="live",
                    equity=latest_equity,
                    realized_delta=0.0,
                    unrealized_pnl=0.0,
                    source="live_execution_service",
                    symbol=symbol,
                    strategy=strategy,
                )
            except Exception as risk_error:
                logger.error("RISK_GOVERNOR_UPDATE_FAILED mode=live symbol=%s error=%s", symbol, risk_error)
                runtime_monitor.log_event(
                    event="risk_governor_update_failed",
                    level="error",
                    mode="live",
                    symbol=symbol,
                )

            runtime_monitor.record_order_submitted(
                order_id=result.get("internal_order_id", "unknown"),
                symbol=symbol,
                latency_ms=0.0,
            )
            return result
        except ExecutionConfigurationError as exc:
            return {
                "error": str(exc),
                "error_code": "EXECUTION_PROVIDER_BLOCKED",
                "status_code": 503,
                "details": {"error": "EXECUTION_PROVIDER_BLOCKED", "message": str(exc)},
            }
        except HTTPException as exc:
            runtime_monitor.record_order_failed(symbol=symbol, error_type="HTTPException", latency_ms=0.0)
            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            return {
                "error": detail.get("message", "Live execution rejected"),
                "error_code": detail.get("error", "LIVE_EXECUTION_REJECTED"),
                "status_code": exc.status_code,
                "details": detail,
            }
        except Exception as exc:
            logger.exception("Unexpected live execution failure")
            runtime_monitor.record_order_failed(symbol=symbol, error_type=type(exc).__name__, latency_ms=0.0)
            return {
                "error": "Unexpected live execution failure",
                "error_code": "LIVE_EXECUTION_INTERNAL_ERROR",
                "status_code": 500,
                "details": {"message": str(exc)},
            }

    def reconcile_live_orders(self, broker_adapters: Dict[str, Any], limit: int = 100) -> Dict:
        def _resolver(broker_name: str):
            adapter = broker_adapters.get(broker_name.lower())
            if adapter is None:
                return None
            provider = self.execution_provider()
            return build_broker_client(
                provider=provider,
                broker_name=broker_name,
                adapter=adapter,
                trading_mode=self.trading_mode,
                allow_live_trading=self.allow_live_trading() or self.trading_mode == "live",
            )

        result = self.execution_engine.reconcile_once(
            broker_client_resolver=_resolver,
            limit=limit,
        )
        runtime_monitor.record_reconciliation_mismatch(count=int(result.get("flagged") or 0))
        return result
    
    def get_risk_summary(self, portfolio_value: float) -> Dict:
        """Get risk management summary"""
        return {
            "trading_mode": self.trading_mode,
            "risk_settings": self.risk_settings,
            "daily_stats": self.daily_stats,
            "portfolio_value": portfolio_value,
            "max_position_value": portfolio_value * (self.risk_settings["max_position_size_percent"] / 100),
            "max_daily_loss": portfolio_value * (self.risk_settings["max_daily_loss_percent"] / 100),
            "available_risk": abs(self.daily_stats["daily_loss"]) < abs(portfolio_value * (self.risk_settings["max_daily_loss_percent"] / 100)),
            "timestamp": datetime.now().isoformat()
        }


# Global instance
live_trading_service = LiveTradingService()

