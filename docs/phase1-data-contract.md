# Phase 1 データ契約

- 状態: 実装に合わせて改訂（2026-11-17、TASK-001）。Phase 2A の契約は末尾の「Phase 2A 契約」を参照
- 対象: 自分と相手のチャンピオン選択、検索、対面リプレイへのアクセス
- 前提: データソース・利用条件の調査結果に従う（詳細メモ `phase1-source-research.md` は作業環境内のみで、Git管理対象外）

## 範囲

Phase 1は、チャンピオン選択結果に対応する確認済みリプレイへのアクセスを提供する。チャンピオンのレーン推奨、勝率・統計、ルーン・アイテム推薦、動画解析、ログイン、ゲームクライアント連携は含めない。

動画の出どころは次の2つで、どちらも YouTube 視聴ページへのリンクと埋め込みのみを扱う。動画ファイル・サムネイルの複製や再配布は行わない。

- **保存済み（`origin: "saved"`）**: DB（`matchup_videos`）に `verified` として保存された動画。`backend/src/app/data/matchups.json` に動画があれば起動時に投入する。公開に備えて、同梱のファイルは空にしている（第三者のチャンネルのデータを載せない）。取り込む場合は `scripts/update_matchup_catalog.py --playlist <URL>`。
- **YouTube検索の候補（`origin: "youtube_search"`）**: マッチアップ画面を開くたびに、YouTube を検索して得る（**暫定。保存済みがあっても検索する**。仕様書 DEC-019）。検索結果は72時間キャッシュする。タイトルがマッチアップ条件（下記）を満たしたものだけを返す。管理者による個別確認は行わない。

**候補を `verified` として扱う方針（決定: 2026-11-17）**: 検索候補は、タイトル条件を満たせば `verificationStatus: "verified"` として表示する。利用者が UV（👍 参考になった）を押すと、その候補は `verified` の保存済み動画として DB に保存され、次回から優先して表示される。UV を人による確認の代わりとして扱うため、画面では取得元バッジ（`DB保存済` / `YouTube検索`）で区別して示す。YouTube の検索は `YOUTUBE_API_KEY` があれば Data API v3、なければ検索ページの HTML 解析で行う（HTML 解析は規約・仕様変更のリスクがあるため、公開前に API へ移行する。TASK-005）。

## チャンピオン

Data Dragonを出典とし、チャンピオンの識別には表示名ではなくパッチ内で安定した `id`（例: `Aatrox`）を用いる。

| フィールド | 型 | 必須 | 説明 |
|---|---|---:|---|
| `id` | string | はい | Data DragonのチャンピオンID。選択・関連付けのキー |
| `nameJa` | string | はい | `ja_JP`データの表示名 |
| `nameEn` | string | はい | 対応する英語ロケールの表示名 |
| `aliases` | string[] | はい | 検索用別名。初期値は空配列可。手動で追加する別名は出典・確認を経て登録 |
| `imageUrl` | string | はい | 対象パッチのData Dragonチャンピオン画像URL |
| `dataDragonVersion` | string | はい | 表示名・画像を取得したData Dragonのバージョン |
| `sourceUrl` | string | はい | 当該バージョン・ロケールのData Dragon出典URL |

`nameEn`は英語ロケールのチャンピオンデータを対応づけて取得する。日本語名は検索用にヘボン式ベースでローマ字化する。ローマ字検索では大文字小文字を無視し、長音記号・区切り記号を無視して照合する。日本語の「ヴ」と「ベ」等の表記差を扱うため、ローマ字照合に限り `v` と `b` を同一視する。たとえば `eitorokkusu` は「エイトロックス」に一致し、`be` は「ベルヴェス」「ヴェルコズ」「ベイガー」に一致する。これは検索補助の正規化であり、表示名・正式なローマ字表記は変更しない。Data DragonにないTopレーン適性はこの契約から推定しない。

### 検索

