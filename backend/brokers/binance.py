"""
Binance API Integration for AURA
Handles connection, market data, and order execution.
"""

import hashlib
import hmac
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode

import httpx


class BinanceAPI:
    """Binance API client for AURA"""
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = True):
        """
        Initialize Binance API client
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet (default: True for paper trading)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base_url = "https://testnet.binance.vision" if testnet else "https://api.binance.com"
        self.connected = False

    def _signed_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        timeout: float = 10.0
    ) -> Dict:
        """Execute a signed Binance REST request."""
        if not self.api_key or not self.api_secret:
            return {
                "error": "Binance API credentials are missing",
                "status": "failed"
            }

        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        payload.setdefault("recvWindow", 5000)

        query_string = urlencode(payload)
        payload["signature"] = self._generate_signature(query_string)

        try:
            with httpx.Client(base_url=self.base_url, timeout=timeout) as client:
                response = client.request(
                    method=method.upper(),
                    url=path,
                    params=payload,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = {}
            try:
                detail = exc.response.json()
            except ValueError:
                detail = {"message": exc.response.text}
            return {
                "error": detail.get("msg", "Binance request failed"),
                "status": "failed",
                "code": detail.get("code"),
                "details": detail
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "status": "failed"
            }

    def _public_request(self, path: str, params: Optional[Dict] = None, timeout: float = 10.0) -> Dict:
        """Execute an unsigned Binance REST request."""
        try:
            with httpx.Client(base_url=self.base_url, timeout=timeout) as client:
                response = client.get(path, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = {}
            try:
                detail = exc.response.json()
            except ValueError:
                detail = {"message": exc.response.text}
            return {
                "error": detail.get("msg", "Binance request failed"),
                "status": "failed",
                "code": detail.get("code"),
                "details": detail
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "status": "failed"
            }
        
    def _generate_signature(self, query_string: str) -> str:
        """Generate HMAC SHA256 signature for authenticated requests"""
        if not self.api_secret:
            raise ValueError("API secret is required for authenticated requests")
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        headers = {
            'Content-Type': 'application/json',
            'X-MBX-APIKEY': self.api_key or ''
        }
        return headers

    def get_status(self) -> Dict:
        """Get broker connection status."""
        return {
            "broker": "binance",
            "connected": self.connected,
            "has_api_key": bool(self.api_key),
            "testnet": self.testnet,
            "timestamp": datetime.now().isoformat()
        }
    
    def test_connection(self) -> Dict:
        """
        Test connection to Binance API
        
        Returns:
            Dict with connection status
        """
        try:
            account_info = self._signed_request("GET", "/api/v3/account")
            if "error" in account_info:
                return {
                    "status": "error",
                    "broker": "binance",
                    "testnet": self.testnet,
                    "error": account_info["error"],
                    "details": account_info.get("details")
                }

            self.connected = True
            return {
                "status": "connected",
                "broker": "binance",
                "testnet": self.testnet,
                "can_trade": account_info.get("canTrade"),
                "account_type": account_info.get("accountType"),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "broker": "binance",
                "error": str(e)
            }
    
    def get_account_balance(self) -> Dict:
        """
        Get account balance (simulated for paper trading)
        
        Returns:
            Dict with account balance information
        """
        if not self.connected:
            return {
                "error": "Not connected to Binance",
                "balance": 0.0
            }
        
        account_info = self._signed_request("GET", "/api/v3/account")
        if "error" in account_info:
            return account_info

        balances = {
            item["asset"]: float(item["free"]) + float(item["locked"])
            for item in account_info.get("balances", [])
            if float(item["free"]) or float(item["locked"])
        }

        usdc_total = balances.get("USDC", 0.0)
        usdc_available = next(
            (
                float(item["free"])
                for item in account_info.get("balances", [])
                if item["asset"] == "USDC"
            ),
            0.0
        )
        usdc_locked = next(
            (
                float(item["locked"])
                for item in account_info.get("balances", [])
                if item["asset"] == "USDC"
            ),
            0.0
        )

        return {
            "broker": "binance",
            "testnet": self.testnet,
            "total_balance": usdc_total,
            "available_balance": usdc_available,
            "locked_balance": usdc_locked,
            "currencies": balances,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_market_price(self, symbol: str) -> Dict:
        """
        Get current market price for a symbol
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDC')
            
        Returns:
            Dict with price information
        """
        ticker = self._public_request("/api/v3/ticker/price", {"symbol": symbol.upper()})
        if "error" in ticker:
            return ticker

        return {
            "symbol": symbol.upper(),
            "price": float(ticker["price"]),
            "timestamp": datetime.now().isoformat(),
            "broker": "binance"
        }
    
    def get_supported_symbols(self) -> List[str]:
        """Get list of supported trading symbols"""
        return [
            "BTCUSDC",  # Bitcoin
            "ETHUSDC",  # Ethereum
            "BNBUSDC",  # Binance Coin
        ]
    
    def place_paper_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET") -> Dict:
        """
        Place a paper trading order (simulated)
        
        Args:
            symbol: Trading pair
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            order_type: Order type (MARKET, LIMIT, etc.)
            
        Returns:
            Dict with order information
        """
        if not self.connected:
            return {
                "error": "Not connected to Binance",
                "status": "failed"
            }
        
        # Get current price
        price_info = self.get_market_price(symbol)
        price = price_info["price"]
        
        # Simulate order execution
        order = {
            "order_id": f"PAPER_{int(time.time() * 1000)}",
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type,
            "quantity": quantity,
            "price": price,
            "status": "FILLED",
            "executed_qty": quantity,
            "timestamp": datetime.now().isoformat(),
            "broker": "binance",
            "paper_trading": True
        }
        
        return order

    def place_live_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET", client_order_id: str = None) -> Dict:
        """
        Place a real order on Binance.
        client_order_id: unique idempotency key to prevent duplicate orders.
        """
        if not self.connected:
            return {
                "error": "Not connected to Binance",
                "status": "failed"
            }

        payload = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }
        if client_order_id:
            payload["newClientOrderId"] = client_order_id

        response = self._signed_request("POST", "/api/v3/order", payload, timeout=20.0)
        if "error" in response:
            return response

        fills = response.get("fills", [])
        executed_price = None
        if fills:
            executed_price = float(fills[0].get("price", 0.0))
        elif response.get("cummulativeQuoteQty") and response.get("executedQty"):
            executed_qty = float(response["executedQty"])
            if executed_qty > 0:
                executed_price = float(response["cummulativeQuoteQty"]) / executed_qty

        return {
            "order_id": str(response.get("orderId")),
            "client_order_id": response.get("clientOrderId"),
            "symbol": response.get("symbol", symbol.upper()),
            "side": response.get("side", side.upper()),
            "type": response.get("type", order_type.upper()),
            "quantity": float(response.get("origQty", quantity)),
            "executed_qty": float(response.get("executedQty", 0.0)),
            "price": executed_price,
            "status": response.get("status"),
            "broker": "binance",
            "paper_trading": False,
            "testnet": self.testnet,
            "transact_time": response.get("transactTime"),
            "executed_at": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "raw_response": response
        }
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get real open orders from Binance."""
        if not self.connected:
            return []
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        result = self._signed_request("GET", "/api/v3/openOrders", params)
        if "error" in result:
            return []
        return result if isinstance(result, list) else []

    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel an open order."""
        if not self.connected:
            return {"error": "Not connected"}
        return self._signed_request("DELETE", "/api/v3/order", {
            "symbol": symbol.upper(),
            "orderId": order_id,
        })

    def place_limit_order(
        self, symbol: str, side: str, quantity: float,
        price: float, time_in_force: str = "GTC", client_order_id: str = None
    ) -> Dict:
        """Place a LIMIT order."""
        if not self.connected:
            return {"error": "Not connected", "status": "failed"}
        payload = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": time_in_force,
            "quantity": quantity,
            "price": str(price),
        }
        if client_order_id:
            payload["newClientOrderId"] = client_order_id
        response = self._signed_request("POST", "/api/v3/order", payload, timeout=20.0)
        if "error" in response:
            return response
        return {
            "order_id": str(response.get("orderId")),
            "symbol": response.get("symbol"),
            "side": response.get("side"),
            "type": "LIMIT",
            "quantity": float(response.get("origQty", quantity)),
            "price": float(response.get("price", price)),
            "status": response.get("status"),
            "broker": "binance",
            "timestamp": datetime.now().isoformat(),
        }

    def place_oco_order(
        self, symbol: str, side: str, quantity: float,
        price: float, stop_price: float, stop_limit_price: float
    ) -> Dict:
        """Place an OCO (One-Cancels-Other) order for SL/TP."""
        if not self.connected:
            return {"error": "Not connected", "status": "failed"}
        payload = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "quantity": quantity,
            "price": str(price),
            "stopPrice": str(stop_price),
            "stopLimitPrice": str(stop_limit_price),
            "stopLimitTimeInForce": "GTC",
        }
        return self._signed_request("POST", "/api/v3/order/oco", payload, timeout=20.0)

    def get_symbol_price(self, symbol: str) -> float:
        """Get current price for a symbol."""
        result = self._public_request("/api/v3/ticker/price", {"symbol": symbol.upper()})
        if "error" in result:
            return 0.0
        return float(result.get("price", 0))

    # ── Futures ──────────────────────────────────────────────────
    def _futures_signed_request(self, method: str, path: str, params: Optional[Dict] = None, timeout: float = 10.0) -> Dict:
        """Execute a signed Binance Futures request."""
        if not self.api_key or not self.api_secret:
            return {"error": "API credentials missing", "status": "failed"}
        base = "https://testnet.binancefuture.com" if self.testnet else "https://fapi.binance.com"
        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        payload.setdefault("recvWindow", 5000)
        query_string = urlencode(payload)
        payload["signature"] = self._generate_signature(query_string)
        try:
            with httpx.Client(base_url=base, timeout=timeout) as client:
                response = client.request(method.upper(), path, params=payload, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = {}
            try:
                detail = exc.response.json()
            except ValueError:
                detail = {"message": exc.response.text}
            return {"error": detail.get("msg", "Futures request failed"), "status": "failed", "code": detail.get("code"), "details": detail}
        except Exception as exc:
            return {"error": str(exc), "status": "failed"}

    def futures_account(self) -> Dict:
        """Get futures account info."""
        return self._futures_signed_request("GET", "/fapi/v2/account")

    def futures_positions(self) -> List[Dict]:
        """Get futures positions."""
        result = self._futures_signed_request("GET", "/fapi/v2/positionRisk")
        if "error" in result:
            return []
        return [p for p in result if float(p.get("positionAmt", 0)) != 0] if isinstance(result, list) else []

    def futures_create_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET", client_order_id: str = None) -> Dict:
        """Place a futures order."""
        payload = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }
        if client_order_id:
            payload["newClientOrderId"] = client_order_id
        return self._futures_signed_request("POST", "/fapi/v1/order", payload, timeout=20.0)

    def futures_set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for a futures symbol."""
        return self._futures_signed_request("POST", "/fapi/v1/leverage", {
            "symbol": symbol.upper(),
            "leverage": leverage,
        })

    def get_trade_history(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get real trade history from Binance."""
        if not self.connected:
            return []
        params = {"limit": 50}
        if symbol:
            params["symbol"] = symbol.upper()
        result = self._signed_request("GET", "/api/v3/myTrades", params)
        if "error" in result:
            return []
        return result if isinstance(result, list) else []

