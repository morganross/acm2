"""
Migration: Add output configuration columns to presets table.

New columns:
- output_destination: Where to write winning documents ("none", "library", "github")
- output_filename_template: Template for output filename
- github_commit_message: Commit message for GitHub output

Also adds OUTPUT_DOCUMENT to content types.
"""
import sqlite3
from pathlib import Path


def migrate_database(db_path: str):
    """Add output columns to presets table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(presets)")
    existing_columns = {col[1] for col in cursor.fetchall()}
    
    columns_to_add = [
        ("output_destination", "TEXT DEFAULT 'library'"),
        ("output_filename_template", "TEXT DEFAULT '{source_doc_name}_{winner_model}_{timestamp}'"),
        ("github_commit_message", "TEXT DEFAULT 'ACM2: Add winning document'"),
    ]
    
    for col_name, col_def in columns_to_add:
        if col_name not in existing_columns:
            print(f"Adding column: {col_name}")
            cursor.execute(f"ALTER TABLE presets ADD COLUMN {col_name} {col_def}")
        else:
            print(f"Column already exists: {col_name}")
    
    conn.commit()
    conn.close()
    print(f"Migration complete for: {db_path}")


def migrate_all():
    """Migrate shared DB and all user DBs."""
    # Shared DB
    shared_db = Path.home() / ".acm2" / "acm2.db"
    if shared_db.exists():
        print(f"\n=== Migrating shared DB: {shared_db} ===")
        migrate_database(str(shared_db))
    
    # User DBs
    data_dir = Path(__file__).parent / "data"
    if data_dir.exists():
        for db_file in data_dir.glob("user_*.db"):
            print(f"\n=== Migrating user DB: {db_file} ===")
            migrate_database(str(db_file))


if __name__ == "__main__":
    migrate_all()
