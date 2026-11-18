# 開発引継ぎメモ（2026-11-18 更新）

別のマシンで開発を再開するための現状まとめです。作業を始める前に、本書、[`GEMINI.md`](../GEMINI.md)、[プロジェクト仕様書](../LoLタイマン勝てるのツール.md)、[Phase 1 データ契約](./phase1-data-contract.md)、[Phase 2 ロードマップ](./phase2-roadmap.md) を読んでください。

## 1. 現在の状態

| 項目 | 状態 |
|---|---|
| ブランチ | `main` |
| 最新コミット | `git log` を参照（2026-11-17 の変更は未コミットの場合あり）。機能の最終コミットは `a777791`（Phase 2A） |
| リモート | `origin` = https://github.com/as-key-bar/lol_wintop_wingame.git |
| テスト | バックエンド 34件、フロントエンド 19件（Vitest）、lint、本番ビルドすべて成功（2026-11-18） |
| フェーズ | Phase 1 はほぼ完了（未完了は 6 章）。Phase 2A（動画概要欄の解析とビルド表示）は実装済み。Phase 2B（画像認識）は未着手 |

> [!IMPORTANT]
> Git の管理対象外のため、GitHub 経由では引き継がれないファイルがあります。
> - `.env`（`.env.example` からコピーして作成）、`frontend/.env.local`（`frontend/.env.example` からコピー）
> - `phase1-source-research.md`（データソース調査の長文メモ。`.gitignore` に記載あり。必要なら別の手段で移してください）
> - MySQL のデータ（Docker volume `mysql_data`）。UV や手動で登録したビルド情報は移りません。初期データは同梱しておらず、DB は空から始まります（動画は検索候補への UV で貯まります）。

## 2. 新しいマシンでのセットアップ

必要なもの：Node.js 20.9 以上（動作確認は v22.18）、npm、Python 3.12 以上（動作確認は 3.12.3）、Docker Compose。

```sh
git clone https://github.com/as-key-bar/lol_wintop_wingame.git wintop
cd wintop
cp .env.example .env
cp frontend/.env.example frontend/.env.local

docker compose up -d          # MySQL 8.4（Homebrew + Colima では docker-compose を使う）

python3 -m venv .venv
.venv/bin/pip install -e "backend[dev]"

cd frontend && npm install && cd ..
```

起動（VS Code ではコマンドパレットの **Tasks: Run Task → Dev: Start app** でまとめて起動できます）：

```sh
.venv/bin/python -m uvicorn app.main:app --app-dir backend/src --host 0.0.0.0 --port 8000 --reload
cd frontend && npm run dev
```

- フロントエンド: http://localhost:3000
- API ドキュメント: http://localhost:8000/docs
- DB 接続の確認: http://localhost:8000/api/health/database

チェック：

```sh
.venv/bin/python -m pytest -q backend/tests
cd frontend && npm run lint && npm test && npm run build
```

### 環境変数

| 変数 | 必須 | 用途 |
|---|---|---|
| `DATABASE_URL` | いいえ（`.env.example` の値が既定） | SQLAlchemy の接続先。つながらない場合、閲覧は `matchups.json` で継続し、UV とビルド保存は 503 を返す |
| `NEXT_PUBLIC_API_BASE_URL` | いいえ（未設定なら `http://localhost:8000`） | フロントエンドから呼ぶ API の URL。**空文字なら同一オリジン**（本番の Caddy 構成）。ビルド時にブラウザ向けの値として埋め込まれる |
| `ADMIN_TOKEN` | いいえ | 設定すると `PUT /metadata`（ビルド情報の手動保存）が使える。未設定なら 403 で無効 |
| `YOUTUBE_API_KEY` | いいえ（本番では事実上必須） | 設定すると候補検索と概要欄の取得に YouTube Data API v3 を使う。未設定なら YouTube の HTML を解析する |
| `CORS_ALLOW_ORIGINS` | いいえ | カンマ区切りで許可するオリジン。既定は localhost:3000。同一オリジンの本番構成では不要 |

## 3. 実装済みの機能

