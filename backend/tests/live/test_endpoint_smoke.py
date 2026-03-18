from __future__ import annotations

import os

import pytest


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif("AURA_LIVE_BASE_URL" not in os.environ, reason="Set AURA_LIVE_BASE_URL to run live endpoint smoke tests."),
]


@pytest.mark.parametrize(
    ("path", "status_code"),
    [
        ("/health", 200),
        ("/assets", 200),
        ("/prices/BTCUSDT", 200),
        ("/prices/AAPL", 200),
    ],
)
def test_public_endpoint_smoke(live_api_client, path: str, status_code: int) -> None:
    response = live_api_client.get(path)
    assert response.status_code == status_code