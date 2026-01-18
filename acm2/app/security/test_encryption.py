"""
Test Provider Key Encryption

Verifies encryption, storage, and retrieval of provider keys.
"""
import asyncio
import sys
from pathlib import Path
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app.security.encryption import get_encryption_service
from app.security.provider_keys import get_provider_key_manager
from app.db.user_db import get_user_db


async def test_encryption():
    """Test basic encryption/decryption."""
    print("=" * 60)
    print("Test 1: Basic Encryption")
    print("=" * 60)
    
    encryption_service = get_encryption_service()
    
    # Test data
    test_key = "sk-test-1234567890abcdefghijklmnop"
    print(f"Original key: {test_key}")
    
    # Encrypt
    encrypted = encryption_service.encrypt(test_key)
    print(f"Encrypted: {encrypted[:50]}..." if len(encrypted) > 50 else f"Encrypted: {encrypted}")
    
    # Decrypt
    decrypted = encryption_service.decrypt(encrypted)
    print(f"Decrypted: {decrypted}")
    
    # Verify
    if decrypted == test_key:
        print("✅ Encryption/decryption works correctly")
    else:
        print("❌ Encryption/decryption failed")
        return False
    
    return True


async def test_provider_key_manager():
    """Test provider key manager."""
    print("\n" + "=" * 60)
    print("Test 2: Provider Key Manager")
    print("=" * 60)
    
    # Use test user (ID 1 from initialization)
    user_id = 1
    key_manager = await get_provider_key_manager(user_id)
    
    # Test keys
    test_keys = {
        'openai': 'sk-proj-test-openai-1234567890',
        'anthropic': 'sk-ant-test-anthropic-0987654321',
        'google': 'AIza-test-google-abcdefghij'
    }
    
    print(f"\n📝 Saving provider keys for user {user_id}...")
    for provider, api_key in test_keys.items():
        await key_manager.save_key(provider, api_key)
        print(f"  ✅ Saved {provider} key")
    
    print(f"\n📖 Retrieving provider keys...")
    for provider, original_key in test_keys.items():
        retrieved_key = await key_manager.get_key(provider)
        if retrieved_key == original_key:
            print(f"  ✅ {provider}: Key matches")
        else:
            print(f"  ❌ {provider}: Key mismatch!")
            print(f"     Expected: {original_key}")
            print(f"     Got: {retrieved_key}")
            return False
    
    print(f"\n📋 Listing configured providers...")
    providers = await key_manager.list_configured_providers()
    print(f"  Configured: {', '.join(providers)}")
    
    if set(providers) == set(test_keys.keys()):
        print("  ✅ All providers configured")
    else:
        print("  ❌ Provider list mismatch")
        return False
    
    print(f"\n🗑️  Testing key deletion...")
    await key_manager.delete_key('google')
    has_google = await key_manager.has_key('google')
    if not has_google:
        print("  ✅ Google key deleted successfully")
    else:
        print("  ❌ Google key still exists")
        return False
    
    # Restore for next tests
    await key_manager.save_key('google', test_keys['google'])
    
    return True


async def test_database_storage():
    """Test that keys are actually stored encrypted in database."""
    print("\n" + "=" * 60)
    print("Test 3: Database Storage (Encrypted)")
    print("=" * 60)
    
    user_id = 1
    user_db = await get_user_db(user_id)
    
    # Get raw encrypted key from database
    async with user_db.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT provider, encrypted_key FROM provider_keys"
        )
        rows = await cursor.fetchall()
        
        print(f"\n📦 Raw database contents:")
        for row in rows:
            provider = row['provider']
            encrypted = row['encrypted_key']
            print(f"  {provider}: {encrypted[:60]}..." if len(encrypted) > 60 else f"  {provider}: {encrypted}")
        
        # Verify keys are actually encrypted (not plaintext)
        for row in rows:
            encrypted = row['encrypted_key']
            if encrypted.startswith('sk-') or encrypted.startswith('AIza'):
                print(f"\n  ❌ Key is not encrypted! Found plaintext key")
                return False
        
        print(f"\n  ✅ All keys are encrypted in database")
    
    return True


async def main():
    """Run all tests."""
    print("ACM2 Provider Key Encryption Tests")
    print("=" * 60)
    
    # Test 1: Basic encryption
    if not await test_encryption():
        print("\n❌ Basic encryption test failed")
        sys.exit(1)
    
    # Test 2: Provider key manager
    if not await test_provider_key_manager():
        print("\n❌ Provider key manager test failed")
        sys.exit(1)
    
    # Test 3: Database storage
    if not await test_database_storage():
        print("\n❌ Database storage test failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✨ All tests passed!")
    print("=" * 60)
    print("\nProvider key encryption is working correctly.")
    print("Keys are encrypted before storage and decrypted only when needed.")


if __name__ == "__main__":
    asyncio.run(main())
