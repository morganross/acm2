import sqlite3
conn = sqlite3.connect('data/user_6.db')
c = conn.cursor()

# Check artifacts table
c.execute("PRAGMA table_info(artifacts)")
print("Artifacts columns:", [col[1] for col in c.fetchall()])

# Check if there are artifacts for this run
run_id = "c7ee99a7-8832-40e6-aacd-28a686142ecf"
c.execute("SELECT id, artifact_type, run_id FROM artifacts WHERE run_id = ? LIMIT 5", (run_id,))
rows = c.fetchall()
print(f"\nArtifacts for run (found {len(rows)}):")
for r in rows:
    print(f"  id={r[0][:30]}... type={r[1]}")
