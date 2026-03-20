#!/usr/bin/env python3
"""
BINANCE AUTHENTICATION TEST - HETZNER STATIC IP VERIFICATION
Executes ONLY from Hetzner server (116.203.75.114)
Safety: READ-ONLY + SIGNED requests, NO order placement
"""

import os
import sys
import json
import socket
import time
import hashlib
import hmac
from urllib.parse import urlencode
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: requests library not found. Installing...")
    os.system("pip install requests -q")
    import requests


def get_hostname():
    """Get current machine hostname"""
    return socket.gethostname()


def get_public_ip():
    """Detect public IP via ipify"""
    try:
        response = requests.get("https://api.ipify.org", timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        return f"FAILED: {str(e)}"
    return "UNKNOWN"


def verify_hetzner_ip():
    """Verify we're running from Hetzner static IP"""
    expected_ip = "116.203.75.114"
    detected_ip = get_public_ip()
    
    if detected_ip != expected_ip:
        print(f"\n❌ ENVIRONMENT ERROR: Not running from Hetzner static IP")
        print(f"   Expected: {expected_ip}")
        print(f"   Detected: {detected_ip}")
        sys.exit(1)
    
    return True


def load_env_variables():
    """Load and validate Binance API credentials"""
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    
    if not api_key or not api_secret:
        print("\n❌ ENV ERROR: BINANCE_API_KEY or BINANCE_API_SECRET not set")
        sys.exit(1)
    
    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "api_key_preview": f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) >= 8 else "****",
        "api_secret_preview": f"[REDACTED]"
    }


def network_check():
    """Check connectivity to Binance public API"""
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/ping",
            timeout=10
        )
        if response.status_code == 200:
            return True, "HTTP 200 OK"
    except requests.exceptions.Timeout:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)
    
    return False, f"HTTP {response.status_code}"


def sign_request(query_string, api_secret):
    """Generate HMAC-SHA256 signature for Binance request"""
    return hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def signed_auth_test(api_key, api_secret):
    """
    Test signed authentication with Binance
    GET /api/v3/account - requires valid signature + valid IP whitelist
    """
    try:
        # Build request parameters
        timestamp = int(time.time() * 1000)
        params = {
            "recvWindow": 5000,
            "timestamp": timestamp
        }
        
        # Create query string
        query_string = urlencode(params)
        
        # Sign the request
        signature = sign_request(query_string, api_secret)
        params["signature"] = signature
        
        # Make signed request
        headers = {
            "X-MBX-APIKEY": api_key,
            "Accept": "application/json"
        }
        
        response = requests.get(
            "https://api.binance.com/api/v3/account",
            params=params,
            headers=headers,
            timeout=10
        )
        
        # Parse response
        data = response.json()
        
        if response.status_code == 200:
            return True, data
        else:
            # Binance error response
            error_code = data.get("code", "UNKNOWN")
            error_msg = data.get("msg", "Unknown error")
            return False, {
                "code": error_code,
                "msg": error_msg,
                "http_status": response.status_code
            }
    
    except Exception as e:
        return False, {"error": str(e)}


