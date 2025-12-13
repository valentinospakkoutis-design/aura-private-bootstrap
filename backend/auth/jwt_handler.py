"""
JWT Token Handler for AURA
Token generation, validation, and refresh
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict
import jwt
from jwt import PyJWTError
from fastapi import HTTPException, status
from utils.error_handler import AuthenticationError


# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "aura-secret-key-change-in-production-2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 minutes
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token
    
    Args:
        data: Data to encode in token (e.g., {"sub": user_id, "email": email})
        expires_delta: Optional expiration time
    
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict) -> str:
    """
    Create JWT refresh token
    
    Args:
        data: Data to encode in token
    
    Returns:
        Encoded refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Dict:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token to verify
        token_type: Expected token type ("access" or "refresh")
    
    Returns:
        Decoded token payload
    
    Raises:
        AuthenticationError: If token is invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify token type
        if payload.get("type") != token_type:
            raise AuthenticationError("Invalid token type")
        
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")
    except Exception as e:
        raise AuthenticationError(f"Token verification failed: {str(e)}")


def get_user_from_token(token: str) -> Dict:
    """
    Get user information from access token
    
    Args:
        token: JWT access token
    
    Returns:
        User information dict
    """
    try:
        payload = verify_token(token, "access")
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "full_name": payload.get("full_name")
        }
    except Exception as e:
        raise AuthenticationError(f"Failed to get user from token: {str(e)}")


def refresh_access_token(refresh_token: str) -> str:
    """
    Generate new access token from refresh token
    
    Args:
        refresh_token: Valid refresh token
    
    Returns:
        New access token
    """
    payload = verify_token(refresh_token, "refresh")
    
    # Create new access token with same user data
    new_token_data = {
        "sub": payload.get("sub"),
        "email": payload.get("email"),
        "full_name": payload.get("full_name")
    }
    
    return create_access_token(new_token_data)

