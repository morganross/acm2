import sqlite3
import os

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("SELECT enable_combine, combine_models, combine_strategy FROM presets WHERE name = 'Default Preset'")
    row = c.fetchone()
    if row:
        print('Default Preset Combine Settings:')
        print(f'  enable_combine: {row[0]}')
        print(f'  combine_models: {row[1]}')
        print(f'  combine_strategy: {row[2]}')
    else:
        print("Default Preset not found")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
