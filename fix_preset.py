import sqlite3

conn = sqlite3.connect(r'C:/Users/kjhgf/.acm2/acm2.db')
cur = conn.cursor()

print("Documents:")
cur.execute("SELECT id, name, path FROM documents")
print(cur.fetchall())

print("\nPresets:")
cur.execute("SELECT name, documents FROM presets WHERE name = 'Default Preset'")
print(cur.fetchall())

conn.close()
