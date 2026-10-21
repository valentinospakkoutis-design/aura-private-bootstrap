"""
conftest.py — pytest configuration for the backend test suite.

Excludes legacy integration scripts (test_endpoints.py, test_jwt_auth.py)
from automatic collection — these are manual scripts that hit a live server
at localhost:8000 and are not compatible with the unit-test runner.
"""

import os

collect_ignore = [
    "test_endpoints.py",
    "test_jwt_auth.py",
]


def pytest_configure(config):
    """
    Set required environment variables before any test module is imported.

    JWT_SECRET_KEY is validated at module-level in auth/jwt_handler.py — if it
    is missing the import raises RuntimeError and the whole collection fails.
    We use a deterministic CI-only sentinel so production code never sees a
    weak secret; the CI workflow overrides this with its own secret.
    """
    if not os.environ.get("JWT_SECRET_KEY"):
        os.environ["JWT_SECRET_KEY"] = "ci-test-only-secret-not-for-production-use-32x"
