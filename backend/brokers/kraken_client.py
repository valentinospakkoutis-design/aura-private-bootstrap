"""
Kraken Spot API Integration for AURA

Thin wrapper around the ``krakenex`` client that normalises symbol formats
(e.g. ``BTCUSDT`` -> ``XBTUSD``) and guarantees every public method returns
either the expected payload or ``{"error": str}`` so callers don't have to
reason about ``krakenex`` exception types.

Kraken does not expose a public spot testnet. The ``testnet`` flag is kept
for API parity with the other broker clients — when True we short-circuit
private calls to a clear error instead of hitting live accounts accidentally.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional


# AURA-internal symbol -> Kraken asset-pair code.
# Kraken uses XBT for BTC and ZUSD/USD depending on the pair, so we cannot
# derive the Kraken code by simple string substitution.
SYMBOL_MAP: Dict[str, str] = {
    "BTCUSDT": "XBTUSDT",
    "BTCUSD": "XBTUSD",
    "BTCUSDC": "XBTUSDC",
    "BTCEUR": "XBTEUR",
    "ETHUSDT": "ETHUSDT",
    "ETHUSD": "ETHUSD",
    "ETHUSDC": "ETHUSDC",
    "ETHEUR": "ETHEUR",
    "SOLUSDT": "SOLUSDT",
    "SOLUSD": "SOLUSD",
    "ADAUSDT": "ADAUSDT",
    "ADAUSD": "ADAUSD",
    "DOTUSDT": "DOTUSDT",
    "DOTUSD": "DOTUSD",
    "XRPUSDT": "XRPUSDT",
    "XRPUSD": "XRPUSD",
    "LTCUSDT": "LTCUSDT",
    "LTCUSD": "LTCUSD",
    "LINKUSDT": "LINKUSDT",
    "LINKUSD": "LINKUSD",
    "MATICUSDT": "MATICUSDT",
    "MATICUSD": "MATICUSD",
    "AVAXUSDT": "AVAXUSDT",
    "AVAXUSD": "AVAXUSD",
    "DOGEUSDT": "XDGUSDT",
    "DOGEUSD": "XDGUSD",
}


def _normalize_symbol(symbol: str) -> str:
    """Map an AURA symbol to a Kraken asset-pair code."""
    if not symbol:
        return symbol
    key = symbol.upper().replace("/", "").replace("-", "")
    return SYMBOL_MAP.get(key, key)


class KrakenClient:
    """Kraken Spot API client."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.connected = False

        try:
            import krakenex  # type: ignore

            self._krakenex = krakenex
            self._client = krakenex.API(key=api_key or "", secret=api_secret or "")
        except ImportError:
            self._krakenex = None
            self._client = None

    # ── Internal helpers ────────────────────────────────────────────

    def _require_client(self) -> Optional[Dict]:
        if self._client is None:
            return {"error": "krakenex library not installed"}
        if self.testnet:
            return {"error": "Kraken has no public spot testnet"}
        if not self.api_key or not self.api_secret:
            return {"error": "Kraken API credentials are missing"}
        return None

    def _private(self, method: str, data: Optional[Dict] = None) -> Dict:
        """Call a private endpoint and flatten Kraken's result/error envelope."""
        guard = self._require_client()
        if guard is not None:
            return guard
        try:
            resp = self._client.query_private(method, data or {})
        except Exception as exc:  # network, auth, krakenex.APIError, ...
            return {"error": str(exc)}

        errors = resp.get("error") or []
        if errors:
            return {"error": "; ".join(errors)}
        return resp.get("result") or {}

    def _public(self, method: str, data: Optional[Dict] = None) -> Dict:
        if self._client is None:
            return {"error": "krakenex library not installed"}
        try:
            resp = self._client.query_public(method, data or {})
        except Exception as exc:
            return {"error": str(exc)}

        errors = resp.get("error") or []
        if errors:
            return {"error": "; ".join(errors)}
        return resp.get("result") or {}

    # ── Public API ──────────────────────────────────────────────────

    def test_connection(self) -> Dict:
        """Ping a private endpoint to verify credentials."""
        result = self._private("Balance")
        if "error" in result:
            return {
                "status": "error",
                "broker": "kraken",
                "error": result["error"],
                "timestamp": datetime.now().isoformat(),
            }
        self.connected = True
        return {
            "status": "connected",
            "broker": "kraken",
            "timestamp": datetime.now().isoformat(),
        }

    def get_balance(self) -> Dict:
        """Return ``{asset: amount}`` for every asset with a non-zero balance."""
        try:
            result = self._private("Balance")
            if "error" in result:
                return {"error": result["error"]}
            balances: Dict[str, float] = {}
            for asset, amount in result.items():
                try:
                    value = float(amount)
                except (TypeError, ValueError):
                    continue
                if value != 0.0:
                    balances[asset] = value
            return balances
        except Exception as exc:
            return {"error": str(exc)}

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
    ) -> Dict:
        """Submit a spot order. ``side`` is ``buy``/``sell``; ``order_type`` is Kraken's ``market``/``limit``/etc."""
        try:
            pair = _normalize_symbol(symbol)
            payload = {
                "pair": pair,
                "type": side.lower(),
                "ordertype": order_type.lower(),
                "volume": str(quantity),
            }
            result = self._private("AddOrder", payload)
            if "error" in result:
                return {"error": result["error"]}
            txids = result.get("txid") or []
            return {
                "order_id": txids[0] if txids else None,
                "txids": txids,
                "symbol": pair,
                "side": side.lower(),
                "type": order_type.lower(),
                "quantity": float(quantity),
                "description": (result.get("descr") or {}).get("order"),
                "broker": "kraken",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def get_open_orders(self) -> List:
        """List open orders. Returns ``[{"error": str}]`` if the request fails."""
        try:
            result = self._private("OpenOrders")
            if "error" in result:
                return [{"error": result["error"]}]
            orders = result.get("open") or {}
            out: List[Dict] = []
            for order_id, info in orders.items():
                descr = info.get("descr") or {}
                out.append({
                    "order_id": order_id,
                    "status": info.get("status"),
                    "symbol": descr.get("pair"),
                    "side": descr.get("type"),
                    "type": descr.get("ordertype"),
                    "price": descr.get("price"),
                    "volume": info.get("vol"),
                    "volume_executed": info.get("vol_exec"),
                    "opened_at": info.get("opentm"),
                })
            return out
        except Exception as exc:
            return [{"error": str(exc)}]

    def cancel_order(self, order_id: str) -> Dict:
        try:
            result = self._private("CancelOrder", {"txid": order_id})
            if "error" in result:
                return {"error": result["error"]}
            return {
                "order_id": order_id,
                "count": int(result.get("count") or 0),
                "pending": bool(result.get("pending")),
                "broker": "kraken",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def get_ticker(self, symbol: str) -> Dict:
        try:
            pair = _normalize_symbol(symbol)
            result = self._public("Ticker", {"pair": pair})
            if "error" in result:
                return {"error": result["error"]}
            if not result:
                return {"error": f"No ticker data for {pair}"}

            # Kraken returns the canonical pair name as the sole top-level key,
            # which is not guaranteed to equal our requested ``pair`` string.
            pair_key, ticker = next(iter(result.items()))
            last = (ticker.get("c") or [None])[0]
            bid = (ticker.get("b") or [None])[0]
            ask = (ticker.get("a") or [None])[0]

            return {
                "symbol": pair_key,
                "price": float(last) if last is not None else None,
                "bid": float(bid) if bid is not None else None,
                "ask": float(ask) if ask is not None else None,
            }
        except Exception as exc:
            return {"error": str(exc)}

    # ── Status helper used by AURA's broker registry ───────────────

    def get_status(self) -> Dict:
        return {
            "broker": "kraken",
            "connected": self.connected,
            "has_api_key": bool(self.api_key),
            "testnet": self.testnet,
            "timestamp": datetime.now().isoformat(),
        }
