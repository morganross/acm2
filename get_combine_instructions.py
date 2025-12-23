import sqlite3

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cur = conn.cursor()

# Get combine instructions for default preset
cur.execute("""
    SELECT c.name, c.body 
    FROM presets p 
    JOIN content c ON p.combine_instructions_id = c.id 
    WHERE p.name = 'default'
""")
row = cur.fetchone()

if row:
    print(f"Name: {row[0]}")
    print()
    print("=" * 60)
    print("COMBINE INSTRUCTIONS (as sent to models)")
    print("=" * 60)
    print()
    print(row[1])
else:
    print("Not found")

conn.close()
