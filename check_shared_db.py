import sqlite3
import os

# Check shared DB
print('=== SHARED DB (acm2.db) ===')
conn = sqlite3.connect('C:/Users/Administrator/.acm2/acm2.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    count = cur.fetchone()[0]
    if count > 0:
        print(f'{t}: {count}')
    else:
        print(f'{t}: 0')
conn.close()

# Check user databases
for user_id in [1, 2, 6, 7]:
    db_path = f'C:/devlop/acm2/acm2/data/user_{user_id}.db'
    if os.path.exists(db_path):
        print(f'\n=== user_{user_id}.db ===')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cur.fetchall()]
        for t in tables:
            cur.execute(f'SELECT COUNT(*) FROM "{t}"')
            count = cur.fetchone()[0]
            if count > 0:
                print(f'{t}: {count}')
        conn.close()
