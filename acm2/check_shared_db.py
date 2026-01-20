import sqlite3

# Check acm2_master MySQL for users and keys
import os

# First check the shared db structure
shared_db = 'C:/Users/kjhgf/.acm2/acm2.db'
print("Checking shared DB:", shared_db)
conn = sqlite3.connect(shared_db)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [t[0] for t in c.fetchall()])
