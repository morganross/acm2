import sqlite3
import json

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cursor = conn.cursor()

# Check Default Preset config
print("=== DEFAULT PRESET ===")
cursor.execute("SELECT id, name, documents FROM presets WHERE name = 'Default Preset'")
row = cursor.fetchone()
if row:
    print(f"ID: {row[0]}")
    print(f"Name: {row[1]}")
    documents = json.loads(row[2]) if row[2] else []
    print(f"documents: {documents}")
    
    # Fix: Remove orphaned document IDs (keep only 0dd19fd9...)
    old_doc_ids = documents
    new_doc_ids = [d for d in old_doc_ids if d.startswith('0dd19fd9')]
    
    if old_doc_ids != new_doc_ids:
        print(f"\nRemoving orphaned IDs...")
        print(f"  Old: {old_doc_ids}")
        print(f"  New: {new_doc_ids}")
        cursor.execute("UPDATE presets SET documents = ? WHERE id = ?", (json.dumps(new_doc_ids), row[0]))
        conn.commit()
        print("  Updated!")
    else:
        print("  No orphaned IDs found")

conn.close()
