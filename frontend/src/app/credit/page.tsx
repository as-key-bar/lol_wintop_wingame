import type { Metadata } from "next";
import Link from "next/link";
import styles from "@/app/page.module.css";
import { RiotFooter } from "@/components/RiotFooter";

export const metadata: Metadata = {
  title: "クレジット | wintop-wingame",
  description: "wintop-wingameのサービス概要、データの出典、免責事項",
};

export default function CreditPage() {
  return (
    <main className={styles.page}>
      <section className={styles.creditSection}>
        <p>
          <Link href="/">← トップへ戻る</Link>
        </p>
        <h1>クレジット</h1>

        <h2>サービス概要</h2>
        <p>
          wintop-wingame は、League of Legends
          のトップレーンのマッチアップ知識を、試合前に素早く確認するための非公式ツールです。
          自分と相手のチャンピオンを選ぶと、その対面のリプレイ動画と、動画の概要欄に書かれたルーン・サモナースペル・タイムラインを表示します。
          ゲームクライアントの操作や自動プレイは行いません。
        </p>

        <h2>データの出典</h2>
        <ul>
          <li>
            チャンピオン・ルーン・サモナースペル・アイテムの名前とアイコン:{" "}
            <a
              href="https://developer.riotgames.com/docs/lol#data-dragon"
              target="_blank"
              rel="noopener noreferrer"
            >
              Riot Games Data Dragon
            </a>
          </li>
          <li>
            リプレイ動画: YouTube
            上の公開動画へのリンクと埋め込みです。動画の複製や再配布は行っていません。初期データは{" "}
            <a
              href="https://www.youtube.com/@ChallengerReplays"
              target="_blank"
              rel="noopener noreferrer"
            >
              Challenger Replays
            </a>{" "}
            のプレイリストから選んでいます。動画の著作権は各投稿者に帰属します。
          </li>
          <li>
            ルーン・スペル・タイムラインは、動画の概要欄の記載から自動で抽出しています。
            抽出結果には誤りが含まれる可能性があるため、動画の内容と合わせて確認してください。
          </li>
        </ul>

        <h2>動画の表示について</h2>
        <p>
          「YouTube検索」と表示される動画は、タイトルの条件で自動的に見つけた候補です。
          「👍
          参考になった」が押された候補は、確認済みの動画として保存され、次回から優先して表示されます。
        </p>
      </section>

      <RiotFooter />
    </main>
  );
}
