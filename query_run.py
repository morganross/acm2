import sqlite3

conn = sqlite3.connect(r'C:\Users\kjhgf\.acm2\acm2.db')
c = conn.cursor()

# Get tasks for the run  
run_id = "c48187c5-403c-4229-bbdd-af44c9b66a15"
c.execute("SELECT id, model_name, status, duration_seconds FROM tasks WHERE run_id = ?", (run_id,))
print("\nTasks for run:")
for row in c.fetchall():
    print(f"  {row}")

# Get artifacts by task_id
c.execute("""
    SELECT a.id, a.artifact_type, a.name, LENGTH(a.content) as content_len, t.model_name
    FROM artifacts a
    JOIN tasks t ON a.task_id = t.id
    WHERE t.run_id = ?
""", (run_id,))
print("\nArtifacts for run:")
for row in c.fetchall():
    print(f"  {row}")

conn.close()
