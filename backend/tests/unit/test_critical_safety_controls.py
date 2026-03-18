from __future__ import annotations

import importlib
import sys
import types
from typing import Any, Dict

import pytest
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.testclient import TestClient


pytestmark = pytest.mark.unit


def _install_main_import_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    precious_mod = types.ModuleType("ai.precious_metals")
    precious_mod.precious_metals_predictor = types.SimpleNamespace(
        predict_price=lambda *args, **kwargs: {},
        get_all_predictions=lambda *args, **kwargs: {},
    )

    asset_mod = types.ModuleType("ai.asset_predictor")

    class _AssetType(str):
        def __new__(cls, value):
            return str.__new__(cls, value)

    asset_mod.AssetType = _AssetType
    asset_mod.asset_predictor = types.SimpleNamespace(
        predict_price=lambda *args, **kwargs: {},
        get_all_predictions=lambda *args, **kwargs: {},
        get_trading_signal=lambda *args, **kwargs: {},
        get_all_signals=lambda *args, **kwargs: {},
        list_assets=lambda *args, **kwargs: {"assets": {}},
        get_asset_info=lambda *args, **kwargs: None,
        get_current_price=lambda *args, **kwargs: 0.0,
    )

    cms_mod = types.ModuleType("services.cms_service")
    cms_mod.cms_service = types.SimpleNamespace()

    voice_mod = types.ModuleType("services.voice_briefing")
    voice_mod.voice_briefing_service = types.SimpleNamespace()

    model_mod = types.ModuleType("ml.model_manager")
    model_mod.model_manager = types.SimpleNamespace(get_model_status=lambda: {})

    training_mod = types.ModuleType("ml.training_prep")
    training_mod.training_prep = types.SimpleNamespace(get_training_status=lambda: {})

    annotation_mod = types.ModuleType("ml.annotation_api")
    annotation_mod.router = APIRouter()

    market_data_pkg = types.ModuleType("market_data")
    market_data_mod = types.ModuleType("market_data.yfinance_client")
    market_data_mod.get_price = lambda *args, **kwargs: {"price": 100.0, "volume": 0.0}
    market_data_mod.get_historical_prices = lambda *args, **kwargs: []

    monkeypatch.setitem(sys.modules, "ai.precious_metals", precious_mod)
    monkeypatch.setitem(sys.modules, "ai.asset_predictor", asset_mod)
    monkeypatch.setitem(sys.modules, "services.cms_service", cms_mod)
    monkeypatch.setitem(sys.modules, "services.voice_briefing", voice_mod)
    monkeypatch.setitem(sys.modules, "ml.model_manager", model_mod)
    monkeypatch.setitem(sys.modules, "ml.training_prep", training_mod)
    monkeypatch.setitem(sys.modules, "ml.annotation_api", annotation_mod)
    monkeypatch.setitem(sys.modules, "market_data", market_data_pkg)
    monkeypatch.setitem(sys.modules, "market_data.yfinance_client", market_data_mod)


def _make_token(email: str, roles: list[str]) -> str:
    jwt_handler = importlib.import_module("auth.jwt_handler")
    return jwt_handler.create_access_token(
        {
            "sub": "1",
            "email": email,
            "full_name": "Test User",
            "roles": roles,
        }
    )


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _install_main_import_stubs(monkeypatch)
    sys.modules.pop("main", None)
    main = importlib.import_module("main")

    # Keep tests deterministic and isolated from local user files.
    monkeypatch.setattr(main, "users_db", {}, raising=True)
    monkeypatch.setattr(main, "save_users_db", lambda data: True, raising=True)

    return TestClient(main.app)


def test_unauthenticated_control_endpoint_is_rejected(app_client: TestClient) -> None:
    response = app_client.post("/api/trading/mode", json={"mode": "paper"})
    assert response.status_code == 401


