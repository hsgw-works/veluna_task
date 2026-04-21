import sqlite3
import os

DB_PATH = "quest_board.db"

def cleanup():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        print("Cleaning up database tables...")
        
        # Delete from tables
        cur.execute("DELETE FROM submissions")
        cur.execute("DELETE FROM quests")
        cur.execute("DELETE FROM announcements")
        cur.execute("DELETE FROM announcement_reads")
        
        # Delete users except 'Teaquen'
        cur.execute("DELETE FROM users WHERE name != 'Teaquen'")
        
        # Reset Teaquen's stats
        cur.execute("UPDATE users SET points = 0, level = 1, title = 'Novice' WHERE name = 'Teaquen'")
        
        conn.commit()
        print("Cleanup successful. All test data removed. 'Teaquen' stats reset.")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        conn.rollback()
    finally:
        conn.close()

    # Vacuum outside of transaction
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("VACUUM")
        conn.close()
        print("Database vacuumed and optimized.")
    except:
        pass

if __name__ == "__main__":
    cleanup()
