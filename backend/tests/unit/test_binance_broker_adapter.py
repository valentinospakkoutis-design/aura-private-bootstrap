from __future__ import annotations

from typing import Any, Dict

import pytest

from services.execution.binance_adapter import BinanceBrokerClient
from services.execution.broker_client import BrokerClientError

pytestmark = pytest.mark.unit


class _Response:
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def test_place_order_maps_partial_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BinanceBrokerClient(api_key="k", api_secret="s", testnet=True)

    monkeypatch.setattr(client, "_normalize_quantity", lambda symbol, qty: "0.1", raising=True)
    monkeypatch.setattr(client, "_normalize_price", lambda symbol, price: "1000", raising=True)
    monkeypatch.setattr(
        client,
        "_signed_request",
        lambda method, path, params: {
            "orderId": 123,
            "status": "PARTIALLY_FILLED",
            "symbol": "BTCUSDT",
            "origQty": "0.1",
            "executedQty": "0.04",
            "fills": [{"price": "1000", "qty": "0.04"}],
        },
        raising=True,
    )

    response = client.place_order(
        request=type("Req", (), {
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 0.1,
            "order_type": "market",
            "price": None,
            "client_order_id": "idem-1",
        })(),
    )

    assert response.status.value == "PARTIALLY_FILLED"
    assert response.broker_order_id == "123"
    assert response.symbol == "BTCUSDT"
    assert response.filled_quantity == pytest.approx(0.04)


def test_broker_error_mapping_is_explicit() -> None:
    client = BinanceBrokerClient(api_key="k", api_secret="s", testnet=True)
    with pytest.raises(BrokerClientError) as exc:
        client._handle_response(_Response(400, {"code": -2010, "msg": "Account has insufficient balance"}))

    assert "BINANCE_API_ERROR" in str(exc.value)
    assert "insufficient balance" in str(exc.value).lower()


def test_status_mapping_filled_failed_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BinanceBrokerClient(api_key="k", api_secret="s", testnet=True)

    states: Dict[str, str] = {
        "FILLED": "FILLED",
        "REJECTED": "FAILED",
        "CANCELED": "CANCELLED",
    }

    for broker_state, expected in states.items():
        monkeypatch.setattr(
            client,
            "_signed_request",
            lambda method, path, params, state=broker_state: {
                "orderId": 77,
                "status": state,
                "executedQty": "0.0",
            },
            raising=True,
        )
        status = client.get_order_status("77")
        assert status["status"] == expected