def account_access_validation(account_data):
    """Validate account response structure"""
    try:
        can_trade = account_data.get("canTrade", False)
        account_type = account_data.get("accountType", "UNKNOWN")
        balances = account_data.get("balances", [])
        
        return {
            "can_trade": can_trade,
            "account_type": account_type,
            "balances_count": len(balances),
            "valid": can_trade is not None
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def permissions_validation(account_data):
    """Validate trading permissions"""
    try:
        can_trade = account_data.get("canTrade", False)
        permissions = account_data.get("permissions", [])
        
        has_spot = "SPOT" in permissions
        
        return {
            "can_trade": can_trade,
            "permissions": permissions,
            "has_spot": has_spot,
            "valid": can_trade and has_spot
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def symbol_check(api_key, api_secret):
    """Verify BTCUSDT symbol exists in exchange info"""
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/exchangeInfo",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            symbols = [s["symbol"] for s in data.get("symbols", [])]
            btcusdt_exists = "BTCUSDT" in symbols
            
            return btcusdt_exists, {"exists": btcusdt_exists, "total_symbols": len(symbols)}
        else:
            return False, {"error": f"HTTP {response.status_code}"}
    
    except Exception as e:
        return False, {"error": str(e)}


def main():
    """Execute full 8-step Binance authentication test"""
    
    print("\n" + "="*70)
    print("BINANCE AUTHENTICATION TEST - HETZNER STATIC IP VERIFICATION")
    print("="*70)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "environment": {},
        "checks": {},
        "safety": {"no_orders_placed": True, "no_state_changes": True}
    }
    
    # STEP 1: VERIFY EXECUTION ENVIRONMENT
    print("\n[STEP 1] Verifying execution environment...")
    hostname = get_hostname()
    public_ip = get_public_ip()
    
    print(f"  Hostname: {hostname}")
    print(f"  Public IP: {public_ip}")
    
    results["environment"]["hostname"] = hostname
    results["environment"]["public_ip"] = public_ip
    
    # Validate Hetzner IP
    try:
        verify_hetzner_ip()
        print("  ✅ IP whitelist check: PASS")
        results["checks"]["ip_verification"] = "PASS"
    except SystemExit:
        results["checks"]["ip_verification"] = "FAIL"
        print(json.dumps(results, indent=2))
        return
    
    # STEP 2: LOAD ENV VARIABLES
    print("\n[STEP 2] Loading environment variables...")
    try:
        env_data = load_env_variables()
        print(f"  BINANCE_API_KEY: {env_data['api_key_preview']}")
        print(f"  BINANCE_API_SECRET: {env_data['api_secret_preview']}")
        print("  ✅ Env Check: PASS")
        results["checks"]["env_check"] = "PASS"
    except SystemExit:
        results["checks"]["env_check"] = "FAIL"
        print(json.dumps(results, indent=2))
        return
    
    # STEP 3: NETWORK CHECK
    print("\n[STEP 3] Network connectivity check...")
    network_ok, network_msg = network_check()
    if network_ok:
        print(f"  GET /api/v3/ping: {network_msg}")
        print("  ✅ Network: PASS")
        results["checks"]["network"] = "PASS"
    else:
        print(f"  ❌ Network: FAIL - {network_msg}")
        results["checks"]["network"] = "FAIL"
        print(json.dumps(results, indent=2))
        return
    
    # STEP 4: SIGNED AUTHENTICATION TEST
    print("\n[STEP 4] Signed authentication test...")
    auth_ok, auth_data = signed_auth_test(env_data["api_key"], env_data["api_secret"])
    
    if auth_ok:
        print("  GET /api/v3/account (signed): HTTP 200")
        print("  ✅ Authentication: PASS")
        results["checks"]["authentication"] = "PASS"
        account_data = auth_data
    else:
        error_code = auth_data.get("code", "UNKNOWN")
        error_msg = auth_data.get("msg", auth_data.get("error", "Unknown error"))
        print(f"  ❌ Authentication: FAIL")
        print(f"     Error Code: {error_code}")
        print(f"     Error Message: {error_msg}")
        results["checks"]["authentication"] = "FAIL"
        results["checks"]["auth_error"] = {"code": error_code, "msg": error_msg}
        print(json.dumps(results, indent=2))
        return
    
    # STEP 5: ACCOUNT ACCESS VALIDATION
    print("\n[STEP 5] Account access validation...")
    account_validation = account_access_validation(account_data)
    
    if account_validation.get("valid"):
        print(f"  Account Type: {account_validation['account_type']}")
        print(f"  Can Trade: {account_validation['can_trade']}")
        print(f"  Balances Count: {account_validation['balances_count']}")
        print("  ✅ Account Access: PASS")
        results["checks"]["account_access"] = "PASS"
        results["checks"]["account_info"] = account_validation
    else:
        print(f"  ❌ Account Access: FAIL")
        print(f"     Error: {account_validation.get('error', 'Unknown')}")
        results["checks"]["account_access"] = "FAIL"
        print(json.dumps(results, indent=2))
        return
    
    # STEP 6: PERMISSIONS VALIDATION
    print("\n[STEP 6] Permissions validation...")
    permissions = permissions_validation(account_data)
    
    if permissions.get("valid"):
        print(f"  Can Trade: {permissions['can_trade']}")
        print(f"  Has SPOT: {permissions['has_spot']}")
        print(f"  Permissions: {permissions['permissions']}")
        print("  ✅ Permissions: PASS")
        results["checks"]["permissions"] = "PASS"
    else:
        print(f"  ❌ Permissions: FAIL")
        print(f"     Details: {permissions}")
        results["checks"]["permissions"] = "FAIL"
        print(json.dumps(results, indent=2))
        return
    
    # STEP 7: SYMBOL CHECK
    print("\n[STEP 7] Symbol check...")
    symbol_ok, symbol_data = symbol_check(env_data["api_key"], env_data["api_secret"])
    
    if symbol_ok:
        print(f"  BTCUSDT exists: {symbol_data['exists']}")
        print(f"  Total symbols: {symbol_data['total_symbols']}")
        print("  ✅ Symbol Check: PASS")
        results["checks"]["symbol_check"] = "PASS"
    else:
        print(f"  ❌ Symbol Check: FAIL")
        print(f"     Error: {symbol_data.get('error', 'Unknown')}")
        results["checks"]["symbol_check"] = "FAIL"
        print(json.dumps(results, indent=2))
        return
    
    # STEP 8: FINAL OUTPUT
    print("\n" + "="*70)
    print("FINAL VALIDATION REPORT")
    print("="*70)
    
    results["overall_verdict"] = "READY"
    
    print(f"\nExecution Hostname: {hostname}")
    print(f"Detected Public IP: {public_ip}")
    print(f"\nValidation Results:")
    print(f"  Env Check: ✅ PASS")
    print(f"  Network: ✅ PASS")
    print(f"  Authentication: ✅ PASS")
    print(f"  Account Access: ✅ PASS")
    print(f"  Permissions: ✅ PASS")
    print(f"  Symbol Check: ✅ PASS")
    
    print(f"\nSafety Confirmation:")
    print(f"  • NO orders placed: TRUE ✅")
    print(f"  • NO account state modified: TRUE ✅")
    
    print(f"\n🎯 FINAL VERDICT: READY FOR LIVE TRADING ✅")
    print("\n" + "="*70)
    
    # Output JSON results
    print("\nJSON Output:")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
