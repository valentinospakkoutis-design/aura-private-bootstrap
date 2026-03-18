from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("JWT_SECRET_KEY", "test-only-super-secure-jwt-secret-0123456789")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def reset_rate_limiter_state() -> None:
    module = None
    try:
        module = importlib.import_module("utils.rate_limiter")
        module._rate_limit_store.clear()
    except Exception:
        module = None
    yield
    if module is not None:
        module._rate_limit_store.clear()


@pytest.fixture(scope="session")
def aura_live_base_url() -> str:
    base_url = os.getenv("AURA_LIVE_BASE_URL")
    if not base_url:
        pytest.skip("Set AURA_LIVE_BASE_URL to run live tests.")
    return base_url.rstrip("/")


@pytest.fixture(scope="session")
def live_api_base(aura_live_base_url: str) -> str:
    return f"{aura_live_base_url}/api/v1"


@pytest.fixture
def live_api_client(live_api_base: str):
    import httpx

    with httpx.Client(base_url=live_api_base, timeout=5.0, follow_redirects=True) as client:
        yield client