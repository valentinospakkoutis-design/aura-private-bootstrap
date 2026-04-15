"""
Coinbase Advanced Trade API Integration for AURA

Thin wrapper around ``coinbase.rest.RESTClient`` from the
``coinbase-advanced-py`` library. Normalises symbol formats (e.g.
``BTCUSDT`` -> ``BTC-USD``) and guarantees every public method returns
either the expected payload or ``{"error": str}`` so callers don't have to
reason about library-specific exception types.

Coinbase deprecated its public sandbox for Advanced Trade, so the
``testnet`` flag is kept for API parity with the other broker clients
— when True we short-circuit private calls to a clear error instead of
hitting live accounts accidentally.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional


# AURA-internal symbol -> Coinbase product id. Coinbase uses hyphenated
# base-quote pairs (e.g. ``BTC-USD``) and only lists a subset of USDT
# markets, so the common ``...USDT`` pairs route to the USD equivalent.
SYMBOL_MAP: Dict[str, str] = {
    "BTCUSD": "BTC-USD",
    "BTCUSDT": "BTC-USD",
    "BTCUSDC": "BTC-USDC",
    "BTCEUR": "BTC-EUR",
    "ETHUSD": "ETH-USD",
    "ETHUSDT": "ETH-USD",
    "ETHUSDC": "ETH-USDC",
    "ETHEUR": "ETH-EUR",
    "SOLUSD": "SOL-USD",
    "SOLUSDT": "SOL-USD",
    "ADAUSD": "ADA-USD",
    "ADAUSDT": "ADA-USD",
    "DOTUSD": "DOT-USD",
    "DOTUSDT": "DOT-USD",
    "XRPUSD": "XRP-USD",
    "XRPUSDT": "XRP-USD",
    "LTCUSD": "LTC-USD",
    "LTCUSDT": "LTC-USD",
    "LINKUSD": "LINK-USD",
    "LINKUSDT": "LINK-USD",
    "MATICUSD": "MATIC-USD",
    "MATICUSDT": "MATIC-USD",
    "AVAXUSD": "AVAX-USD",
    "AVAXUSDT": "AVAX-USD",
    "DOGEUSD": "DOGE-USD",
    "DOGEUSDT": "DOGE-USD",
}


def _normalize_symbol(symbol: str) -> str:
    """Map an AURA symbol to a Coinbase product id."""
    if not symbol:
        return symbol
    key = symbol.upper().replace("/", "").replace("-", "")
    if key in SYMBOL_MAP:
        return SYMBOL_MAP[key]
    # Fallback: inject a dash after the base (first 3-4 chars). Coinbase pair
    # ids are always hyphenated, so an un-hyphenated passthrough would fail.
    if "-" in symbol:
        return symbol.upper()
    for split in (3, 4):
        if len(key) > split:
            return f"{key[:split]}-{key[split:]}"
    return symbol.upper()


def _extract(obj, attr: str, default=None):
    """Read a field from either a dict or an attribute-style SDK response."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


