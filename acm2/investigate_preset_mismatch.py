"""Deep investigation: WHY does the preset never match the run?"""
import sqlite3
import os
import json

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 80)
print("INVESTIGATION: WHY DOES PRESET NEVER MATCH RUN?")
print("=" * 80)

# 1. Get the Default Preset
print("\n1. DEFAULT PRESET IN DATABASE:")
print("-" * 40)
c.execute("SELECT id, name, documents, models, input_content_ids FROM presets WHERE name LIKE '%Default%'")
preset = c.fetchone()
if preset:
    print(f"   Preset ID: {preset['id']}")
    print(f"   Name: {preset['name']}")
    print(f"   documents column: {preset['documents']}")
    print(f"   input_content_ids column: {preset['input_content_ids']}")
    print(f"   models column: {preset['models']}")
    
    # Parse JSON
    try:
        docs = json.loads(preset['documents']) if preset['documents'] else []
        print(f"   Parsed documents: {len(docs)} items -> {docs}")
    except:
        print(f"   Could not parse documents JSON")
        
    try:
        content_ids = json.loads(preset['input_content_ids']) if preset['input_content_ids'] else []
        print(f"   Parsed input_content_ids: {len(content_ids)} items -> {content_ids}")
    except:
        print(f"   Could not parse input_content_ids JSON")

# 2. Check the documents table
print("\n2. DOCUMENTS TABLE:")
print("-" * 40)
c.execute("SELECT id, name FROM documents")
docs = c.fetchall()
print(f"   Total documents: {len(docs)}")
for d in docs:
    print(f"   - {d['id'][:8]}... : {d['name']}")

# 3. Check the contents table (input_document type)
print("\n3. CONTENTS TABLE (input_document type):")
print("-" * 40)
c.execute("SELECT id, name, content_type FROM contents WHERE content_type = 'input_document'")
contents = c.fetchall()
print(f"   Total input_documents: {len(contents)}")
for c2 in contents:
    print(f"   - {c2['id'][:8]}... : {c2['name']}")

# 4. Check recent run configs
print("\n4. RECENT RUN CONFIGS:")
print("-" * 40)
c.execute("SELECT id, name, config FROM runs ORDER BY created_at DESC LIMIT 3")
runs = c.fetchall()
for run in runs:
    print(f"\n   Run {run['id'][:8]}:")
    if run['config']:
        try:
            config = json.loads(run['config'])
            if 'documents' in config:
                print(f"      config.documents: {len(config.get('documents', []))} items")
                for doc in config.get('documents', []):
                    if isinstance(doc, dict):
                        print(f"         - {doc.get('id', 'no-id')[:8]}...: {doc.get('name', 'no-name')}")
                    else:
                        print(f"         - {doc}")
            if 'models' in config:
                print(f"      config.models: {config.get('models', [])}")
        except Exception as e:
            print(f"      Error parsing config: {e}")

# 5. CRITICAL: Check how preset documents are loaded in the API
print("\n5. THE LIKELY ROOT CAUSE:")
print("-" * 40)

# Check if preset.documents references IDs that exist in multiple tables
if preset:
    try:
        doc_ids = json.loads(preset['documents']) if preset['documents'] else []
        print(f"\n   Preset references these document IDs: {doc_ids}")
        
        for doc_id in doc_ids:
            # Check documents table
            c.execute("SELECT id, name FROM documents WHERE id = ?", (doc_id,))
            doc_match = c.fetchone()
            
            # Check contents table
            c.execute("SELECT id, name FROM contents WHERE id = ?", (doc_id,))
            content_match = c.fetchone()
            
            print(f"\n   ID {doc_id[:8]}...:")
            print(f"      In documents table: {doc_match['name'] if doc_match else 'NOT FOUND'}")
            print(f"      In contents table: {content_match['name'] if content_match else 'NOT FOUND'}")
    except Exception as e:
        print(f"   Error: {e}")

# 6. Check input_content_ids separately
print("\n6. INPUT_CONTENT_IDS ANALYSIS:")
print("-" * 40)
if preset and preset['input_content_ids']:
    try:
        content_ids = json.loads(preset['input_content_ids'])
        print(f"   Preset has {len(content_ids)} input_content_ids: {content_ids}")
    except:
        print(f"   Could not parse input_content_ids")
else:
    print("   input_content_ids is NULL or empty")

conn.close()
