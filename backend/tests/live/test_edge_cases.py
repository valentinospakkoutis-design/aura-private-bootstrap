from __future__ import annotations

import os

import pytest


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif("AURA_LIVE_BASE_URL" not in os.environ, reason="Set AURA_LIVE_BASE_URL to run live edge-case tests."),
]


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "expected_statuses"),
    [
        ("post", "/auth/register", {"json": {"email": "", "password": "test", "full_name": "Test"}}, {400, 422}),
        ("get", "/prices/INVALID_ASSET_12345", {}, {400, 404}),
        ("post", "/portfolio/buy", {"json": {"asset_id": "XAUUSDT", "quantity": -10, "price": 2000}}, {400, 422}),
        ("post", "/portfolio/buy", {"json": {"asset_id": "XAUUSDT", "quantity": 1, "price": 0}}, {400, 422}),
        ("get", "/auth/me", {"headers": {"Authorization": "Bearer invalid_token_12345"}}, {401}),
        ("get", "/prices/" + ("A" * 200), {}, {400, 404, 422}),
        ("get", "/prices/<script>alert('xss')</script>", {}, {400, 404, 422}),
    ],
)
def test_live_edge_cases(live_api_client, method: str, path: str, kwargs: dict, expected_statuses: set[int]) -> None:
    response = getattr(live_api_client, method)(path, **kwargs)
    assert response.status_code in expected_statuses