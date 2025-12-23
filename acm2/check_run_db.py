import sqlite3
import json

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
r = conn.execute("SELECT results_summary FROM runs WHERE id LIKE '649427f0%'").fetchone()

print("=== results_summary ===")
if r[0]:
    data = json.loads(r[0])
    print(json.dumps(data, indent=2)[:8000])
else:
    print("None")

conn.close()
