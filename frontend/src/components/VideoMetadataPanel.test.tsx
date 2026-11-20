import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { GameAssetsCatalog, VideoMetadataAnalysis } from "@/lib/api";
import { VideoMetadataPanel } from "./VideoMetadataPanel";

const assets: GameAssetsCatalog = {
  dataDragonVersion: "16.22.1",
  sourceUrl: "https://example.com",
  runeStyles: [
    {
      id: 8000,
      key: "Precision",
      nameJa: "栄華",
      nameEn: "Precision",
      iconUrl: "https://example.com/precision.png",
      slots: [],
    },
    {
      id: 8200,
      key: "Sorcery",
      nameJa: "魔導",
      nameEn: "Sorcery",
      iconUrl: "https://example.com/sorcery.png",
      slots: [],
    },
  ],
  statShardRows: [],
  summonerSpells: [
    {
      id: "SummonerFlash",
      key: "4",
      nameJa: "フラッシュ",
      nameEn: "Flash",
      iconUrl: "https://example.com/flash.png",
    },
  ],
  starterItems: [
    {
      id: "1054",
      nameJa: "ドランシールド",
      nameEn: "Doran's Shield",
      gold: 450,
      iconUrl: "https://example.com/doran.png",
    },
  ],
};

function metadata(
  overrides: Partial<VideoMetadataAnalysis> = {},
): VideoMetadataAnalysis {
  return {
    analysisStatus: "auto_parsed",
    runes: null,
    summonerSpells: ["SummonerFlash"],
    startingItems: [],
    timestamps: [],
    waves: [],
    ...overrides,
  };
}

function renderPanel(
  props: Partial<React.ComponentProps<typeof VideoMetadataPanel>> = {},
) {
  const onAnalyzeDescription = vi.fn();
  const onSaveManualMetadata = vi.fn().mockResolvedValue(undefined);
  render(
    <VideoMetadataPanel
      metadata={metadata()}
      gameAssets={assets}
      analyzing={false}
      savingManual={false}
      onAnalyzeDescription={onAnalyzeDescription}
      onSaveManualMetadata={onSaveManualMetadata}
      canEdit
      onJumpToTimestamp={vi.fn()}
      {...props}
    />,
  );
  return { onAnalyzeDescription, onSaveManualMetadata };
}

describe("VideoMetadataPanel analyze button", () => {
  it("offers the first extraction when nothing is analyzed", async () => {
    const { onAnalyzeDescription } = renderPanel({
      metadata: metadata({ analysisStatus: "unanalyzed", summonerSpells: [] }),
    });

    await userEvent.click(
      screen.getByRole("button", { name: "概要欄から自動取得" }),
    );

    expect(onAnalyzeDescription).toHaveBeenCalledWith(false);
  });

  it("asks for a refresh when auto-parsed data already exists", async () => {
    const { onAnalyzeDescription } = renderPanel();

    await userEvent.click(
      screen.getByRole("button", { name: "概要欄から再取得" }),
    );

    expect(onAnalyzeDescription).toHaveBeenCalledWith(true);
  });

  it("is disabled for manually verified data", () => {
    renderPanel({ metadata: metadata({ analysisStatus: "manual_verified" }) });

    expect(
      screen.getByRole("button", { name: "概要欄から再取得" }),
    ).toBeDisabled();
  });
});

describe("VideoMetadataPanel starter items", () => {
  it("shows an unconfirmed note when no starter item is known", () => {
    renderPanel();

    expect(screen.getByText(/未確認（概要欄に記載がなく/)).toBeInTheDocument();
  });

  it("labels the source of a listed starter item", () => {
    renderPanel({ metadata: metadata({ startingItems: ["1054"] }) });

    expect(screen.getByText("スタートアイテム（概要欄の記載）")).toBeInTheDocument();
    expect(screen.getByText("ドランシールド")).toBeInTheDocument();
  });
});

describe("VideoMetadataPanel manual save", () => {
  async function openEditor() {
    await userEvent.click(screen.getByRole("button", { name: "ビルドを手動編集" }));
  }

  it("saves as the logged-in editor, with no token to type", async () => {
    const { onSaveManualMetadata } = renderPanel();
    await openEditor();

    await userEvent.click(
      screen.getByRole("button", { name: "このビルド情報をDBに保存" }),
    );

    await waitFor(() => expect(onSaveManualMetadata).toHaveBeenCalledTimes(1));
    const [saved] = onSaveManualMetadata.mock.calls[0];
    expect(saved.analysisStatus).toBe("manual_verified");
    expect(onSaveManualMetadata.mock.calls[0]).toHaveLength(1);
  });

  it("hides the edit button from people who may not edit", () => {
    renderPanel({ canEdit: false });

    expect(
      screen.queryByRole("button", { name: "ビルドを手動編集" }),
    ).not.toBeInTheDocument();
  });

  it("shows the server error and keeps the editor open when saving fails", async () => {
    const { onSaveManualMetadata } = renderPanel();
    onSaveManualMetadata.mockRejectedValueOnce(
      new Error("編集には、管理者の承認が必要です。"),
    );
    await openEditor();

    await userEvent.click(
      screen.getByRole("button", { name: "このビルド情報をDBに保存" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "編集には、管理者の承認が必要です。",
    );
    expect(screen.getByRole("button", { name: "編集を閉じる" })).toBeInTheDocument();
  });
});


describe("VideoMetadataPanel build editing (independent of waves)", () => {
  it("does not show waves: they live in their own strip", () => {
    renderPanel({
      metadata: metadata({
        waves: [{ waveNumber: 1, state: "push" }],
      }),
    });

    expect(screen.queryByText(/ウェーブ/)).not.toBeInTheDocument();
  });

  it("saves the edited timeline with the build and sends no wave data", async () => {
    const { onSaveManualMetadata } = renderPanel({
      metadata: metadata({
        timestamps: [{ timeSeconds: 60, timeLabel: "1:00", label: "auto", isKillEvent: false }],
        waves: [{ waveNumber: 1, state: "push" }],
      }),
    });

    await userEvent.click(screen.getByRole("button", { name: "ビルドを手動編集" }));
    await userEvent.click(screen.getByRole("button", { name: "1:00 を削除" }));
    await userEvent.click(screen.getByRole("button", { name: "このビルド情報をDBに保存" }));

    await waitFor(() => expect(onSaveManualMetadata).toHaveBeenCalledTimes(1));
    const [saved] = onSaveManualMetadata.mock.calls[0];
    expect(saved.timestamps).toEqual([]);
    expect(saved).not.toHaveProperty("waves");
  });

  it("tells the page when the editor opens and closes so the player can be controlled", async () => {
    const onEditingChange = vi.fn();
    renderPanel({ onEditingChange });

    await userEvent.click(screen.getByRole("button", { name: "ビルドを手動編集" }));
    expect(onEditingChange).toHaveBeenLastCalledWith(true);

    await userEvent.click(screen.getByRole("button", { name: "編集を閉じる" }));
    expect(onEditingChange).toHaveBeenLastCalledWith(false);
  });
});
