import sqlite3
conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cur = conn.cursor()

# List all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('=== TABLES ===')
print([r[0] for r in cur.fetchall()])

# Get run info
cur.execute("SELECT id, status, config FROM runs WHERE id LIKE '6c9494cb%'")
run = cur.fetchone()
print('\n=== RUN ===')
print(f'ID: {run[0]}')
print(f'Status: {run[1]}')

# Get all tasks
cur.execute("SELECT id, model_name, status, duration_seconds, error_message FROM tasks WHERE run_id LIKE '6c9494cb%' ORDER BY created_at")
tasks = cur.fetchall()
print(f'\n=== TASKS ({len(tasks)} total) ===')
for t in tasks:
    err_preview = t[4][:50] if t[4] else None
    print(f'{str(t[1]):35} | {t[2]:10} | {t[3]}s | err={err_preview}')

# Get artifacts
cur.execute("SELECT id, artifact_type, name, avg_score FROM artifacts WHERE task_id IN (SELECT id FROM tasks WHERE run_id LIKE '6c9494cb%')")
artifacts = cur.fetchall()
print(f'\n=== ARTIFACTS ({len(artifacts)} total) ===')
for a in artifacts:
    print(f'{a[1]:20} | {a[2]:40} | avg={a[3]}')

conn.close()
