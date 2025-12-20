import sqlite3
import os

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("SELECT post_combine_top_n, pairwise_enabled, eval_iterations, generation_concurrency, eval_concurrency, request_timeout, eval_timeout FROM presets WHERE name = 'Default Preset'")
    row = c.fetchone()
    if row:
        print('Default Preset DB Values:')
        print(f'  post_combine_top_n: {row[0]}')
        print(f'  pairwise_enabled: {row[1]}')
        print(f'  eval_iterations: {row[2]}')
        print(f'  generation_concurrency: {row[3]}')
        print(f'  eval_concurrency: {row[4]}')
        print(f'  request_timeout: {row[5]}')
        print(f'  eval_timeout: {row[6]}')
    else:
        print("Default Preset not found")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
