import sqlite3
import json

conn = sqlite3.connect("C:/Users/kjhgf/.acm2/acm2.db")
cursor = conn.cursor()

cursor.execute("SELECT instruction_ids, generators, models, fpf_config FROM presets WHERE id = ?", ('86f721fc-742c-4489-9626-f148cb3d6209',))
row = cursor.fetchone()

if row:
    instruction_ids, generators, models, fpf_config = row
    print('instruction_ids:', instruction_ids)
    print('generators:', generators)
    print('models:', models)
    print('fpf_config:', fpf_config)
else:
    print("Preset not found")

conn.close()