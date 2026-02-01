import sqlite3

db_path = 'C:/dev/godzilla/acm2/acm2/acm2.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print('=== Tables ===')
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
print(tables)

if 'presets' in tables:
    print()
    print('=== Presets ===')
    cur.execute('SELECT id, name, is_deleted FROM presets')
    for row in cur.fetchall():
        print(f'  ID: {row[0]}')
        print(f'  Name: {row[1]}')
        print(f'  Deleted: {row[2]}')
        print()

    # Get full preset data for Default Preset
    cur.execute("SELECT * FROM presets WHERE name = 'Default Preset'")
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    if row:
        print('=== Default Preset Full Data ===')
        for col, val in zip(cols, row):
            print(f'  {col}: {val}')

conn.close()
