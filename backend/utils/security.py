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
            key = key.encode()
        
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
        Encrypt API key using Fernet (AES-128)
        
        Args:
            api_key: Plain text API key
        
        Returns:
            Encrypted API key (base64)
        """
        encrypted = self.cipher.encrypt(api_key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """
        Decrypt API key
        
        Args:
            encrypted_key: Encrypted API key
        
        Returns:
            Plain text API key
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt API key: {e}")
    
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

