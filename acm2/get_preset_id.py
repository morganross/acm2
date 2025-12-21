import sqlite3
import os

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, name FROM presets WHERE name = 'Default Preset'")
row = cursor.fetchone()
if row:
    print(f"Full ID: {row[0]}")
else:
    print("Preset not found")
conn.close()
