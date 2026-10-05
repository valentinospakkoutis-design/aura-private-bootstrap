"""
conftest.py — pytest configuration for the backend test suite.

Excludes legacy integration scripts (test_endpoints.py, test_jwt_auth.py)
from automatic collection — these are manual scripts that hit a live server
at localhost:8000 and are not compatible with the unit-test runner.
"""

collect_ignore = [
    "test_endpoints.py",
    "test_jwt_auth.py",
]
