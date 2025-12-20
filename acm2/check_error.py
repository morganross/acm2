import sqlite3

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
r = conn.execute("SELECT error_message, status FROM runs ORDER BY created_at DESC LIMIT 1").fetchone()
print(f"Error: {r[0]}")
print(f"Status: {r[1]}")
conn.close()
