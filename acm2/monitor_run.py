import sqlite3
import os
import time
import sys

db_path = os.path.expanduser('~/.acm2/acm2.db')
run_id = 'b7fc39f2-a7b3-45a4-a814-8a4a17c7b65f'

def check_status():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute("SELECT status, error_message FROM runs WHERE id = ?", (run_id,))
        row = c.fetchone()
        if row:
            return row[0], row[1]
        return None, None
    finally:
        conn.close()

def check_logs():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        # Since run_logs table doesn't exist, we can't check logs this way.
        # We'll rely on status changes or maybe check tasks if they appear.
        pass
    finally:
        conn.close()

print(f"Monitoring run {run_id}...")
start_time = time.time()
while True:
    status, error = check_status()
    if status is None:
        print("Run not found!")
        break
    
    print(f"Status: {status}")
    if error:
        print(f"Error: {error}")
    
    if status in ['completed', 'failed', 'cancelled']:
        print(f"Run finished with status: {status}")
        break
    
    # No timeout; wait until completion
        
    time.sleep(10)
