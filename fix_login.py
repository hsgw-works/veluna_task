"""
DBの users テーブルを正しいスキーマで再作成するマイグレーションスクリプト。
既存のユーザーデータを引き継ぎ、Teaquenを正しく作成する。
"""
import sqlite3
from passlib.context import CryptContext

DB = "quest_board.db"
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = OFF")  # FK制約を一時無効化

print("=== スキーマ移行開始 ===")

# 1. 既存データを退避
old_users = conn.execute(
    "SELECT rowid, id, name, role, password_hash, google_id, points, level, title, specialty, bio, icon_url FROM users"
).fetchall()
print(f"既存ユーザー数: {len(old_users)}")
for u in old_users:
    print(f"  rowid={u['rowid']} id={u['id']} name={u['name']} role={u['role']}")

# 2. 旧テーブルを削除
conn.execute("DROP TABLE IF EXISTS users")
print("旧テーブル削除")

# 3. 正しいスキーマでテーブルを再作成
conn.execute("""
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('admin', 'user')),
    password_hash TEXT,
    google_id     TEXT,
    points        INTEGER DEFAULT 0,
    level         INTEGER DEFAULT 1,
    title         TEXT DEFAULT 'Novice',
    specialty     TEXT,
    bio           TEXT,
    icon_url      TEXT
)
""")
print("新テーブル作成 (id INTEGER PRIMARY KEY AUTOINCREMENT)")

# 4. 不要なアカウントを除いて移行
junk = {"MasterAdmin", "SuperAdmin", "MainAdmin", "Teaquun", "TestAgent",
        "Verifier", "FinalHero", "FinalTestUser", "VerifiedHero", "VerifiedHero2",
        "AID", "Bob", "Teaquen"}  # Teaquenは後で正しく作成

migrated = 0
for u in old_users:
    if u['name'] in junk:
        print(f"  スキップ: {u['name']}")
        continue
    conn.execute(
        "INSERT INTO users (name, role, password_hash, google_id, points, level, title, specialty, bio, icon_url) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (u['name'], 'user', u['password_hash'], u['google_id'],
         u['points'] or 0, u['level'] or 1, u['title'] or 'Novice',
         u['specialty'], u['bio'], u['icon_url'])
    )
    migrated += 1
    print(f"  移行: {u['name']}")

# 5. Teaquenを正しく作成
teaquen_hash = pwd.hash("0924")
conn.execute(
    "INSERT INTO users (name, role, password_hash, points, level, title) VALUES ('Teaquen','admin',?,1000,99,'High Administrator')",
    (teaquen_hash,)
)
print("Teaquen 作成完了")

conn.commit()

# 6. 検証
print("\n=== 最終確認 ===")
for u in conn.execute("SELECT id, name, role FROM users ORDER BY role DESC, id ASC"):
    print(f"  [{u['id']}] {u['name']} ({u['role']})")

row = conn.execute("SELECT id, password_hash FROM users WHERE name='Teaquen'").fetchone()
ok = pwd.verify("0924", row['password_hash'])
print(f"\nTeaquen: id={row['id']}, PIN認証={'+OK' if ok else '-NG'}")

schema = conn.execute("PRAGMA table_info(users)").fetchall()
for c in schema:
    print(f"  列: {c[1]} {c[2]} pk={c[5]}")

conn.execute("PRAGMA foreign_keys = ON")
conn.close()
print("\n移行完了!")
