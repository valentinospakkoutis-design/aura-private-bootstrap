"""
Live Trading Service
Handles real order execution with risk management and safety checks
"""

from typing import Dict, Optional, List
from datetime import datetime
from decimal import Decimal


class LiveTradingService:
    """
    Service for managing live trading
    Includes risk management, position sizing, and safety checks
    """
    
    def __init__(self):
        self.trading_mode = "paper"  # "paper" or "live"
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
        current_positions: List[Dict]
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
        validation_result: Optional[Dict] = None
    ) -> Dict:
        """
        Execute live order (real money)
        This would call the actual broker API
        """
        if self.trading_mode != "live":
            return {
                "error": "Trading mode is not 'live'. Switch to live mode first.",
                "current_mode": self.trading_mode
            }
        
        if validation_result and not validation_result.get("valid", False):
            return {
                "error": "Order validation failed",
                "errors": validation_result.get("errors", [])
            }
        
        # In production, this would call the actual broker API
        # For now, return simulated execution
        order_id = f"LIVE_{int(datetime.now().timestamp() * 1000)}"
        
        # Update daily stats
        self.daily_stats["total_trades"] += 1
        
        return {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "status": "FILLED",
            "executed_at": datetime.now().isoformat(),
            "mode": "live",
            "warning": "This is a simulated execution. In production, this would execute real trades.",
            "timestamp": datetime.now().isoformat()
        }
    
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

