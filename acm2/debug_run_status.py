import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.expanduser("~/.acm2/acm2.db")

def check_run():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"--- Checking Runs in {DB_PATH} ---")
    cursor.execute("SELECT id, status, created_at, completed_at, error_message, total_tasks, completed_tasks FROM runs ORDER BY created_at DESC LIMIT 5")
    runs = cursor.fetchall()
    for run in runs:
        print(f"Run ID: {run['id']}")
        print(f"  Status: {run['status']}")
        print(f"  Created: {run['created_at']}")
        print(f"  Completed: {run['completed_at']}")
        print(f"  Error: {run['error_message']}")
        print(f"  Progress: {run['completed_tasks']}/{run['total_tasks']}")
        
        # Check steps for this run
        cursor.execute("SELECT id, phase, status, error FROM run_steps WHERE run_id = ? ORDER BY created_at", (run['id'],))
        steps = cursor.fetchall()
        if steps:
            print("  Steps:")
            for step in steps:
                print(f"    - {step['phase']}: {step['status']} (Err: {step['error']})")
        else:
            print("  No steps found.")
        print("-" * 30)

    conn.close()

if __name__ == "__main__":
    check_run()
