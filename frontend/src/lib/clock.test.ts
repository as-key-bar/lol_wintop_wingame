import { describe, expect, it } from "vitest";
import { formatClock, parseClock } from "./clock";

describe("clock text", () => {
  it("formats and parses minutes and seconds", () => {
    expect(formatClock(85)).toBe("1:25");
    expect(formatClock(5)).toBe("0:05");
    expect(parseClock("1:25")).toBe(85);
    expect(parseClock("01:05")).toBe(65);
    expect(parseClock("85")).toBe(85);
  });

  it("rejects text that is not a time", () => {
    expect(parseClock("")).toBeNull();
    expect(parseClock("1:75")).toBeNull();
    expect(parseClock("abc")).toBeNull();
  });
});
