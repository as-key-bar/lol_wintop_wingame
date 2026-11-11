"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RiotFooter } from "@/components/RiotFooter";
import { apiBaseUrl, type Champion, type ChampionResponse } from "@/lib/api";
import styles from "./page.module.css";

type ChampionPickerProps = {
  id: string;
  side: "player" | "opponent";
  title: string;
  selected: Champion | null;
  onSelect: (champion: Champion | null) => void;
};

function ChampionPicker({
  id,
  side,
  title,
  selected,
  onSelect,
}: ChampionPickerProps) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Champion[]>([]);
  const [version, setVersion] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError("");

      try {
        const url = new URL("/api/v1/champions", apiBaseUrl);
        const trimmedQuery = query.trim();
        if (trimmedQuery) {
          url.searchParams.set("q", trimmedQuery);
        }

        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`Champion request failed (${response.status})`);
        }

        const data = (await response.json()) as ChampionResponse;
        setItems(data.items);
        setVersion(data.dataDragonVersion);
      } catch (requestError) {
        if (requestError instanceof Error && requestError.name === "AbortError") {
          return;
        }
        setError("チャンピオン一覧を読み込めませんでした。APIの起動状態を確認してください。");
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, 120);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  return (
    <section
      className={`${styles.picker} ${side === "player" ? styles.playerPicker : styles.opponentPicker}`}
      aria-labelledby={`${id}-heading`}
    >
      <div className={styles.pickerHeader}>
        <div>
          <p className={styles.step}>CHAMPION SELECT</p>
          <h2 id={`${id}-heading`}>{title}</h2>
        </div>
        {selected && (
          <button
            className={styles.clearButton}
            type="button"
            onClick={() => onSelect(null)}
          >
            解除
          </button>
        )}
      </div>

      <div
        className={`${styles.selected} ${selected ? "" : styles.selectedEmpty}`}
        aria-live="polite"
      >
        {selected ? (
          <>
            <Image
              src={selected.imageUrl}
              alt=""
              width={48}
              height={48}
              unoptimized
            />
            <div>
              <strong>{selected.nameJa}</strong>
              <span>{selected.nameEn}</span>
            </div>
            <span className={styles.selectedMark}>選択中</span>
          </>
        ) : (
          <span className={styles.selectionPlaceholder}>
            チャンピオン未選択
          </span>
        )}
      </div>

      <label className={styles.searchLabel} htmlFor={`${id}-search`}>
        チャンピオン名で検索
      </label>
      <input
        id={`${id}-search`}
        className={styles.searchInput}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="日本語・英語・ローマ字"
        autoComplete="off"
      />

      <div className={styles.results} aria-busy={loading}>
        {loading && <p className={styles.message}>読み込み中...</p>}
        {!loading && error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}
        {!loading && !error && items.length === 0 && (
          <p className={styles.message}>該当するチャンピオンがいません。</p>
        )}
        {!loading && !error && items.length > 0 && (
          <div className={styles.championGrid}>
            {items.map((champion) => {
              const isSelected = selected?.id === champion.id;
              return (
                <button
                  className={`${styles.champion} ${isSelected ? styles.championSelected : ""}`}
                  key={champion.id}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => onSelect(champion)}
                  title={`${champion.nameJa} (${champion.nameEn})`}
                >
                  <Image
                    src={champion.imageUrl}
                    alt=""
                    width={48}
                    height={48}
                    unoptimized
                  />
                  <span>{champion.nameJa}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      {version && <p className={styles.version}>Data Dragon {version}</p>}
    </section>
  );
}

export default function Home() {
  const router = useRouter();
  const [playerChampion, setPlayerChampion] = useState<Champion | null>(null);
  const [opponentChampion, setOpponentChampion] = useState<Champion | null>(null);

  function handleOpenMatchup() {
    if (!playerChampion || !opponentChampion) {
      return;
    }

    router.push(
      `/matchup/${encodeURIComponent(playerChampion.id)}/${encodeURIComponent(opponentChampion.id)}`,
    );
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>LEAGUE OF LEGENDS · TOP LANE</p>
          <h1>wintop-wingame</h1>
          <p className={styles.description}>
            自分と相手のチャンピオンを選択して、マッチアップを確認しましょう。
          </p>
        </div>
        <span className={styles.phase}>PHASE 1 · MVP</span>
      </header>

      <div className={styles.matchupSelector}>
        <ChampionPicker
          id="player"
          side="player"
          title="自分のチャンピオン"
          selected={playerChampion}
          onSelect={setPlayerChampion}
        />
        <div className={styles.searchAction}>
          <button
            className={styles.matchupSearchButton}
            type="button"
            disabled={!playerChampion || !opponentChampion}
            onClick={handleOpenMatchup}
          >
            WinTop!!
          </button>
        </div>
        <ChampionPicker
          id="opponent"
          side="opponent"
          title="相手のチャンピオン"
          selected={opponentChampion}
          onSelect={setOpponentChampion}
        />
      </div>

      <RiotFooter />
    </main>
  );
}
