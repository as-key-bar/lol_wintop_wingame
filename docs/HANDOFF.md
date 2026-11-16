# 開発引継ぎメモ（2026-11-16 時点）

別のマシンで開発を再開するための現状まとめです。作業を始める前に、本書、[`GEMINI.md`](../GEMINI.md)、[プロジェクト仕様書](../LoLタイマン勝てるのツール.md)、[Phase 1 データ契約](./phase1-data-contract.md)、[Phase 2 ロードマップ](./phase2-roadmap.md) を読んでください。

## 1. 現在の状態

| 項目 | 状態 |
|---|---|
| ブランチ | `main` |
| 最新コミット | `a777791` Add Phase 2A description analysis, full rune/timeline UI, and current Sorcery keystones |
| リモート | `origin` = https://github.com/as-key-bar/lol_wintop_wingame.git |
| テスト | バックエンド 24件成功、フロントエンドの lint / 本番ビルド成功 |
| フェーズ | Phase 1 はほぼ完了（未完了は 6 章）。Phase 2A（動画概要欄の解析とビルド表示）は実装済み。Phase 2B（画像認識）は未着手 |

> [!IMPORTANT]
> Git の管理対象外のため、GitHub 経由では引き継がれないファイルがあります。
> - `.env`（`.env.example` からコピーして作成）、`frontend/.env.local`（`frontend/.env.example` からコピー）
> - `phase1-source-research.md`（データソース調査の長文メモ。`.gitignore` に記載あり。必要なら別の手段で移してください）
> - MySQL のデータ（Docker volume `mysql_data`）。UV や手動で登録したビルド情報は移りません。初期データは起動時に `matchups.json` から自動でシードされます。

## 2. 新しいマシンでのセットアップ

必要なもの：Node.js 20.9 以上（動作確認は v22.18）、npm、Python 3.12 以上（動作確認は 3.12.3）、Docker Compose。

```sh
git clone https://github.com/as-key-bar/lol_wintop_wingame.git wintop
cd wintop
cp .env.example .env
cp frontend/.env.example frontend/.env.local

docker compose up -d          # MySQL 8.4

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
cd frontend && npm run lint && npm run build
```

### 環境変数

| 変数 | 必須 | 用途 |
|---|---|---|
| `DATABASE_URL` | いいえ（`.env.example` の値が既定） | SQLAlchemy の接続先。つながらない場合、閲覧は `matchups.json` で継続し、UV とビルド保存は 503 を返す |
| `NEXT_PUBLIC_API_BASE_URL` | いいえ（既定 `http://localhost:8000`） | フロントエンドから呼ぶ API の URL |
| `YOUTUBE_API_KEY` | いいえ | 設定すると候補検索に YouTube Data API v3 を使う。未設定なら YouTube の検索ページの HTML を解析する |

## 3. 実装済みの機能

### 画面
- `/`：自分と相手のチャンピオンを選ぶ画面（日本語・英語・ローマ字で検索可）。`WinTop!!` ボタンでマッチアップ画面へ移動。
- `/matchup/{playerChampionId}/{opponentChampionId}`：
  - 動画上部のカルーセルで動画を切り替え。取得元を `DB保存済`（緑）と `YouTube検索`（青）のバッジで区別。
  - ファーストビューに収まる 16:9 の埋め込みプレーヤー。
  - UV ボタン（押すたびに付与と取り消しが切り替わる）。
  - ビルドパネル（[`VideoMetadataPanel.tsx`](../frontend/src/components/VideoMetadataPanel.tsx)）：ルーン9枠の全表示、サモナースペル、スタートアイテム、タイムライン。タイムスタンプを押すとその秒数から再生。キル関連のイベントだけに絞り込み可能。
  - 「概要欄から自動取得」ボタンと「ビルドを手動編集」ボタン。

### API（[`main.py`](../backend/src/app/main.py)）

| メソッド・パス | 内容 |
|---|---|
| `GET /api/v1/champions?q=` | チャンピオン検索 |
| `GET /api/v1/matchups/{p}/{o}?includeCandidates=&voterToken=` | 保存済み動画を返す。保存済みが1件でもあれば YouTube にはアクセスしない。YouTube を検索するのは、保存済みが0件のときと `includeCandidates=true` のときだけ |
| `POST /api/v1/matchups/{p}/{o}/upvote` | UV の付与と取り消し。UV された YouTube 候補は `matchup_videos` に保存される。保存時にビルド情報が未登録なら、概要欄から自動で取得する |
| `GET /api/v1/game-assets` | ルーン、シャード、スペル、スタートアイテムのカタログ |
| `POST /api/v1/matchups/{p}/{o}/analyze` | 動画ページから概要欄を取得してビルド情報を抽出する。DB に保存済みの動画なら結果を保存する |
| `PUT /api/v1/matchups/{p}/{o}/metadata` | 手動で編集したビルド情報を `manual_verified` として保存する |

