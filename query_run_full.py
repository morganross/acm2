import sqlite3
import json

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cur = conn.cursor()

# Get full run record
cur.execute("SELECT * FROM runs WHERE id LIKE '6c9494cb%'")
row = cur.fetchone()
cols = [d[0] for d in cur.description]
run_data = dict(zip(cols, row))

print('=== FULL RUN RECORD ===')
for k, v in run_data.items():
    if k == 'config' and v:
        print(f'{k}: {v[:100]}...')
    elif k == 'results_summary' and v:
        print(f'{k}:')
        try:
            summary = json.loads(v)
            print(json.dumps(summary, indent=2))
        except:
            print(v[:500])
    else:
        print(f'{k}: {v}')

conn.close()
