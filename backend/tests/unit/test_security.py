from __future__ import annotations

import pytest

from utils.error_handler import get_error_message
from utils.rate_limiter import rate_limiter
from utils.security import security_manager


pytestmark = pytest.mark.unit


def test_password_hashing() -> None:
    password = "test_password_123"
    hashed = security_manager.hash_password(password)

    assert hashed != password
    assert security_manager.verify_password(password, hashed)
    assert not security_manager.verify_password("wrong_password", hashed)


def test_api_key_encryption() -> None:
    api_key = "test_api_key_12345"
    encrypted = security_manager.encrypt_api_key(api_key)

    assert encrypted != api_key
    assert len(encrypted) > len(api_key)
    assert security_manager.decrypt_api_key(encrypted) == api_key


def test_token_generation() -> None:
    token1 = security_manager.generate_token()
    token2 = security_manager.generate_token()

    assert token1 != token2
    assert len(token1) >= 32
    assert len(token2) >= 32


def test_rate_limiting_first_request_is_allowed() -> None:
    import importlib

    rate_limiter_module = importlib.import_module("utils.rate_limiter")

    rate_limiter_module.cache_get = lambda key, default=None: None
    rate_limiter_module.cache_set = lambda key, value, expire=3600: False

    allowed, remaining_min, remaining_hour = rate_limiter.check("test_client_123")

    assert allowed is True
    assert remaining_min is not None
    assert remaining_hour is not None


def test_error_messages() -> None:
    assert get_error_message("VALIDATION_ERROR") == "Τα δεδομένα που εισήγαγες δεν είναι έγκυρα"
    assert get_error_message("NOT_FOUND") == "Το αντικείμενο που αναζητάς δεν βρέθηκε"
    assert get_error_message("UNKNOWN_ERROR", "Default message") == "Default message"