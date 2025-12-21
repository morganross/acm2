import sqlite3
import os

conn = sqlite3.connect(os.path.expanduser('~/.acm2/acm2.db'))
c = conn.cursor()

print("CONTENTS TABLE (input_document type):")
c.execute("SELECT id, name, body FROM contents WHERE content_type = 'input_document'")
for r in c.fetchall():
    body_preview = r[2][:100] if r[2] else "NULL"
    print(f"  {r[0][:8]}... : {r[1]}")
    print(f"     Body: {body_preview}...")

print("\nDOCUMENTS TABLE:")
c.execute("SELECT id, name, content FROM documents")
for r in c.fetchall():
    content_preview = r[2][:100] if r[2] else "NULL"
    print(f"  {r[0][:8]}... : {r[1]}")
    print(f"     Content: {content_preview}...")

print("\nPRESET documents field:")
c.execute("SELECT documents FROM presets WHERE name LIKE '%Default%'")
row = c.fetchone()
if row:
    print(f"  {row[0]}")

conn.close()
