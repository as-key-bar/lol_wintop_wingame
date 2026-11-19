import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { WaveNote } from "@/lib/api";
import { WaveTagger } from "./WaveTagger";

function Harness({
  initialWaves = [],
  initialFirst = null,
  seekAndPause = vi.fn(),
  currentTime = () => 85 as number | null,
  ready = true,
  onSeen,
}: {
  initialWaves?: WaveNote[];
  initialFirst?: number | null;
  seekAndPause?: (s: number) => void;
  currentTime?: () => number | null;
  ready?: boolean;
  onSeen?: (waves: WaveNote[], first: number | null) => void;
}) {
  const [waves, setWaves] = useState(initialWaves);
  const [first, setFirst] = useState(initialFirst);
  return (
    <WaveTagger
      waves={waves}
      firstWaveSeconds={first}
      onChange={(w, f) => {
        setWaves(w);
        setFirst(f);
        onSeen?.(w, f);
      }}
      playerReady={ready}
      currentTime={currentTime}
      seekAndPause={seekAndPause}
    />
  );
}

describe("WaveTagger", () => {
  it("asks for the first wave time before any wave can be recorded", () => {
    render(<Harness />);

    expect(screen.queryByRole("button", { name: /プッシュ/ })).not.toBeInTheDocument();
  });

  it("sets the first wave from the typed time and seeks there", async () => {
    const seekAndPause = vi.fn();
    render(<Harness seekAndPause={seekAndPause} />);

    await userEvent.type(screen.getByLabelText("最初のウェーブの時刻"), "1:25");
    await userEvent.click(screen.getByRole("button", { name: "設定" }));

    expect(seekAndPause).toHaveBeenLastCalledWith(85);
    expect(screen.getByText(/ウェーブ 1（1:25）/)).toBeInTheDocument();
  });

  it("uses the current playback position as the first wave time", async () => {
    const seekAndPause = vi.fn();
    render(<Harness seekAndPause={seekAndPause} currentTime={() => 92} />);

    await userEvent.click(screen.getByRole("button", { name: "今の再生位置にする" }));

    expect(screen.getByLabelText("最初のウェーブの時刻")).toHaveValue("1:32");
  });

  it("records a wave with one press, moves to the next wave and seeks 30 seconds ahead", async () => {
    const seekAndPause = vi.fn();
    const seen = vi.fn();
    render(<Harness initialFirst={85} seekAndPause={seekAndPause} onSeen={seen} />);

    await userEvent.click(screen.getByRole("button", { name: /^プッシュ/ }));

    const [waves] = seen.mock.calls.at(-1)!;
    expect(waves).toEqual([{ waveNumber: 1, timeSeconds: 85, state: "push", note: "" }]);
    expect(seekAndPause).toHaveBeenLastCalledWith(115);
    expect(screen.getByText(/ウェーブ 2（1:55）/)).toBeInTheDocument();
  });

  it("walks through several waves with the keyboard shortcuts", async () => {
    const seen = vi.fn();
    render(<Harness initialFirst={85} onSeen={seen} />);

    await userEvent.keyboard("1");
    await userEvent.keyboard("2");
    await userEvent.keyboard("4");

    const [waves] = seen.mock.calls.at(-1)!;
    expect(waves.map((w: WaveNote) => [w.waveNumber, w.timeSeconds, w.state])).toEqual([
      [1, 85, "push"],
      [2, 115, "pull"],
      [3, 145, "unknown"],
    ]);
  });

  it("does not record keys typed into a text field", async () => {
    const seen = vi.fn();
    render(<Harness initialFirst={85} onSeen={seen} />);

    await userEvent.type(screen.getByLabelText("最初のウェーブの時刻"), "1");

    expect(seen).not.toHaveBeenCalled();
  });

  it("moves later waves when the first wave time changes", async () => {
    const seen = vi.fn();
    const initial: WaveNote[] = [
      { waveNumber: 1, timeSeconds: 85, state: "push", note: "" },
      { waveNumber: 2, timeSeconds: 115, state: "pull", note: "" },
    ];
    render(<Harness initialWaves={initial} initialFirst={85} onSeen={seen} />);

    const input = screen.getByLabelText("最初のウェーブの時刻");
    await userEvent.clear(input);
    await userEvent.type(input, "1:30");
    await userEvent.click(screen.getByRole("button", { name: "設定" }));

    const [waves, first] = seen.mock.calls.at(-1)!;
    expect(first).toBe(90);
    expect(waves.map((w: WaveNote) => w.timeSeconds)).toEqual([90, 120]);
  });

  it("lets a recorded wave be corrected and removed", async () => {
    const seen = vi.fn();
    const initial: WaveNote[] = [{ waveNumber: 1, timeSeconds: 85, state: "push", note: "" }];
    render(<Harness initialWaves={initial} initialFirst={85} onSeen={seen} />);

    await userEvent.selectOptions(screen.getByLabelText("ウェーブ1の状態"), "pull");
    expect(seen.mock.calls.at(-1)![0][0].state).toBe("pull");

    await userEvent.click(screen.getByRole("button", { name: "ウェーブ1を削除" }));
    expect(seen.mock.calls.at(-1)![0]).toEqual([]);
  });

  it("still works by typed times when the player is not ready", () => {
    render(<Harness ready={false} />);

    expect(screen.getByRole("button", { name: "今の再生位置にする" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "設定" })).toBeEnabled();
  });
});
