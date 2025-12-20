import sqlite3
import os
import json

db_path = r"C:/Users/kjhgf/.acm2/acm2.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Recent Runs:")
cursor.execute("SELECT id, title, status, created_at FROM runs ORDER BY created_at DESC LIMIT 5")
runs = cursor.fetchall()
for r in runs:
    print(f"  {r['id']} - {r['title']} ({r['status']}) at {r['created_at']}")

print("\nAll Tasks in DB:")
cursor.execute("SELECT id, run_id, model_name, status, created_at FROM tasks ORDER BY created_at DESC")
tasks = cursor.fetchall()
if not tasks:
    print("  No tasks found.")
else:
    for t in tasks:
        print(f"  Task {t['id']} (Run: {t['run_id']}) - {t['model_name']} ({t['status']})")

conn.close()
