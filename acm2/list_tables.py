import sqlite3
conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([r[0] for r in c.fetchall()])
