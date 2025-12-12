"""
Test script for all API endpoints
"""

import requests
import json
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


def test_endpoint(method: str, path: str, expected_status: int = 200, data: Optional[Dict] = None, headers: Optional[Dict] = None) -> bool:
    """
    Test an endpoint
    """
    url = f"{API_BASE}{path}" if path.startswith("/") else f"{BASE_URL}{path}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=5)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers, timeout=5)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, timeout=5)
        else:
            print_error(f"Unsupported method: {method}")
            return False
        
        if response.status_code == expected_status:
            print_success(f"{method} {path} - Status: {response.status_code}")
            try:
                result = response.json()
                if isinstance(result, dict) and len(result) < 100:
                    print_info(f"  Response: {json.dumps(result, indent=2)[:200]}")
            except:
                pass
            return True
        else:
            print_error(f"{method} {path} - Expected {expected_status}, got {response.status_code}")
            try:
                error = response.json()
                print_error(f"  Error: {error}")
            except:
                print_error(f"  Response: {response.text[:200]}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"{method} {path} - Connection error: {e}")
        return False


def main():
    print_info("=" * 60)
    print_info("AURA Backend API - Endpoint Testing")
    print_info("=" * 60)
    print()
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": 0
    }
    
    # Health Check
    print_info("Testing Health Endpoints...")
    results["total"] += 1
    if test_endpoint("GET", "/api/v1/health"):
        results["passed"] += 1
    else:
        results["failed"] += 1
    print()
    
    # Assets
    print_info("Testing Asset Endpoints...")
    results["total"] += 1
    if test_endpoint("GET", "/api/v1/assets"):
        results["passed"] += 1
    else:
        results["failed"] += 1
    print()
    
    # Price endpoints
    print_info("Testing Price Endpoints...")
    test_symbols = ["AAPL", "BTCUSDT", "XAUUSDT"]
    for symbol in test_symbols:
        results["total"] += 1
        if test_endpoint("GET", f"/api/v1/price/{symbol}"):
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        results["total"] += 1
        if test_endpoint("GET", f"/api/v1/prices/{symbol}/historical?period=1M"):
            results["passed"] += 1
        else:
            results["failed"] += 1
    print()
    
    # Predictions
    print_info("Testing Prediction Endpoints...")
    for symbol in test_symbols[:2]:  # Test first 2
        results["total"] += 1
        if test_endpoint("GET", f"/api/v1/predictions/{symbol}"):
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

