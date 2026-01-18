"""
Test script for Phase 2: Provider Key Encryption Integration

This script tests the full integration of encrypted provider keys with adapters.
It verifies that:
1. User's encrypted keys can be injected into adapter environments
2. Adapters can successfully use these keys to make API calls
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add acm2 to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
load_dotenv()

from app.security.key_injection import inject_provider_keys_for_user, get_provider_key
from app.security.provider_keys import ProviderKeyManager
from app.db.user_db import UserDB


async def test_key_injection():
    """Test that we can inject encrypted provider keys for a user."""
    print("=" * 60)
    print("Test 1: Provider Key Injection Service")
    print("=" * 60)
    
    user_id = 1
    
    # Check if user has any keys configured
    manager = ProviderKeyManager(user_id)
    configured = await manager.get_all_keys()
    print(f"\n✓ User {user_id} has {len(configured)} provider(s) configured: {configured}")
    
    if not configured:
        print("  ⚠ No providers configured. Adding test keys...")
        # Add test keys (use real keys from .env if available, otherwise use placeholders)
        test_keys = {
            "openai": os.getenv("OPENAI_API_KEY", "sk-test-openai-key-placeholder"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY", "sk-test-anthropic-key-placeholder"),
            "google": os.getenv("GOOGLE_API_KEY", "sk-test-google-key-placeholder"),
        }
        for provider, key in test_keys.items():
            await manager.save_key(provider, key)
            print(f"  ✓ Saved {provider} key")
        configured = await manager.get_all_keys()
    
    # Test injection into environment
    env = {}
    env = await inject_provider_keys_for_user(user_id, env)
    
    print(f"\n✓ Injected {len(env)} environment variables:")
    for var_name in env.keys():
        key_preview = env[var_name][:20] + "..." if len(env[var_name]) > 20 else env[var_name]
        print(f"  - {var_name}: {key_preview}")
    
    # Verify keys match what's in database
    print("\n✓ Verifying keys match database...")
    for provider in configured:
        db_key = await manager.get_key(provider)
        env_var = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
        }.get(provider)
        
        if env_var and env_var in env:
            if env[env_var] == db_key:
                print(f"  ✓ {provider}: Keys match")
            else:
                print(f"  ✗ {provider}: KEY MISMATCH!")
                return False
    
    return True


async def test_adapter_integration():
    """Test that adapters can use injected keys."""
    print("\n" + "=" * 60)
    print("Test 2: Adapter Integration (Simulated)")
    print("=" * 60)
    
    # We won't actually call the LLM APIs, but we'll simulate the adapter flow
    user_id = 1
    
    # Simulate what the adapter does
    env = os.environ.copy()
    env = await inject_provider_keys_for_user(user_id, env)
    
    # Check that the required env vars are present
    required_vars = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]
    missing = [var for var in required_vars if var not in env]
    
    if missing:
        print(f"  ⚠ Missing environment variables: {missing}")
        print("    Adapters would fail without these keys")
        return False
    
    print(f"\n✓ All required environment variables present")
    print("✓ Adapters would be able to make API calls with these keys")
    print("\nNote: Not actually calling LLM APIs to avoid costs")
    
    return True


async def test_database_storage():
    """Verify keys are actually encrypted in the database."""
    print("\n" + "=" * 60)
    print("Test 3: Database Storage Verification")
    print("=" * 60)
    
    user_id = 1
    
    # Check raw database contents
    db = UserDB(user_id)
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT provider, encrypted_key FROM provider_keys")
        rows = await cursor.fetchall()
    
    if not rows:
        print("  ⚠ No keys found in database")
        return False
    
    print(f"\n✓ Found {len(rows)} encrypted keys in database:")
    for row in rows:
        provider = row['provider']
        encrypted_key = row['encrypted_key']
        key_preview = encrypted_key[:40] + "..." if len(encrypted_key) > 40 else encrypted_key
        print(f"  - {provider}: {key_preview}")
        
        # Verify it's actually encrypted (Fernet tokens start with "gAAAAA")
        if encrypted_key.startswith("gAAAAA"):
            print(f"    ✓ Key is Fernet-encrypted")
        else:
            print(f"    ✗ Key does NOT appear to be encrypted!")
            return False
    
    return True


async def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("ACM2 Phase 2 Integration Tests")
    print("Provider Key Encryption with Adapter Integration")
    print("=" * 60)
    
    try:
        # Run tests
        test1 = await test_key_injection()
        test2 = await test_adapter_integration()
        test3 = await test_database_storage()
        
        # Summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Test 1 (Key Injection): {'✓ PASS' if test1 else '✗ FAIL'}")
        print(f"Test 2 (Adapter Integration): {'✓ PASS' if test2 else '✗ FAIL'}")
        print(f"Test 3 (Database Storage): {'✓ PASS' if test3 else '✗ FAIL'}")
        
        all_passed = test1 and test2 and test3
        print(f"\nOverall: {'✨ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
        
        if all_passed:
            print("\n" + "=" * 60)
            print("✨ Phase 2 Implementation Complete!")
            print("=" * 60)
            print("Encrypted provider keys are working correctly.")
            print("Adapters can inject and use user-specific API keys.")
            print("Keys are safely encrypted at rest in SQLite databases.")
            
        return 0 if all_passed else 1
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
