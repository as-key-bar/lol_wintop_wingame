# Database

ローカル開発ではプロジェクトルートの `compose.yaml` からMySQL 8.4を起動します。

## スキーマ

`database/schema.sql` にマッチアップ動画とユーザー評価（UV）のテーブル定義を記載しています。バックエンド起動時・リクエスト時には `backend/src/app/database.py` のSQLAlchemyモデルから自動的にテーブルが作成され、`backend/src/app/data/matchups.json` の初期データが `matchup_videos` にシードされます。

- `matchup_videos`: 確認済み（`verified`）マッチアップ動画と累計UV数（`upvote_count`）を管理
- `matchup_video_votes`: ユーザー匿名トークンのハッシュ（`voter_hash`）単位の重複投票防止・トグル管理

