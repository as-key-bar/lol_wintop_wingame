# wintop-wingame

League of Legendsのトップレーン向けマッチアップ攻略ツールです。チャンピオンを2体選ぶと、その対面のリプレイ動画を再生でき、動画の概要欄から取得したルーン・サモナースペル・タイムスタンプも確認できます。ゲームクライアントの操作や自動プレイは行いません。

## 現在の状況

- Phase 1（チャンピオン選択、対面リプレイ、UV、MySQL永続化）：ほぼ完了
- Phase 2A（概要欄の解析、ルーン9枠・スペル・タイムスタンプの表示と手動編集）：実装済み
- Phase 2B/3（手動入力ベース）：全項目の手動入力・修正、ウェーブのプッシュ・プルのワンボタン入力は実装済み（本番にデプロイ済み。保存は Google ログインした編集者だけ（HTTPS 化と同時に有効化））。映像の画像認識は行いません（YouTube の書面許可が要るため）

公開前に必要な作業（YouTube Data API キーの発行、Riotポリシーの確認、AWSデプロイの実施）と次のステップは、[開発引継ぎメモ](./docs/HANDOFF.md)と[仕様書の第8章](./LoLタイマン勝てるのツール.md)にまとめています。

## 構成

- `frontend/`: Next.js、TypeScript
- `backend/`: Python、FastAPI
- `database/`: DB関連資料
- `scripts/`: 開発・保守用スクリプト
- `docs/`: プロジェクト資料
- `compose.yaml`: ローカル開発用MySQL 8.4

## 必要なツール

- Node.js 20.9以上、npm
- Python 3.12以上
- Docker Compose

## セットアップ

1. 開発用環境変数ファイルを作成します。

   ```sh
   cp .env.example .env
   cp frontend/.env.example frontend/.env.local
   ```

2. ローカルMySQLを起動します。

   ```sh
   docker compose up -d
   docker compose ps
   ```

   `docker compose` が使えない環境（Homebrew + Colima など）では、`docker-compose up -d` を使います。

3. フロントエンドを起動します（別ターミナル）。

   ```sh
   cd frontend
   npm run dev
   ```

   <http://localhost:3000> を開きます。

4. Python APIを起動します（別ターミナル、プロジェクトルートから実行）。

   ```sh
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -e "backend[dev]"
   python -m uvicorn app.main:app --app-dir backend/src --reload
   ```

   APIは <http://localhost:8000>、Swagger UIは <http://localhost:8000/docs> です。
   `/api/health` はAPIの稼働確認、`/api/health/database` はMySQL接続確認に使えます。

VS Codeでは、コマンドパレットから **Tasks: Run Task → Dev: Start app** を実行すると、APIとフロントエンドを同時に起動できます。停止するときは、それぞれのターミナルで `Ctrl+C` を押してください。アプリの確認先は <http://localhost:3000> です。

ローカル用のDB認証情報は `.env.example` に記載した開発専用値です。本番環境では使用せず、`.env` をコミットしないでください。

## 本番用の構成

AWS の EC2 1台に Docker Compose で載せる構成を用意しています（`compose.prod.yaml`、`deploy/`、`backend/Dockerfile`、`frontend/Dockerfile`）。環境変数の雛形は `deploy/env.example` です。実際の値は `deploy/.env`（Git 管理外）に書きます。デプロイ手順は非公開の `docs/DEPLOY_PRIVATE.md`（Git 管理外）にまとめています。

## YouTube データの保存期限

YouTube API で取得したデータ（動画のタイトル・チャンネル・URL、概要欄から抽出したビルド、その動画への UV）は、YouTube API Services Developer Policies III.E.4 に従い、**取得から3週間（21日）で自動削除**します（上限は30日。`YOUTUBE_DATA_RETENTION_DAYS` で短くできますが、30を超える値は30に丸められます）。更新（再取得）はせず、単純に削除します。

- 削除は `python -m app.retention`（本番は systemd のタイマー、毎日 04:00 JST。`deploy/install-retention-timer.sh`）。
- 期限切れの行は、削除ジョブが遅れても、API が返しません。
- 管理者が手動で保存したビルドも、動画の行と一緒に消えます。

