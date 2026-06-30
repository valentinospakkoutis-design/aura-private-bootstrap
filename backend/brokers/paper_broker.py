"""
Paper trading broker — mirrors the BinanceAPI interface but executes against
virtual balances via paper_trading_service. Lets the FULL autonomous engine run
end-to-end (signal -> filter -> Kelly -> execution) with REAL market prices and
ZERO real-money risk. Drop-in: set engine.broker = PaperBroker().
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PaperBroker:
    def __init__(self, user_id: Optional[int] = None, starting_balance: float = 10000.0):
        self.connected = True          # always "connected" — no real API
        self.testnet = True
        self.user_id = user_id
        self.starting_balance = starting_balance

    # ── price source: same as predictor (realtime feed -> yfinance -> base) ──
    def _price(self, symbol: str) -> float:
        try:
            from ai.asset_predictor import asset_predictor
            p = float(asset_predictor.get_current_price(symbol) or 0.0)
            if p > 0:
                return p
        except Exception as e:
            logger.debug(f"[paper] price lookup failed for {symbol}: {e}")
        return 0.0

    def get_symbol_price(self, symbol: str) -> float:
        return self._price(symbol)

    def get_market_price(self, symbol: str) -> Dict:
        return {"symbol": symbol.upper(), "price": self._price(symbol)}

    def get_status(self) -> Dict:
        return {"connected": self.connected, "broker": "paper", "testnet": True}

    def test_connection(self) -> Dict:
        self.connected = True
        return {"connected": True, "broker": "paper"}

    def get_account_balance(self) -> Dict:
        cash = self.starting_balance
        total = self.starting_balance
        try:
            from services.paper_trading import paper_trading_service
            pf = paper_trading_service.get_portfolio(user_id=self.user_id)
            cash = float(pf.get("cash", self.starting_balance))
            total = float(pf.get("total_value", cash))
        except Exception as e:
            logger.debug(f"[paper] balance lookup failed: {e}")
        return {
            "broker": "paper",
            "testnet": True,
            "total_balance": total,
            "available_balance": cash,
            "locked_balance": 0.0,
            "currencies": {"USDC": cash},
            "timestamp": datetime.now().isoformat(),
        }

    def place_live_order(self, symbol: str, side: str, quantity: float,
                         order_type: str = "MARKET", client_order_id: str = None) -> Dict:
        price = self._price(symbol)
        if price <= 0:
            return {"error": f"No price for {symbol}", "status": "failed"}
        try:
            from services.paper_trading import paper_trading_service
            result = paper_trading_service.place_order({
                "symbol": symbol, "side": side, "quantity": quantity,
                "price": price, "order_type": order_type,
            }, user_id=self.user_id)
        except Exception as e:
            return {"error": f"paper place_order failed: {e}", "status": "failed"}
        if isinstance(result, dict) and "error" in result:
            return {"error": result["error"], "status": "failed"}
        return {
            "order_id": str(result.get("order_id", client_order_id or "PAPER")),
            "client_order_id": client_order_id,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": float(quantity),
            "executed_qty": float(quantity),
            "price": price,
            "status": "FILLED",
            "broker": "paper",
            "paper_trading": True,
            "testnet": True,
            "executed_at": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat(),
        }

    # Stubs the engine may touch (no-ops for paper)
    def get_lot_size(self, symbol: str) -> Dict:
        return {"step_size": 0.0, "min_qty": 0.0}

    @staticmethod
    def round_to_step_size(quantity: float, step_size: float) -> float:
        return quantity

    def get_open_orders(self, symbol: Optional[str] = None):
        return []


paper_broker = PaperBroker()
