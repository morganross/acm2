import sqlite3

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cursor = conn.cursor()

cursor.execute('SELECT id, title, status, error_message FROM runs ORDER BY created_at DESC LIMIT 1')
run = cursor.fetchone()

print('=== LATEST RUN ===')
print(f'ID: {run[0]}')
print(f'Title: {run[1]}')
print(f'Status: {run[2]}')
print(f'Error: {run[3] if run[3] else "None"}')

conn.close()
