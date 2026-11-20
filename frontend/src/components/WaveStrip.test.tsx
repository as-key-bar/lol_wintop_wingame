import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { WaveNote } from "@/lib/api";
import { WaveStrip } from "./WaveStrip";

const sample: WaveNote[] = [
  { waveNumber: 1, state: "push" },
  { waveNumber: 2, state: "push" },
  { waveNumber: 3, state: "pull" },
];

function renderStrip(
  props: Partial<React.ComponentProps<typeof WaveStrip>> = {},
) {
  const onSave = vi.fn().mockResolvedValue(undefined);
  render(<WaveStrip waves={[]} onSave={onSave} saving={false} {...props} />);
  return { onSave };
}

afterEach(() => {
  window.sessionStorage.clear();
});

describe("WaveStrip (normal view)", () => {
  it("shows the title first and each wave as 'number：state' in a single row", () => {
    renderStrip({ waves: sample });

    const strip = screen.getByRole("region", { name: "ウェーブ管理" });
    expect(within(strip).getByRole("heading", { name: "ウェーブ管理" })).toBeInTheDocument();
    expect(screen.getByText("1：プッシュ")).toBeInTheDocument();
    expect(screen.getByText("2：プッシュ")).toBeInTheDocument();
    expect(screen.getByText("3：プル")).toBeInTheDocument();
    expect(within(strip).getAllByRole("button").map((b) => b.textContent)).toEqual(["編集"]);
  });

  it("says nothing is entered yet when there are no waves", () => {
    renderStrip();

    expect(screen.getByText("未入力")).toBeInTheDocument();
  });

  it("has no memo text and no video time anywhere", () => {
    renderStrip({ waves: sample });

    expect(screen.queryByText("メモ")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("メモ")).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+:\d{2}/)).not.toBeInTheDocument();
  });
});

describe("WaveStrip (edit view)", () => {
  async function openEditor(props: Partial<React.ComponentProps<typeof WaveStrip>> = {}) {
    const result = renderStrip(props);
    await userEvent.click(screen.getByRole("button", { name: "編集" }));
    return result;
  }

  const editRegion = () => screen.getByRole("region", { name: "ウェーブ管理（編集）" });

  async function saveWithToken() {
    await userEvent.type(screen.getByPlaceholderText("ADMIN_TOKEN"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "ウェーブを保存" }));
  }

  it("swaps the strip for the input controls in place", async () => {
    await openEditor();

    expect(editRegion()).toBeInTheDocument();
  });

  it("has no first-wave time setting and no time field at all", async () => {
    await openEditor();

    expect(
      screen.queryByRole("button", { name: "ファーストウェーブの時間を現在時間に設定" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("最初のウェーブの時刻")).not.toBeInTheDocument();
  });

  it("can record from the very first push/pull, with the buttons always shown", async () => {
    await openEditor();

    expect(screen.getByRole("button", { name: /^プッシュ/ })).toBeInTheDocument();
    expect(screen.getByText(/ウェーブ 1：まだ記録していません/)).toBeInTheDocument();
  });

  it("explains how to use it in a help tooltip next to the title", async () => {
    await openEditor();

    const header = within(editRegion()).getByRole("heading", { name: "ウェーブ管理（編集）" })
      .parentElement as HTMLElement;
    expect(within(header).getByRole("button", { name: "ウェーブ管理の使い方" })).toBeInTheDocument();
    const help = screen.getByRole("tooltip");
    expect(help).toHaveTextContent("概要欄から取得できないため");
    expect(help).toHaveTextContent("再生位置は記録しません");
    expect(help).not.toHaveTextContent("現在時間に設定");
    expect(help).toHaveTextContent("赤い×で削除");
    expect(screen.getByRole("button", { name: "ウェーブ管理の使い方" })).toHaveAttribute(
      "aria-describedby",
      help.id,
    );
  });

  it("records waves in order with the buttons and saves only number and state", async () => {
    const { onSave } = await openEditor();

    await userEvent.click(screen.getByRole("button", { name: /^プッシュ/ }));
    expect(screen.getByText(/ウェーブ 2：まだ記録していません/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^プル/ }));
    await saveWithToken();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const [waves, token] = onSave.mock.calls[0];
    expect(waves).toEqual([
      { waveNumber: 1, state: "push" },
      { waveNumber: 2, state: "pull" },
    ]);
    expect(token).toBe("secret");
  });

  it("records several waves with the keyboard shortcuts", async () => {
    await openEditor();

    await userEvent.keyboard("1");
    await userEvent.keyboard("2");
    await userEvent.keyboard("4");

    const labels = within(editRegion())
      .getAllByRole("listitem")
      .map((item) => item.textContent?.replace("×", ""));
    expect(labels).toEqual(["1：プッシュ", "2：プル", "3：不明"]);
  });

  it("ignores shortcut keys typed into a text field", async () => {
    await openEditor();

    await userEvent.type(screen.getByPlaceholderText("ADMIN_TOKEN"), "1");

    expect(within(editRegion()).queryAllByRole("listitem")).toHaveLength(0);
  });

  it("continues after the existing waves", async () => {
    await openEditor({ waves: sample });

    expect(screen.getByText(/ウェーブ 4：まだ記録していません/)).toBeInTheDocument();
  });

  it("deletes a wave with the red × at the left end of its icon, and has no 削除 buttons", async () => {
    await openEditor({ waves: sample });

    expect(screen.queryByRole("button", { name: "削除" })).not.toBeInTheDocument();
    const item = within(editRegion()).getAllByRole("listitem")[2];
    const mark = within(item).getByRole("button", { name: "ウェーブ3を削除" });
    expect(mark).toHaveTextContent("×");
    const chip = mark.parentElement as HTMLElement;
    expect(chip.firstElementChild).toBe(mark);

    await userEvent.click(mark);

    expect(within(editRegion()).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText(/ウェーブ 3：まだ記録していません/)).toBeInTheDocument();
  });

  it("corrects a wave by deleting it and recording the same number again", async () => {
    const { onSave } = await openEditor({ waves: sample });

    await userEvent.click(screen.getByRole("button", { name: "ウェーブ3を削除" }));
    await userEvent.click(screen.getByRole("button", { name: /^プッシュ/ }));
    await saveWithToken();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const [waves] = onSave.mock.calls[0];
    expect(waves.map((wave: WaveNote) => [wave.waveNumber, wave.state])).toEqual([
      [1, "push"],
      [2, "push"],
      [3, "push"],
    ]);
  });

  it("offers deletion only: no state selector and no memo", async () => {
    await openEditor({ waves: sample });

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("メモ")).not.toBeInTheDocument();
  });

  it("requires the admin token and shows the server's error without closing", async () => {
    const { onSave } = await openEditor({ waves: sample });

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
    await openEditor({ waves: sample });

    await saveWithToken();

    await waitFor(() =>
      expect(screen.getByRole("region", { name: "ウェーブ管理" })).toBeInTheDocument(),
    );
    expect(window.sessionStorage.getItem("wintop_admin_token")).toBe("secret");
  });

  it("discards unsaved changes when closed", async () => {
    await openEditor({ waves: sample });

    await userEvent.click(screen.getByRole("button", { name: "ウェーブ1を削除" }));
    await userEvent.click(screen.getByRole("button", { name: "閉じる" }));

    expect(screen.getByText("1：プッシュ")).toBeInTheDocument();
  });
});
