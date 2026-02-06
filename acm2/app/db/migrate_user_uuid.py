"""
Migrate per-user SQLite databases to include user_uuid columns.

Adds user_uuid to tables that now scope data by UUID and backfills
existing rows to the owning user's UUID (derived from the filename).
"""
import logging
import re
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"

TABLES_WITH_USER_UUID = [
    "contents",
    "documents",
    "presets",
    "runs",
    "provider_keys",
    "github_connections",
    "usage_stats",
    "user_settings",
]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str) -> None:
    if _column_exists(conn, table, column):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")


def _backfill_user_uuid(conn: sqlite3.Connection, table: str, user_uuid: str) -> None:
    conn.execute(
        f"UPDATE {table} SET user_uuid = ? WHERE user_uuid IS NULL OR user_uuid = ''",
        (user_uuid,),
    )


def _backfill_user_meta(conn: sqlite3.Connection, user_uuid: str) -> None:
    if not _table_exists(conn, "user_meta"):
        return
    if not _column_exists(conn, "user_meta", "uuid"):
        return
    conn.execute(
        "UPDATE user_meta SET uuid = ? WHERE uuid IS NULL OR uuid = ''",
        (user_uuid,),
    )


def migrate_user_db(db_path: Path, user_uuid: str) -> None:
    logger.info("Migrating %s for user %s", db_path.name, user_uuid)

    conn = sqlite3.connect(db_path)
    try:
        for table in TABLES_WITH_USER_UUID:
            if not _table_exists(conn, table):
                continue
            _add_column_if_missing(conn, table, "user_uuid")
            _backfill_user_uuid(conn, table, user_uuid)

        _backfill_user_meta(conn, user_uuid)
        conn.commit()
        logger.info("Migration complete for %s", db_path.name)
    finally:
        conn.close()


def _iter_user_dbs(filter_uuid: Optional[str] = None) -> Iterable[tuple[Path, str]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(
        r"^user_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.db$",
        re.IGNORECASE,
    )

    for db_path in DATA_DIR.glob("user_*.db"):
        match = pattern.match(db_path.name)
        if not match:
            continue
        user_uuid = match.group(1).lower()
        if filter_uuid and user_uuid != filter_uuid.lower():
            continue
        yield db_path, user_uuid


def main(filter_uuid: Optional[str] = None) -> None:
    logging.basicConfig(level=logging.INFO)

    any_found = False
    for db_path, user_uuid in _iter_user_dbs(filter_uuid):
        any_found = True
        migrate_user_db(db_path, user_uuid)

    if not any_found:
        logger.warning("No user databases found to migrate")


if __name__ == "__main__":
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg)
