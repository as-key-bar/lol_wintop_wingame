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

  const editRegion = () => screen.getByRole("region", { name: "ウェーブ管理（編集）" });

  it("swaps the strip for the input controls in place and reports editing", async () => {
    const { onEditingChange } = await openEditor();

    expect(editRegion()).toBeInTheDocument();
    expect(onEditingChange).toHaveBeenLastCalledWith(true);
  });

  it("parks the video at the 40 second default as soon as the editor opens", async () => {
    const { seekAndPause } = await openEditor();

    expect(seekAndPause).toHaveBeenCalledTimes(1);
    expect(seekAndPause).toHaveBeenCalledWith(40);
  });

  it("does not park the video when only viewing", () => {
    const { seekAndPause } = renderStrip();

    expect(seekAndPause).not.toHaveBeenCalled();
  });

  it("waits for the player before parking the video", async () => {
    const seekAndPause = vi.fn();
    const props = {
      waves: [] as WaveNote[],
      firstWaveSeconds: null,
      onSave: vi.fn().mockResolvedValue(undefined),
      saving: false,
      onJumpToTimestamp: vi.fn(),
      currentTime: () => 92 as number | null,
      seekAndPause,
    };
    const { rerender } = render(<WaveStrip {...props} playerReady={false} />);
    await userEvent.click(screen.getByRole("button", { name: "編集" }));
    expect(seekAndPause).not.toHaveBeenCalled();

    rerender(<WaveStrip {...props} playerReady />);

    expect(seekAndPause).toHaveBeenCalledWith(40);
  });

  it("parks at an already set first wave time instead of the default", async () => {
    const { seekAndPause } = await openEditor({ waves: sample, firstWaveSeconds: 85 });

    expect(seekAndPause).toHaveBeenCalledWith(85);
  });

  it("has no typed first-wave field and only the 'set to the current time' button", async () => {
    await openEditor();

    expect(screen.queryByLabelText("最初のウェーブの時刻")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "設定" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "今の再生位置にする" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "ファーストウェーブの時間を現在時間に設定" }),
    ).toBeInTheDocument();
  });

  it("places the current-time button and the help icon right after the title", async () => {
    await openEditor();

    const header = within(editRegion()).getByRole("heading", { name: "ウェーブ管理（編集）" })
      .parentElement as HTMLElement;
    const order = Array.from(header.children).map((child) => child.textContent?.trim());
    expect(order[0]).toBe("ウェーブ管理（編集）");
    expect(order[1]).toBe("ファーストウェーブの時間を現在時間に設定");
    expect(within(header).getByRole("button", { name: "ウェーブ管理の使い方" })).toBeInTheDocument();
  });

  it("explains how to use it in a help tooltip instead of a paragraph", async () => {
    await openEditor();

    const help = screen.getByRole("tooltip");
    expect(help).toHaveTextContent("概要欄から取得できないため");
    expect(help).toHaveTextContent("25秒先へ送って一時停止");
    expect(help).toHaveTextContent("赤い×で削除");
    expect(screen.getByRole("button", { name: "ウェーブ管理の使い方" })).toHaveAttribute(
      "aria-describedby",
      help.id,
    );
  });

  it("sets the first wave to the current playback time, re-times the waves and seeks there", async () => {
    const { seekAndPause, onSave } = await openEditor({
      waves: sample.slice(0, 2),
      firstWaveSeconds: 85,
      currentTime: () => 92,
    });

    await userEvent.click(
      screen.getByRole("button", { name: "ファーストウェーブの時間を現在時間に設定" }),
    );
    expect(seekAndPause).toHaveBeenLastCalledWith(92);
    await userEvent.type(screen.getByPlaceholderText("ADMIN_TOKEN"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "ウェーブを保存" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const [waves, first] = onSave.mock.calls[0];
    expect(first).toBe(92);
    expect(waves.map((wave: WaveNote) => wave.timeSeconds)).toEqual([92, 122]);
  });

  it("disables the current-time button while the player is not ready", async () => {
    await openEditor({ playerReady: false });

    expect(
      screen.getByRole("button", { name: "ファーストウェーブの時間を現在時間に設定" }),
    ).toBeDisabled();
  });

  it("records from the 40 second default without any setup and stores the 30 second spacing", async () => {
    const { onSave } = await openEditor();

    await userEvent.keyboard("1");
    await userEvent.keyboard("2");
    await userEvent.type(screen.getByPlaceholderText("ADMIN_TOKEN"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "ウェーブを保存" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const [waves, first] = onSave.mock.calls[0];
    expect(first).toBe(40);
    expect(waves.map((w: WaveNote) => [w.waveNumber, w.timeSeconds, w.state])).toEqual([
      [1, 40, "push"],
      [2, 70, "pull"],
    ]);
  });

  it("moves the video only 25 seconds after recording, from that wave's time", async () => {
    const { seekAndPause } = await openEditor({ firstWaveSeconds: 85 });
    seekAndPause.mockClear();

    await userEvent.click(screen.getByRole("button", { name: /^プッシュ/ }));
    expect(seekAndPause).toHaveBeenLastCalledWith(110);

    await userEvent.click(screen.getByRole("button", { name: /^プル/ }));
    expect(seekAndPause).toHaveBeenLastCalledWith(140);
  });

  it("shows the next wave at its 30 second based time even though the video moves 25 seconds", async () => {
    await openEditor({ firstWaveSeconds: 85 });

    await userEvent.click(screen.getByRole("button", { name: /^プッシュ/ }));

    expect(screen.getByText(/ウェーブ 2（1:55）/)).toBeInTheDocument();
  });

  it("records several waves with the keyboard shortcuts", async () => {
    await openEditor({ firstWaveSeconds: 85 });

    await userEvent.keyboard("1");
    await userEvent.keyboard("2");
    await userEvent.keyboard("4");

    const labels = within(editRegion())
      .getAllByRole("listitem")
      .map((item) => item.textContent?.replace("×", "").replace(/^\d+:\d{2}/, ""));
    expect(labels).toEqual(["1：プッシュ", "2：プル", "3：不明"]);
  });

  it("ignores shortcut keys typed into a text field", async () => {
    await openEditor({ firstWaveSeconds: 85 });

    await userEvent.type(screen.getByPlaceholderText("ADMIN_TOKEN"), "1");

    expect(within(editRegion()).queryAllByRole("listitem")).toHaveLength(0);
  });

  it("shows each wave's time in small text above its icon, in the edit view only", async () => {
    renderStrip({ waves: sample, firstWaveSeconds: 85 });
    const strip = screen.getByRole("region", { name: "ウェーブ管理" });
    expect(within(strip).queryByText("1:25")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "編集" }));

    const items = within(editRegion()).getAllByRole("listitem");
    expect(items.map((item) => item.firstElementChild?.textContent)).toEqual(["1:25", "1:55", "2:25"]);
  });

  it("deletes a wave with the red × at the left end of its icon, and has no 削除 buttons", async () => {
    await openEditor({ waves: sample, firstWaveSeconds: 85 });

    expect(screen.queryByRole("button", { name: "削除" })).not.toBeInTheDocument();
    const item = within(editRegion()).getAllByRole("listitem")[2];
    const mark = within(item).getByRole("button", { name: "ウェーブ3を削除" });
    expect(mark).toHaveTextContent("×");
    const chip = mark.parentElement as HTMLElement;
    expect(chip.firstElementChild).toBe(mark);

    await userEvent.click(mark);

    expect(within(editRegion()).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText(/ウェーブ 3（2:25）/)).toBeInTheDocument();
  });

  it("corrects a wave by deleting it and recording the same number again", async () => {
    const { onSave } = await openEditor({ waves: sample, firstWaveSeconds: 85 });

    await userEvent.click(screen.getByRole("button", { name: "ウェーブ3を削除" }));
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

  it("offers deletion only: no state selector and no memo", async () => {
    await openEditor({ waves: sample, firstWaveSeconds: 85 });

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("メモ")).not.toBeInTheDocument();
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
    expect(editRegion()).toBeInTheDocument();
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
});
