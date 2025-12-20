"""Add new required columns to presets table."""
from app.infra.db.database import engine

def add_columns():
    """Add new columns to presets table."""
    conn = engine.connect()
    
    columns_to_add = [
        ('max_retries', 'INTEGER NOT NULL DEFAULT 3'),
        ('retry_delay', 'REAL NOT NULL DEFAULT 2.0'),
        ('request_timeout', 'INTEGER NOT NULL DEFAULT 600'),
        ('eval_timeout', 'INTEGER NOT NULL DEFAULT 600'),
        ('generation_concurrency', 'INTEGER NOT NULL DEFAULT 5'),
        ('eval_concurrency', 'INTEGER NOT NULL DEFAULT 5'),
        ('iterations', 'INTEGER NOT NULL DEFAULT 1'),
        ('eval_iterations', 'INTEGER NOT NULL DEFAULT 1'),
        ('fpf_log_output', 'TEXT NOT NULL DEFAULT "file"'),
        ('fpf_log_file_path', 'TEXT'),
        ('post_combine_top_n', 'INTEGER')
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            sql = f'ALTER TABLE presets ADD COLUMN {col_name} {col_type}'
            print(f"Executing: {sql}")
            conn.exec_driver_sql(sql)
            conn.commit()
            print(f"  ✓ Added column {col_name}")
        except Exception as e:
            if 'duplicate column name' in str(e).lower():
                print(f"  - Column {col_name} already exists, skipping")
            else:
                print(f"  ✗ Error adding {col_name}: {e}")
    
    conn.close()
    print("\nDone!")

if __name__ == '__main__':
    add_columns()
