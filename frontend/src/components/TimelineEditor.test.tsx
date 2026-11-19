import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { VideoTimestamp } from "@/lib/api";
import { TimelineEditor } from "./TimelineEditor";

function Harness({
  initial = [],
  onSeen,
  currentTime,
}: {
  initial?: VideoTimestamp[];
  onSeen?: (items: VideoTimestamp[]) => void;
  currentTime?: () => number | null;
}) {
  const [items, setItems] = useState(initial);
  return (
    <TimelineEditor
      timestamps={items}
      currentTime={currentTime}
      onChange={(next) => {
        setItems(next);
        onSeen?.(next);
      }}
    />
  );
}

const sample: VideoTimestamp[] = [
  { timeSeconds: 182, timeLabel: "3:02", label: "First Blood", isKillEvent: true },
  { timeSeconds: 60, timeLabel: "1:00", label: "Level 3", isKillEvent: false },
];

describe("TimelineEditor", () => {
  it("adds an entry from a typed time and label", async () => {
    const seen = vi.fn();
    render(<Harness onSeen={seen} />);

    await userEvent.type(screen.getByLabelText("新しい項目の時刻"), "2:10");
    await userEvent.type(screen.getByLabelText("新しい項目の内容"), "Gank");
    await userEvent.click(screen.getByLabelText("キル"));
    await userEvent.click(screen.getByRole("button", { name: "追加" }));

    expect(seen.mock.calls.at(-1)![0]).toEqual([
      { timeSeconds: 130, timeLabel: "2:10", label: "Gank", isKillEvent: true },
    ]);
  });

  it("explains a time that cannot be read instead of adding it", async () => {
    const seen = vi.fn();
    render(<Harness onSeen={seen} />);

    await userEvent.type(screen.getByLabelText("新しい項目の時刻"), "abc");
    await userEvent.type(screen.getByLabelText("新しい項目の内容"), "x");
    await userEvent.click(screen.getByRole("button", { name: "追加" }));

    expect(screen.getByRole("alert")).toHaveTextContent("時刻は");
    expect(seen).not.toHaveBeenCalled();
  });

  it("lists entries in time order and deletes one", async () => {
    const seen = vi.fn();
    render(<Harness initial={sample} onSeen={seen} />);

    const times = screen.getAllByLabelText(/ の時刻$/).map((el) => (el as HTMLInputElement).value);
    expect(times).toEqual(["1:00", "3:02"]);

    await userEvent.click(screen.getByRole("button", { name: "1:00 を削除" }));
    expect(seen.mock.calls.at(-1)![0].map((t: VideoTimestamp) => t.label)).toEqual(["First Blood"]);
  });

  it("fills the time from the current playback position", async () => {
    render(<Harness currentTime={() => 95} />);

    await userEvent.click(screen.getByRole("button", { name: "再生位置" }));

    expect(screen.getByLabelText("新しい項目の時刻")).toHaveValue("1:35");
  });
});
