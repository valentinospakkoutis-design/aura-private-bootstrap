"""
Comprehensive Integration Tests for All AURA Backend Endpoints
Tests all API endpoints with various scenarios
"""

import requests
import json
from typing import Dict, Optional
from datetime import datetime

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Test credentials
TEST_EMAIL = f"test_{datetime.now().timestamp()}@test.com"
TEST_PASSWORD = "testpass123"
TEST_NAME = "Test User"

# Global tokens
access_token: Optional[str] = None
refresh_token: Optional[str] = None
csrf_token: Optional[str] = None


def print_test(name: str, status: str, details: str = ""):
    """Print test result"""
    status_symbol = "[OK]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[WARN]"
    print(f"{status_symbol} {name}: {status}")
    if details:
        print(f"   {details}")


def get_headers(include_csrf: bool = False) -> Dict[str, str]:
    """Get request headers"""
    headers = {
        "Content-Type": "application/json"
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if include_csrf and csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return headers


def test_health_check():
    """Test health check endpoint"""
    print("\n" + "="*60)
    print("Testing Health Check")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_test("Health Check", "PASS", f"Status: {data.get('status')}")
            return True
        else:
            print_test("Health Check", "FAIL", f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_test("Health Check", "FAIL", str(e))
        return False


def test_authentication():
    """Test authentication endpoints"""
    global access_token, refresh_token
    
    print("\n" + "="*60)
    print("Testing Authentication Endpoints")
    print("="*60)
    
    # Register
    try:
        register_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME
        }
        response = requests.post(
            f"{API_BASE}/auth/register",
            json=register_data,
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            print_test("Register", "PASS", f"User: {TEST_EMAIL}")
        else:
            print_test("Register", "FAIL", f"Status: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        print_test("Register", "FAIL", str(e))
        return False
    
    # Login
    try:
        login_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        response = requests.post(
            f"{API_BASE}/auth/login",
            json=login_data,
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print_test("Login", "PASS")
        else:
            print_test("Login", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_test("Login", "FAIL", str(e))
        return False
    
    # Get Current User
    try:
        response = requests.get(
            f"{API_BASE}/auth/me",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print_test("Get Current User", "PASS", f"Email: {data.get('email')}")
        else:
            print_test("Get Current User", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Get Current User", "FAIL", str(e))
    
    # Refresh Token
    if refresh_token:
        try:
            refresh_data = {"refresh_token": refresh_token}
            response = requests.post(
                f"{API_BASE}/auth/refresh",
                json=refresh_data,
                headers=get_headers(),
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                new_access = data.get("access_token")
                if new_access:
                    access_token = new_access
                    print_test("Refresh Token", "PASS")
                else:
                    print_test("Refresh Token", "FAIL", "No access token in response")
            else:
                print_test("Refresh Token", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            print_test("Refresh Token", "FAIL", str(e))
    
    return True


def test_assets():
    """Test asset endpoints"""
    print("\n" + "="*60)
    print("Testing Asset Endpoints")
    print("="*60)
    
    # Get All Assets
    try:
        response = requests.get(
            f"{API_BASE}/assets",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            asset_count = len(data) if isinstance(data, list) else 0
            print_test("Get All Assets", "PASS", f"Found {asset_count} assets")
        else:
            print_test("Get All Assets", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Get All Assets", "FAIL", str(e))
    
    # Get Asset Price
    test_assets = ["XAUUSDT", "BTCUSDT", "AAPL"]
    for asset in test_assets:
        try:
            response = requests.get(
                f"{API_BASE}/prices/{asset}",
                headers=get_headers(),
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                price = data.get("price", 0)
                print_test(f"Get Price ({asset})", "PASS", f"Price: ${price}")
            else:
                print_test(f"Get Price ({asset})", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            print_test(f"Get Price ({asset})", "FAIL", str(e))


def test_predictions():
    """Test prediction endpoints"""
    print("\n" + "="*60)
    print("Testing Prediction Endpoints")
    print("="*60)
    
    test_assets = ["XAUUSDT", "BTCUSDT"]
    for asset in test_assets:
        try:
            response = requests.post(
                f"{API_BASE}/predict/{asset}",
                headers=get_headers(),
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                predictions = data.get("predictions", [])
                print_test(f"Predict ({asset})", "PASS", f"{len(predictions)} predictions")
            else:
                print_test(f"Predict ({asset})", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            print_test(f"Predict ({asset})", "FAIL", str(e))


def test_portfolio():
    """Test portfolio endpoints"""
    print("\n" + "="*60)
    print("Testing Portfolio Endpoints")
    print("="*60)
    
    # Get Portfolio Positions
    try:
        response = requests.get(
            f"{API_BASE}/portfolio/positions",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            positions = len(data) if isinstance(data, list) else 0
            print_test("Get Positions", "PASS", f"{positions} positions")
        else:
            print_test("Get Positions", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Get Positions", "FAIL", str(e))
    
    # Get Portfolio Summary
    try:
        response = requests.get(
            f"{API_BASE}/portfolio/summary",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            print_test("Get Portfolio Summary", "PASS")
        else:
            print_test("Get Portfolio Summary", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Get Portfolio Summary", "FAIL", str(e))


def test_accuracy():
    """Test accuracy endpoints"""
    print("\n" + "="*60)
    print("Testing Accuracy Endpoints")
    print("="*60)
    
    # Get Overall Accuracy
    try:
        response = requests.get(
            f"{API_BASE}/accuracy",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            avg_accuracy = data.get("average_accuracy", 0)
            print_test("Get Overall Accuracy", "PASS", f"Avg: {avg_accuracy}%")
        else:
            print_test("Get Overall Accuracy", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Get Overall Accuracy", "FAIL", str(e))
    
    # Get Asset Accuracy
    try:
        response = requests.get(
            f"{API_BASE}/accuracy/XAUUSDT",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            print_test("Get Asset Accuracy", "PASS")
        else:
            print_test("Get Asset Accuracy", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Get Asset Accuracy", "FAIL", str(e))


def test_news():
    """Test news endpoints"""
    print("\n" + "="*60)
    print("Testing News Endpoints")
    print("="*60)
    
    # Get News
    try:
        response = requests.get(
            f"{API_BASE}/news?limit=5",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])
            print_test("Get News", "PASS", f"{len(articles)} articles")
        else:
            print_test("Get News", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Get News", "FAIL", str(e))


def test_csrf():
    """Test CSRF token endpoint"""
    global csrf_token
    
    print("\n" + "="*60)
    print("Testing CSRF Endpoint")
    print("="*60)
    
    try:
        response = requests.get(
            f"{API_BASE}/csrf-token",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            csrf_token = data.get("csrf_token")
            print_test("Get CSRF Token", "PASS", f"Token: {csrf_token[:20]}...")
        else:
            print_test("Get CSRF Token", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Get CSRF Token", "FAIL", str(e))


def test_error_handling():
    """Test error handling scenarios"""
    print("\n" + "="*60)
    print("Testing Error Handling")
    print("="*60)
    
    # Invalid endpoint
    try:
        response = requests.get(
            f"{API_BASE}/invalid-endpoint",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code == 404:
            print_test("404 Error Handling", "PASS")
        else:
            print_test("404 Error Handling", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("404 Error Handling", "FAIL", str(e))
    
    # Invalid asset
    try:
        response = requests.get(
            f"{API_BASE}/prices/INVALIDASSET123",
            headers=get_headers(),
            timeout=5
        )
        if response.status_code in [404, 400]:
            print_test("Invalid Asset Error", "PASS")
        else:
            print_test("Invalid Asset Error", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Invalid Asset Error", "FAIL", str(e))
    
    # Unauthorized access
    try:
        response = requests.get(
            f"{API_BASE}/auth/me",
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if response.status_code == 401:
            print_test("Unauthorized Error", "PASS")
        else:
            print_test("Unauthorized Error", "FAIL", f"Status: {response.status_code}")
    except Exception as e:
        print_test("Unauthorized Error", "FAIL", str(e))


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AURA Backend - Comprehensive Integration Tests")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Test User: {TEST_EMAIL}")
    print("="*60)
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": 0
    }
    
    # Run tests
    tests = [
        ("Health Check", test_health_check),
        ("Authentication", test_authentication),
        ("Assets", test_assets),
        ("Predictions", test_predictions),
        ("Portfolio", test_portfolio),
        ("Accuracy", test_accuracy),
        ("News", test_news),
        ("CSRF", test_csrf),
        ("Error Handling", test_error_handling),
    ]
    
    for test_name, test_func in tests:
        try:
            if test_func():
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            print(f"[FAIL] {test_name} crashed: {e}")
            results["failed"] += 1
        results["total"] += 1
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total Tests: {results['total']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Success Rate: {(results['passed']/results['total']*100):.1f}%")
    print("="*60)


if __name__ == "__main__":
    main()

