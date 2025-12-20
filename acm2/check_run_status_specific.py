import sqlite3
import os
import json

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

run_id = 'b7fc39f2-a7b3-45a4-a814-8a4a17c7b65f'

try:
    c.execute("SELECT status, error_message FROM runs WHERE id = ?", (run_id,))
    row = c.fetchone()
    if row:
        print(f'Run Status: {row[0]}')
        if row[1]:
            print(f'Error: {row[1]}')
    else:
        print("Run not found")

    # Check for logs related to post-combine
    c.execute("SELECT message FROM run_logs WHERE run_id = ? AND message LIKE '%post-combine%' ORDER BY timestamp DESC LIMIT 5", (run_id,))
    logs = c.fetchall()
    if logs:
        print("\nRecent Post-Combine Logs:")
        for log in logs:
            print(f"  {log[0]}")
    else:
        print("\nNo recent post-combine logs found yet.")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