### 画面
- `/`：自分と相手のチャンピオンを選ぶ画面（日本語・英語・ローマ字で検索可）。`WinTop!!` ボタンでマッチアップ画面へ移動。
- `/matchup/{playerChampionId}/{opponentChampionId}`：
  - 動画上部のカルーセルで動画を切り替え。取得元を `DB保存済`（緑）と `YouTube検索`（青）のバッジで区別。
  - ファーストビューに収まる 16:9 の埋め込みプレーヤー。
  - UV ボタン（押すたびに付与と取り消しが切り替わる）。
  - ビルドパネル（[`VideoMetadataPanel.tsx`](../frontend/src/components/VideoMetadataPanel.tsx)）：ルーン9枠の全表示、サモナースペル、スタートアイテム、タイムライン。タイムスタンプを押すとその秒数から再生。キル関連のイベントだけに絞り込み可能。
  - 「概要欄から自動取得」（取得済みなら「再取得」）ボタンと「ビルドを手動編集」ボタン。手動保存には管理者トークンの入力が必要。
- `/credit`：サービス概要、データの出典、動画の扱い。フッターからリンク。

### API（[`main.py`](../backend/src/app/main.py)）

| メソッド・パス | 内容 |
|---|---|
| `GET /api/v1/champions?q=` | チャンピオン検索 |
| `GET /api/v1/matchups/{p}/{o}?includeCandidates=&voterToken=` | 保存済み動画を返す。保存済みが1件でもあれば YouTube にはアクセスしない。YouTube を検索するのは、保存済みが0件のときと `includeCandidates=true` のときだけ |
| `POST /api/v1/matchups/{p}/{o}/upvote` | UV の付与と取り消し。UV された YouTube 候補は `matchup_videos` に保存される。保存時にビルド情報が未登録なら、概要欄から自動で取得する |
| `GET /api/v1/game-assets` | ルーン、シャード、スペル、スタートアイテムのカタログ |
| `POST /api/v1/matchups/{p}/{o}/analyze` | 動画ページから概要欄を取得してビルド情報を抽出する。保存済みのビルド情報があれば YouTube にアクセスせずそれを返す（`refresh: true` で再取得。`manual_verified` は上書きしない） |
| `PUT /api/v1/matchups/{p}/{o}/metadata` | 手動で編集したビルド情報を `manual_verified` として保存する。`Authorization: Bearer <ADMIN_TOKEN>` が必要 |

### データ
- [`champions.json`](../backend/src/app/data/champions.json)：Data Dragon 16.22.1 から生成（`scripts/update_champion_catalog.py`）。
- [`matchups.json`](../backend/src/app/data/matchups.json)：公開に備えて**空**のまま同梱している（第三者のチャンネルのデータを載せないため）。取り込む場合は `scripts/update_matchup_catalog.py --playlist <URL>`。動画は、検索候補への UV で DB に貯まる。
- [`game_assets.json`](../backend/src/app/data/game_assets.json)：Data Dragon 16.22.1 から生成（`scripts/update_game_assets_catalog.py`）。ステータスシャードとスタートアイテムの一覧は、スクリプトに直接書いた定義を使用。旧名の別名（例：Phase Rush → 嵐乗りの勇躍）は `aliases` に持たせている。
- DB（[`schema.sql`](../database/schema.sql)、[`database.py`](../backend/src/app/database.py)）：`matchup_videos`、`matchup_video_votes`、`matchup_video_metadata` の3テーブル。テーブルは起動時に `Base.metadata.create_all` で作られる。列の変更は Alembic（`backend/migrations/`、[`database/README.md`](../database/README.md) 参照）で行う。

### 概要欄の解析（[`video_analysis.py`](../backend/src/app/video_analysis.py)）
Challenger Replays の概要欄には次の2つの書式があります。
- **全記載型**：`Spells: Teleport Flash` / `Runes: Domination - …, … | Sorcery - …, … | Shards - …, …, …` / `Timeline:` の各行。ルーン9枠すべて、スペル、タイムスタンプを抽出できる。
- **省略型**：`Skin: X | Grasp of the Undying + Precision | Ignite Flash`。抽出できるのはキーストーン、サブパスの種類、スペルのみ。
- 動画ページの `ytInitialPlayerResponse` は `json.JSONDecoder.raw_decode` で読み込む。正規表現で切り出すと JSON が途中で切れて失敗するため。

## 4. 確定している仕様上の決定

