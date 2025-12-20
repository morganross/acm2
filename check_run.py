import sqlite3
import json

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cursor = conn.cursor()

run_id = "1fde956f-609c-4c1a-a9f7-db8bba0046d5"

cursor.execute('''SELECT id, preset_id, status, title, description,
                  created_at, completed_at, started_at,
                  total_cost_usd, total_tokens,
                  total_tasks, completed_tasks, failed_tasks,
                  results_summary, config
                  FROM runs WHERE id = ?''', (run_id,))

row = cursor.fetchone()
if row:
    print("="*60)
    print("RUN DETAILS")
    print("="*60)
    print(f"ID: {row[0]}")
    print(f"Preset ID: {row[1]}")
    print(f"Status: {row[2]}")
    print(f"Title: {row[3]}")
    print(f"Description: {row[4]}")
    print(f"Created: {row[5]}")
    print(f"Started: {row[7]}")
    print(f"Completed: {row[6]}")
    print(f"Total Cost USD: ${row[8]:.4f}" if row[8] else "N/A")
    print(f"Total Tokens: {row[9]}")
    print(f"Tasks: {row[11]}/{row[10]} completed, {row[12]} failed")
    
    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60)
    if row[13]:
        results = json.loads(row[13])
        print(json.dumps(results, indent=2, default=str)[:5000])
    else:
        print("No results summary")
        
    print("\n" + "="*60)
    print("CONFIG")
    print("="*60)
    if row[14]:
        config = json.loads(row[14])
        print(json.dumps(config, indent=2)[:2000])
else:
    print("Run not found!")

conn.close()
