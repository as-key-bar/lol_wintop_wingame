import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { WaveNote } from "@/lib/api";
import { WaveStrip } from "./WaveStrip";

const sample: WaveNote[] = [
  { waveNumber: 1, timeSeconds: 85, state: "push" },
  { waveNumber: 2, timeSeconds: 115, state: "push" },
  { waveNumber: 3, timeSeconds: 145, state: "pull" },
];

function renderStrip(
  props: Partial<React.ComponentProps<typeof WaveStrip>> = {},
) {
  const onSave = vi.fn().mockResolvedValue(undefined);
  const onJumpToTimestamp = vi.fn();
  const seekAndPause = vi.fn();
  const onEditingChange = vi.fn();
  render(
    <WaveStrip
      waves={[]}
      firstWaveSeconds={null}
      onSave={onSave}
      saving={false}
      onJumpToTimestamp={onJumpToTimestamp}
      playerReady
      currentTime={() => 92}
      seekAndPause={seekAndPause}
      onEditingChange={onEditingChange}
      {...props}
    />,
  );
  return { onSave, onJumpToTimestamp, seekAndPause, onEditingChange };
}

afterEach(() => {
  window.sessionStorage.clear();
});

describe("WaveStrip (normal view)", () => {
  it("shows the title first and each wave as 'number：state' in a single row", () => {
    renderStrip({ waves: sample, firstWaveSeconds: 85 });

    const strip = screen.getByRole("region", { name: "ウェーブ管理" });
    expect(within(strip).getByRole("heading", { name: "ウェーブ管理" })).toBeInTheDocument();
    const chips = within(strip)
      .getAllByRole("button")
      .map((button) => button.textContent);
    expect(chips).toEqual(["1：プッシュ", "2：プッシュ", "3：プル", "編集"]);
  });

  it("says nothing is entered yet when there are no waves", () => {
    renderStrip();

    expect(screen.getByText("未入力")).toBeInTheDocument();
  });

  it("has no memo text anywhere", () => {
    renderStrip({ waves: sample, firstWaveSeconds: 85 });

    expect(screen.queryByText("メモ")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("メモ")).not.toBeInTheDocument();
  });

  it("jumps the video to a wave when its chip is clicked", async () => {
    const { onJumpToTimestamp } = renderStrip({ waves: sample, firstWaveSeconds: 85 });

    await userEvent.click(screen.getByRole("button", { name: "3：プル" }));

    expect(onJumpToTimestamp).toHaveBeenCalledWith(145);
  });
});