### データ
- [`champions.json`](../backend/src/app/data/champions.json)：Data Dragon 16.22.1 から生成（`scripts/update_champion_catalog.py`）。
- [`matchups.json`](../backend/src/app/data/matchups.json)：Challenger Replays のプレイリストから取得した初期データ100件（`scripts/update_matchup_catalog.py`）。DB に自動でシードされる。
- [`game_assets.json`](../backend/src/app/data/game_assets.json)：Data Dragon 16.22.1 から生成（`scripts/update_game_assets_catalog.py`）。ステータスシャードとスタートアイテムの一覧は、スクリプトに直接書いた定義を使用。旧名の別名（例：Phase Rush → 嵐乗りの勇躍）は `aliases` に持たせている。
- DB（[`schema.sql`](../database/schema.sql)、[`database.py`](../backend/src/app/database.py)）：`matchup_videos`、`matchup_video_votes`、`matchup_video_metadata` の3テーブル。テーブルは起動時に `Base.metadata.create_all` で作られる。マイグレーションの仕組みはない。

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

優先度の高い順に記載しています。

1. **ドキュメントとデータ方針が実装と食い違っている**：[`phase1-data-contract.md`](./phase1-data-contract.md) と `GEMINI.md` では「YouTube の動画は手動で確認し、未確認の候補は表示しない」としているが、実装では YouTube 検索で見つけた候補をタイトルの条件だけで `verified` 扱いにして表示し、UV があれば DB に保存している。ユーザーの承認を得て進めた変更だが、契約書側は更新していない。公開前に、方針を確定させて契約書を書き直す必要がある。
2. **YouTube の HTML を解析している**：`YOUTUBE_API_KEY` が未設定の場合、検索ページと動画ページの HTML を直接取得している。利用規約やブロックのリスクがあり、YouTube 側の HTML 構造が変わると動かなくなる。公開前に YouTube Data API への移行と、規約の確認が必要。
3. **ビルド情報の手動保存 API に認証がない**：`PUT /metadata` は誰でも呼べ、内容を上書きして `manual_verified` にできる。公開前に管理者限定にするか、投票方式に変える必要がある。
4. **スタートアイテムの抽出が推定に頼っている**：`Build:` 行（試合終了時の装備）にドラン系のアイテムが残っていれば、それをスタートアイテムとして扱っている。実際の初手と違う可能性がある。仕様書 4.4 の「推測値を確定情報として表示しない」に反するおそれがあるため、Phase 2B で画像認識に置き換えるか、推定値であることを画面に表示する必要がある。
5. **概要欄の取得結果をキャッシュしていない**：`analyze` を呼ぶたびに YouTube の動画ページを取得する。DB に未保存の候補動画では結果も保存されない。フロントエンドも、ビルド情報が登録済みかどうかにかかわらずボタンを押せる。
6. **ステータスシャードの定義を目視で確認していない**：スクリプトに直接書いた3段の定義と、体力系のアイコンのファイル名が、現在のゲーム内表示と一致しているか未確認。
7. **UV の投票者の識別**：`voterToken` とクライアントの IP をまとめてハッシュ化しているため、IP が変わると同じブラウザでも別の投票者として扱われる。
8. **DB マイグレーションがない**：既存テーブルの列を変える場合に対応できない。Alembic の導入を検討する。
9. **フロントエンドのテストがない**：画面の確認はすべて手動で行っている。

## 6. 次のステップの提案

**A. 引継ぎ直後の確認（推奨）**
1. 新しいマシンでセットアップし、テスト、lint、ビルドがすべて通ることを確認する。
2. `docker compose up -d` を実行した状態で、次を画面上で確認する：初期データ100件のシード、UV による候補の DB 保存、「概要欄から自動取得」の結果（例：Chogath vs Gwen はルーン9枠すべて、TahmKench vs Gwen は省略型）。

**B. Phase 2B の前に片付けたい項目**
1. 5 章の 1：データ方針を確定し、`phase1-data-contract.md` を書き直す（Phase 2 の契約、つまり metadata API とビルド情報の各フィールドも追記する）。
2. 5 章の 3：`PUT /metadata` に保護をかける（管理者トークンなど）。
3. 5 章の 4：推定したスタートアイテムに「推定」と表示するか、抽出をやめる。
4. 5 章の 5：取得済みのビルド情報がある動画では `analyze` を省略する。

**C. Phase 2B（[ロードマップ](./phase2-roadmap.md)を参照）**
1. 2B-1：Challenger Replays の動画序盤の画面（HUD）から、Data Dragon のアイテムアイコンとの照合で所持アイテムを特定する試作。まず、動画のフレームをどう取得するかを利用規約の面から確認する必要がある（仕様書では、動画のダウンロードや再配布を禁止している）。
2. 2B-2：判定結果を `matchup_video_metadata.starting_items_json` に自動で保存する。
