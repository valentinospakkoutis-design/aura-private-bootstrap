"""
JWT Authentication Integration Tests
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from typing import Dict, Optional

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def print_success(msg: str):
    print(f"{Colors.GREEN}[+] {msg}{Colors.RESET}")


def print_error(msg: str):
    print(f"{Colors.RED}[-] {msg}{Colors.RESET}")


def print_info(msg: str):
    print(f"{Colors.BLUE}[*] {msg}{Colors.RESET}")


def test_register() -> Optional[Dict]:
    """Test user registration"""
    print_info("Testing registration...")
    
    test_email = f"test_{os.urandom(4).hex()}@test.com"
    data = {
        "email": test_email,
        "password": "testpass123",
        "full_name": "Test User"
    }
    
    try:
        response = requests.post(f"{API_BASE}/auth/register", json=data, timeout=5)
        if response.status_code == 201:
            result = response.json()
            print_success(f"Registration successful: {test_email}")
            return result
        else:
            print_error(f"Registration failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print_error(f"Registration error: {e}")
        return None


def test_login(email: str, password: str) -> Optional[Dict]:
    """Test user login"""
    print_info("Testing login...")
    
    data = {
        "email": email,
        "password": password
    }
    
    try:
        response = requests.post(f"{API_BASE}/auth/login", json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            print_success("Login successful")
            return result
        else:
            print_error(f"Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print_error(f"Login error: {e}")
        return None


def test_get_me(access_token: str) -> bool:
    """Test get current user"""
    print_info("Testing /auth/me...")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        response = requests.get(f"{API_BASE}/auth/me", headers=headers, timeout=5)
        if response.status_code == 200:
            user = response.json()
            print_success(f"Get user successful: {user.get('email')}")
            return True
        else:
            print_error(f"Get user failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print_error(f"Get user error: {e}")
        return False


def test_refresh_token(refresh_token: str) -> Optional[Dict]:
    """Test token refresh"""
    print_info("Testing token refresh...")
    
    data = {"refresh_token": refresh_token}
    
    try:
        response = requests.post(f"{API_BASE}/auth/refresh", json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            print_success("Token refresh successful")
            return result
        else:
            print_error(f"Token refresh failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print_error(f"Token refresh error: {e}")
        return None


def main():
    print_info("=" * 60)
    print_info("JWT Authentication Integration Tests")
    print_info("=" * 60)
    print()
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": 0
    }
    
    # Test registration
    results["total"] += 1
    test_email = f"test_{os.urandom(4).hex()}@test.com"
    register_result = test_register()
    if register_result:
        results["passed"] += 1
        access_token = register_result.get("access_token")
        refresh_token = register_result.get("refresh_token")
    else:
        results["failed"] += 1
        print_error("Cannot continue without registration")
        return
    
    print()
    
    # Test login
    results["total"] += 1
    login_result = test_login(test_email, "testpass123")
    if login_result:
        results["passed"] += 1
        access_token = login_result.get("access_token")
        refresh_token = login_result.get("refresh_token")
    else:
        results["failed"] += 1
    
    print()
    
    # Test get current user
    if access_token:
        results["total"] += 1
        if test_get_me(access_token):
            results["passed"] += 1
        else:
            results["failed"] += 1
        print()
    
    # Test token refresh
    if refresh_token:
        results["total"] += 1
        if test_refresh_token(refresh_token):
            results["passed"] += 1
        else:
            results["failed"] += 1
        print()
    
    # Summary
    print_info("=" * 60)
    print_info("Test Summary")
    print_info("=" * 60)
    print_success(f"Passed: {results['passed']}/{results['total']}")
    if results["failed"] > 0:
        print_error(f"Failed: {results['failed']}/{results['total']}")
    print()
    
    success_rate = (results["passed"] / results["total"] * 100) if results["total"] > 0 else 0
    print_info(f"Success Rate: {success_rate:.1f}%")


if __name__ == "__main__":
    main()

