import sqlite3
conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
c = conn.cursor()

# Get the preset
c.execute('SELECT generation_instructions_id, fpf_config FROM presets LIMIT 1')
row = c.fetchone()
gen_id, fpf_config = row
print(f"generation_instructions_id: {gen_id}")
print(f"fpf_config: {fpf_config}")

# Get the generation instructions body
c.execute('SELECT name, body FROM contents WHERE id = ?', (gen_id,))
row = c.fetchone()
if row:
    name, body = row
    print(f"\nGeneration Instructions Content '{name}':")
    print(body[:1000] if len(body) > 1000 else body)
else:
    print("No content found for generation_instructions_id")

conn.close()