## バージョン管理

リポジトリ直下の `VERSION` に `0.<フェーズ>.<プッシュ番号>` の形式で書きます。

- 1つ目：リリースするまでは `0`
- 2つ目：現在のフェーズ（現在は `2`）
- 3つ目：**`main` へのプッシュごとに1つ上げる**

画面のフッター（`v0.2.1`）と `GET /api/version`（版数とコミット）に表示されます。デプロイは `deploy/update.sh` が `VERSION` と現在のコミットをビルドに渡すので、画面の表示でデプロイ済みのバージョンを確認できます（版数にカーソルを合わせるとコミットが出ます）。

プッシュ前に `VERSION` を上げ忘れると、git の pre-push フックが止めます。クローンごとに、一度だけ次を実行してください。

    ./scripts/install-git-hooks.sh

どうしても上げずに送る場合は `git push --no-verify` を使います。

## チェック

```sh
cd frontend && npm run lint && npm test && npm run build
```

```sh
source .venv/bin/activate
pytest backend/tests
```

## 仕様

詳細は[プロジェクト仕様書](./LoLタイマン勝てるのツール.md)、[Phase 1データ契約](./docs/phase1-data-contract.md)、[Phase 2ロードマップ](./docs/phase2-roadmap.md)を参照してください。現在の開発状況、別マシンでのセットアップ手順、既知の課題は[開発引継ぎメモ](./docs/HANDOFF.md)にまとめています。動画ソースの利用条件、チャンピオン情報の出典・利用条件は、作業環境内の `phase1-source-research.md` にまとめています（Git管理対象外）。

チャンピオンカタログはData Dragonのバージョン付きデータです。パッチ更新時はプロジェクトルートから `python3 scripts/update_champion_catalog.py` を実行し、生成された差分を確認してください。

チャンピオン一覧APIは `GET /api/v1/champions?q=<検索語>` です。`q` は日本語名・英語名・登録済み別名・ローマ字表記を部分一致検索します。

マッチアップ動画APIは `GET /api/v1/matchups/{playerChampionId}/{opponentChampionId}` です。MySQLの `matchup_videos` テーブル（`backend/src/app/data/matchups.json` に動画があれば起動時に投入されます。同梱のファイルは空です。DB未接続時はJSONにフォールバック）に保存された `verificationStatus: "verified"` のレコード（UV の多い順）を先に、YouTube検索の結果をその後ろに並べて返します（最大8件）。**保存済みがあっても検索します**（暫定の方針。検索結果は72時間キャッシュ）。また、`POST /api/v1/matchups/{playerChampionId}/{opponentChampionId}/upvote` で動画をUV（高評価トグル）すると、候補動画も即座にDBへ確認済みとして蓄積されます。プレイリストから初期マッチアップ一覧を更新する場合は `python3 scripts/update_matchup_catalog.py` を実行してください。

Phase 2Aで追加したAPIは次のとおりです。

| API | 内容 |
|---|---|
| `GET /api/v1/game-assets` | ルーン、シャード、スペル、スタートアイテムのカタログ（`backend/src/app/data/game_assets.json`。更新は `python3 scripts/update_game_assets_catalog.py`） |
| `POST /api/v1/matchups/{playerChampionId}/{opponentChampionId}/analyze` | 動画の概要欄を取得し、ルーン・スペル・タイムスタンプを抽出する。DB保存済みの動画なら結果を保存し、保存済みのビルド情報があればYouTubeにアクセスせず返す（`refresh: true` で再取得） |
| `PUT /api/v1/matchups/{playerChampionId}/{opponentChampionId}/metadata` | 手動で編集したビルド情報を保存する。Google でログインして、管理者が承認した編集者だけが使える（未ログインは401、承認前は403。`GOOGLE_CLIENT_ID` などが未設定なら403） |

環境変数 `YOUTUBE_API_KEY`（任意）を設定すると、候補検索にYouTube Data API v3を使います。未設定の場合はYouTubeの検索ページのHTMLを解析します。
