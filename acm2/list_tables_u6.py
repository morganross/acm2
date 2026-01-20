import sqlite3
conn = sqlite3.connect('data/user_6.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([t[0] for t in c.fetchall()])
