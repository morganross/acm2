import sqlite3
import os

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("Columns in presets table:")
c.execute("PRAGMA table_info(presets)")
columns = [row[1] for row in c.fetchall()]
print(columns)

if 'post_combine_top_n' in columns:
    print("\nValue for Default Preset:")
    c.execute("SELECT post_combine_top_n FROM presets WHERE name = 'Default Preset'")
    row = c.fetchone()
    print(row)
else:
    print("\npost_combine_top_n column NOT FOUND in presets table")

conn.close()
