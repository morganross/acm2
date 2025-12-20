import sqlite3
import os

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

run_id = 'b7fc39f2-a7b3-45a4-a814-8a4a17c7b65f'

try:
    c.execute("SELECT id, type, status, error_message FROM tasks WHERE run_id = ?", (run_id,))
    tasks = c.fetchall()
    print(f"Tasks for run {run_id}:")
    for task in tasks:
        print(f"  ID: {task[0]}, Type: {task[1]}, Status: {task[2]}, Error: {task[3]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
