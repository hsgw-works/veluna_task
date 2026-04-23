import sqlite3

def migrate():
    conn = sqlite3.connect('quest_board.db')
    try:
        conn.execute('ALTER TABLE users ADD COLUMN discord_user_id TEXT')
        conn.commit()
        print(" Column 'discord_user_id' added successfully.")
    except sqlite3.OperationalError:
        print("ℹ Column 'discord_user_id' already exists.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
