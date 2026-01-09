"""
Database Initialization Script

Run this to set up the hybrid database architecture:
- MySQL master database (acm2_master)
- SQLite per-user databases (created on-demand)
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from acm2.app.db.master import MasterDB
from acm2.app.db.user_db import UserDB
from acm2.app.auth.api_keys import generate_api_key


async def init_master_db():
    """Initialize master database in MySQL."""
    print("🔧 Initializing master database (MySQL)...")
    
    try:
        master_db = MasterDB()
        await master_db.connect()
        print("✅ Master database connected successfully")
        print(f"   Host: {master_db.config['host']}")
        print(f"   Database: {master_db.config['db']}")
        return master_db
    except Exception as e:
        print(f"❌ Failed to connect to master database: {e}")
        print("\nMake sure:")
        print("  1. XAMPP MySQL is running")
        print("  2. Database 'acm2_master' exists")
        print("  3. Run: mysql -u root acm2_master < app/db/master_schema_mysql.sql")
        sys.exit(1)


async def create_test_user(master_db):
    """Create a test user to verify setup."""
    print("\n👤 Creating test user...")
    
    try:
        # Create user
        user_id = await master_db.create_user(
            username="testuser",
            email="test@example.com"
        )
        print(f"✅ Created user: testuser (ID: {user_id})")
        
        # Generate API key
        full_key, key_hash, key_prefix = generate_api_key()
        key_id = await master_db.create_api_key(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name="Test Key"
        )
        print(f"✅ Generated API key: {key_prefix}...")
        print(f"\n   🔑 SAVE THIS KEY: {full_key}")
        print(f"   ⚠️  This is the only time you'll see the full key!\n")
        
        return user_id
        
    except Exception as e:
        if "UNIQUE constraint failed" in str(e) or "Duplicate entry" in str(e):
            print("ℹ️  Test user already exists")
            # Get existing user
            async with master_db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT id FROM users WHERE username = %s",
                        ("testuser",)
                    )
                    result = await cursor.fetchone()
                    return result[0] if result else None
        else:
            print(f"❌ Error creating test user: {e}")
            return None


async def init_user_db(user_id: int):
    """Initialize test user's database."""
    print(f"\n📁 Initializing user database for user {user_id}...")
    
    try:
        user_db = UserDB(user_id)
        await user_db.init_db()
        print(f"✅ User database created: {user_db.db_path}")
        
        # Create a test run
        async with user_db.get_connection() as conn:
            await conn.execute(
                """INSERT INTO runs (id, name, status)
                   VALUES (?, ?, ?)""",
                ("test-run-1", "Test Evaluation", "completed")
            )
            await conn.commit()
        print("✅ Created test run")
        
        return user_db
        
    except Exception as e:
        print(f"❌ Error initializing user database: {e}")
        return None


async def verify_setup(master_db, user_id):
    """Verify the setup works."""
    print("\n🔍 Verifying setup...")
    
    try:
        # Check user in master DB
        user = await master_db.get_user_by_id(user_id)
        if user:
            print(f"✅ User found in master DB: {user['username']}")
        
        # Check API keys
        keys = await master_db.list_user_api_keys(user_id)
        if keys:
            print(f"✅ API keys: {len(keys)} key(s) found")
        
        # Check user database
        user_db = UserDB(user_id)
        async with user_db.get_connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM runs")
            count = (await cursor.fetchone())[0]
            print(f"✅ User database accessible: {count} run(s)")
        
        print("\n✨ Setup complete! Everything is working.")
        print("\nNext steps:")
        print("  1. Start the ACM2 backend: uvicorn acm2.app.main:app --reload")
        print("  2. Use the API key above to make authenticated requests")
        print("  3. Header: X-ACM2-API-Key: <your-key-here>")
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")


async def main():
    """Main initialization function."""
    print("=" * 60)
    print("ACM2 Hybrid Database Initialization")
    print("=" * 60)
    
    # Step 1: Connect to master DB
    master_db = await init_master_db()
    
    # Step 2: Create test user
    user_id = await create_test_user(master_db)
    if not user_id:
        print("❌ Failed to create test user")
        await master_db.close()
        sys.exit(1)
    
    # Step 3: Initialize user database
    user_db = await init_user_db(user_id)
    if not user_db:
        print("❌ Failed to initialize user database")
        await master_db.close()
        sys.exit(1)
    
    # Step 4: Verify everything works
    await verify_setup(master_db, user_id)
    
    # Cleanup
    await master_db.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
