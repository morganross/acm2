import sqlite3
import os

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    print("Tables:")
    for table in tables:
        print(f"  {table[0]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
