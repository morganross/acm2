import sqlite3
import os

# Check shared database first
shared_db = 'C:/Users/Administrator/.acm2/acm2.db'
print("=== SHARED DATABASE (source for seeding) ===")
print(f"Path: {shared_db}")
print(f"Exists: {os.path.exists(shared_db)}")

if os.path.exists(shared_db):
    conn = sqlite3.connect(shared_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cur.fetchall()]
    print(f"Tables: {tables}")
    
    if 'presets' in tables:
        cur.execute("SELECT id, name, is_deleted FROM presets")
        presets = cur.fetchall()
        print(f"Presets count: {len(presets)}")
        for p in presets:
            print(f"  ID: {p[0]} | Name: {p[1]} | Deleted: {p[2]}")
    else:
        print("NO PRESETS TABLE!")
    conn.close()

print()
print("=== USER DATABASES ===")
data_dir = 'C:/devlop/acm2/acm2/data'
for f in sorted(os.listdir(data_dir)):
    if f.endswith('.db'):
        db_path = os.path.join(data_dir, f)
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='presets'")
            if cur.fetchone():
                cur.execute("SELECT id, name, is_deleted FROM presets")
                presets = cur.fetchall()
                print(f"{f}: {len(presets)} presets")
                for row in presets:
                    print(f"  {row[1]} (deleted={row[2]})")
            else:
                print(f"{f}: no presets table")
            conn.close()
        except Exception as e:
            print(f"{f}: ERROR {e}")
