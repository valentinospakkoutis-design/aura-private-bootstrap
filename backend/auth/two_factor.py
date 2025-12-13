"""
Two-Factor Authentication (2FA) for AURA
TOTP-based 2FA using pyotp
"""

import os
import secrets
import qrcode
import io
import base64
from typing import Dict, Optional
import pyotp
from utils.error_handler import AuthenticationError


def generate_2fa_secret() -> str:
    """
    Generate a new 2FA secret
    
    Returns:
        Base32 encoded secret
    """
    return pyotp.random_base32()


def generate_qr_code(secret: str, email: str, issuer: str = "AURA") -> str:
    """
    Generate QR code for 2FA setup
    
    Args:
        secret: 2FA secret
        email: User email
        issuer: Service name
    
    Returns:
        Base64 encoded QR code image
    """
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name=issuer
    )
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"


def generate_backup_codes(count: int = 10) -> list[str]:
    """
    Generate backup codes for 2FA
    
    Args:
        count: Number of backup codes to generate
    
    Returns:
        List of backup codes
    """
    return [secrets.token_urlsafe(8).upper() for _ in range(count)]


def verify_2fa_token(secret: str, token: str) -> bool:
    """
    Verify a 2FA TOTP token
    
    Args:
        secret: 2FA secret
        token: TOTP token to verify
    
    Returns:
        True if token is valid
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)  # Allow 1 time step tolerance


def verify_backup_code(backup_codes: list[str], code: str) -> tuple[bool, list[str]]:
    """
    Verify and consume a backup code
    
    Args:
        backup_codes: List of valid backup codes
        code: Backup code to verify
    
    Returns:
        (is_valid, remaining_codes)
    """
    code_upper = code.upper().strip()
    if code_upper in backup_codes:
        remaining = [c for c in backup_codes if c != code_upper]
        return True, remaining
    return False, backup_codes