- 空の検索語はチャンピオン一覧を返す。
- 検索語は前後空白を除去し、大文字・小文字を区別せず照合する。ローマ字はハイフンなどの区切りと連続する長母音を正規化し、長音を省略した入力も照合する（例: `kami-ru` → 「カミール」）。
- `nameJa`、`nameEn`、`aliases`に対する部分一致に加え、日本語名のローマ字表記も部分一致で検索する。
- 正規化ルールを追加する場合も、表示用の元名称は変更しない。
- 結果順はチャンピオンIDの昇順とし、空検索でも安定した順序を保つ。
- 同一チャンピオンを自分と相手の両方に選択できる。将来要件が変わる場合は別途変更する。

## マッチアップ動画

選択順を保持し、「自分のチャンピオン」と「相手のチャンピオン」の**順序付き組み合わせ**で検索する。各動画は確認された対面の記録として管理する。

| フィールド | 型 | 必須 | 説明 |
|---|---|---:|---|
| `id` | string | はい | アプリ内の動画レコードID |
| `playerChampionId` | string | はい | 自分側チャンピオンID |
| `opponentChampionId` | string | はい | 相手側チャンピオンID |
| `title` | string | はい | 動画タイトル。確認できた原題を保存 |
| `videoUrl` | string | はい | YouTube視聴ページのHTTPS URL。動画ファイルURLは不可 |
| `channelName` | string | はい | 動画掲載チャンネル名 |
| `channelUrl` | string | はい | チャンネルへのHTTPS URL |
| `publishedAt` | string \| null | いいえ | 確認できる場合の公開日時（ISO 8601） |
| `gamePatch` | string \| null | いいえ | 確認できる場合のゲームパッチ |
| `verifiedAt` | string | はい | 対面内容とリンク状態を最後に確認した日時（ISO 8601） |
| `verificationStatus` | `"verified"` \| `"candidate"` | はい | API が返すのは `verified` のみ（検索候補もタイトル条件を満たせば `verified`。上記の方針を参照） |
| `embedStatus` | `"unknown"` \| `"allowed"` \| `"disabled"` | はい | 埋め込み許可状況。`disabled` 以外の動画は結果ページにYouTube埋め込みプレーヤーを表示し、併せて外部リンクも提供する |
| `sourceUrl` | string | はい | 動画情報を確認した出典URL |
| `origin` | `"saved"` \| `"youtube_search"` | はい | 取得元。`saved` は DB 保存済み、`youtube_search` は検索で得た未保存の候補 |
| `upvoteCount` | integer | はい | UV 数。保存済み動画の並び順の第1キー |
| `upvotedByViewer` | boolean | はい | `voterToken` を指定した閲覧者が UV 済みか |
| `metadata` | object \| null | いいえ | Phase 2A のビルド情報（後述） |

動画の公開状態は変わりうる。リンク切れ・非公開を確認した記録は削除または非表示にし、正常な動画があるかのような代替表示をしない。動画・サムネイルの複製や独自ホスティングは行わない。

## API契約案

バックエンドをチャンピオン・マッチアップデータの提供境界とし、情報源の変更をUIから分離する。チャンピオン一覧はData Dragonから生成したバージョン付きJSONとして管理し、更新時は生成スクリプトを明示的に実行して内容を確認する。マッチアップ動画・UV・ビルド情報は MySQL に永続化する（`matchup_videos`、`matchup_video_votes`、`matchup_video_metadata`。スキーマ変更は Alembic で管理）。DB に接続できない場合、閲覧は `matchups.json` にフォールバックするが、UV とビルド情報の保存は `503` を返す。

### `GET /api/v1/champions`

クエリ:

- `q`（任意）: チャンピオン名・別名の部分一致検索。未指定または空文字は全件。

成功時 `200`:

```json
{
  "dataDragonVersion": "16.22.1",
  "items": [
    {
      "id": "Aatrox",
      "nameJa": "エイトロックス",
      "nameEn": "Aatrox",
      "aliases": [],
      "imageUrl": "https://ddragon.leagueoflegends.com/cdn/16.22.1/img/champion/Aatrox.png",
      "dataDragonVersion": "16.22.1",
      "sourceUrl": "https://ddragon.leagueoflegends.com/cdn/16.22.1/data/ja_JP/champion.json"
    }
  ]
}
```

### `GET /api/v1/matchups/{playerChampionId}/{opponentChampionId}`

