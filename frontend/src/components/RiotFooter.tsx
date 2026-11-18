import Link from "next/link";
import styles from "@/app/page.module.css";

export function RiotFooter() {
  return (
    <footer className={styles.footer}>
      <p>
        チャンピオン情報:{" "}
        <a
          href="https://developer.riotgames.com/docs/lol#data-dragon"
          target="_blank"
          rel="noopener noreferrer"
        >
          Riot Games Data Dragon
        </a>
        {" ・ "}
        <Link href="/credit">クレジット</Link>
      </p>
      <p className={styles.legal}>
        wintop-wingame is not endorsed by Riot Games and does not reflect the
        views or opinions of Riot Games or anyone officially involved in
        producing or managing Riot Games properties. Riot Games and all
        associated properties are trademarks or registered trademarks of Riot
        Games, Inc.
      </p>
    </footer>
  );
}
