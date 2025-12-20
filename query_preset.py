import sqlite3
import json

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cursor = conn.cursor()

cursor.execute("SELECT id, name, models, evaluation_enabled, pairwise_enabled FROM presets WHERE name LIKE '%Default%'")
rows = cursor.fetchall()

for r in rows:
    print(f"ID: {r[0]}")
    print(f"Name: {r[1]}")
    print(f"Models (raw): {r[2]}")
    if r[2]:
        models = json.loads(r[2])
        print(f"Models (parsed):")
        print(json.dumps(models, indent=2))
    print(f"Evaluation Enabled: {r[3]}")
    print(f"Pairwise Enabled: {r[4]}")
    print()

conn.close()
