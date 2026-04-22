"""
Quest Board - タスク管理アプリ
FastAPI + SQLite + HTMX によるシンプルな実装
"""

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from datetime import datetime
import asyncio
import sqlite3
import os
from contextlib import contextmanager, asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

# ─── Integration Tools ───
# Note: These require valid credentials to be fully functional.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "REPLACE_ME")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "REPLACE_ME")
ADMIN_DISCORD_ID = os.getenv("ADMIN_DISCORD_ID", "REPLACE_ME")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
EXEC_CHANNEL_ID = os.getenv("EXEC_CHANNEL_ID", "REPLACE_ME")
# データベース接続URL（クラウド用）
DATABASE_URL = os.getenv("DATABASE_URL")

# クラウド用の永続データ保存先 (Railwayの /data 等)
DATA_DIR = os.getenv("DATA_DIR", ".")
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "quest_board.db")

try:
    import discord
    from discord.ext import commands
    intents = discord.Intents.default()
    intents.message_content = True  # Required for !submit
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f" Discord Bot logged in as {bot.user}")
        
    def broadcast_to_discord(title: str, description: str, color=0x00ff00):
        if not bot or not bot.is_ready():
            print(" Discord Bot is not ready yet.")
            return
            
        server_id = 1490336248022438109
        
        async def send_msg():
            guild = bot.get_guild(server_id)
            if not guild:
                print(f" 指定されたサーバー (ID: {server_id}) にBotが参加していません！")
                return
                
            # 「bot」という名前のチャンネルを検索
            channel = discord.utils.get(guild.text_channels, name="bot")
            
            if not channel:
                print(" 「bot」という名前のテキストチャンネルが見つかりませんでした。")
                return
                
            try:
                embed = discord.Embed(title=title, description=description, color=color)
                await channel.send(embed=embed)
                print(f"✅ Discordへ通知しました: {title}")
            except Exception as e:
                print(f"⚠️ Discordへの送信に失敗: {e}")
                
        asyncio.run_coroutine_threadsafe(send_msg(), bot.loop)

    def broadcast_to_channel(channel_id_str, title: str, description: str, color=0x9b59b6):
        """特定のチャンネルIDへ通知を送るヘルパー"""
        if not bot or not bot.is_ready() or channel_id_str == "REPLACE_ME":
            return

        async def send_msg():
            try:
                channel = bot.get_channel(int(channel_id_str))
                if channel:
                    embed = discord.Embed(title=title, description=description, color=color)
                    await channel.send(embed=embed)
                    print(f"✅ 共有チャンネル({channel_id_str})へ通知しました。")
            except Exception as e:
                print(f"⚠️ 共有チャンネルへの送信に失敗: {e}")

        asyncio.run_coroutine_threadsafe(send_msg(), bot.loop)
except ImportError:
    bot = None
    def broadcast_to_discord(title, description, color=0): pass
    def broadcast_to_channel(channel_id_str, title, description, color=0): pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Discord bot if token is provided
    if bot and DISCORD_TOKEN != "REPLACE_ME":
        asyncio.create_task(bot.start(DISCORD_TOKEN))
    yield
    # Shutdown
    if bot:
        await bot.close()

# ─── Auth Setup ───
# Use pbkdf2_sha256 which is more robust and avoids the bcrypt 72-byte limit/bug
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)

