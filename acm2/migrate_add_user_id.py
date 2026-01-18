"""
Add user_id columns to all tables for multi-tenant support.

This migration adds a nullable user_id column to:
- presets
- runs
- contents
- documents
- github_connections

Run with: python migrate_add_user_id.py
"""
import sqlite3
import os
from pathlib import Path

# Get the database path (SQLite in home dir)
db_path = Path.home() / '.acm2' / 'acm2.db'

print(f"Database: {db_path}")

if not db_path.exists():
    print("Database does not exist at expected location.")
    print("Checking current directory...")
    db_path = Path(__file__).parent / 'acm2.db'
    if not db_path.exists():
        print("No database found. This migration will be applied when DB is created.")
        exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Tables that need user_id column
tables = [
    'presets',
    'runs',
    'contents',
    'documents',
    'github_connections',
]

for table in tables:
    try:
        # Check if table exists first
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cursor.fetchone():
            print(f"  - Table {table} does not exist, skipping")
            continue
            
        sql = f'ALTER TABLE {table} ADD COLUMN user_id INTEGER'
        print(f"Executing: {sql}")
        cursor.execute(sql)
        conn.commit()
        print(f"  ✓ Added user_id column to {table}")
        
        # Create index for faster lookups
        idx_sql = f'CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table}(user_id)'
        cursor.execute(idx_sql)
        conn.commit()
        print(f"  ✓ Created index on {table}.user_id")
        
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            print(f"  - Column user_id already exists in {table}, skipping")
        else:
            print(f"  ✗ Error adding user_id to {table}: {e}")

conn.close()
print("\n✅ Migration complete!")
print("\nNote: All existing data will have user_id=NULL.")
print("You may want to assign existing data to a default user if needed.")