クエリ:

- `includeCandidates`（任意）: 互換のために残している。保存済みがあっても検索するため、指定しても結果は変わらない。
- `voterToken`（任意）: 指定すると `upvotedByViewer` を返す。

並び順は、保存済み動画を UV 数の降順、ゲームパッチの降順、タイトルから推定したランクの降順とし、その後ろに YouTube の検索結果を並べる（保存済みと重複する動画は除く）。合計は最大8件。**この並べ方は暫定で、運用しながら変更する可能性が高い**（TBD-007）。

成功時 `200`:

```json
{
  "playerChampionId": "Aatrox",
  "opponentChampionId": "Darius",
  "items": []
}
```

- 有効なチャンピオンIDの組み合わせに動画がない場合は `200` と空の `items` を返す。これは正常な「該当データなし」状態。
- 無効なチャンピオンIDは `404` と機械判読可能なエラーを返す。
- データソースが読めない・不正な場合は、空配列で成功したように見せず、運用ログに原因を記録して `503` を返す。
- 動画を返す場合は `verificationStatus: "verified"` のレコードに限る。
- 候補検索のタイトル条件: チャンピオン名が単語単位で「自分 → 相手」の順に現れること、`Top` を含むこと、他レーンやハイライト系でないこと、10分以上であること。

エラー形式:

```json
{
  "detail": {
    "code": "unknown_champion",
    "message": "指定されたチャンピオンが見つかりません。"
  }
}
```

### `POST /api/v1/matchups/{playerChampionId}/{opponentChampionId}/upvote`

リクエスト: `{ "video": <MatchupVideo>, "voterToken": string }`。UV の付与と取り消しを切り替える（トグル）。

- 保存済みでない候補を UV すると、`verified` として DB に保存する。このとき、ビルド情報が未登録なら概要欄から自動取得する。
- `voterToken` は SHA-256 でハッシュ化して保存する（クライアントの IP も加える）。同一の閲覧者は1動画につき1票。
- 動画のチャンピオン ID がルートと一致しない、またはタイトルがマッチアップ条件を満たさない場合は `400`（`invalid_upvote`）。DB が使えない場合は `503`（`upvote_unavailable`）。

## UIの振る舞い

- 選択フローは「自分のチャンピオン」→「相手のチャンピオン」→中央ボタン押下でマッチアップ画面（`/matchup/{playerChampionId}/{opponentChampionId}`）へ遷移し、結果を表示する順とする。
- チャンピオン検索時は入力文字ごとに該当結果へ絞り込む。
- API読み込み中、検索結果0件、マッチアップ動画0件、通信・データエラーを区別して表示する。
- 動画なしの場合は「この対面の確認済み動画はまだありません」と案内する。類似対面を同一対面として表示しない。
- 動画の取得元（`DB保存済` / `YouTube検索`）をバッジで区別して示す。
- フッターに Data Dragon の出典と Riot 非公認の注記、およびクレジット画面（`/credit`）へのリンクを表示する。
- YouTubeへのリンクは新しいタブで開き、`rel="noopener noreferrer"`を指定する。リンク先が外部サイトであることを利用者に分かるようにする。
- 動画情報には確認済みの出典・チャンネルを表示する。

## データ品質・運用

- すべての確定データに出典を持たせ、動画レコードには確認日を記録する。
- Data Dragonのパッチ更新は手動確認を挟み、使用バージョンを記録する。
- `candidate` は内部用の状態で、一般向け API には含めない。
- 自動動画候補検索は実装済み。取得手段（YouTube Data API）と利用条件の再確認は公開前の作業として残る（TASK-005、TASK-006）。

## Phase 2A 契約（動画の概要欄から取得するビルド情報）

### `metadata` オブジェクト