app = FastAPI(title="Veluna Task", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

from fastapi.staticfiles import StaticFiles
# UPLOAD_FOLDERが存在しない場合は作成
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# /uploads へのアクセスを、実際のUPLOAD_FOLDERディレクトリに紐付け
app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")

# ─── Auth Exception Handlers ───
@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code in [401, 403]:
        lang = request.cookies.get("preferred_lang", "ja")
        return templates.TemplateResponse(request, "auth_error.html", {
            "message": exc.detail,
            "lang": lang
        }, status_code=exc.status_code)
    # Fallback for others
    return templates.TemplateResponse(request, "auth_error.html", {
        "message": f"Error {exc.status_code}: {exc.detail}",
        "lang": "ja"
    }, status_code=exc.status_code)


# ────────────────────────────────────────────
# DB ユーティリティ
# ────────────────────────────────────────────

def get_db():
    if DATABASE_URL:
        # PostgreSQL (Cloud)
        import psycopg2
        from psycopg2.extras import RealDictCursor
        # Render等の環境変数によっては 'postgres://' で始まることがあるが、
        # psycopg2 は 'postgresql://' を推奨するため自動置換
        db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        conn.autocommit = True # Raw SQL の場合は自動コミットを推奨
        return conn
    else:
        # SQLite (Local)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

def execute_query(conn, query, params=None):
    """DBによってプレースホルダ (? か %s) を切り替える"""
    if DATABASE_URL:
        query = query.replace("?", "%s")
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    return cursor


def init_db():
    """テーブル作成 & 初期データ投入"""
    conn = get_db()
    cur = conn.cursor()

    # PostgreSQL互換のデータ型に置換 (SQLiteの場合は無視される)
    script = """
        CREATE TABLE IF NOT EXISTS users (
            id            SERIAL PRIMARY KEY,
            name          TEXT NOT NULL,
            role          TEXT NOT NULL CHECK(role IN ('admin', 'user')),
            password_hash TEXT,
            google_id     TEXT,
            points        INTEGER DEFAULT 0,
            level         INTEGER DEFAULT 1,
            title         TEXT DEFAULT 'Novice',
            specialty     TEXT,
            bio           TEXT,
            icon_url      TEXT,
            last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            discord_user_id TEXT
        );

        CREATE TABLE IF NOT EXISTS quests (
            id            SERIAL PRIMARY KEY,
            title         TEXT NOT NULL,
            description   TEXT,
            status        TEXT NOT NULL DEFAULT 'OPEN'
                          CHECK(status IN ('OPEN','CLAIMED','SUBMITTED','APPROVED','REJECTED')),
            type          TEXT NOT NULL DEFAULT 'NORMAL'
                          CHECK(type IN ('NORMAL', 'EMERGENCY', 'SPECIAL')),
            reward        INTEGER DEFAULT 10,
            created_by    INTEGER NOT NULL REFERENCES users(id),
            claimed_by    INTEGER REFERENCES users(id),
            delivered_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deadline_at   TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id            SERIAL PRIMARY KEY,
            quest_id      INTEGER NOT NULL REFERENCES quests(id),
            user_id       INTEGER NOT NULL REFERENCES users(id),
            content       TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'SUBMITTED'
                          CHECK(status IN ('SUBMITTED','APPROVED','REJECTED')),
            claimed_at    TIMESTAMP,
            submitted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at   TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id            SERIAL PRIMARY KEY,
            title         TEXT NOT NULL,
            content       TEXT NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS announcement_reads (
            announcement_id INTEGER NOT NULL REFERENCES announcements(id),
            user_id         INTEGER NOT NULL REFERENCES users(id),
            read_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (announcement_id, user_id)
        );
    """
    
    if not DATABASE_URL:
        # SQLite変換
        script = script.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        script = script.replace("TIMESTAMP", "DATETIME")
        conn.executescript(script)
    else:
        # PostgreSQL直接実行
        with conn.cursor() as cur:
            cur.execute(script)

    # 以降、execute_queryを使用して共通化
    execute_query(conn, "UPDATE users SET role = 'user' WHERE name != 'Teaquen'")
    
    existing = execute_query(conn, "SELECT id, password_hash FROM users WHERE name = 'Teaquen'").fetchone()

    if existing:
        # ロールと称号だけ修正。パスワードは照合できないときのみ更新
        needs_pw_update = not existing["password_hash"] or not verify_password("0924", existing["password_hash"])
        if needs_pw_update:
            new_hash = hash_password("0924")
            execute_query(conn, "UPDATE users SET role='admin', password_hash=?, title='High Administrator', level=99, points=1000 WHERE name='Teaquen'", (new_hash,))
        else:
            execute_query(conn, "UPDATE users SET role='admin', title='High Administrator' WHERE name='Teaquen'")
    else:
        new_hash = hash_password("0924")
        execute_query(conn, "INSERT INTO users (name, role, password_hash, points, level, title) VALUES (?, ?, ?, ?, ?, ?)", ("Teaquen", "admin", new_hash, 1000, 99, "High Administrator"))

    # 他の初期ユーザー
    if not execute_query(conn, "SELECT 1 FROM users WHERE name != 'Teaquen' LIMIT 1").fetchone():
        users_to_add = [
            ("セラフィナ", "user"),
            ("魔法使いカル", "user"),
            ("弓使いダナ",   "user"),
        ]
        for u in users_to_add:
            execute_query(conn, "INSERT INTO users (name, role) VALUES (?, ?)", u)

    conn.commit()
    conn.close()


# ────────────────────────────────────────────
# ヘルパー
# ────────────────────────────────────────────

def current_user(request: Request):
    """Cookie からユーザー ID を取得する簡易認証 + オンライン更新"""
    uid = request.cookies.get("user_id")
    if not uid:
        return None
    try:
        user_id = int(uid)
    except (ValueError, TypeError):
        return None

    conn = get_db()
    # 最終アクティブ日時を更新
    execute_query(conn, "UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
    conn.commit()
    user = execute_query(conn, "SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def require_user(request: Request):
    """Cookie からユーザー ID を取得し、なければ 401 をスロー"""
    user = current_user(request)
    if not user:
        lang = request.cookies.get("preferred_lang", "ja")
        msg = "ログインが必要です" if lang == "ja" else "Login required"
        raise HTTPException(status_code=401, detail=msg)
    return user


def require_admin(request: Request):
    user = require_user(request)
    # Strictly enforce Teaquen as the only admin
    if user["name"] != "Teaquen" or user["role"] != "admin":
        lang = request.cookies.get("preferred_lang", "ja")
        msg = "管理者権限が必要です" if lang == "ja" else "Admin privileges required"
        raise HTTPException(status_code=403, detail=msg)
    return user


# ────────────────────────────────────────────
# ページルート
# ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = current_user(request)
    lang = request.cookies.get("preferred_lang", "ja")
    if user:
        return RedirectResponse(url="/home", status_code=303)
    return templates.TemplateResponse(request, "index.html", {"user": user, "lang": lang})


@app.get("/toggle-lang")
def toggle_lang(request: Request):
    current_lang = request.cookies.get("preferred_lang", "ja")
    new_lang = "en" if current_lang == "ja" else "ja"
    # Go back to previous page
    referer = request.headers.get("referer", "/")
    resp = RedirectResponse(url=referer, status_code=303)
    resp.set_cookie("preferred_lang", new_lang, max_age=365*24*60*60)
    return resp


@app.get("/home", response_class=HTMLResponse)
def home_portal(request: Request):
    user = require_user(request)
    lang = request.cookies.get("preferred_lang", "ja")
    conn = get_db()
    # Stats - COUNT(*) as count とエイリアスをつけて辞書形式で取得
    res = execute_query(conn, "SELECT COUNT(*) as count FROM quests WHERE claimed_by = ? AND status IN ('CLAIMED','SUBMITTED')", (user["id"],)).fetchone()
    my_active = res["count"] if res else 0
    
    # Recent quests
    recent_quests = execute_query(conn, "SELECT * FROM quests WHERE status = 'OPEN' ORDER BY delivered_at DESC LIMIT 3").fetchall()
    
    # Recent announcements
    announcements = execute_query(conn, "SELECT * FROM announcements ORDER BY created_at DESC LIMIT 3").fetchall()
    
    # All members (for the online member strip)
    all_members = execute_query(conn, """SELECT id, name, icon_url, level, title, role, 
           (last_active_at >= (CURRENT_TIMESTAMP - INTERVAL '5 minutes')) as is_online 
           FROM users ORDER BY role DESC, points DESC""" if DATABASE_URL else """SELECT id, name, icon_url, level, title, role, 
           (last_active_at >= datetime('now', '-5 minutes')) as is_online 
           FROM users ORDER BY role DESC, points DESC""").fetchall()
    
    conn.close()
    return templates.TemplateResponse(request, "home.html", {
        "user": user, 
        "lang": lang,
        "active_count": my_active,
        "recent_quests": recent_quests,
        "announcements": announcements,
        "all_members": all_members,
    })


@app.post("/signup")
def signup(name: str = Form(...), password: str = Form(...)):
    conn = get_db()
    # Check if user exists
    if execute_query(conn, "SELECT 1 FROM users WHERE name = ?", (name,)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="User already exists")
    
    hashed = hash_password(password)
    # 常に 'user' ロールで作成（Teaquenのみが管理者のため）
    execute_query(conn, "INSERT INTO users (name, role, password_hash) VALUES (?, 'user', ?)", (name, hashed))
    conn.commit()
    user = execute_query(conn, "SELECT * FROM users WHERE name = ?", (name,)).fetchone()
    conn.close()
    
    resp = RedirectResponse(url="/home", status_code=303)
    # Automatic login: 30 days
    resp.set_cookie("user_id", str(user["id"]), max_age=30*24*60*60)
    return resp


@app.get("/auth/google", response_class=HTMLResponse)
def auth_google(request: Request):
    return templates.TemplateResponse(request, "auth_error.html", {
        "message": "Google Login requires configuration. Please contact the administrator to set up Client ID and Secret."
    })


@app.post("/login")
def login(request: Request, name: str = Form(...), password: str = Form(...)):
    name = name.strip() # Handle trailing spaces
    conn = get_db()
    user = execute_query(conn, "SELECT * FROM users WHERE name = ?", (name,)).fetchone()
    conn.close()
    
    lang = request.cookies.get("preferred_lang", "ja")
    
    if not user:
        msg = "ユーザーが見つかりません" if lang == "ja" else "User not found"
        return templates.TemplateResponse(request, "auth_error.html", {"message": msg, "lang": lang}, status_code=401)
        
    if not user["password_hash"]:
        return templates.TemplateResponse(request, "auth_error.html", {
            "message": f"Account '{name}' exists but has no password set (Legacy).",
            "lang": lang
        })

    if not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(request, "auth_error.html", {
            "message": "Invalid PIN." if lang == "en" else "PINが正しくありません。",
            "lang": lang
        })
        
    resp = RedirectResponse(url="/home", status_code=303)
    # Automatic login: 30 days
    resp.set_cookie("user_id", str(user["id"]), max_age=30*24*60*60)
    return resp


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    user = require_user(request)
    lang = request.cookies.get("preferred_lang", "ja")
    return templates.TemplateResponse(request, "profile.html", {"user": user, "lang": lang})


@app.post("/profile")
def update_profile(
    request: Request,
    name: str = Form(...),
    specialty: str = Form(""),
    bio: str = Form(""),
    icon_url: str = Form(""),
    discord_user_id: str = Form("")
):
    user = require_user(request)
    conn = get_db()
    execute_query(conn, "UPDATE users SET name = ?, specialty = ?, bio = ?, icon_url = ?, discord_user_id = ? WHERE id = ?", (name, specialty, bio, icon_url, discord_user_id, user["id"]))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/profile", status_code=303)


@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("user_id")
    return resp


@app.get("/board", response_class=HTMLResponse)
def board(request: Request):
    user = require_user(request)
    lang = request.cookies.get("preferred_lang", "ja")
    conn = get_db()
    quests = execute_query(conn, "SELECT q.*, u.name AS creator_name FROM quests q "
        "JOIN users u ON q.created_by = u.id "
        "WHERE q.status = 'OPEN' ORDER BY q.id DESC").fetchall()
    conn.close()
    return templates.TemplateResponse(request, "board.html", {"user": user, "quests": quests, "lang": lang})


@app.get("/my-quests", response_class=HTMLResponse)
def my_quests(request: Request):
    user = require_user(request)
    lang = request.cookies.get("preferred_lang", "ja")
    conn = get_db()
    quests = execute_query(conn, "SELECT q.*, u.name AS creator_name FROM quests q "
        "JOIN users u ON q.created_by = u.id "
        "WHERE q.claimed_by = ? ORDER BY q.id DESC", (user["id"],)).fetchall()
    conn.close()
    return templates.TemplateResponse(request, "my_quests.html", {"user": user, "quests": quests, "lang": lang})


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = require_admin(request)
    conn = get_db()
    # 提出済みクエストと提出内容を結合して取得
    submitted = execute_query(conn, """
        SELECT s.id AS sub_id, s.content, s.status AS sub_status,
               q.id AS quest_id, q.title,
               u.name AS user_name
        FROM submissions s
        JOIN quests q ON s.quest_id = q.id
        JOIN users u ON s.user_id = u.id
        WHERE s.status = 'SUBMITTED'
        ORDER BY s.id DESC
    """).fetchall()
    all_quests = execute_query(conn, "SELECT q.*, u.name AS creator_name FROM quests q "
        "JOIN users u ON q.created_by = u.id ORDER BY q.id DESC").fetchall()
    
    # メンバー名簿の取得
    members = execute_query(conn, "SELECT * FROM users ORDER BY level DESC, points DESC").fetchall()
    
    conn.close()
    return templates.TemplateResponse(request, "admin.html", {
        "user": user,
        "lang": request.cookies.get("preferred_lang", "ja"),
        "submitted": submitted, 
        "all_quests": all_quests,
        "members": members
    })


# ────────────────────────────────────────────
# API エンドポイント
# ────────────────────────────────────────────

@app.get("/quests")
def list_quests(request: Request):
    user = require_user(request)
    conn = get_db()
    quests = execute_query(conn, "SELECT q.*, u.name AS creator_name FROM quests q "
        "JOIN users u ON q.created_by = u.id WHERE q.status = 'OPEN'").fetchall()
    conn.close()
    return [dict(q) for q in quests]


@app.get("/rankings", response_class=HTMLResponse)
def rankings_page(request: Request):
    user = require_user(request)
    lang = request.cookies.get("preferred_lang", "ja")
    conn = get_db()
    # ポイントとレベルでソート。完了クエスト数もカウント。
    members = execute_query(conn, """
        SELECT u.*, 
               (SELECT COUNT(*) FROM submissions s WHERE s.user_id = u.id AND s.status = 'APPROVED') as completed_quests
        FROM users u 
        ORDER BY u.points DESC, u.level DESC
        LIMIT 20
    """).fetchall()
    conn.close()
    return templates.TemplateResponse(request, "rankings.html", {"user": user, "members": members, "lang": lang})


@app.post("/quests")
def create_quest(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    type: str = Form("NORMAL"),
    reward: int = Form(10),
    deadline: str = Form(None),
    quantity: int = Form(1)
):
    user = require_admin(request)
    conn = get_db()
    for _ in range(quantity):
        execute_query(conn, "INSERT INTO quests (title, description, type, reward, created_by, deadline_at) VALUES (?, ?, ?, ?, ?, ?)", (title, description, type, reward, user["id"], deadline))
    conn.commit()
    conn.close()
    
    quantity_text = f" (x{quantity}件)" if quantity > 1 else ""
    msg = f"報酬: **{reward} Pts**\n\n{description}"
    broadcast_to_discord(" 新着クエスト発行: " + title + quantity_text, msg, 0xe74c3c if type == 'EMERGENCY' else 0x3498db)
    
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/announcements")
def create_announcement(
    request: Request,
    title: str = Form(...),
    content: str = Form(...)
):
    require_admin(request)
    conn = get_db()
    execute_query(conn, "INSERT INTO announcements (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()
    
    broadcast_to_discord(" お知らせ: " + title, content, 0xf1c40f)
    
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/announcements/{ann_id}/check")
def check_announcement(ann_id: int, request: Request):
    user = require_user(request)
    conn = get_db()
    try:
        execute_query(conn, "INSERT INTO announcement_reads (announcement_id, user_id) VALUES (?, ?)", (ann_id, user["id"]))
        conn.commit()
    except:
        pass # Already read or unique constraint
    conn.close()
    return RedirectResponse(url="/home", status_code=303)


# ─── Quest Edit (Admin) ───

@app.get("/admin/quests/{quest_id}/edit", response_class=HTMLResponse)
def edit_quest_page(quest_id: int, request: Request):
    user = require_admin(request)
    lang = request.cookies.get("preferred_lang", "ja")
    conn = get_db()
    quest = execute_query(conn, "SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
    conn.close()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
        
    return templates.TemplateResponse(request, "edit_quest.html", {"user": user, "lang": lang, "q": quest})

@app.post("/admin/quests/{quest_id}/edit")
def edit_quest_submit(
    quest_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    type: str = Form(...),
    reward: int = Form(...),
    deadline: str = Form("")
):
    require_admin(request)
    conn = get_db()
    execute_query(conn, "UPDATE quests SET title = ?, description = ?, type = ?, reward = ?, deadline_at = ? WHERE id = ?", (title, description, type, reward, deadline if deadline else None, quest_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=303)


# ─── Google Sheets Sync Boilerplate ───
def sync_to_sheets(action: str, details: dict):
    """
    Export activity logs to Google Sheets.
    Requires: pip install gspread oauth2client
    Setup: Place 'service_account.json' in the project root.
    """
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        
        if GOOGLE_SHEET_ID == "REPLACE_ME": return

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        
        # Append a row: Time, Action, User, Details
        row = [datetime.now().isoformat(), action, details.get("user", "System"), str(details)]
        sheet.append_row(row)
    except Exception as e:
        print(f"Sheets Sync Error: {e}")

# ─── Local Storage Sync Boilerplate ───
def save_file_locally(file_bytes, filename, quest_type):
    import os
    import uuid
    import urllib.parse
    
    # 拡張子を維持しつつ安全なファイル名にする
    ext = os.path.splitext(filename)[1].lower()
    safe_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
    folder_path = os.path.join(UPLOAD_FOLDER, quest_type)
    
    # OSレベルでフォルダを作成
    os.makedirs(folder_path, exist_ok=True)
    
    file_path = os.path.join(folder_path, safe_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    # ウェブアプリでアクセスできる形式のURLを返す
    encoded_quest_type = urllib.parse.quote(quest_type)
    encoded_filename = urllib.parse.quote(safe_filename)
    return f"/uploads/{encoded_quest_type}/{encoded_filename}"



# ─── Discord Bot Listeners ───
if bot:
    @bot.command()
    async def submit(ctx, quest_id: int):
        """Allow users to submit reports via Discord: !submit 5 + attach file"""
        if not ctx.message.attachments:
            await ctx.send(" エラー: 提出するファイルをメッセージに添付してください。")
            return
            
        attachment = ctx.message.attachments[0]
        # 拡張子の緩和 (.pdf, .md, 画像)
        allowed_exts = (".pdf", ".md", ".jpg", ".jpeg", ".png", ".gif")
        if not attachment.filename.lower().endswith(allowed_exts):
            await ctx.send(" エラー: 許可されているファイル形式は PDF, 画像, または Markdown (.md) のみです。")
            return
            
        conn = get_db()
        quest = execute_query(conn, "SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
        
        if not quest:
            conn.close()
            await ctx.send(f" エラー: クエスト ID #{quest_id} が見つかりません。")
            return
            
        if quest["status"] != "CLAIMED" or not quest["claimed_by"]:
            conn.close()
            await ctx.send(f" エラー: クエスト ID #{quest_id} は受注状態（CLAIMED）ではありません。")
            return
            
        user_id = quest["claimed_by"]
        user = execute_query(conn, "SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
        
        # ローカル(OneDrive連携)への保存プロセス
        await ctx.send(" ファイルをサーバーの専用フォルダに保存しています...")
        import functools
        try:
            file_bytes = await attachment.read()
            quest_type = quest["type"]  # NORMAL, EMERGENCY, SPECIAL etc
            
            loop = asyncio.get_running_loop()
            local_url = await loop.run_in_executor(None, functools.partial(save_file_locally, file_bytes, attachment.filename, quest_type))
            content_url = local_url
            absolute_url = f"{BASE_URL}{local_url}"
        except Exception as e:
            await ctx.send(f"⚠️ 保存に失敗しました (フォールバックとしてDiscordのURLを記録します): {e}")
            content_url = attachment.url
            absolute_url = attachment.url
            
        # 提出記録を追加 (URLを保持)
        from datetime import datetime
        now = datetime.now().isoformat()
        execute_query(conn, "INSERT INTO submissions (quest_id, user_id, content, submitted_at) VALUES (?, ?, ?, ?)", (quest_id, user_id, content_url, now))
        execute_query(conn, "UPDATE quests SET status = 'SUBMITTED' WHERE id = ?", (quest_id,))
        conn.commit()
        conn.close()
        
        # 提出ログをGoogle Sheetsに同期
        try:
            sync_to_sheets("DISCORD_SUBMISSION", {"user": user['name'], "quest_id": quest_id, "file_url": absolute_url})
        except Exception as e:
            print(f"Failed to sync sheet: {e}")
            
        # 管理者へDM通知（ADMIN_DISCORD_IDが設定されていれば複数人対応）
        admin_text = f" **提出通知**\n**{user['name']}** さんが クエスト #{quest_id} の資料を提出しました！\n確認リンク: {absolute_url}"
        if ADMIN_DISCORD_ID and ADMIN_DISCORD_ID != "REPLACE_ME":
            for single_id in ADMIN_DISCORD_ID.split(','):
                single_id = single_id.strip()
                if not single_id: continue
                try:
                    admin_user = await bot.fetch_user(int(single_id))
                    if admin_user:
                        await admin_user.send(admin_text)
                except Exception as e:
                    print(f"Failed to DM Admin {single_id}: {e}")
        else:
            print("ADMIN_DISCORD_ID is not set. Admin DM skipped.")
        
        # 提出者へ通知（可能ならDM、無理ならチャンネル）
        submit_text = f" **提出完了**\nクエスト #{quest_id} の提出代行を受け付け、専用の保管庫に保存しました。\n管理者の審査をお待ちください。\nファイル: {attachment.filename}"
        try:
            await ctx.author.send(submit_text)
        except:
            await ctx.send(f"{ctx.author.mention} {submit_text}")



@app.post("/quests/{quest_id}/claim")
def claim_quest(quest_id: int, request: Request):
    user = require_user(request)
    if user["role"] == "admin":
        raise HTTPException(status_code=403, detail="管理者はクエストを受注できません")
        
    conn = get_db()
    quest = execute_query(conn, "SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
    if not quest or quest["status"] != "OPEN":
        conn.close()
        raise HTTPException(status_code=400, detail="Quest not available")
    
    execute_query(conn, "UPDATE quests SET status = 'CLAIMED', claimed_by = ? WHERE id = ?", (user["id"], quest_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/my-quests", status_code=303)


@app.post("/quests/{quest_id}/cancel")
def cancel_claim(quest_id: int, request: Request):
    user = require_user(request)
    conn = get_db()
    execute_query(conn, "UPDATE quests SET status = 'OPEN', claimed_by = NULL WHERE id = ? AND claimed_by = ? AND status IN ('CLAIMED', 'REJECTED')", (quest_id, user["id"]))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/my-quests", status_code=303)


@app.post("/quests/{quest_id}/unsubmit")
def unsubmit_quest(quest_id: int, request: Request):
    user = require_user(request)
    conn = get_db()
    quest = execute_query(conn, "SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
    if not quest or quest["status"] != "SUBMITTED" or quest["claimed_by"] != user["id"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot unsubmit this quest")
    
    execute_query(conn, "DELETE FROM submissions WHERE quest_id = ?", (quest_id,))
    execute_query(conn, "UPDATE quests SET status = 'CLAIMED' WHERE id = ?", (quest_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/my-quests", status_code=303)


@app.post("/quests/{quest_id}/duplicate")
def duplicate_quest(quest_id: int, request: Request):
    require_admin(request)
    conn = get_db()
    quest = execute_query(conn, "SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
    if not quest:
        conn.close()
        raise HTTPException(status_code=404)
        
    execute_query(conn, "INSERT INTO quests (title, description, type, reward, created_by) VALUES (?, ?, ?, ?, ?)", (quest["title"], quest["description"], quest["type"], quest["reward"], quest["created_by"]))
    conn.commit()
    conn.close()
    
    # 複製時のDiscord通知
    msg = f"報酬: **{quest['reward']} Pts**\n\n{quest['description']}"
    broadcast_to_discord(" クエスト再発行: " + quest['title'], msg, 0xe74c3c if quest['type'] == 'EMERGENCY' else 0x3498db)
    
    return RedirectResponse(url="/admin", status_code=303)



@app.post("/submissions/{sub_id}/approve")
def approve_submission(sub_id: int, request: Request):
    user = require_admin(request)
    conn = get_db()
    sub = execute_query(conn, "SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    if not sub:
        conn.close()
        raise HTTPException(status_code=404, detail="提出が見つかりません")
    
    # クエスト情報の取得
    quest = execute_query(conn, "SELECT * FROM quests WHERE id = ?", (sub["quest_id"],)).fetchone()
    
    # ポイントと報酬の処理
    reward = quest["reward"]
    now = datetime.now().isoformat()
    execute_query(conn, "UPDATE submissions SET status = 'APPROVED', approved_at = ? WHERE id = ?", (now, sub_id))
    execute_query(conn, "UPDATE quests SET status = 'APPROVED' WHERE id = ?", (sub["quest_id"],))
    
    # 受注者のポイントとレベルを更新
    claimant = execute_query(conn, "SELECT * FROM users WHERE id = ?", (sub["user_id"],)).fetchone()
    new_points = claimant["points"] + reward
    new_level = (new_points // 50) + 1
    
    # 称号の決定
    title = "Novice"
    if new_level >= 10: title = "Master"
    elif new_level >= 5: title = "Veteran"
    elif new_level >= 3: title = "Adept"
    
    execute_query(conn, "UPDATE users SET points = ?, level = ?, title = ? WHERE id = ?", (new_points, new_level, title, sub["user_id"]))
    conn.commit()
    conn.close()

    # メンバーへ通知 (DM)
    if claimant["discord_user_id"]:
        msg = f"🎉 **クエスト完了報告!**\nあなたの「{quest['title']}」の報告が承認されました！\n獲得ポイント: **{reward} Pts**\n現在のランク: **Lv.{new_level} {title}**\nお見事です、冒険者よ。"
        try:
            async def send_dm():
                discord_user = await bot.fetch_user(int(claimant["discord_user_id"]))
                if discord_user:
                    await discord_user.send(msg)
            asyncio.run_coroutine_threadsafe(send_dm(), bot.loop)
        except Exception as e:
            print(f"Failed to send approval DM: {e}")

    return RedirectResponse(url="/admin", status_code=303)


@app.post("/submissions/{sub_id}/reject")
def reject_submission(sub_id: int, request: Request):
    user = require_admin(request)
    conn = get_db()
    sub = execute_query(conn, "SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    if not sub:
        conn.close()
        raise HTTPException(status_code=404, detail="提出が見つかりません")
    execute_query(conn, "UPDATE submissions SET status = 'REJECTED' WHERE id = ?", (sub_id,))
    # クエストを CLAIMED に戻してユーザーが再提出できるようにする
    execute_query(conn, "UPDATE quests SET status = 'CLAIMED' WHERE id = ?", (sub["quest_id"],))
    conn.commit()

    # メンバー情報の取得
    claimant = execute_query(conn, "SELECT * FROM users WHERE id = ?", (sub["user_id"],)).fetchone()
    quest = execute_query(conn, "SELECT * FROM quests WHERE id = ?", (sub["quest_id"],)).fetchone()
    conn.close()

    # メンバーへ通知 (DM)
    if claimant["discord_user_id"]:
        msg = f"⚠️ **クエスト再提出連絡**\nあなたの「{quest['title']}」の報告は承認されませんでした。\n修正または不足資料を添付して、再度 `!submit` してください。"
        try:
            async def send_dm():
                discord_user = await bot.fetch_user(int(claimant["discord_user_id"]))
                if discord_user:
                    await discord_user.send(msg)
            asyncio.run_coroutine_threadsafe(send_dm(), bot.loop)
        except Exception as e:
            print(f"Failed to send rejection DM: {e}")

    return RedirectResponse(url="/admin", status_code=303)


# ────────────────────────────────────────────
# Admin: Member Management
# ────────────────────────────────────────────

@app.post("/admin/members/{target_id}/title")
def admin_set_title(request: Request, target_id: int, title: str = Form(...)):
    user = require_admin(request)
    conn = get_db()
    execute_query(conn, "UPDATE users SET title = ? WHERE id = ?", (title, target_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/members/{target_id}/penalty")
def admin_set_penalty(request: Request, target_id: int, points: int = Form(...)):
    user = require_admin(request)
    conn = get_db()
    # ポイントがマイナスにならないように各DBに応じた関数を使用
    penalty_query = "UPDATE users SET points = GREATEST(0, points - ?) WHERE id = ?" if DATABASE_URL else "UPDATE users SET points = MAX(0, points - ?) WHERE id = ?"
    execute_query(conn, penalty_query, (points, target_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=303)


# ────────────────────────────────────────────
# 外部連携 (Google & Discord)
# ────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()


if __name__ == "__main__":
    import uvicorn
    # クラウド環境では PORT 環境変数が指定されることが多いため、それに従う
    server_port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=server_port, reload=False if os.getenv("PORT") else True)
