"""
Security utilities for bin2nlp application.

This module provides encryption capabilities for sensitive data storage,
particularly API keys for user-configured LLM providers.
"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet


class ProviderCredentialManager:
    """
    Manages encryption and decryption of LLM provider credentials.
    
    Uses Fernet symmetric encryption to securely store API keys in the database.
    The encryption key can be provided via environment variable or generated
    ephemeral keys for development.
    """
    
    def __init__(self) -> None:
        """Initialize the credential manager with encryption key."""
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
    
    def _get_or_create_encryption_key(self) -> bytes:
        """
        Get encryption key from environment or generate ephemeral key.
        
        Returns:
            bytes: Encryption key for Fernet cipher
            
        Notes:
            - In production, LLM_PROVIDER_ENCRYPTION_KEY should be set
            - In development, generates ephemeral key (data won't survive restarts)
            - Key should be base64-encoded 32-byte key
        """
        key_b64 = os.getenv('LLM_PROVIDER_ENCRYPTION_KEY')
        if key_b64:
            try:
                return base64.urlsafe_b64decode(key_b64)
            except Exception as e:
                raise ValueError(f"Invalid encryption key format: {e}")
        else:
            # Generate ephemeral key for development
            # WARNING: Data encrypted with this key will be lost on restart
            return Fernet.generate_key()
    
    def encrypt_api_key(self, api_key: str) -> str:
        """
        Encrypt an API key for database storage.
        
        Args:
            api_key: The plaintext API key to encrypt
            
        Returns:
            str: Base64-encoded encrypted API key
            
        Raises:
            ValueError: If api_key is empty or None
        """
        if not api_key:
            raise ValueError("API key cannot be empty")
        
        try:
            encrypted_bytes = self.cipher_suite.encrypt(api_key.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('ascii')
        except Exception as e:
            raise ValueError(f"Failed to encrypt API key: {e}")
    
    def decrypt_api_key(self, encrypted_api_key: str) -> str:
        """
        Decrypt an API key from database storage.
        
        Args:
            encrypted_api_key: Base64-encoded encrypted API key
            
        Returns:
            str: Plaintext API key
            
        Raises:
            ValueError: If decryption fails or key is invalid
        """
        if not encrypted_api_key:
            raise ValueError("Encrypted API key cannot be empty")
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_api_key.encode('ascii'))
            decrypted_bytes = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decrypt API key: {e}")
    
    @classmethod
    def generate_encryption_key(cls) -> str:
        """
        Generate a new base64-encoded encryption key for production use.
        
        Returns:
            str: Base64-encoded encryption key suitable for environment variable
            
        Usage:
            key = ProviderCredentialManager.generate_encryption_key()
            # Set LLM_PROVIDER_ENCRYPTION_KEY=<key> in production environment
        """
        key = Fernet.generate_key()
        return base64.urlsafe_b64encode(key).decode('ascii')


# Global instance for application use
credential_manager = ProviderCredentialManager()


def encrypt_provider_api_key(api_key: str) -> str:
    """
    Convenience function to encrypt an API key.
    
    Args:
        api_key: The plaintext API key to encrypt
        
    Returns:
        str: Encrypted API key for database storage
    """
    return credential_manager.encrypt_api_key(api_key)


def decrypt_provider_api_key(encrypted_api_key: str) -> str:
    """
    Convenience function to decrypt an API key.
    
    Args:
        encrypted_api_key: The encrypted API key from database
        
    Returns:
        str: Plaintext API key for use with providers
    """
    return credential_manager.decrypt_api_key(encrypted_api_key)