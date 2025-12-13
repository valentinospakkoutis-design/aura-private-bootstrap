"""
Edge Case Testing for AURA Backend
Tests edge cases, empty states, network failures, etc.
"""

import requests
from typing import Dict, Optional
from datetime import datetime

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Test credentials
TEST_EMAIL = f"edge_test_{datetime.now().timestamp()}@test.com"
TEST_PASSWORD = "testpass123"
access_token: Optional[str] = None


def print_test(name: str, status: str, details: str = ""):
    """Print test result"""
    status_symbol = "[OK]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[WARN]"
    print(f"{status_symbol} {name}: {status}")
    if details:
        print(f"   {details}")


def get_headers() -> Dict[str, str]:
    """Get request headers"""
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def test_empty_inputs():
    """Test endpoints with empty/invalid inputs"""
    print("\n" + "="*60)
    print("Testing Empty/Invalid Inputs")
    print("="*60)
    
    # Empty email
    try:
        response = requests.post(
            f"{API_BASE}/auth/register",
            json={"email": "", "password": "test", "full_name": "Test"},
            headers=get_headers(),
            timeout=5
        )
        if response.status_code in [400, 422]:
            print_test("Empty Email Validation", "PASS")
        else:
            print_test("Empty Email Validation", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Empty Email Validation", "FAIL", str(e))
    
    # Invalid asset ID
    try:
        response = requests.get(
            f"{API_BASE}/prices/INVALID_ASSET_12345",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code in [404, 400]:
            print_test("Invalid Asset ID", "PASS")
        else:
            print_test("Invalid Asset ID", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Invalid Asset ID", "FAIL", str(e))
    
    # Negative quantity
    try:
        response = requests.post(
            f"{API_BASE}/portfolio/buy",
            json={"asset_id": "XAUUSDT", "quantity": -10, "price": 2000},
            headers=get_headers(),
            timeout=5
        )
        if response.status_code in [400, 422]:
            print_test("Negative Quantity Validation", "PASS")
        else:
            print_test("Negative Quantity Validation", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Negative Quantity Validation", "FAIL", str(e))
    
    # Zero price
    try:
        response = requests.post(
            f"{API_BASE}/portfolio/buy",
            json={"asset_id": "XAUUSDT", "quantity": 1, "price": 0},
            headers=get_headers(),
            timeout=5
        )
        if response.status_code in [400, 422]:
            print_test("Zero Price Validation", "PASS")
        else:
            print_test("Zero Price Validation", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Zero Price Validation", "FAIL", str(e))


def test_missing_authentication():
    """Test endpoints without authentication"""
    print("\n" + "="*60)
    print("Testing Missing Authentication")
    print("="*60)
    
    # Get assets without auth (should work if public)
    try:
        response = requests.get(
            f"{API_BASE}/assets",
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        # Some endpoints might be public
        if response.status_code in [200, 401]:
            print_test("Get Assets (No Auth)", "PASS", f"Status: {response.status_code}")
        else:
            print_test("Get Assets (No Auth)", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Get Assets (No Auth)", "FAIL", str(e))
    
    # Protected endpoint without auth
    try:
        response = requests.get(
            f"{API_BASE}/auth/me",
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if response.status_code == 401:
            print_test("Protected Endpoint (No Auth)", "PASS")
        else:
            print_test("Protected Endpoint (No Auth)", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Protected Endpoint (No Auth)", "FAIL", str(e))


def test_invalid_tokens():
    """Test with invalid tokens"""
    print("\n" + "="*60)
    print("Testing Invalid Tokens")
    print("="*60)
    
    # Invalid token format
    try:
        response = requests.get(
            f"{API_BASE}/auth/me",
            headers={"Authorization": "Bearer invalid_token_12345"},
            timeout=5
        )
        if response.status_code == 401:
            print_test("Invalid Token Format", "PASS")
        else:
            print_test("Invalid Token Format", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Invalid Token Format", "FAIL", str(e))
    
    # Expired token (if we had one)
    try:
        response = requests.get(
            f"{API_BASE}/auth/me",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"},
            timeout=5
        )
        if response.status_code == 401:
            print_test("Expired/Invalid Token", "PASS")
        else:
            print_test("Expired/Invalid Token", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Expired/Invalid Token", "FAIL", str(e))


def test_large_inputs():
    """Test with very large inputs"""
    print("\n" + "="*60)
    print("Testing Large Inputs")
    print("="*60)
    
    # Very large quantity
    try:
        response = requests.post(
            f"{API_BASE}/portfolio/buy",
            json={"asset_id": "XAUUSDT", "quantity": 1e10, "price": 2000},
            headers=get_headers(),
            timeout=5
        )
        # Should either accept or reject gracefully
        if response.status_code in [200, 400, 422]:
            print_test("Very Large Quantity", "PASS", f"Status: {response.status_code}")
        else:
            print_test("Very Large Quantity", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Very Large Quantity", "FAIL", str(e))
    
    # Very long asset ID
    try:
        long_asset = "A" * 1000
        response = requests.get(
            f"{API_BASE}/prices/{long_asset}",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code in [400, 404, 422]:
            print_test("Very Long Asset ID", "PASS")
        else:
            print_test("Very Long Asset ID", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Very Long Asset ID", "FAIL", str(e))


def test_special_characters():
    """Test with special characters"""
    print("\n" + "="*60)
    print("Testing Special Characters")
    print("="*60)
    
    # SQL injection attempt
    try:
        sql_injection = "'; DROP TABLE users; --"
        response = requests.get(
            f"{API_BASE}/prices/{sql_injection}",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code in [400, 404, 422]:
            print_test("SQL Injection Attempt", "PASS")
        else:
            print_test("SQL Injection Attempt", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("SQL Injection Attempt", "FAIL", str(e))
    
    # XSS attempt
    try:
        xss_attempt = "<script>alert('xss')</script>"
        response = requests.get(
            f"{API_BASE}/prices/{xss_attempt}",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code in [400, 404, 422]:
            print_test("XSS Attempt", "PASS")
        else:
            print_test("XSS Attempt", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("XSS Attempt", "FAIL", str(e))


def test_empty_responses():
    """Test endpoints that might return empty responses"""
    print("\n" + "="*60)
    print("Testing Empty Responses")
    print("="*60)
    
    # Portfolio with no positions
    try:
        response = requests.get(
            f"{API_BASE}/portfolio/positions",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                print_test("Empty Portfolio", "PASS", f"Positions: {len(data)}")
            else:
                print_test("Empty Portfolio", "PASS")
        else:
            print_test("Empty Portfolio", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Empty Portfolio", "FAIL", str(e))
    
    # News with no articles
    try:
        response = requests.get(
            f"{API_BASE}/news?limit=0",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])
            print_test("Empty News", "PASS", f"Articles: {len(articles)}")
        else:
            print_test("Empty News", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Empty News", "FAIL", str(e))


def main():
    """Run all edge case tests"""
    print("\n" + "="*60)
    print("AURA Backend - Edge Case Testing")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print("="*60)
    
    # Register test user
    try:
        register_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": "Edge Test User"
        }
        response = requests.post(
            f"{API_BASE}/auth/register",
            json=register_data,
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            global access_token
            access_token = data.get("access_token")
            print(f"[OK] Registered test user: {TEST_EMAIL}")
    except Exception as e:
        print(f"[WARN] Could not register test user: {e}")
    
    # Run tests
    tests = [
        ("Empty/Invalid Inputs", test_empty_inputs),
        ("Missing Authentication", test_missing_authentication),
        ("Invalid Tokens", test_invalid_tokens),
        ("Large Inputs", test_large_inputs),
        ("Special Characters", test_special_characters),
        ("Empty Responses", test_empty_responses),
    ]
    
    results = {"passed": 0, "failed": 0, "total": 0}
    
    for test_name, test_func in tests:
        try:
            test_func()
            results["total"] += 1
        except Exception as e:
            print(f"[FAIL] {test_name} crashed: {e}")
            results["failed"] += 1
    
    # Summary
    print("\n" + "="*60)
    print("EDGE CASE TEST SUMMARY")
    print("="*60)
    print(f"Total Test Categories: {results['total']}")
    print(f"[OK] Completed: {results['total'] - results['failed']}")
    if results["failed"] > 0:
        print(f"[FAIL] Failed: {results['failed']}")
    print("="*60)


if __name__ == "__main__":
    main()

