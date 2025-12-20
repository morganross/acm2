"""Add new required columns to presets table."""
import sqlite3
import os
from pathlib import Path

# Get the database path
db_path = Path.home() / '.acm2' / 'acm2.db'

print(f"Database: {db_path}")

if not db_path.exists():
    print("Database does not exist!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

columns_to_add = [
    ('max_retries', 'INTEGER NOT NULL DEFAULT 3'),
    ('retry_delay', 'REAL NOT NULL DEFAULT 2.0'),
    ('request_timeout', 'INTEGER NOT NULL DEFAULT 600'),
    ('eval_timeout', 'INTEGER NOT NULL DEFAULT 600'),
    ('generation_concurrency', 'INTEGER NOT NULL DEFAULT 5'),
    ('eval_concurrency', 'INTEGER NOT NULL DEFAULT 5'),
    ('iterations', 'INTEGER NOT NULL DEFAULT 1'),
    ('eval_iterations', 'INTEGER NOT NULL DEFAULT 1'),
    ('fpf_log_output', 'TEXT NOT NULL DEFAULT "file"'),
    ('fpf_log_file_path', 'TEXT'),
    ('post_combine_top_n', 'INTEGER')
]

for col_name, col_type in columns_to_add:
    try:
        sql = f'ALTER TABLE presets ADD COLUMN {col_name} {col_type}'
        print(f"Executing: {sql}")
        cursor.execute(sql)
        conn.commit()
        print(f"  ✓ Added column {col_name}")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            print(f"  - Column {col_name} already exists, skipping")
        else:
            print(f"  ✗ Error adding {col_name}: {e}")

conn.close()
print("\n✅ Done!")
