# Database

ローカル開発ではプロジェクトルートの `compose.yaml` からMySQL 8.4を起動します。

## スキーマ

`database/schema.sql` にマッチアップ動画とユーザー評価（UV）のテーブル定義を記載しています。バックエンド起動時・リクエスト時には `backend/src/app/database.py` のSQLAlchemyモデルから自動的にテーブルが作成され、`backend/src/app/data/matchups.json` に動画があれば `matchup_videos` にシードされます（同梱のファイルは空です）。

- `matchup_videos`: 確認済み（`verified`）マッチアップ動画と累計UV数（`upvote_count`）を管理
- `matchup_video_votes`: ユーザー匿名トークンのハッシュ（`voter_hash`）単位の重複投票防止・トグル管理


## マイグレーション（Alembic）

スキーマ変更は Alembic で管理します（設定は `backend/alembic.ini`、スクリプトは `backend/migrations/`）。`DATABASE_URL` は `.env` から読み込まれます。

```sh
cd backend
../.venv/bin/alembic upgrade head                                  # 適用（既存DBでは何も変更しません）
../.venv/bin/alembic revision --autogenerate -m "変更内容"         # モデル変更から新しい版を生成
../.venv/bin/alembic check                                         # モデルとDBの差分の有無を確認
```

- `0001_baseline` は現行の3テーブルを定義します。Alembic導入前に `create_all` で作成済みのDBでは、存在するテーブルをスキップして版だけを記録します。
- アプリは起動時に引き続き `create_all` を実行します（新規テーブルの作成のみ。列の変更は行いません）。列の追加・変更は、モデルを変更したうえで Alembic の版を作成し、`upgrade head` を実行してください。