def test_non_admin_cannot_change_trading_mode(app_client: TestClient) -> None:
    token = _make_token("trader@example.com", ["trader"])
    response = app_client.post(
        "/api/trading/mode",
        json={"mode": "paper"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_non_admin_cannot_update_risk_settings(app_client: TestClient) -> None:
    token = _make_token("trader@example.com", ["trader"])
    response = app_client.put(
        "/api/trading/risk-settings",
        json={"max_daily_loss_percent": 2.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_non_admin_cannot_toggle_kill_switch(app_client: TestClient) -> None:
    token = _make_token("trader@example.com", ["trader"])
    response = app_client.post(
        "/api/trading/kill-switch",
        json={"active": True, "scope": "global", "reason": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_risk_governor_block_prevents_new_order_submission(app_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    main = importlib.import_module("main")

    class _StubBroker:
        def get_market_price(self, symbol: str) -> Dict[str, Any]:
            return {"price": 100.0}

    monkeypatch.setattr(main, "broker_instances", {"binance": _StubBroker()}, raising=True)
    monkeypatch.setattr(main.risk_governor_service, "can_execute", lambda **kwargs: (False, "RISK_PRESERVATION_ACTIVE"), raising=True)

    token = _make_token("trader@example.com", ["trader"])
    response = app_client.post(
        "/api/brokers/order",
        json={
            "broker": "binance",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "risk-block-001",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "RISK_PRESERVATION_ACTIVE"


def test_execution_endpoint_without_token_is_rejected(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/brokers/order",
        json={
            "broker": "binance",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.01,
            "order_type": "MARKET",
        },
    )
    assert response.status_code == 401


def test_auth_login_invalid_credentials_does_not_raise_name_error(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "badpass"},
    )
    assert response.status_code == 401
    payload = response.json()
    assert "NameError" not in str(payload)


def test_register_stores_password_hash_not_plaintext(app_client: TestClient) -> None:
    main = importlib.import_module("main")

    response = app_client.post(
        "/register",
        data={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "SecretPass123",
            "confirmPassword": "SecretPass123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    user = main.users_db["alice@example.com"]
    assert "password_hash" in user
    assert "password" not in user


def test_login_failure_does_not_log_password_details(app_client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    main = importlib.import_module("main")
    security_manager = importlib.import_module("utils.security").security_manager

    main.users_db["bob@example.com"] = {
        "name": "Bob",
        "email": "bob@example.com",
        "password_hash": security_manager.hash_password("CorrectPassword123"),
        "roles": ["trader"],
    }

    attempted_password = "WrongPassword123"
    response = app_client.post(
        "/login",
        data={"email": "bob@example.com", "password": attempted_password},
        follow_redirects=False,
    )

    assert response.status_code == 303
    captured = capsys.readouterr()
    combined = (captured.out or "") + (captured.err or "")
    assert attempted_password not in combined
    assert "Stored:" not in combined


def test_missing_idempotency_key_is_rejected(app_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    main = importlib.import_module("main")

    class _StubBroker:
        def get_market_price(self, symbol: str) -> Dict[str, Any]:
            return {"price": 100.0}

    monkeypatch.setattr(main, "broker_instances", {"binance": _StubBroker()}, raising=True)

    token = _make_token("trader@example.com", ["trader"])
    response = app_client.post(
        "/api/brokers/order",
        json={
            "broker": "binance",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_same_idempotency_key_does_not_duplicate_order(app_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    main = importlib.import_module("main")
    paper_trading_service = importlib.import_module("services.paper_trading").paper_trading_service
    idempotency_module = importlib.import_module("services.idempotency")

    paper_trading_service.reset()

    class _StubBroker:
        def get_market_price(self, symbol: str) -> Dict[str, Any]:
            return {"price": 100.0}

    monkeypatch.setattr(main, "broker_instances", {"binance": _StubBroker()}, raising=True)

    service = idempotency_module.idempotency_service
    state: Dict[str, Dict[str, Any]] = {}

    def _begin_request(*, principal_id: str, endpoint: str, idempotency_key: str, request_fingerprint: str):
        key = f"{principal_id}:{idempotency_key}"
        existing = state.get(key)
        if existing is None:
            state[key] = {
                "request_fingerprint": request_fingerprint,
                "status": "processing",
                "result_payload": None,
            }
            return {"action": "proceed", "backend": "stub"}
        if existing["request_fingerprint"] != request_fingerprint:
            return {
                "action": "conflict",
                "http_status": 409,
                "error": "IDEMPOTENCY_KEY_REUSE_MISMATCH",
                "message": "mismatch",
            }
        if existing["status"] == "succeeded":
            return {"action": "replay", "existing": {"result_payload": existing["result_payload"]}}
        return {
            "action": "in_progress",
            "http_status": 409,
            "error": "IDEMPOTENCY_IN_PROGRESS",
            "message": "in progress",
        }

    def _finalize_success(*, principal_id: str, endpoint: str, idempotency_key: str, request_fingerprint: str, result_order_id: str, result_payload: Dict[str, Any]):
        key = f"{principal_id}:{idempotency_key}"
        state[key] = {
            "request_fingerprint": request_fingerprint,
            "status": "succeeded",
            "result_payload": result_payload,
        }

    monkeypatch.setattr(service, "begin_request", _begin_request, raising=True)
    monkeypatch.setattr(service, "finalize_success", _finalize_success, raising=True)
    monkeypatch.setattr(service, "finalize_failure", lambda **kwargs: None, raising=True)

    token = _make_token("trader@example.com", ["trader"])
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "fixed-order-key-001",
    }
    payload = {
        "broker": "binance",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": 1,
        "order_type": "MARKET",
    }

    first = app_client.post("/api/brokers/order", json=payload, headers=headers)
    second = app_client.post("/api/brokers/order", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert len(paper_trading_service.trade_history) == 1


def test_dedupe_backend_unavailable_rejects_submission(app_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    main = importlib.import_module("main")
    idempotency_module = importlib.import_module("services.idempotency")

    class _StubBroker:
        def get_market_price(self, symbol: str) -> Dict[str, Any]:
            return {"price": 100.0}

    monkeypatch.setattr(main, "broker_instances", {"binance": _StubBroker()}, raising=True)

    service = idempotency_module.idempotency_service

    def _raise_backend(*args, **kwargs):
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(service, "_redis_set", _raise_backend, raising=True)
    monkeypatch.setattr(service, "_redis_get", _raise_backend, raising=True)
    monkeypatch.setattr(service, "_db_get", _raise_backend, raising=True)

    token = _make_token("trader@example.com", ["trader"])
    response = app_client.post(
        "/api/brokers/order",
        json={
            "broker": "binance",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "down-backend-key-001",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "IDEMPOTENCY_UNAVAILABLE"


def test_rate_limiter_failure_blocks_sensitive_route(app_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    main = importlib.import_module("main")

    async def _raise_limiter(request, call_next):
        raise RuntimeError("limiter down")

    monkeypatch.setattr(main, "rate_limit_middleware", _raise_limiter, raising=True)

    response = app_client.get("/api/trading/mode")
    assert response.status_code == 503
    assert response.json()["error"] == "SECURITY_GUARD_UNAVAILABLE"


def test_jwt_secret_missing_or_weak_fails_module_load(monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = "auth.jwt_handler"

    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    sys.modules.pop(module_name, None)
    with pytest.raises(RuntimeError):
        importlib.import_module(module_name)

    monkeypatch.setenv("JWT_SECRET_KEY", "weak")
    sys.modules.pop(module_name, None)
    with pytest.raises(RuntimeError):
        importlib.import_module(module_name)

    monkeypatch.setenv("JWT_SECRET_KEY", "restored-super-secure-jwt-secret-0123456789")
    sys.modules.pop(module_name, None)
    importlib.import_module(module_name)


def test_live_execution_requires_validation_result() -> None:
    live_service = importlib.import_module("services.live_trading").LiveTradingService()
    live_service.set_trading_mode("live")

    result = live_service.execute_live_order(
        broker="binance",
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
    )

    assert "error" in result
    assert "validation" in result["error"].lower()


def test_symbol_scoped_kill_switch_blocks_matching_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    live_module = importlib.import_module("services.live_trading")
    kill_switch_module = importlib.import_module("ops.kill_switch")

    service = live_module.LiveTradingService()
    service.set_trading_mode("live")

    monkeypatch.setenv("EXECUTION_PROVIDER", "binance")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    monkeypatch.setenv("TRADING_MODE", "live")

    kill_switch_module.kill_switch_manager.activate(
        actor="admin@example.com",
        scope="symbol",
        value="BTCUSDT",
        reason="maintenance",
    )

    result = service.execute_live_order(
        broker="binance",
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.01,
        order_type="MARKET",
        validation_result={"valid": True, "errors": []},
        idempotency_key="idem-kill-symbol-1",
        user_email="trader@example.com",
        user_roles=["trader"],
        broker_adapter=types.SimpleNamespace(api_key="key", api_secret="secret", testnet=True),
        price=1000.0,
        stop_loss_price=990.0,
        idempotency_reserved=True,
    )

    assert result["error_code"] == "SYMBOL_KILL_SWITCH_ACTIVE"

    kill_switch_module.kill_switch_manager.deactivate(
        actor="admin@example.com",
        scope="symbol",
        value="BTCUSDT",
    )
