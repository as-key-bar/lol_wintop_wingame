import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function renderFooter() {
  const { RiotFooter } = await import("./RiotFooter");
  render(<RiotFooter />);
}

describe("RiotFooter version label", () => {
  it("shows the build version and exposes the commit as a tooltip", async () => {
    vi.stubEnv("NEXT_PUBLIC_APP_VERSION", "0.2.1");
    vi.stubEnv("NEXT_PUBLIC_APP_COMMIT", "abc1234");
    vi.resetModules();

    await renderFooter();

    const label = screen.getByTestId("app-version");
    expect(label).toHaveTextContent("v0.2.1");
    expect(label).toHaveAttribute("title", "commit abc1234");
  });

  it("falls back to dev when the build did not set a version", async () => {
    vi.stubEnv("NEXT_PUBLIC_APP_VERSION", "");
    vi.stubEnv("NEXT_PUBLIC_APP_COMMIT", "");
    vi.resetModules();

    await renderFooter();

    expect(screen.getByTestId("app-version")).toHaveTextContent("vdev");
    expect(screen.getByTestId("app-version")).not.toHaveAttribute("title");
  });
});
