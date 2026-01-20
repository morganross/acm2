import sqlite3
import os

run_id = "c7ee99a7-8832-40e6-aacd-28a686142ecf"

for db in os.listdir('data'):
    if db.endswith('.db'):
        try:
            conn = sqlite3.connect(f'data/{db}')
            r = conn.execute("SELECT id, status FROM runs WHERE id = ?", (run_id,)).fetchone()
            if r:
                print(f'{db}: FOUND - status={r[1]}')
        except Exception as e:
            pass
