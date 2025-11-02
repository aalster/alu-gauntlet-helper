import sqlite3
from pathlib import Path

DB_FILE = "app.db"
MIGRATIONS_DIR = Path("migrations")

def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
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
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration.name not in applied:
                with open(migration) as f:
                    conn.executescript(f.read())
                conn.execute("INSERT INTO migrations (id) VALUES (:migration)", {"migration": migration.name})
                print(f"Applied migration {migration.name}")
