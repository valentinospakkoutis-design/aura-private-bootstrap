"""
Security utilities for AURA
API key encryption, password hashing, etc.
"""

import os
import hashlib
import secrets
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import bcrypt


class SecurityManager:
    """
    Security manager for encryption and hashing
    """
    
    def __init__(self):
        # Get encryption key from environment or generate
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            # Generate key from machine ID (hardware-bound)
            machine_id = self._get_machine_id()
            key = self._derive_key(machine_id)
        
        if isinstance(key, str):
            key = key.strip()
            # If it's a hex string (not valid base64 Fernet key), derive a proper key from it
            try:
                decoded = base64.urlsafe_b64decode(key + '==')
                if len(decoded) != 32:
                    raise ValueError("not 32 bytes")
                key = key.encode()
            except Exception:
                # Derive a valid Fernet key from whatever string was provided
                key = key.encode()
                key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())

        if isinstance(key, bytes):
            self._master_key_bytes = key
        else:
            self._master_key_bytes = key.encode() if isinstance(key, str) else key
        self.cipher = Fernet(key)
    
    def _get_machine_id(self) -> str:
        """
        Get machine-specific ID for hardware-bound encryption
        """
        import platform
        import uuid
        
        # Combine machine info
        machine_info = f"{platform.node()}{platform.machine()}{platform.processor()}"
        # Add MAC address
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                       for elements in range(0,2*6,2)][::-1])
        
        return f"{machine_info}{mac}"
    
    def _derive_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """
        Derive encryption key from password using PBKDF2
        """
        if salt is None:
            salt = b"aura_salt_2025"  # In production, use random salt per user
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt_api_key(self, api_key: str) -> str:
        """
        Encrypt API key using Fernet (AES-128).
        Prepends a random 16-byte salt for per-key uniqueness.
        """
        salt = os.urandom(16)
        # Derive a per-key Fernet cipher from the master key + salt
        per_key_cipher = self._derive_cipher(salt)
        encrypted = per_key_cipher.encrypt(api_key.encode())
        # Store salt + encrypted together
        combined = salt + encrypted
        return base64.urlsafe_b64encode(combined).decode()

    def decrypt_api_key(self, encrypted_key: str) -> str:
        """
        Decrypt API key. Supports both new (salted) and legacy (unsalted) formats.
        """
        try:
            combined = base64.urlsafe_b64decode(encrypted_key.encode())
            # New format: first 16 bytes are salt
            if len(combined) > 16:
                salt = combined[:16]
                encrypted = combined[16:]
                try:
                    per_key_cipher = self._derive_cipher(salt)
                    return per_key_cipher.decrypt(encrypted).decode()
                except Exception:
                    pass  # fall through to legacy
            # Legacy format: no salt, use master cipher
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
            return self.cipher.decrypt(encrypted_bytes).decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt API key")

    def _derive_cipher(self, salt: bytes) -> Fernet:
        """Derive a Fernet cipher from master key + per-key salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        # Use the master key's encoded form as input to derive a per-key key
        master_key_bytes = self._master_key_bytes
        derived = base64.urlsafe_b64encode(kdf.derive(master_key_bytes))
        return Fernet(derived)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt
        
        Args:
            password: Plain text password
        
        Returns:
            Hashed password
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Plain text password
            hashed: Hashed password
        
        Returns:
            True if password matches
        """
        return bcrypt.checkpw(password.encode(), hashed.encode())
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """
        Generate secure random token
        
        Args:
            length: Token length in bytes
        
        Returns:
            URL-safe token
        """
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_api_key(prefix: str = "aura") -> str:
        """
        Generate API key
        
        Args:
            prefix: Key prefix
        
        Returns:
            API key string
        """
        random_part = secrets.token_urlsafe(24)
        return f"{prefix}_{random_part}"


# Global security manager instance
security_manager = SecurityManager()