- 保存済みの動画が1件でもあるマッチアップでは、YouTube にアクセスしない。
- 候補検索の条件：検索は1回のみ（`"{Player} Top vs {Opponent}"`）。タイトルのチャンピオン名は単語単位で、自分→相手の順に一致すること。`Top` を含むこと。他レーンやハイライト系は除外。10分以上。並び順はパッチ、ランク、チャンネル信頼度の降順。
- UV が1票でも入った候補は、即座に DB に `verified` として保存する。保存済み動画は UV 数、パッチ、ランクの降順に並べる。
- ルーンは9枠すべてを表示する。概要欄で取れる情報（ルーン、スペル、タイムスタンプ）は Phase 2A で抽出する。画像認識が必要な情報（ファーストアイテム、ウェーブ管理）は Phase 2B 以降に回す。

## 5. 既知の課題・リスク（未対応）

2026-11-18 時点で、旧 7（UV の識別）も解消した（IP を使わずトークンのみにした。仕様書 DEC-013）。残りは次のとおり。

1. **デプロイが未実施（TASK-007）**：コード・Docker 構成・手順書は完了。AWS アカウントの準備（認証情報が未設定）と、実際の EC2 作成・起動が残る。
2. **YouTube Data API のキーが未発行（TASK-005）**：コードは対応済み（候補検索と概要欄の取得が `YOUTUBE_API_KEY` で Data API を使う）。キー未設定だと HTML 解析にフォールバックするが、クラウドの IP では YouTube にブロックされる可能性が高い。規約の確認も残る。
3. **Riot のポリシー確認が未了（TASK-006）**：Riot Developer Portal への登録と、現行の利用規約・必須表示の確認。
4. **Free Plan は 6 か月で終わる**：クレジット消化、または 6 か月でアカウントが閉鎖される。続け方の決定が必要（TBD-003）。
5. **HTTP のままでは `ADMIN_TOKEN` が平文で流れる**：ドメインを取得して HTTPS にするまでは、`ADMIN_TOKEN` を空にして手動編集を無効にしておく。
6. **フロントエンドのテストは一部のみ**：`lib/api.ts` と `VideoMetadataPanel` のみ。ページ全体（`page.tsx`）のテストはない。
7. **バックアップは同一サーバー内のみ**：`deploy/backup.sh` は `backups/` に保存する。S3 への退避は未実装。

## 5.1 YouTube データの保存期限（2026-11-18 追加）

取得から28日（上限30日）で、YouTube 由来のデータを削除する（仕様書 DEC-016）。`matchup_videos.fetched_at`（マイグレーション `0002`）を基準に、`app/retention.py` が、動画の行・その票・ひもづくビルド（手動保存分も含む）を削除する。本番は systemd のタイマー（毎日 04:00 JST）。期限を過ぎた行は、削除が遅れても API が返さない。**更新はしない**ため、UV による蓄積は、28日でリセットされる。

## 6. 次のステップの提案

**A. デプロイ（進行中）**
非公開の手順書 `docs/DEPLOY_PRIVATE.md`（Git 管理外。別マシンには移らないので、必要なら別途コピーする）に従う。構成は、EC2 t4g.small 1台に Docker Compose（Caddy、Next.js、FastAPI、MySQL）。構成ファイルは `compose.prod.yaml` と `deploy/`、環境変数の雛形は `deploy/env.example`。AWS で進められない場合は Vercel を使う（手順書 §9）。

**B. 目視確認**
ローカルで `docker-compose up -d` を実行した状態で、画面上で次を確認する：UV による候補の DB 保存、「概要欄から自動取得」の結果（例：Chogath vs Gwen はルーン9枠すべて、TahmKench vs Gwen は省略型）、`.env` に `ADMIN_TOKEN` を設定したうえでの手動保存、`/credit`。

**C. Phase 2B（[ロードマップ](./phase2-roadmap.md)を参照）**
1. 2B-1：Challenger Replays の動画序盤の画面（HUD）から、Data Dragon のアイテムアイコンとの照合で所持アイテムを特定する試作。まず、動画のフレームをどう取得するかを利用規約の面から確認する必要がある（仕様書では、動画のダウンロードや再配布を禁止している）。
2. 2B-2：判定結果を `matchup_video_metadata.starting_items_json` に自動で保存する。