| フィールド | 型 | 説明 |
|---|---|---|
| `analysisStatus` | `"unanalyzed"` \| `"auto_parsed"` \| `"manual_verified"` | `auto_parsed` は概要欄から自動抽出、`manual_verified` は管理者が手動で確認・保存したデータ |
| `runes` | object \| null | `primaryStyleId`、`subStyleId`、`primarySelections`（メイン4）、`subSelections`（サブ2）、`statShards`（3段）。ID は Data Dragon / `game_assets.json` のルーン ID |
| `summonerSpells` | string[] | サモナースペルのID（例: `SummonerFlash`）。最大2つ |
| `startingItems` | string[] | スタートアイテムのID。概要欄に `Starter Items:` 行がある場合、または手動登録の場合のみ。試合終了時の `Build:` 行からの推定は行わない（仕様書 4.4） |
| `timestamps` | object[] | `timeSeconds`、`timeLabel`、`label`、`isKillEvent`。最大300件。手動で追加・変更・削除できる |
| `waves` | object[] | ウェーブのプッシュ・プル。**手動入力のみ**（概要欄からは取得しない）。`waveNumber`（1〜20）、`state`（`push` / `pull` / `neutral` / `unknown`）、（メモ欄も、動画の再生時間も無い。以前のデータに残っていても読み込み時に無視する）。向きは、この動画の「自分側」のチャンピオンから見たもの。最大20件。未入力は「まだ入力していない」ことを表し、「中立」ではない |

手動保存（`PUT /metadata`）では、ルーン・スペル・スタートアイテム・タイムラインを上書きできる。自動取得した値に誤りや不足があり得るため。**ウェーブは含めず、保存しても変わらない**（下の `PUT /waves` で、独立して保存する）。

### `GET /api/v1/game-assets`

ルーン、シャード、スペル、スタートアイテムのカタログ（`game_assets.json`、Data Dragon 由来）を返す。読み込めない場合は `503`。

### `POST /api/v1/matchups/{p}/{o}/analyze`

リクエスト: `{ "video": <MatchupVideo>, "refresh": boolean }`。動画の概要欄を取得して `metadata` を返す。

- DB に保存済みのビルド情報があれば、YouTube にアクセスせずにそれを返す。`refresh: true` のときだけ `auto_parsed` のデータを再取得する。
- `manual_verified` のデータは、`refresh` を指定しても自動取得で上書きしない。
- 抽出結果は、DB に保存済みの動画に対してのみ保存する（未保存の候補は結果を返すだけ）。

### `PUT /api/v1/matchups/{p}/{o}/metadata`

リクエスト: `{ "video": <MatchupVideo>, "metadata": <metadata> }`。手動編集したビルド情報を `manual_verified` として保存する。

- **管理者限定**: `Authorization: Bearer <ADMIN_TOKEN>` が必要。サーバーに環境変数 `ADMIN_TOKEN` が未設定なら `403`（`admin_disabled`）、トークンが違えば `401`（`invalid_admin_token`）。
- 画面の手動編集では、トークンを入力して保存する（トークンはそのブラウザセッションのみ保持）。

### `PUT /api/v1/matchups/{p}/{o}/waves`

リクエスト: `{ "video": <MatchupVideo>, "waves": WaveNote[] }`。ウェーブのプッシュ・プル**だけ**を保存する。ルーン・スペル・スタートアイテム・タイムラインには触れない。送った `waves` の一覧で、保存済みの一覧を**置き換える**（一覧から外したウェーブは削除される）。

- **管理者限定**: `PUT /metadata` と同じ（`Authorization: Bearer <ADMIN_TOKEN>`。未設定なら `403`、違えば `401`）。
- 同じウェーブ番号を2つ含めると `400`。値が範囲外なら `422`。
- 保存済みでない動画は、サーバーの検索が提示した動画に限り、行として作る（それ以外は `400`、`invalid_waves`）。
- レスポンスは、保存後の `metadata` 全体（ビルドの値を含む）。
- 画面では、記録したウェーブの状態は**後から変更できず、削除のみ**（間違えたら、削除して入力し直す）。

## 未決事項

- ローマ字日本語別名の生成・品質確認方法（ヘボン式ベースの自動ローマ字化と正規化を `backend/src/app/romanization.py` に実装済み）。
- YouTube Data APIによる自動検索の実現範囲、クォータ、必要な利用者向け表示（TASK-005）。
- 動画リンクの定期的な有効性確認の頻度・運用方法。
- UV の投票者の識別方法（IP が変わると別の投票者になる。TBD-005）。
