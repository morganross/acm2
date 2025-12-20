import sqlite3
conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cur = conn.cursor()

# Get run info
cur.execute("SELECT id, status, config FROM runs WHERE id LIKE '6c9494cb%'")
run = cur.fetchone()
print('=== RUN ===')
print(f'ID: {run[0]}')
print(f'Status: {run[1]}')
print(f'Config: {run[2][:200] if run[2] else None}...')

# Get all tasks
cur.execute("SELECT id, model_name, status, duration_seconds, error_message FROM tasks WHERE run_id LIKE '6c9494cb%' ORDER BY created_at")
tasks = cur.fetchall()
print(f'\n=== TASKS ({len(tasks)} total) ===')
for t in tasks:
    err_preview = t[4][:50] if t[4] else None
    print(f'{str(t[1]):35} | {t[2]:10} | {t[3]}s | err={err_preview}')

# Get artifacts
cur.execute("SELECT id, artifact_type, source_model FROM artifacts WHERE run_id LIKE '6c9494cb%'")
artifacts = cur.fetchall()
print(f'\n=== ARTIFACTS ({len(artifacts)} total) ===')
for a in artifacts:
    print(f'{a[1]:20} | {a[2]}')

# Get pre_combine_evals
cur.execute("SELECT doc_id, evaluator, avg_score FROM pre_combine_evals_detailed WHERE run_id LIKE '6c9494cb%'")
evals = cur.fetchall()
print(f'\n=== PRE_COMBINE_EVALS ({len(evals)} total) ===')
for e in evals:
    print(f'{e[0]:50} | {e[1]:25} | avg={e[2]}')

conn.close()
