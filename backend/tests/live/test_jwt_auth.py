from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif("AURA_LIVE_BASE_URL" not in os.environ, reason="Set AURA_LIVE_BASE_URL to run live JWT tests."),
]


def test_jwt_auth_flow(live_api_client) -> None:
    email = f"jwt_{int(datetime.now(timezone.utc).timestamp())}@test.com"
    password = "testpass123"

    register = live_api_client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "JWT Test User"},
    )
    assert register.status_code in {200, 201}
    register_payload = register.json()
    assert register_payload.get("access_token")
    assert register_payload.get("refresh_token")

    login = live_api_client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    login_payload = login.json()
    assert login_payload.get("access_token")
    assert login_payload.get("refresh_token")

    current_user = live_api_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert current_user.status_code == 200
    assert current_user.json().get("email") == email

    refresh = live_api_client.post(
        "/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )
    assert refresh.status_code == 200
    assert refresh.json().get("access_token")