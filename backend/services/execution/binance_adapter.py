from __future__ import annotations

import hashlib
import hmac
import os
import time
import socket
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
import urllib3.util.connection as urllib3_connection

from ops.secret_loader import SecretConfigurationError, get_secret_loader
from services.execution.broker_client import BrokerClient, BrokerClientError
from services.execution.reliability import BrokerExecutionGuard
from services.execution.types import BrokerOrderRequest, BrokerOrderResponse, ExecutionStatus


class BinanceBrokerClient(BrokerClient):
    """Production Binance spot adapter with normalized AURA execution responses."""

    STATUS_MAP = {
        "NEW": ExecutionStatus.SUBMITTED,
        "PARTIALLY_FILLED": ExecutionStatus.PARTIALLY_FILLED,
        "FILLED": ExecutionStatus.FILLED,
        "CANCELED": ExecutionStatus.CANCELLED,
        "PENDING_CANCEL": ExecutionStatus.CANCELLED,
        "REJECTED": ExecutionStatus.FAILED,
        "EXPIRED": ExecutionStatus.FAILED,
    }

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        testnet: bool,
        recv_window: int = 5000,
        timeout_seconds: int = 10,
    ) -> None:
        if not api_key or not api_secret:
            raise BrokerClientError("Missing Binance API credentials")

        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = bool(testnet)
        self.recv_window = recv_window
        self.timeout_seconds = timeout_seconds
        self.base_url = (
            "https://testnet.binance.vision"
            if self.testnet
            else "https://api.binance.com"
        )
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})
        self._symbol_filters: Dict[str, Dict[str, Any]] = {}
        self.guard = BrokerExecutionGuard(provider="binance")

    @staticmethod
    def _truthy(value: Optional[str]) -> bool:
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _assert_static_execution_host(cls) -> None:
        if not cls._truthy(os.getenv("AURA_FIRST_LIVE_PROFILE", "false")):
            return

        if not cls._truthy(os.getenv("AURA_REQUIRE_STATIC_EGRESS", "true")):
            return

        expected_ip = os.getenv("AURA_EXECUTION_STATIC_PUBLIC_IP", "116.203.75.114").strip()
        required_role = os.getenv("AURA_EXECUTION_REQUIRED_HOST_ROLE", "execution").strip().lower()
        host_role = os.getenv("AURA_EXECUTION_HOST_ROLE", "").strip().lower()

        if required_role and host_role != required_role:
            raise BrokerClientError(
                f"EXECUTION_HOST_ROLE_MISMATCH required={required_role} actual={host_role or 'unset'}"
            )

        try:
            response = requests.get("https://api4.ipify.org", timeout=5)
            detected_ip = response.text.strip() if response.status_code == 200 else ""
        except requests.RequestException as exc:
            raise BrokerClientError(f"STATIC_EGRESS_CHECK_FAILED: {exc}") from exc

        if not detected_ip or detected_ip != expected_ip:
            hostname = socket.gethostname()
            raise BrokerClientError(
                "STATIC_EGRESS_IP_MISMATCH "
                f"host={hostname} detected={detected_ip or 'unknown'} expected={expected_ip}"
            )

    @staticmethod
    def _request_ipv4(session: requests.Session, *, method: str, url: str, params: Optional[Dict[str, Any]], timeout: int) -> requests.Response:
        # Keep IPv4 pinning scoped to broker HTTP calls only.
        original_allowed_gai_family = urllib3_connection.allowed_gai_family
        try:
            urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
            return session.request(
                method=method,
                url=url,
                params=params or {},
                timeout=timeout,
            )
        finally:
            urllib3_connection.allowed_gai_family = original_allowed_gai_family

    @classmethod
    def from_adapter(cls, adapter: Any) -> "BinanceBrokerClient":
        cls._assert_static_execution_host()
        loader = get_secret_loader()

        api_key = getattr(adapter, "api_key", None)
        api_secret = getattr(adapter, "api_secret", None)
        if not api_key:
            try:
                api_key = loader.get_secret("BINANCE_API_KEY")
            except SecretConfigurationError as exc:
                raise BrokerClientError("Missing Binance API credentials") from exc

        if not api_secret:
            try:
                api_secret = loader.get_secret("BINANCE_API_SECRET")
            except SecretConfigurationError as exc:
                raise BrokerClientError("Missing Binance API credentials") from exc

        testnet = getattr(adapter, "testnet", None)
        if testnet is None:
            testnet = os.getenv("BINANCE_TESTNET", "true").strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            api_key=str(api_key or ""),
            api_secret=str(api_secret or ""),
            testnet=bool(testnet),
        )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = (symbol or "").upper().replace("/", "").replace("-", "").replace("_", "")
        if not normalized:
            raise BrokerClientError("Invalid symbol")
        return normalized

    @staticmethod
    def _normalize_side(side: str) -> str:
        mapped = (side or "").upper()
        if mapped not in {"BUY", "SELL"}:
            raise BrokerClientError("Invalid side for Binance order")
        return mapped

    @staticmethod
    def _normalize_order_type(order_type: str) -> str:
        mapped = (order_type or "").upper()
        if mapped not in {"MARKET", "LIMIT"}:
            raise BrokerClientError("Unsupported Binance order type")
        return mapped

    def _sign_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(params)
        payload["timestamp"] = int(time.time() * 1000)
        payload["recvWindow"] = self.recv_window
        query_string = urlencode(payload)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        payload["signature"] = signature
        return payload

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
        except Exception as exc:
            raise BrokerClientError(f"Binance returned non-JSON response: {exc}")

        if response.status_code >= 400:
            message = payload.get("msg") if isinstance(payload, dict) else None
            code = payload.get("code") if isinstance(payload, dict) else None
            raise BrokerClientError(
                f"BINANCE_API_ERROR code={code} status={response.status_code} message={message or payload}"
            )

        if not isinstance(payload, dict):
            raise BrokerClientError("Binance returned malformed payload")

        return payload

    def _signed_request(self, method: str, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        signed = self._sign_params(params)
        url = f"{self.base_url}{path}"

        def _send() -> requests.Response:
            try:
                return self._request_ipv4(
                    self.session,
                    method=method.upper(),
                    url=url,
                    params=signed,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                raise BrokerClientError(f"BINANCE_NETWORK_ERROR: {exc}")

        symbol = str(params.get("symbol") or "UNKNOWN")
        response = self.guard.execute(
            operation=f"{method.upper()} {path}",
            symbol=symbol,
            fn=_send,
        )
        return self._handle_response(response)

    def _public_request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"

        def _send() -> requests.Response:
            try:
                return self._request_ipv4(
                    self.session,
                    method="GET",
                    url=url,
                    params=params or {},
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                raise BrokerClientError(f"BINANCE_NETWORK_ERROR: {exc}")

        symbol = str((params or {}).get("symbol") or "PUBLIC")
        response = self.guard.execute(
            operation=f"GET {path}",
            symbol=symbol,
            fn=_send,
        )
        return self._handle_response(response)

    def _symbol_rules(self, symbol: str) -> Dict[str, Any]:
        symbol = self._normalize_symbol(symbol)
        cached = self._symbol_filters.get(symbol)
        if cached is not None:
            return cached

        exchange_info = self._public_request("/api/v3/exchangeInfo", params={"symbol": symbol})
        symbols = exchange_info.get("symbols") or []
        if not symbols:
            raise BrokerClientError(f"Unsupported Binance symbol: {symbol}")

        item = symbols[0]
        filters = {entry.get("filterType"): entry for entry in item.get("filters") or []}
        lot = filters.get("LOT_SIZE") or {}
        price_filter = filters.get("PRICE_FILTER") or {}

        rules = {
            "symbol": symbol,
            "step_size": Decimal(str(lot.get("stepSize", "1"))),
            "min_qty": Decimal(str(lot.get("minQty", "0.00000001"))),
            "tick_size": Decimal(str(price_filter.get("tickSize", "0.00000001"))),
        }
        self._symbol_filters[symbol] = rules
        return rules

    @staticmethod
    def _quantize(value: Decimal, step: Decimal) -> Decimal:
        if step <= 0:
            return value
        units = (value / step).quantize(Decimal("1"), rounding=ROUND_DOWN)
        return units * step

    def _normalize_quantity(self, symbol: str, quantity: float) -> str:
        rules = self._symbol_rules(symbol)
        qty = self._quantize(Decimal(str(quantity)), rules["step_size"])
        if qty < rules["min_qty"]:
            raise BrokerClientError("Order quantity below broker minimum")
        return format(qty.normalize(), "f")

    def _normalize_price(self, symbol: str, price: Optional[float]) -> Optional[str]:
        if price is None:
            return None
        rules = self._symbol_rules(symbol)
        normalized = self._quantize(Decimal(str(price)), rules["tick_size"])
        return format(normalized.normalize(), "f")

    def place_order(self, request: BrokerOrderRequest) -> BrokerOrderResponse:
        symbol = self._normalize_symbol(request.symbol)
        side = self._normalize_side(request.side)
        order_type = self._normalize_order_type(request.order_type)
        quantity = self._normalize_quantity(symbol, request.quantity)

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "newClientOrderId": request.client_order_id,
            "newOrderRespType": "FULL",
        }

        if order_type == "LIMIT":
            normalized_price = self._normalize_price(symbol, request.price)
            if normalized_price is None:
                raise BrokerClientError("LIMIT orders require price")
            params["price"] = normalized_price
            params["timeInForce"] = "GTC"

        payload = self._signed_request("POST", "/api/v3/order", params)
        status = self.STATUS_MAP.get(str(payload.get("status", "NEW")).upper(), ExecutionStatus.SUBMITTED)
        executed_qty = float(payload.get("executedQty") or 0.0)

        avg_fill_price: Optional[float] = None
        fills = payload.get("fills")
        if isinstance(fills, list) and fills:
            filled_notional = 0.0
            filled_qty = 0.0
            for fill in fills:
                fill_price = float(fill.get("price") or 0.0)
                fill_qty = float(fill.get("qty") or 0.0)
                filled_notional += fill_price * fill_qty
                filled_qty += fill_qty
            if filled_qty > 0:
                avg_fill_price = filled_notional / filled_qty
        elif payload.get("price"):
            avg_fill_price = float(payload.get("price"))

        return BrokerOrderResponse(
            broker_order_id=str(payload.get("orderId")),
            status=status,
            symbol=symbol,
            side=side,
            quantity=float(payload.get("origQty") or quantity),
            filled_quantity=executed_qty,
            avg_fill_price=avg_fill_price,
            raw=payload,
        )

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        payload = self._signed_request("GET", "/api/v3/order", {"orderId": order_id})
        mapped_status = self.STATUS_MAP.get(str(payload.get("status", "NEW")).upper(), ExecutionStatus.SUBMITTED)
        return {
            "order_id": str(payload.get("orderId") or order_id),
            "status": mapped_status.value,
            "filled_quantity": float(payload.get("executedQty") or 0.0),
            "avg_fill_price": float(payload.get("price") or 0.0) if payload.get("price") else None,
            "raw": payload,
        }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        payload = self._signed_request("DELETE", "/api/v3/order", {"orderId": order_id})
        return {
            "order_id": str(payload.get("orderId") or order_id),
            "status": ExecutionStatus.CANCELLED.value,
            "raw": payload,
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        payload = self._signed_request("GET", "/api/v3/account", {})
        balances = payload.get("balances") or []
        positions: List[Dict[str, Any]] = []
        for item in balances:
            free_amount = float(item.get("free") or 0.0)
            locked_amount = float(item.get("locked") or 0.0)
            total = free_amount + locked_amount
            if total <= 0:
                continue
            positions.append(
                {
                    "asset": item.get("asset"),
                    "free": free_amount,
                    "locked": locked_amount,
                    "total": total,
                }
            )
        return positions

    def get_balance(self) -> Dict[str, Any]:
        payload = self._signed_request("GET", "/api/v3/account", {})
        balances = payload.get("balances") or []

        total_balance = 0.0
        available_balance = 0.0
        for item in balances:
            free_amount = float(item.get("free") or 0.0)
            locked_amount = float(item.get("locked") or 0.0)
            if (free_amount + locked_amount) <= 0:
                continue
            if item.get("asset") == "USDT":
                total_balance += free_amount + locked_amount
                available_balance += free_amount

        return {
            "broker": "binance",
            "total_balance": total_balance,
            "available_balance": available_balance,
            "raw": payload,
        }
