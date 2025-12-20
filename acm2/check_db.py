import sqlite3

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
c = conn.cursor()

run_id = 'a272a109-ccda-434c-89d0-8c38f74257f0'

# Check tasks for the run
print("=== Tasks for this run ===")
c.execute("SELECT id, model_name, status, error_message, duration_seconds FROM tasks WHERE run_id = ?", (run_id,))
for row in c.fetchall():
    print(f"  {row[0][:40]}... model={row[1]}: status={row[2]}, error={row[3]}, dur={row[4]}")

# Look for tvly-pro specifically in artifacts
print("\n=== Searching for tvly-pro content in artifacts ===")
c.execute("SELECT id, task_id, artifact_type, name, LENGTH(content) as content_len, SUBSTR(content, 1, 200) as preview FROM artifacts WHERE name LIKE '%tvly%' OR id LIKE '%tvly%' OR task_id LIKE '%tvly%'")
for row in c.fetchall():
    print(f"  id={row[0][:30]}..., task_id={row[1]}, type={row[2]}, name={row[3]}, len={row[4]}")
    print(f"    preview='{row[5]}'")

# Get all artifacts to understand structure
print("\n=== All artifacts (first 20) ===")
c.execute("SELECT id, task_id, artifact_type, name, LENGTH(content) as content_len FROM artifacts LIMIT 20")
for row in c.fetchall():
    print(f"  id={row[0][:40]}..., type={row[2]}, name={row[3]}, len={row[4]}")

conn.close()
