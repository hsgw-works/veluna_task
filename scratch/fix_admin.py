import sqlite3
from passlib.hash import pbkdf2_sha256

def hash_password(password: str):
    return pbkdf2_sha256.hash(password)

def fix():
    conn = sqlite3.connect('quest_board.db')
    cur = conn.cursor()
    
    # 既存の 'Teaqun' もしあれば 'Teaquen' にリネームするか削除
    cur.execute("DELETE FROM users WHERE name = 'Teaqun'")
    
    # Teaquen の作成または更新
    teaquen_hash = hash_password("0924")
    user = cur.execute("SELECT id FROM users WHERE name = 'Teaquen'").fetchone()
    
    if not user:
        cur.execute(
            "INSERT INTO users (name, role, password_hash, title, level, points) VALUES (?, ?, ?, ?, ?, ?)",
            ("Teaquen", "admin", teaquen_hash, "High Administrator", 1, 0)
        )
        print("Teaquen created as admin")
    else:
        cur.execute(
            "UPDATE users SET role = 'admin', password_hash = ? WHERE name = 'Teaquen'",
            (teaquen_hash,)
        )
        print("Teaquen promoted to admin")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix()
