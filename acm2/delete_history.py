import sqlite3
import os
import shutil
from pathlib import Path

def delete_history():
    # 1. Delete from Database
    db_path = Path.home() / '.acm2' / 'acm2.db'
    print(f"Database path: {db_path}")
    
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if tables exist before deleting
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            if 'artifacts' in tables:
                print("Deleting artifacts...")
                cursor.execute("DELETE FROM artifacts")
            
            if 'tasks' in tables:
                print("Deleting tasks...")
                cursor.execute("DELETE FROM tasks")
                
            if 'runs' in tables:
                print("Deleting runs...")
                cursor.execute("DELETE FROM runs")
                
            conn.commit()
            conn.close()
            print("Database records deleted.")
        except Exception as e:
            print(f"Error deleting from database: {e}")
    else:
        print("Database file not found.")

    # 2. Delete Logs
    logs_dir = Path(r"c:\dev\fats\logs")
    print(f"Logs directory: {logs_dir}")
    
    if logs_dir.exists():
        for item in logs_dir.iterdir():
            if item.is_dir():
                try:
                    shutil.rmtree(item)
                    print(f"Deleted log directory: {item.name}")
                except Exception as e:
                    print(f"Error deleting log directory {item.name}: {e}")
            else:
                # Optional: delete files in logs root too?
                # User said "delete all current and past runs".
                # Usually logs root might contain global logs.
                pass
    else:
        print("Logs directory not found.")

if __name__ == "__main__":
    delete_history()
