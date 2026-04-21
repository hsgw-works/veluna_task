# Veluna Task 外部連携ガイド

本アプリケーションで Discord 通知や Google Sheets 同期を有効にするための手順を解説します。

## 1. Discord Bot の連携

### ステップ 1: Bot の作成
1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセスし、「New Application」を作成します。
2. 左メニューの「Bot」を選択し、「Reset Token」をクリックして表示される **Token** をコピーします。
3. 同ページ下部の「Privileged Gateway Intents」セクションで **Message Content Intent** を ON にします（これがないとコマンドに反応できません）。

### ステップ 2: サーバーへの追加
1. 「OAuth2」→「URL Generator」を開きます。
2. `bot` と `applications.commands` にチェックを入れ、Permissionsで `Send Messages` などを選択します。
3. 生成された URL をブラウザで開き、自分のサーバーに Bot を追加します。

### ステップ 3: コードの設定
- `main.py` の `DISCORD_TOKEN` 変数にコピーした Token を貼り付けてください。

---

## 2. Google Sheets の連携

### ステップ 1: プロジェクトの作成
1. [Google Cloud Console](https://console.cloud.google.com/) で新しいプロジェクトを作成します。
2. 「API とサービス」→「ライブラリ」から **Google Sheets API** と **Google Drive API** を検索し、有効化（Enable）します。

### ステップ 2: サービスアカウントの作成
1. 「API とサービス」→「認証情報」から「認証情報を作成」→「サービスアカウント」を選択します。
2. 適当な名前を付けて作成し、作成したアカウントの「キー（Key）」タブから「鍵を追加」→「新しい鍵を作成（JSON）」を選択します。
3. ダウンロードされた JSON ファイルの名前を `service_account.json` に変更し、プロジェクトのルートディレクトリ（`main.py` と同じ場所）に配置します。

### ステップ 3: スプレッドシートの共有
1. 使用する Google スプレッドシートを新規作成し、URL から **Sheet ID**（`/d/` と `/edit` の間の文字列）をコピーします。
2. `service_account.json` 内の `client_email` アドレスをコピーし、スプレッドシートの「共有」ボタンからそのメールアドレスを **編集者 (Editor)** として追加します。

### ステップ 4: コードの設定
- `main.py` の `GOOGLE_SHEET_ID` 変数にコピーした Sheet ID を貼り付けてください。

---

## 3. キャパシティについて (SQLite)

本システムが採用している SQLite は、以下の理由により個人の「ギルド運営」レベルでは十分すぎる性能を持っています。

- **最大サイズ**: 理論上 140テラバイトまで対応。
- **同時読み込み**: 制限なし。
- **同時書き込み**: WAL（Write-Ahead Logging）モードを有効にしているため、短時間に数十人の書き込みが重なっても自動的にキューイングされ、エラーになりにくい設計です。
- **想定利用者数**: 秒間に数百回のアクセスがない限り、数千人規模のユーザーが登録されても動作に支障はありません。
