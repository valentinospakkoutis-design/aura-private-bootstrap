"""
Security testing
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.security import security_manager
from utils.error_handler import ValidationError, NotFoundError, AuthenticationError
from utils.rate_limiter import rate_limiter


def test_password_hashing():
    """Test password hashing and verification"""
    password = "test_password_123"
    hashed = security_manager.hash_password(password)
    
    assert hashed != password
    assert security_manager.verify_password(password, hashed)
    assert not security_manager.verify_password("wrong_password", hashed)


def test_api_key_encryption():
    """Test API key encryption and decryption"""
    api_key = "test_api_key_12345"
    encrypted = security_manager.encrypt_api_key(api_key)
    
    assert encrypted != api_key
    assert len(encrypted) > len(api_key)
    
    decrypted = security_manager.decrypt_api_key(encrypted)
    assert decrypted == api_key


def test_token_generation():
    """Test secure token generation"""
    token1 = security_manager.generate_token()
    token2 = security_manager.generate_token()
    
    assert token1 != token2
    assert len(token1) >= 32
    assert len(token2) >= 32


def test_rate_limiting():
    """Test rate limiting"""
    identifier = "test_client_123"
    
    # First request should be allowed
    allowed, remaining_min, remaining_hour = rate_limiter.check(identifier)
    assert allowed is True
    assert remaining_min is not None
    assert remaining_hour is not None


def test_error_messages():
    """Test error message handling"""
    from utils.error_handler import get_error_message
    
    assert get_error_message("VALIDATION_ERROR") == "Τα δεδομένα που εισήγαγες δεν είναι έγκυρα"
    assert get_error_message("NOT_FOUND") == "Το αντικείμενο που αναζητάς δεν βρέθηκε"
    assert get_error_message("UNKNOWN_ERROR", "Default message") == "Default message"


if __name__ == "__main__":
    print("Running security tests...")
    test_password_hashing()
    print("[+] Password hashing: OK")
    
    test_api_key_encryption()
    print("[+] API key encryption: OK")
    
    test_token_generation()
    print("[+] Token generation: OK")
    
    test_rate_limiting()
    print("[+] Rate limiting: OK")
    
    test_error_messages()
    print("[+] Error messages: OK")
    
    print("\n[+] All security tests passed!")

