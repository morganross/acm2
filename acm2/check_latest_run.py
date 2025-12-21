import sqlite3
import os

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, created_at, status, error_message FROM runs ORDER BY created_at DESC LIMIT 1")
row = cursor.fetchone()
if row:
    print(f"ID: {row[0]}")
    print(f"Created: {row[1]}")
    print(f"Status: {row[2]}")
    print(f"Error: {row[3]}")
else:
    print("No runs found")
conn.close()
