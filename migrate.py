import sqlite3
DB_PATH = "quest_board.db"
conn = sqlite3.connect(DB_PATH)
try:
    conn.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
except sqlite3.OperationalError: pass
try:
    conn.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
except sqlite3.OperationalError: pass
try:
    conn.execute("ALTER TABLE users ADD COLUMN title TEXT DEFAULT 'Novice'")
except sqlite3.OperationalError: pass
try:
    conn.execute("ALTER TABLE quests ADD COLUMN type TEXT CHECK(type IN ('NORMAL', 'EMERGENCY', 'SPECIAL')) DEFAULT 'NORMAL'")
except sqlite3.OperationalError: pass
try:
    conn.execute("ALTER TABLE quests ADD COLUMN reward INTEGER DEFAULT 10")
except sqlite3.OperationalError: pass
conn.commit()
conn.close()
print("Migration successful")
