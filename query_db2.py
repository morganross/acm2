import sqlite3

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cursor = conn.cursor()

run_id = '6c9494cb-77b2-41ec-87c5-0e6aec032494'

# Query runs table
print("=== RUNS ===")
cursor.execute("PRAGMA table_info(runs)")
columns = [c[1] for c in cursor.fetchall()]
print("Columns:", columns)
cursor.execute(f"SELECT * FROM runs WHERE id = ?", (run_id,))
rows = cursor.fetchall()
for row in rows:
    print(row)

# Query tasks table
print("\n=== TASKS ===")
cursor.execute("PRAGMA table_info(tasks)")
columns = [c[1] for c in cursor.fetchall()]
print("Columns:", columns)
cursor.execute(f"SELECT * FROM tasks WHERE run_id = ?", (run_id,))
rows = cursor.fetchall()
print(f"Total tasks: {len(rows)}")
for row in rows:
    print(row)

# Query artifacts table
print("\n=== ARTIFACTS ===")
cursor.execute("PRAGMA table_info(artifacts)")
columns = [c[1] for c in cursor.fetchall()]
print("Columns:", columns)
cursor.execute(f"SELECT * FROM artifacts WHERE run_id = ?", (run_id,))
rows = cursor.fetchall()
print(f"Total artifacts: {len(rows)}")
for row in rows:
    print(row)

conn.close()
