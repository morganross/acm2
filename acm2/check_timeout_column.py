import sqlite3
import os

DB_PATH = "acm2/acm2/data/acm2.db"

def check_timeouts():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables:", tables)
        
        # cursor.execute("SELECT id, name, request_timeout FROM presets")
        rows = cursor.fetchall()
        print(f"{'ID':<40} {'Name':<30} {'Timeout':<10}")
        print("-" * 80)
        for row in rows:
            print(f"{row[0]:<40} {row[1]:<30} {row[2]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_timeouts()
