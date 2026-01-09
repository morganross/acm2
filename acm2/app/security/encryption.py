"""
Encryption Service

AES-256 encryption for sensitive data (provider API keys).
Uses Fernet (symmetric encryption) from cryptography library.
"""
from cryptography.fernet import Fernet
from typing import Optional
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class EncryptionService:
    """Handles encryption/decryption of sensitive data."""
    
    def __init__(self, key: Optional[bytes] = None):
        """Initialize encryption service.
        
        Args:
            key: 32-byte encryption key (base64 encoded).
                 If None, loads from ENCRYPTION_KEY env var.
        """
        if key is None:
            key = self._load_key_from_env()
        
        self.fernet = Fernet(key)
        self._key = key
        logger.info("Encryption service initialized")
    
    def _load_key_from_env(self) -> bytes:
        """Load encryption key from environment variable.
        
        Returns:
            Encryption key
            
        Raises:
            ValueError: If ENCRYPTION_KEY not set
        """
        key_str = os.getenv('ENCRYPTION_KEY')
        if not key_str:
            raise ValueError(
                "ENCRYPTION_KEY environment variable not set. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        return key_str.encode('utf-8')
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        encrypted_bytes = self.fernet.encrypt(plaintext.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string.
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            cryptography.fernet.InvalidToken: If decryption fails
        """
        decrypted_bytes = self.fernet.decrypt(ciphertext.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    
    def encrypt_dict(self, data: dict) -> dict:
        """Encrypt all string values in a dictionary.
        
        Args:
            data: Dictionary with string values
            
        Returns:
            Dictionary with encrypted values
        """
        return {
            key: self.encrypt(value) if isinstance(value, str) else value
            for key, value in data.items()
        }
    
    def decrypt_dict(self, data: dict) -> dict:
        """Decrypt all string values in a dictionary.
        
        Args:
            data: Dictionary with encrypted string values
            
        Returns:
            Dictionary with decrypted values
        """
        return {
            key: self.decrypt(value) if isinstance(value, str) else value
            for key, value in data.items()
        }


# Global instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get or create encryption service singleton.
    
    Returns:
        EncryptionService instance
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def generate_key() -> str:
    """Generate a new encryption key.
    
    Returns:
        Base64-encoded key string
    """
    key = Fernet.generate_key()
    return key.decode('utf-8')


def save_key_to_env_file(key: str, env_file: str = ".env"):
    """Save encryption key to .env file.
    
    Args:
        key: Base64-encoded key
        env_file: Path to .env file
    """
    env_path = Path(env_file)
    
    # Read existing content
    existing_lines = []
    if env_path.exists():
        with open(env_path, 'r') as f:
            existing_lines = f.readlines()
    
    # Check if ENCRYPTION_KEY already exists
    key_exists = any(line.startswith('ENCRYPTION_KEY=') for line in existing_lines)
    
    if key_exists:
        # Update existing key
        with open(env_path, 'w') as f:
            for line in existing_lines:
                if line.startswith('ENCRYPTION_KEY='):
                    f.write(f'ENCRYPTION_KEY={key}\n')
                else:
                    f.write(line)
    else:
        # Append new key
        with open(env_path, 'a') as f:
            if existing_lines and not existing_lines[-1].endswith('\n'):
                f.write('\n')
            f.write(f'ENCRYPTION_KEY={key}\n')
    
    logger.info(f"Encryption key saved to {env_file}")


if __name__ == "__main__":
    # Generate and save a new key
    print("Generating new encryption key...")
    new_key = generate_key()
    print(f"\nGenerated key: {new_key}")
    print("\nAdd this to your .env file:")
    print(f"ENCRYPTION_KEY={new_key}")
    
    # Optionally save to .env
    save = input("\nSave to .env file? (y/n): ").lower()
    if save == 'y':
        save_key_to_env_file(new_key)
        print("✅ Key saved to .env file")
