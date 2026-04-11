"""
Paper Trading Service
Manages simulated trades, portfolio, and P/L tracking
"""

from typing import Dict, List, Optional
from datetime import datetime

from database.connection import SessionLocal
from database.models import UserProfile


class PaperTradingService:
    """Service for managing paper trading simulation"""
    
    def __init__(self):
        self._default_balance: float = 10000.0

        # Legacy global state (for unauthenticated/old flow).
        self.orders: List[Dict] = []
        self.portfolio: Dict[str, Dict] = {}  # symbol -> {quantity, avg_price, total_cost}
        self.initial_balance: float = self._default_balance
        self.current_balance: float = self._default_balance
        self.cash: float = self._default_balance
        self.trade_history: List[Dict] = []

        # Per-user isolated runtime state.
        self._user_states: Dict[int, Dict] = {}

    def _empty_state(self) -> Dict:
        return {
            "orders": [],
            "portfolio": {},
            "initial_balance": self._default_balance,
            "current_balance": self._default_balance,
            "cash": self._default_balance,
            "trade_history": [],
        }

    def _ensure_user_profile(self, user_id: int) -> Optional[UserProfile]:
        if not SessionLocal:
            return None
        db = SessionLocal()
        try:
            row = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            if row:
                return row

            row = UserProfile(
                user_id=user_id,
                risk_profile="moderate",
                investment_objective="balanced_growth",
                preferred_mode="manual_assist",
                paper_balance=self._default_balance,
                paper_positions=[],
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            return None
        finally:
            db.close()

    def _load_user_state(self, user_id: int) -> Dict:
        state = self._empty_state()

        profile = self._ensure_user_profile(user_id)
        if not profile:
            return state

        balance = float(profile.paper_balance) if profile.paper_balance is not None else self._default_balance
        positions_raw = profile.paper_positions if isinstance(profile.paper_positions, list) else []

        portfolio = {}
        for p in positions_raw:
            try:
                symbol = str(p.get("symbol") or "").upper()
                quantity = float(p.get("quantity", 0) or 0)
                avg_price = float(p.get("avg_price", 0) or 0)
                total_cost = float(p.get("total_cost", avg_price * quantity) or 0)
                if symbol and quantity > 0:
                    portfolio[symbol] = {
                        "quantity": quantity,
                        "avg_price": avg_price,
                        "total_cost": total_cost,
                    }
            except Exception:
                continue

        state["cash"] = balance
        state["current_balance"] = balance
        state["portfolio"] = portfolio
        return state

    def _save_user_state(self, user_id: int, state: Dict):
        if not SessionLocal:
            return
        db = SessionLocal()
        try:
            row = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            if not row:
                row = UserProfile(
                    user_id=user_id,
                    risk_profile="moderate",
                    investment_objective="balanced_growth",
                    preferred_mode="manual_assist",
                )
                db.add(row)

            row.paper_balance = float(state.get("cash", self._default_balance))
            row.paper_positions = [
                {
                    "symbol": sym,
                    "quantity": float(pos.get("quantity", 0) or 0),
                    "avg_price": float(pos.get("avg_price", 0) or 0),
                    "total_cost": float(pos.get("total_cost", 0) or 0),
                }
                for sym, pos in (state.get("portfolio") or {}).items()
                if float(pos.get("quantity", 0) or 0) > 0
            ]
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _get_state(self, user_id: Optional[int]) -> Dict:
        if user_id is None:
            return {
                "orders": self.orders,
                "portfolio": self.portfolio,
                "initial_balance": self.initial_balance,
                "current_balance": self.current_balance,
                "cash": self.cash,
                "trade_history": self.trade_history,
            }

        uid = int(user_id)
        if uid not in self._user_states:
            self._user_states[uid] = self._load_user_state(uid)
        return self._user_states[uid]

    def _set_state(self, user_id: Optional[int], state: Dict):
        if user_id is None:
            self.orders = state["orders"]
            self.portfolio = state["portfolio"]
            self.initial_balance = state["initial_balance"]
            self.current_balance = state["current_balance"]
            self.cash = state["cash"]
            self.trade_history = state["trade_history"]
            return

        uid = int(user_id)
        self._user_states[uid] = state
        self._save_user_state(uid, state)
    
    def place_order(self, order: Dict, user_id: Optional[int] = None) -> Dict:
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
        state = self._get_state(user_id)
        portfolio = state["portfolio"]
        cash = float(state["cash"])
        
        if side == 'BUY':
            # Check if we have enough cash
            if total_cost > cash:
                return {
                    "error": "Insufficient funds",
                    "required": total_cost,
                    "available": cash
                }
            
            # Execute buy order
            cash -= total_cost
            
            # Update portfolio
            if symbol not in portfolio:
                portfolio[symbol] = {
                    "quantity": 0,
                    "avg_price": 0,
                    "total_cost": 0
                }
            
            # Calculate new average price
            old_quantity = portfolio[symbol]["quantity"]
            old_total_cost = portfolio[symbol]["total_cost"]
            
            new_quantity = old_quantity + quantity
            new_total_cost = old_total_cost + total_cost
            new_avg_price = new_total_cost / new_quantity if new_quantity > 0 else 0
            
            portfolio[symbol]["quantity"] = new_quantity
            portfolio[symbol]["avg_price"] = new_avg_price
            portfolio[symbol]["total_cost"] = new_total_cost
            
        elif side == 'SELL':
            # Check if we have enough quantity
            if symbol not in portfolio or portfolio[symbol]["quantity"] < quantity:
                return {
                    "error": "Insufficient quantity",
                    "required": quantity,
                    "available": portfolio.get(symbol, {}).get("quantity", 0)
                }
            
            # Execute sell order
            cash += total_cost
            
            # Update portfolio
            portfolio[symbol]["quantity"] -= quantity
            if portfolio[symbol]["quantity"] == 0:
                # Calculate P/L for this position
                avg_price = portfolio[symbol]["avg_price"]
                pnl = (price - avg_price) * quantity
                
                # Remove from portfolio
                del portfolio[symbol]
            else:
                # Partial sell - calculate P/L for sold portion
                avg_price = portfolio[symbol]["avg_price"]
                pnl = (price - avg_price) * quantity
                # Update total cost
                portfolio[symbol]["total_cost"] -= (avg_price * quantity)
        
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
            "paper_trading": True,
        }

        # Attach P/L and entry price to SELL orders
        if side == 'SELL':
            executed_order["pnl"] = pnl
            executed_order["pnl_percent"] = (pnl / (avg_price * quantity) * 100) if avg_price * quantity > 0 else 0
            executed_order["entry_price"] = avg_price
        
        # Add to history
        state["orders"].append(executed_order)
        state["trade_history"].append(executed_order)
        state["cash"] = cash
        
        # Update current balance
        self._update_balance(user_id=user_id)
        self._set_state(user_id, state)
        
        return executed_order
    
    def _update_balance(self, user_id: Optional[int] = None):
        """Update current balance based on portfolio value"""
        state = self._get_state(user_id)
        portfolio_value = 0.0
        
        # Calculate portfolio value (would need current prices in real implementation)
        # For now, use average price as approximation
        for symbol, position in state["portfolio"].items():
            portfolio_value += position["quantity"] * position["avg_price"]
        
        state["current_balance"] = float(state["cash"]) + portfolio_value
        self._set_state(user_id, state)
    
    def get_portfolio(self, current_prices: Dict[str, float] = None, user_id: Optional[int] = None) -> Dict:
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
        
        state = self._get_state(user_id)

        for symbol, position in state["portfolio"].items():
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
            "cash": state["cash"],
            "portfolio_value": total_value - state["cash"],
            "total_value": total_value,
            "initial_balance": state["initial_balance"],
            "total_pnl": total_pnl,
            "total_pnl_percent": ((total_value - state["initial_balance"]) / state["initial_balance"] * 100) if state["initial_balance"] > 0 else 0,
            "positions": positions,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_trade_history(self, limit: int = 50, user_id: Optional[int] = None) -> List[Dict]:
        """Get trade history"""
        state = self._get_state(user_id)
        history = state["trade_history"]
        return history[-limit:] if limit else history
    
    def get_statistics(self, user_id: Optional[int] = None) -> Dict:
        """Get trading statistics"""
        state = self._get_state(user_id)
        history = state["trade_history"]
        portfolio_state = state["portfolio"]

        total_trades = len(history)
        buy_trades = [t for t in history if t['side'] == 'BUY']
        sell_trades = [t for t in history if t['side'] == 'SELL']

        # Open trades = symbols still in portfolio with quantity > 0
        open_trades = len([s for s, p in portfolio_state.items() if p.get("quantity", 0) > 0])

        # Closed trades: each SELL closes (or partially closes) a position
        # Calculate P/L per closed trade and win rate
        closed_trades = []
        for t in sell_trades:
            pnl = t.get("pnl", 0)
            closed_trades.append(t)

        winning_trades = [t for t in closed_trades if t.get("pnl", 0) > 0]
        win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0

        portfolio = self.get_portfolio(user_id=user_id)
        total_value = portfolio.get("total_value", state["cash"])

        return {
            "total_trades": total_trades,
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "active_positions": open_trades,
            "open_trades": open_trades,
            "closed_trades": len(closed_trades),
            "win_rate": round(win_rate, 1),
            "total_value": total_value,
            "current_balance": total_value,
            "total_pnl": portfolio["total_pnl"],
            "total_pnl_percent": portfolio["total_pnl_percent"],
            "timestamp": datetime.now().isoformat()
        }
    
    def reset(self, user_id: Optional[int] = None):
        """Reset paper trading account"""
        state = self._empty_state()
        self._set_state(user_id, state)


# Global instance
paper_trading_service = PaperTradingService()