class CoinbaseClient:
    """Coinbase Advanced Trade API client."""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.connected = False

        try:
            from coinbase.rest import RESTClient  # type: ignore

            self._RESTClient = RESTClient
            self._client = RESTClient(api_key=api_key or "", api_secret=api_secret or "")
        except ImportError:
            self._RESTClient = None
            self._client = None

    # ── Internal helpers ────────────────────────────────────────────

    def _require_client(self) -> Optional[Dict]:
        if self._client is None:
            return {"error": "coinbase-advanced-py library not installed"}
        if self.testnet:
            return {"error": "Coinbase has no public Advanced Trade sandbox"}
        if not self.api_key or not self.api_secret:
            return {"error": "Coinbase API credentials are missing"}
        return None

    # ── Public API ──────────────────────────────────────────────────

    def test_connection(self) -> Dict:
        """Probe the account endpoint and return balances on success."""
        guard = self._require_client()
        if guard is not None:
            return {"status": "error", "message": guard["error"]}

        balances = self.get_balance()
        if isinstance(balances, dict) and "error" in balances:
            return {"status": "error", "message": balances["error"]}

        self.connected = True
        return {"status": "connected", "balances": balances}

    def get_balance(self) -> Dict:
        """Return ``{asset: amount}`` for every account with a non-zero balance."""
        guard = self._require_client()
        if guard is not None:
            return guard
        try:
            response = self._client.get_accounts()
            accounts = _extract(response, "accounts", []) or []
            balances: Dict[str, float] = {}
            for acct in accounts:
                currency = _extract(acct, "currency") or _extract(acct, "asset")
                available = _extract(acct, "available_balance") or {}
                raw_value = _extract(available, "value")
                if raw_value is None:
                    raw_value = _extract(acct, "balance")
                try:
                    amount = float(raw_value) if raw_value is not None else 0.0
                except (TypeError, ValueError):
                    continue
                if currency and amount != 0.0:
                    balances[str(currency)] = amount
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
        """Submit a spot order via the generic ``create_order`` endpoint."""
        guard = self._require_client()
        if guard is not None:
            return guard
        try:
            product_id = _normalize_symbol(symbol)
            side_upper = side.upper()
            if side_upper not in ("BUY", "SELL"):
                return {"error": f"Invalid side: {side}"}

            client_order_id = str(uuid.uuid4())
            order_type_lower = order_type.lower()

            if order_type_lower == "market":
                order_configuration = {
                    "market_market_ioc": {"base_size": str(quantity)}
                }
            else:
                return {"error": f"Unsupported order_type for Coinbase: {order_type}"}

            response = self._client.create_order(
                client_order_id=client_order_id,
                product_id=product_id,
                side=side_upper,
                order_configuration=order_configuration,
            )

            success = _extract(response, "success")
            if success is False:
                err = _extract(response, "error_response") or {}
                return {"error": _extract(err, "message") or "Coinbase rejected order"}

            success_response = _extract(response, "success_response") or {}
            order_id = _extract(success_response, "order_id") or client_order_id

            return {
                "order_id": order_id,
                "client_order_id": client_order_id,
                "symbol": product_id,
                "side": side_upper,
                "type": order_type_lower,
                "quantity": float(quantity),
                "broker": "coinbase",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def get_open_orders(self) -> List:
        """List open orders. Returns ``[{"error": str}]`` if the call fails."""
        guard = self._require_client()
        if guard is not None:
            return [guard]
        try:
            response = self._client.list_orders(order_status=["OPEN"])
            orders = _extract(response, "orders", []) or []
            out: List[Dict] = []
            for o in orders:
                out.append({
                    "order_id": _extract(o, "order_id"),
                    "client_order_id": _extract(o, "client_order_id"),
                    "symbol": _extract(o, "product_id"),
                    "side": _extract(o, "side"),
                    "status": _extract(o, "status"),
                    "type": _extract(o, "order_type"),
                    "size": _extract(o, "base_size") or _extract(o, "size"),
                    "filled_size": _extract(o, "filled_size"),
                    "created_at": _extract(o, "created_time"),
                })
            return out
        except Exception as exc:
            return [{"error": str(exc)}]

    def cancel_order(self, order_id: str) -> Dict:
        guard = self._require_client()
        if guard is not None:
            return guard
        try:
            response = self._client.cancel_orders(order_ids=[order_id])
            results = _extract(response, "results", []) or []
            if results:
                first = results[0]
                success = _extract(first, "success", False)
                if not success:
                    reason = _extract(first, "failure_reason") or "cancel failed"
                    return {"error": str(reason)}
            return {
                "order_id": order_id,
                "broker": "coinbase",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def get_ticker(self, symbol: str) -> Dict:
        """Return best bid/ask/last for ``symbol``. No credentials required."""
        if self._client is None:
            return {"error": "coinbase-advanced-py library not installed"}
        try:
            product_id = _normalize_symbol(symbol)
            product = self._client.get_product(product_id)
            price = _extract(product, "price")
            bid = _extract(product, "best_bid") or _extract(product, "price_percentage_change_24h")
            ask = _extract(product, "best_ask")

            # Fall back to the dedicated best-bid-ask endpoint when the
            # product payload doesn't include both sides.
            if not bid or not ask:
                try:
                    bbo = self._client.get_best_bid_ask([product_id])
                    pricebooks = _extract(bbo, "pricebooks", []) or []
                    if pricebooks:
                        pb = pricebooks[0]
                        bids = _extract(pb, "bids", []) or []
                        asks = _extract(pb, "asks", []) or []
                        if bids:
                            bid = _extract(bids[0], "price", bid)
                        if asks:
                            ask = _extract(asks[0], "price", ask)
                except Exception:
                    pass

            def _maybe_float(v):
                try:
                    return float(v) if v is not None else None
                except (TypeError, ValueError):
                    return None

            return {
                "symbol": product_id,
                "price": _maybe_float(price),
                "bid": _maybe_float(bid),
                "ask": _maybe_float(ask),
            }
        except Exception as exc:
            return {"error": str(exc)}

    # ── Status helper used by AURA's broker registry ───────────────

    def get_status(self) -> Dict:
        return {
            "broker": "coinbase",
            "connected": self.connected,
            "has_api_key": bool(self.api_key),
            "testnet": self.testnet,
            "timestamp": datetime.now().isoformat(),
        }
