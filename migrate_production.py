import sqlite3
import os

DB_PATH = "quest_board.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("Starting production migration...")
    
    # ─── Quests Table ───
    try:
        conn.execute("ALTER TABLE quests ADD COLUMN type TEXT DEFAULT 'NORMAL'")
        print("Added type to quests")
    except sqlite3.OperationalError as e: print(f"Quests type: {e}")
    
    try:
        conn.execute("ALTER TABLE quests ADD COLUMN reward INTEGER DEFAULT 10")
        print("Added reward to quests")
    except sqlite3.OperationalError as e: print(f"Quests reward: {e}")
    
    try:
        conn.execute("ALTER TABLE quests ADD COLUMN deadline_at DATETIME")
        print("Added deadline_at to quests")
    except sqlite3.OperationalError as e: print(f"Quests deadline: {e}")
    
    try:
        conn.execute("ALTER TABLE quests ADD COLUMN delivered_at DATETIME")
        conn.execute("UPDATE quests SET delivered_at = CURRENT_TIMESTAMP WHERE delivered_at IS NULL")
        print("Added delivered_at to quests")
    except sqlite3.OperationalError as e: print(f"Quests delivered: {e}")

    # ─── Submissions Table ───
    try:
        conn.execute("ALTER TABLE submissions ADD COLUMN submitted_at DATETIME")
        conn.execute("UPDATE submissions SET submitted_at = CURRENT_TIMESTAMP WHERE submitted_at IS NULL")
        print("Added submitted_at to submissions")
    except sqlite3.OperationalError as e: print(f"Submissions submitted: {e}")
    
    try:
        conn.execute("ALTER TABLE submissions ADD COLUMN approved_at DATETIME")
        print("Added approved_at to submissions")
    except sqlite3.OperationalError as e: print(f"Submissions approved: {e}")
    
    try:
        conn.execute("ALTER TABLE submissions ADD COLUMN claimed_at DATETIME")
        print("Added claimed_at to submissions")
    except sqlite3.OperationalError as e: print(f"Submissions claimed: {e}")

    # ─── User Table ───
    try:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        print("Added password_hash to users")
    except sqlite3.OperationalError as e: print(f"Users password_hash: {e}")
    
    try:
        conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
        print("Added google_id to users")
    except sqlite3.OperationalError as e: print(f"Users google_id: {e}")

    try:
        conn.execute("ALTER TABLE users ADD COLUMN specialty TEXT")
        print("Added specialty to users")
    except sqlite3.OperationalError as e: print(f"Users specialty: {e}")

    try:
        conn.execute("ALTER TABLE users ADD COLUMN bio TEXT")
        print("Added bio to users")
    except sqlite3.OperationalError as e: print(f"Users bio: {e}")

    try:
        conn.execute("ALTER TABLE users ADD COLUMN icon_url TEXT")
        print("Added icon_url to users")
    except sqlite3.OperationalError as e: print(f"Users icon_url: {e}")

    # ─── Announcements Tables (Create if not exist) ───
    cur.executescript("""
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
    print("Ensured announcement tables exist")

    conn.commit()
    conn.close()
    print("Migration finished successfully.")

if __name__ == "__main__":
    migrate()
