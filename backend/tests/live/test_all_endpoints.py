from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif("AURA_LIVE_BASE_URL" not in os.environ, reason="Set AURA_LIVE_BASE_URL to run live endpoint tests."),
]


def test_full_endpoint_workflow(live_api_client) -> None:
    unique_email = f"live_{int(datetime.now(timezone.utc).timestamp())}@test.com"
    password = "testpass123"

    health = live_api_client.get("/health")
    assert health.status_code == 200

    register = live_api_client.post(
        "/auth/register",
        json={"email": unique_email, "password": password, "full_name": "Live Test User"},
    )
    assert register.status_code in {200, 201}
    register_payload = register.json()
    assert register_payload.get("access_token")

    auth_headers = {"Authorization": f"Bearer {register_payload['access_token']}"}

    current_user = live_api_client.get("/auth/me", headers=auth_headers)
    assert current_user.status_code == 200
    assert current_user.json().get("email") == unique_email

    assets = live_api_client.get("/assets")
    assert assets.status_code == 200

    news = live_api_client.get("/news", params={"limit": 5})
    assert news.status_code == 200

    csrf = live_api_client.get("/csrf-token")
    assert csrf.status_code == 200
    assert csrf.json().get("csrf_token")

    missing = live_api_client.get("/invalid-endpoint")
    assert missing.status_code == 404