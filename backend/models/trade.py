"""
Trade Model for Paper Trading
Stores and manages paper trading orders and positions
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class Trade(BaseModel):
    """Trade model"""
    trade_id: str
    broker: str
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    price: float
    order_type: str
    status: str  # FILLED, PENDING, CANCELLED
    timestamp: str
    paper_trading: bool = True


class Position(BaseModel):
    """Position model"""
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    total_cost: float


class Portfolio(BaseModel):
    """Portfolio model"""
    total_balance: float
    available_balance: float
    locked_balance: float
    positions: List[Position]
    total_pnl: float
    total_trades: int
    win_rate: float


# In-memory storage (in production, use database)
trades_storage: List[Dict] = []
positions_storage: Dict[str, Dict] = {}  # symbol -> position
portfolio_balance = 10000.0  # Starting balance for paper trading


def add_trade(trade: Trade) -> Dict:
    """Add trade to storage"""
    trade_dict = trade.dict()
    trades_storage.append(trade_dict)
    
    # Update position
    update_position(trade)
    
    return trade_dict


def update_position(trade: Trade):
    """Update position based on trade"""
    symbol = trade.symbol
    current_price = trade.price
    
    if symbol not in positions_storage:
        if trade.side == "BUY":
            positions_storage[symbol] = {
                "symbol": symbol,
                "quantity": trade.quantity,
                "avg_price": trade.price,
                "total_cost": trade.quantity * trade.price,
                "realized_pnl": 0.0
            }
    else:
        position = positions_storage[symbol]
        
        if trade.side == "BUY":
            # Add to position
            total_cost = position["total_cost"] + (trade.quantity * trade.price)
            total_quantity = position["quantity"] + trade.quantity
            position["avg_price"] = total_cost / total_quantity
            position["quantity"] = total_quantity
            position["total_cost"] = total_cost
        elif trade.side == "SELL":
            # Reduce position
            if position["quantity"] >= trade.quantity:
                # Calculate realized P/L
                pnl = (trade.price - position["avg_price"]) * trade.quantity
                position["realized_pnl"] += pnl
                position["quantity"] -= trade.quantity
                position["total_cost"] = position["avg_price"] * position["quantity"]
                
                # Remove if position is closed
                if position["quantity"] <= 0:
                    del positions_storage[symbol]


def get_portfolio(current_prices: Dict[str, float]) -> Portfolio:
    """Get current portfolio state"""
    global portfolio_balance
    
    positions = []
    total_unrealized_pnl = 0.0
    total_realized_pnl = 0.0
    locked_balance = 0.0
    
    for symbol, position_data in positions_storage.items():
        current_price = current_prices.get(symbol, position_data["avg_price"])
        quantity = position_data["quantity"]
        avg_price = position_data["avg_price"]
        
        unrealized_pnl = (current_price - avg_price) * quantity
        total_unrealized_pnl += unrealized_pnl
        total_realized_pnl += position_data.get("realized_pnl", 0.0)
        
        positions.append(Position(
            symbol=symbol,
            quantity=quantity,
            avg_price=avg_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=position_data.get("realized_pnl", 0.0),
            total_cost=avg_price * quantity
        ))
        
        locked_balance += avg_price * quantity
    
    total_pnl = total_unrealized_pnl + total_realized_pnl
    available_balance = portfolio_balance - locked_balance + total_realized_pnl
    
    # Calculate win rate
    closed_trades = [t for t in trades_storage if t["side"] == "SELL" and t["status"] == "FILLED"]
    winning_trades = sum(1 for t in closed_trades if t.get("pnl", 0) > 0)
    win_rate = (winning_trades / len(closed_trades) * 100) if closed_trades else 0.0
    
    return Portfolio(
        total_balance=portfolio_balance + total_pnl,
        available_balance=max(0, available_balance),
        locked_balance=locked_balance,
        positions=positions,
        total_pnl=total_pnl,
        total_trades=len(trades_storage),
        win_rate=win_rate
    )


def get_trade_history(limit: int = 50) -> List[Dict]:
    """Get trade history"""
    return trades_storage[-limit:] if len(trades_storage) > limit else trades_storage


def get_open_positions() -> List[Dict]:
    """Get open positions"""
    return [pos for pos in positions_storage.values() if pos["quantity"] > 0]

