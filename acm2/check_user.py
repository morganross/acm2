import sqlite3

conn = sqlite3.connect(r'C:\devlop\acm2\acm2\data\user_3c39ba0c-e313-4873-bbe9-2437373127f4.db')

# List tables
print("Tables:", [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()])

# Check presets
print("\nPresets:")
for row in conn.execute("SELECT id, name, user_uuid FROM presets").fetchall():
    print(f"  {row}")

# Check api_keys if exists
try:
    print("\nAPI Keys:")
    for row in conn.execute("SELECT * FROM api_keys").fetchall():
        print(f"  {row}")
except Exception as e:
    print(f"  Error: {e}")

conn.close()
