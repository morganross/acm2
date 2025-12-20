import sqlite3
import os
import json

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

run_id = 'b7fc39f2-a7b3-45a4-a814-8a4a17c7b65f'

try:
    c.execute("SELECT config FROM runs WHERE id = ?", (run_id,))
    row = c.fetchone()
    if row and row[0]:
        config = json.loads(row[0])
        print("Run Config Keys:", config.keys())
        print(f"post_combine_top_n: {config.get('post_combine_top_n')}")
    else:
        print("Run not found or no config.")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
