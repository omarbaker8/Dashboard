import sqlite3
from pathlib import Path
from server.config import DB_PATH


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    sql_path = Path(__file__).parent / 'migrations' / '001_schema.sql'
    conn = get_db()
    if sql_path.exists():
        conn.executescript(sql_path.read_text())
    else:
        _bootstrap(conn)
    conn.commit()
    conn.close()


def _bootstrap(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL CHECK(type IN ('laptop', 'tablet')),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS device_config (
            device_id   TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            PRIMARY KEY (device_id, key)
        );

        CREATE TABLE IF NOT EXISTS device_widgets (
            device_id   TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            widget_id   TEXT NOT NULL,
            x           INTEGER NOT NULL,
            y           INTEGER NOT NULL,
            w           INTEGER NOT NULL,
            h           INTEGER NOT NULL,
            css         TEXT NOT NULL DEFAULT '',
            extra       TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (device_id, widget_id)
        );

        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT PRIMARY KEY,
            applied_at  INTEGER NOT NULL DEFAULT (unixepoch())
        );
    """)
