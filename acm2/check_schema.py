import sqlite3

for user_id in [6, 7]:
    conn = sqlite3.connect(f'data/user_{user_id}.db')
    c = conn.cursor()
    c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='runs'")
    sql = c.fetchone()[0]
    print(f'=== user_{user_id} runs CREATE SQL ===')
    print(sql[:500] if len(sql) > 500 else sql)
    print()
