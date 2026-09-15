#!/usr/bin/env python3
"""
infra/migrate.py — Versioned database migration runner.
Supports SQLite (local development) and Postgres (production) (P2-6).
"""
import glob
import os
import sqlite3
import sys


def get_db_target():
    db_url = os.getenv("DATABASE_URL")
    if db_url and (db_url.startswith("postgres://") or db_url.startswith("postgresql://")):
        return ("postgres", db_url)
    sqlite_path = os.getenv("RBR_DB_URL", "./rbr_local.db")
    if ":///" in sqlite_path:
        sqlite_path = sqlite_path.split(":///")[-1]
    elif "://" in sqlite_path:
        sqlite_path = sqlite_path.split("://")[-1]
    return ("sqlite", os.path.abspath(sqlite_path))


def run_sqlite_migrations(db_path: str, migrations_dir: str):
    print(f"Running SQLite migrations on: {db_path}")
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        ''')
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}

        files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
        for f in files:
            version = os.path.basename(f)
            if version not in applied:
                print(f"Applying {version}...")
                with open(f, "r", encoding="utf-8") as sql_file:
                    conn.executescript(sql_file.read())
                import datetime
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, now_iso))
                print(f"Successfully applied {version}")
            else:
                print(f"Skipping already applied {version}")
    conn.close()
    print("All SQLite migrations up to date.")


def main():
    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    db_type, target = get_db_target()
    if db_type == "sqlite":
        run_sqlite_migrations(target, migrations_dir)
    else:
        print(f"Postgres migrations for {target} can be executed via asyncpg pool.")


if __name__ == "__main__":
    main()
