import sqlite3
DB_PATH = "quest_board.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

def add_column(table, column, type, default=None):
    try:
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {type}"
        if default is not None:
            sql += f" DEFAULT {default}"
        c.execute(sql)
        print(f"Added {column} to {table}")
    except sqlite3.OperationalError:
        print(f"Column {column} in {table} already exists")

# Users
add_column("users", "password_hash", "TEXT")
add_column("users", "google_id", "TEXT")
add_column("users", "specialty", "TEXT")
add_column("users", "bio", "TEXT")
add_column("users", "icon_url", "TEXT")

# Quests
add_column("quests", "delivered_at", "DATETIME", "CURRENT_TIMESTAMP")
add_column("quests", "deadline_at", "DATETIME")

# Submissions
add_column("submissions", "claimed_at", "DATETIME")
add_column("submissions", "submitted_at", "DATETIME", "CURRENT_TIMESTAMP")
add_column("submissions", "approved_at", "DATETIME")

# New Tables
try:
    c.executescript("""
        CREATE TABLE IF NOT EXISTS announcements (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            title         TEXT NOT NULL,
            content       TEXT NOT NULL,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS announcement_reads (
            announcement_id INTEGER NOT NULL REFERENCES announcements(id),
            user_id         INTEGER NOT NULL REFERENCES users(id),
            read_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (announcement_id, user_id)
        );
    """)
    print("New tables created")
except Exception as e:
    print(f"Error creating tables: {e}")

conn.commit()
conn.close()
