import sqlite3
import json

conn = sqlite3.connect(r'C:\Users\kjhgf\.acm2\acm2.db')
cursor = conn.cursor()

run_id = 'fc0a913b-68fd-4687-94bd-3b6b306bf910'

# Get the run info
print('=== RUN RESULTS SUMMARY ===')
cursor.execute(f"SELECT results_summary FROM runs WHERE id = '{run_id}'")
row = cursor.fetchone()
if row and row[0]:
    results = json.loads(row[0])
    print(json.dumps(results, indent=2))
