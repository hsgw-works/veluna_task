# ⚔ Quest Board

FastAPI + SQLite + HTMX による軽量タスク管理アプリ（クエストシステム）

## ディレクトリ構成

```
quest-app/
├── main.py              # FastAPI アプリ本体
├── requirements.txt     # 依存パッケージ
├── quest_board.db       # SQLite DB（初回起動時に自動生成）
└── templates/
    ├── base.html        # 共通レイアウト
    ├── index.html       # ログイン（ユーザー選択）
    ├── board.html       # クエスト掲示板
    ├── my_quests.html   # マイクエスト
    └── admin.html       # 管理ダッシュボード
```

## セットアップ & 起動手順

### 1. Python 仮想環境の作成（推奨）

```bash
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows
venv\Scripts\activate
```

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. サーバーの起動

```bash
uvicorn main:app --reload
```

### 4. ブラウザでアクセス

```
http://localhost:8000
```

## 使い方

### 管理者（管理人アリス）の場合

1. ログイン画面で「管理人アリス（管理人）」を選択
2. `/admin` ダッシュボードでクエストを作成
3. ユーザーが提出した完了報告を承認 / 却下

### 一般ユーザーの場合

1. ログイン画面で冒険者を選択
2. `/board` でクエスト一覧を閲覧し「受注する」
3. `/my-quests` で完了報告を提出

## API エンドポイント

| Method | Path | 説明 |
|--------|------|------|
| GET    | /quests | クエスト一覧（JSON） |
| POST   | /quests | クエスト作成（管理者） |
| POST   | /quests/{id}/claim | クエスト受注 |
| POST   | /quests/{id}/submit | 完了報告提出 |
| POST   | /submissions/{id}/approve | 承認（管理者） |
| POST   | /submissions/{id}/reject  | 却下（管理者） |
