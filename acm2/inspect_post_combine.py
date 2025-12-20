import sqlite3
import os
import json

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

run_id = 'b7fc39f2-a7b3-45a4-a814-8a4a17c7b65f'

try:
    c.execute("SELECT results_summary FROM runs WHERE id = ?", (run_id,))
    row = c.fetchone()
    if row and row[0]:
        summary = json.loads(row[0])
        
        print("--- post_combine_eval ---")
        print(json.dumps(summary.get('post_combine_eval'), indent=2))
        
        print("\n--- post_combine_evals ---")
        print(json.dumps(summary.get('post_combine_evals'), indent=2))

    else:
        print("Run not found or no results summary.")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
