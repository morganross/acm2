import sqlite3
import os
import sys

run_id = '8d1502c7-baed-40e9-b06e-55a1176eff78'
db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT status FROM runs WHERE id = ?", (run_id,))
row = cursor.fetchone()
if row:
    print(f"Status: {row[0]}")
else:
    print("Run not found")
conn.close()
