"""
Input sanitization utilities for AURA
Protects against SQL injection, XSS, and other attacks
"""

import re
from typing import Any, Optional
from html import escape


def sanitize_string(value: str, max_length: Optional[int] = None, allow_special: bool = False) -> str:
    """
    Sanitize string input
    
    Args:
        value: String to sanitize
        max_length: Maximum length allowed
        allow_special: Allow special characters (for asset symbols)
    
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return str(value)
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Trim whitespace
    value = value.strip()
    
    # Limit length
    if max_length and len(value) > max_length:
        value = value[:max_length]
    
    # Remove potentially dangerous characters (unless allowed)
    if not allow_special:
        # Remove SQL injection patterns
        value = re.sub(r'[;\'"\\]', '', value)
        # Remove script tags
        value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
        # Remove HTML tags
        value = re.sub(r'<[^>]+>', '', value)
    
    return value


def sanitize_email(email: str) -> str:
    """
    Sanitize email address
    
    Args:
        email: Email to sanitize
    
    Returns:
        Sanitized email
    """
    if not email:
        return ""
    
    email = email.strip().lower()
    
    # Basic email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise ValueError("Invalid email format")
    
    return email


def sanitize_asset_id(asset_id: str) -> str:
    """
    Sanitize asset ID (allows alphanumeric and some special chars)
    
    Args:
        asset_id: Asset ID to sanitize
    
    Returns:
        Sanitized asset ID (uppercase)
    """
    if not asset_id:
        return ""
    
    # Allow alphanumeric, dash, underscore, and common trading symbols
    asset_id = re.sub(r'[^a-zA-Z0-9\-_/]', '', asset_id)
    asset_id = asset_id.upper()
    
    # Limit length
    if len(asset_id) > 50:
        asset_id = asset_id[:50]
    
    return asset_id


def sanitize_numeric(value: Any, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
    """
    Sanitize numeric input
    
    Args:
        value: Numeric value to sanitize
        min_value: Minimum allowed value
        max_value: Maximum allowed value
    
    Returns:
        Sanitized float
    """
    try:
        num = float(value)
        
        if min_value is not None and num < min_value:
            raise ValueError(f"Value must be >= {min_value}")
        
        if max_value is not None and num > max_value:
            raise ValueError(f"Value must be <= {max_value}")
        
        return num
    except (ValueError, TypeError):
        raise ValueError("Invalid numeric value")


def sanitize_quantity(quantity: float) -> float:
    """
    Sanitize trading quantity
    
    Args:
        quantity: Quantity to sanitize
    
    Returns:
        Sanitized quantity
    """
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    
    if quantity > 1e10:  # Reasonable upper limit
        raise ValueError("Quantity too large")
    
    return round(quantity, 8)  # Round to 8 decimal places


def sanitize_price(price: float) -> float:
    """
    Sanitize price
    
    Args:
        price: Price to sanitize
    
    Returns:
        Sanitized price
    """
    if price <= 0:
        raise ValueError("Price must be positive")
    
    if price > 1e15:  # Reasonable upper limit
        raise ValueError("Price too large")
    
    return round(price, 8)


def sanitize_dict(data: dict, schema: dict) -> dict:
    """
    Sanitize dictionary based on schema
    
    Args:
        data: Dictionary to sanitize
        schema: Schema defining sanitization rules
    
    Returns:
        Sanitized dictionary
    """
    sanitized = {}
    
    for key, rules in schema.items():
        if key not in data:
            continue
        
        value = data[key]
        sanitize_func = rules.get("sanitize")
        validate_func = rules.get("validate")
        
        if sanitize_func:
            value = sanitize_func(value)
        
        if validate_func and not validate_func(value):
            raise ValueError(f"Invalid value for {key}")
        
        sanitized[key] = value
    
    return sanitized


def escape_html(text: str) -> str:
    """
    Escape HTML characters
    
    Args:
        text: Text to escape
    
    Returns:
        Escaped text
    """
    return escape(text)


def prevent_sql_injection(value: str) -> str:
    """
    Remove SQL injection patterns
    
    Args:
        value: String to check
    
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return str(value)
    
    # Remove common SQL injection patterns
    dangerous_patterns = [
        r"(\bOR\b|\bAND\b)\s+\d+\s*=\s*\d+",
        r"(\bOR\b|\bAND\b)\s+['\"]\w+['\"]\s*=\s*['\"]\w+['\"]",
        r"UNION\s+SELECT",
        r"DROP\s+TABLE",
        r"DELETE\s+FROM",
        r"INSERT\s+INTO",
        r"UPDATE\s+\w+\s+SET",
        r"--",
        r"/\*",
        r"\*/",
    ]
    
    for pattern in dangerous_patterns:
        value = re.sub(pattern, '', value, flags=re.IGNORECASE)
    
    return value

