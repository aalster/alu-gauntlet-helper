import sqlite3
from pathlib import Path

from alu_gauntlet_helper.utils.utils import get_resource_path

DB_FILE = "app.db"
MIGRATIONS_DIR = Path(get_resource_path("migrations"))

def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # SQLite's built-in LIKE/LOWER fold case only for ASCII, so Cyrillic search
    # would be case-sensitive. Register a Unicode-aware lowercase function.
    conn.create_function("lower_u", 1, lambda s: s.lower() if s is not None else None, deterministic=True)
    return conn

def init_db():
    with connect() as conn:
        conn.execute("""
                     CREATE TABLE IF NOT EXISTS migrations (
                         id         TEXT PRIMARY KEY,
                         applied_at datetime not null default current_timestamp
                     )
                     """)
        applied = {row[0] for row in conn.execute("SELECT id FROM migrations")}

        if not MIGRATIONS_DIR.exists():
            print(f"Migrations directory not found: {MIGRATIONS_DIR}")
            return

        for migration in sorted(MIGRATIONS_DIR.iterdir()):
            if migration.name not in applied:
                try:
                    with open(migration, encoding="utf-8") as f:
                        conn.executescript(f.read())
                    conn.execute("INSERT INTO migrations (id) VALUES (:migration)", {"migration": migration.name})
                    print(f"Applied migration {migration.name}")
                except Exception as e:
                    print(f"Failed to apply migration {migration.name}: {e}")
                    raise