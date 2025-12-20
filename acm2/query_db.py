import sqlite3

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# Query single_evaluations if exists
for table in tables:
    table_name = table[0]
    if 'eval' in table_name.lower() or 'single' in table_name.lower():
        print(f"\n=== {table_name} ===")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [c[1] for c in cursor.fetchall()]
        print("Columns:", columns)
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        print(f"Rows ({len(rows)}):")
        for row in rows:
            print(row)

conn.close()
