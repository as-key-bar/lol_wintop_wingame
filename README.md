# wintop-wingame

League of Legendsのトップレーン向けマッチアップ攻略ツールです。Phase 1では、チャンピオン選択から対面リプレイへアクセスするMVPを予定しています。ゲームクライアントの操作や自動プレイは行いません。

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

## チェック

```sh
cd frontend && npm run lint && npm run build
```

```sh
source .venv/bin/activate
pytest backend/tests
```

## 仕様

詳細は[プロジェクト仕様書](./LoLタイマン勝てるのツール.md)、[Phase 1データ契約](./docs/phase1-data-contract.md)を参照してください。動画ソースの利用条件、チャンピオン情報の出典・利用条件は、作業環境内の `phase1-source-research.md` にまとめています（Git管理対象外）。

チャンピオンカタログはData Dragonのバージョン付きデータです。パッチ更新時はプロジェクトルートから `python3 scripts/update_champion_catalog.py` を実行し、生成された差分を確認してください。

チャンピオン一覧APIは `GET /api/v1/champions?q=<検索語>` です。`q` は日本語名・英語名・登録済み別名・ローマ字表記を部分一致検索します。

マッチアップ動画APIは `GET /api/v1/matchups/{playerChampionId}/{opponentChampionId}` です。`backend/src/app/data/matchups.json` に登録されたデータのうち、`verificationStatus: "verified"` のレコードのみを返します。
