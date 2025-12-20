import sqlite3
import os
import json

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("SELECT config_overrides FROM presets WHERE name = 'Default Preset'")
    row = c.fetchone()
    if row and row[0]:
        overrides = json.loads(row[0])
        print("Default Preset Config Overrides:")
        print(json.dumps(overrides, indent=2))
        
        combine_config = overrides.get('combine', {})
        print("\nCombine Config:")
        print(json.dumps(combine_config, indent=2))
        
        if combine_config.get('enabled'):
            print("\nCombine IS enabled.")
        else:
            print("\nCombine is NOT enabled.")
    else:
        print("Default Preset not found or no config_overrides")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
