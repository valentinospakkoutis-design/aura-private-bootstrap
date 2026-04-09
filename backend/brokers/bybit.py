"""
Bybit API Integration for AURA
V5 Unified API — Crypto & USDT Perpetual Futures.
"""

import hashlib
import hmac
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode

import httpx


class BybitAPI:
    """Bybit V5 API client."""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        self.connected = False

    def _sign(self, timestamp: str, params_str: str) -> str:
        """Generate HMAC-SHA256 signature for Bybit V5."""
        recv_window = "10000"
        sign_payload = f"{timestamp}{self.api_key}{recv_window}{params_str}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            sign_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(self, method: str, path: str, params: Optional[Dict] = None, timeout: float = 10.0) -> Dict:
        """Execute a signed Bybit V5 request."""
        if not self.api_key or not self.api_secret:
            return {"error": "Bybit API credentials missing", "status": "failed"}

        ts = str(int(time.time() * 1000))
        recv_window = "10000"

        if method.upper() == "GET":
            params_str = urlencode(params) if params else ""
        else:
            import json as _json
            params_str = _json.dumps(params) if params else ""

        signature = self._sign(ts, params_str)

        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{path}"
        print(f"[BYBIT] {method.upper()} {path} | key={self.api_key[:8]}... | testnet={self.testnet}")

        try:
            with httpx.Client(timeout=timeout) as client:
                if method.upper() == "GET":
                    resp = client.get(url, params=params, headers=headers)
                else:
                    resp = client.post(url, json=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            if data.get("retCode") != 0:
                print(f"[BYBIT] API error: {data}")
                return {
                    "error": data.get("retMsg", "Bybit request failed"),
                    "status": "failed",
                    "code": data.get("retCode"),
                    "details": data,
                }
            return data.get("result", data)

        except httpx.HTTPStatusError as exc:
            detail = {}
            try:
                detail = exc.response.json()
            except Exception:
                detail = {"message": exc.response.text}
            print(f"[BYBIT] HTTP error {exc.response.status_code}: {detail}")
            return {"error": detail.get("retMsg", "Bybit request failed"), "status": "failed", "details": detail}
        except Exception as exc:
            print(f"[BYBIT] Exception: {exc}")
            return {"error": str(exc), "status": "failed"}

    # ── Connection ──────────────────────────────────────────────

    def test_connection(self) -> Dict:
        """Test API connection by fetching wallet balance."""
        result = self._request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
        if "error" in result:
            return {"status": "error", "broker": "bybit", "testnet": self.testnet, "error": result["error"]}
        self.connected = True
        return {
            "status": "connected",
            "broker": "bybit",
            "testnet": self.testnet,
            "timestamp": datetime.now().isoformat(),
        }

    def get_status(self) -> Dict:
        return {
            "broker": "bybit",
            "connected": self.connected,
            "has_api_key": bool(self.api_key),
            "testnet": self.testnet,
            "timestamp": datetime.now().isoformat(),
        }

    # ── Balance ─────────────────────────────────────────────────

    def get_balance(self) -> Dict:
        """Get unified account wallet balance."""
        result = self._request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
        if "error" in result:
            return result

        coins = []
        total_equity = 0
        for account in result.get("list", []):
            total_equity = float(account.get("totalEquity", 0))
            for coin in account.get("coin", []):
                equity = float(coin.get("equity", 0))
                if equity > 0:
                    coins.append({
                        "symbol": coin.get("coin"),
                        "equity": equity,
                        "available": float(coin.get("availableToWithdraw", 0)),
                        "usd_value": float(coin.get("usdValue", 0)),
                    })

        return {
            "total_equity": total_equity,
            "coins": coins,
            "broker": "bybit",
            "timestamp": datetime.now().isoformat(),
        }

    # ── Positions ───────────────────────────────────────────────

    def get_positions(self, category: str = "linear") -> List[Dict]:
        """Get open positions."""
        result = self._request("GET", "/v5/position/list", {"category": category, "settleCoin": "USDT"})
        if "error" in result:
            return []
        positions = []
        for pos in result.get("list", []):
            size = float(pos.get("size", 0))
            if size > 0:
                positions.append({
                    "symbol": pos.get("symbol"),
                    "side": pos.get("side"),
                    "size": size,
                    "entry_price": float(pos.get("avgPrice", 0)),
                    "mark_price": float(pos.get("markPrice", 0)),
                    "unrealised_pnl": float(pos.get("unrealisedPnl", 0)),
                    "leverage": pos.get("leverage"),
                })
        return positions

    # ── Orders ──────────────────────────────────────────────────

    def set_leverage(self, symbol: str, leverage: int, category: str = "linear") -> Dict:
        """Set leverage for a symbol."""
        return self._request("POST", "/v5/position/set-leverage", {
            "category": category,
            "symbol": symbol.upper(),
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage),
        })

    def place_order(
        self, symbol: str, side: str, quantity: float,
        order_type: str = "Market", category: str = "linear",
        client_order_id: str = None,
    ) -> Dict:
        """Place a USDT perpetual order."""
        if not self.connected:
            return {"error": "Not connected to Bybit", "status": "failed"}

        params = {
            "category": category,
            "symbol": symbol.upper(),
            "side": side,  # "Buy" or "Sell"
            "orderType": order_type,
            "qty": str(quantity),
        }
        if client_order_id:
            params["orderLinkId"] = client_order_id

        result = self._request("POST", "/v5/order/create", params, timeout=20.0)
        if "error" in result:
            return result

        return {
            "order_id": result.get("orderId"),
            "order_link_id": result.get("orderLinkId"),
            "symbol": symbol.upper(),
            "side": side,
            "quantity": quantity,
            "status": "submitted",
            "broker": "bybit",
            "timestamp": datetime.now().isoformat(),
        }

    def get_symbol_price(self, symbol: str) -> float:
        """Get last traded price."""
        result = self._request("GET", "/v5/market/tickers", {"category": "linear", "symbol": symbol.upper()})
        if "error" in result:
            return 0.0
        tickers = result.get("list", [])
        if tickers:
            return float(tickers[0].get("lastPrice", 0))
        return 0.0