describe("WaveStrip (edit view)", () => {
  async function openEditor(props: Partial<React.ComponentProps<typeof WaveStrip>> = {}) {
    const result = renderStrip(props);
    await userEvent.click(screen.getByRole("button", { name: "編集" }));
    return result;
  }

  it("swaps the strip for the input controls in place and reports editing", async () => {
    const { onEditingChange } = await openEditor();

    expect(screen.getByRole("region", { name: "ウェーブ管理（編集）" })).toBeInTheDocument();
    expect(onEditingChange).toHaveBeenLastCalledWith(true);
    expect(screen.getByLabelText("最初のウェーブの時刻")).toBeInTheDocument();
  });

  it("offers deletion only: there is no way to change a recorded state or add a memo", async () => {
    await openEditor({ waves: sample, firstWaveSeconds: 85 });

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("メモ")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ウェーブ1を削除" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ウェーブ3を削除" })).toBeInTheDocument();
  });

  it("needs the first wave time before any wave can be recorded", async () => {
    await openEditor();

    expect(screen.queryByRole("button", { name: /^プッシュ/ })).not.toBeInTheDocument();
  });

  it("records a wave with one press, then seeks 30 seconds ahead and pauses", async () => {
    const { seekAndPause } = await openEditor({ firstWaveSeconds: 85 });

    await userEvent.click(screen.getByRole("button", { name: /^プッシュ/ }));

    expect(seekAndPause).toHaveBeenLastCalledWith(115);
    expect(screen.getByText(/ウェーブ 2（1:55）/)).toBeInTheDocument();
    expect(screen.getByText("1：プッシュ")).toBeInTheDocument();
  });

  it("records several waves with the keyboard shortcuts", async () => {
    await openEditor({ firstWaveSeconds: 85 });

    await userEvent.keyboard("1");
    await userEvent.keyboard("2");
    await userEvent.keyboard("4");

    const list = screen.getAllByRole("listitem").map((item) => item.textContent);
    expect(list.map((text) => text?.replace("削除", ""))).toEqual([
      "1：プッシュ",
      "2：プル",
      "3：不明",
    ]);
  });

  it("ignores shortcut keys typed into a text field", async () => {
    await openEditor({ firstWaveSeconds: 85 });

    await userEvent.type(screen.getByLabelText("最初のウェーブの時刻"), "1");

    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("re-times every wave when the first wave time changes", async () => {
    const { onSave } = await openEditor({ waves: sample.slice(0, 2), firstWaveSeconds: 85 });

    const input = screen.getByLabelText("最初のウェーブの時刻");
    await userEvent.clear(input);
    await userEvent.type(input, "1:30");
    await userEvent.click(screen.getByRole("button", { name: "設定" }));
    await userEvent.type(screen.getByPlaceholderText("ADMIN_TOKEN"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "ウェーブを保存" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const [waves, first] = onSave.mock.calls[0];
    expect(first).toBe(90);
    expect(waves.map((wave: WaveNote) => wave.timeSeconds)).toEqual([90, 120]);
  });

  it("corrects a wave by deleting it and recording the same number again", async () => {
    const { onSave } = await openEditor({ waves: sample, firstWaveSeconds: 85 });

    await userEvent.click(screen.getByRole("button", { name: "ウェーブ3を削除" }));
    expect(screen.getByText(/ウェーブ 3（2:25）/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^プッシュ/ }));
    await userEvent.type(screen.getByPlaceholderText("ADMIN_TOKEN"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "ウェーブを保存" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const [waves] = onSave.mock.calls[0];
    expect(waves.map((wave: WaveNote) => [wave.waveNumber, wave.state])).toEqual([
      [1, "push"],
      [2, "push"],
      [3, "push"],
    ]);
  });

  it("requires the admin token and shows the server's error without closing", async () => {
    const { onSave } = await openEditor({ waves: sample, firstWaveSeconds: 85 });

    await userEvent.click(screen.getByRole("button", { name: "ウェーブを保存" }));
    expect(screen.getByRole("alert")).toHaveTextContent("管理者トークンを入力してください。");
    expect(onSave).not.toHaveBeenCalled();

    onSave.mockRejectedValueOnce(new Error("管理者トークンが正しくありません。"));
    await userEvent.type(screen.getByPlaceholderText("ADMIN_TOKEN"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "ウェーブを保存" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("管理者トークンが正しくありません。");
    expect(screen.getByRole("region", { name: "ウェーブ管理（編集）" })).toBeInTheDocument();
    expect(window.sessionStorage.getItem("wintop_admin_token")).toBeNull();
  });

  it("returns to the strip after a successful save and remembers the token for the tab", async () => {
    const { onEditingChange } = await openEditor({ waves: sample, firstWaveSeconds: 85 });

    await userEvent.type(screen.getByPlaceholderText("ADMIN_TOKEN"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "ウェーブを保存" }));

    await waitFor(() =>
      expect(screen.getByRole("region", { name: "ウェーブ管理" })).toBeInTheDocument(),
    );
    expect(onEditingChange).toHaveBeenLastCalledWith(false);
    expect(window.sessionStorage.getItem("wintop_admin_token")).toBe("secret");
  });

  it("discards unsaved changes when closed", async () => {
    await openEditor({ waves: sample, firstWaveSeconds: 85 });

    await userEvent.click(screen.getByRole("button", { name: "ウェーブ1を削除" }));
    await userEvent.click(screen.getByRole("button", { name: "閉じる" }));

    expect(screen.getByRole("button", { name: "1：プッシュ" })).toBeInTheDocument();
  });

  it("disables 'use the current position' while the player is not ready", async () => {
    await openEditor({ playerReady: false });

    expect(screen.getByRole("button", { name: "今の再生位置にする" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "設定" })).toBeEnabled();
  });
});
