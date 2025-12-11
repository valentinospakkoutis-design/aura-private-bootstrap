"""
Paper Trading Service
Manages simulated trades, portfolio, and P/L tracking
"""

from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal


class PaperTradingService:
    """Service for managing paper trading simulation"""
    
    def __init__(self):
        self.orders: List[Dict] = []
        self.portfolio: Dict[str, Dict] = {}  # symbol -> {quantity, avg_price, total_cost}
        self.initial_balance: float = 10000.0  # Starting balance
        self.current_balance: float = 10000.0
        self.cash: float = 10000.0
        self.trade_history: List[Dict] = []
    
    def place_order(self, order: Dict) -> Dict:
        """
        Place a paper trading order
        
        Args:
            order: Order dict with symbol, side, quantity, price
            
        Returns:
            Executed order with order_id
        """
        symbol = order['symbol']
        side = order['side'].upper()
        quantity = float(order['quantity'])
        price = float(order['price'])
        order_type = order.get('order_type', 'MARKET')
        
        # Generate order ID
        order_id = f"PAPER_{int(datetime.now().timestamp() * 1000)}"
        
        total_cost = quantity * price
        
        if side == 'BUY':
            # Check if we have enough cash
            if total_cost > self.cash:
                return {
                    "error": "Insufficient funds",
                    "required": total_cost,
                    "available": self.cash
                }
            
            # Execute buy order
            self.cash -= total_cost
            
            # Update portfolio
            if symbol not in self.portfolio:
                self.portfolio[symbol] = {
                    "quantity": 0,
                    "avg_price": 0,
                    "total_cost": 0
                }
            
            # Calculate new average price
            old_quantity = self.portfolio[symbol]["quantity"]
            old_total_cost = self.portfolio[symbol]["total_cost"]
            
            new_quantity = old_quantity + quantity
            new_total_cost = old_total_cost + total_cost
            new_avg_price = new_total_cost / new_quantity if new_quantity > 0 else 0
            
            self.portfolio[symbol]["quantity"] = new_quantity
            self.portfolio[symbol]["avg_price"] = new_avg_price
            self.portfolio[symbol]["total_cost"] = new_total_cost
            
        elif side == 'SELL':
            # Check if we have enough quantity
            if symbol not in self.portfolio or self.portfolio[symbol]["quantity"] < quantity:
                return {
                    "error": "Insufficient quantity",
                    "required": quantity,
                    "available": self.portfolio.get(symbol, {}).get("quantity", 0)
                }
            
            # Execute sell order
            self.cash += total_cost
            
            # Update portfolio
            self.portfolio[symbol]["quantity"] -= quantity
            if self.portfolio[symbol]["quantity"] == 0:
                # Calculate P/L for this position
                avg_price = self.portfolio[symbol]["avg_price"]
                pnl = (price - avg_price) * quantity
                
                # Remove from portfolio
                del self.portfolio[symbol]
            else:
                # Partial sell - calculate P/L for sold portion
                avg_price = self.portfolio[symbol]["avg_price"]
                pnl = (price - avg_price) * quantity
                # Update total cost
                self.portfolio[symbol]["total_cost"] -= (avg_price * quantity)
        
        # Create order record
        executed_order = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "price": price,
            "total_cost": total_cost,
            "status": "FILLED",
            "executed_at": datetime.now().isoformat(),
            "paper_trading": True
        }
        
        # Add to history
        self.orders.append(executed_order)
        self.trade_history.append(executed_order)
        
        # Update current balance
        self._update_balance()
        
        return executed_order
    
    def _update_balance(self):
        """Update current balance based on portfolio value"""
        portfolio_value = 0.0
        
        # Calculate portfolio value (would need current prices in real implementation)
        # For now, use average price as approximation
        for symbol, position in self.portfolio.items():
            portfolio_value += position["quantity"] * position["avg_price"]
        
        self.current_balance = self.cash + portfolio_value
    
    def get_portfolio(self, current_prices: Dict[str, float] = None) -> Dict:
        """
        Get current portfolio with P/L
        
        Args:
            current_prices: Dict of symbol -> current price (optional)
            
        Returns:
            Portfolio information
        """
        positions = []
        total_value = self.cash
        total_pnl = 0.0
        
        for symbol, position in self.portfolio.items():
            quantity = position["quantity"]
            avg_price = position["avg_price"]
            current_price = current_prices.get(symbol, avg_price) if current_prices else avg_price
            
            position_value = quantity * current_price
            cost_basis = quantity * avg_price
            pnl = position_value - cost_basis
            pnl_percent = (pnl / cost_basis * 100) if cost_basis > 0 else 0
            
            positions.append({
                "symbol": symbol,
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": current_price,
                "value": position_value,
                "cost_basis": cost_basis,
                "pnl": pnl,
                "pnl_percent": pnl_percent
            })
            
            total_value += position_value
            total_pnl += pnl
        
        return {
            "cash": self.cash,
            "portfolio_value": total_value - self.cash,
            "total_value": total_value,
            "initial_balance": self.initial_balance,
            "total_pnl": total_pnl,
            "total_pnl_percent": ((total_value - self.initial_balance) / self.initial_balance * 100) if self.initial_balance > 0 else 0,
            "positions": positions,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get trade history"""
        return self.trade_history[-limit:] if limit else self.trade_history
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        total_trades = len(self.trade_history)
        buy_trades = [t for t in self.trade_history if t['side'] == 'BUY']
        sell_trades = [t for t in self.trade_history if t['side'] == 'SELL']
        
        portfolio = self.get_portfolio()
        
        return {
            "total_trades": total_trades,
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "active_positions": len(self.portfolio),
            "current_balance": portfolio["total_value"],
            "total_pnl": portfolio["total_pnl"],
            "total_pnl_percent": portfolio["total_pnl_percent"],
            "timestamp": datetime.now().isoformat()
        }
    
    def reset(self):
        """Reset paper trading account"""
        self.orders = []
        self.portfolio = {}
        self.cash = self.initial_balance
        self.current_balance = self.initial_balance
        self.trade_history = []


# Global instance
paper_trading_service = PaperTradingService()

