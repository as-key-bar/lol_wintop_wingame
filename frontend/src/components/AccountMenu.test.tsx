import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { AuthState } from "@/lib/auth";
import { AccountMenu } from "./AccountMenu";

function auth(overrides: Partial<AuthState> = {}): AuthState {
  return {
    loading: false,
    loginEnabled: true,
    user: null,
    canEdit: false,
    refresh: vi.fn(),
    ...overrides,
  };
}

describe("AccountMenu", () => {
  it("shows nothing while loading or when login is not set up on the server", () => {
    const { container, rerender } = render(<AccountMenu auth={auth({ loading: true })} />);
    expect(container).toBeEmptyDOMElement();

    rerender(<AccountMenu auth={auth({ loginEnabled: false })} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("offers a login for editing to a visitor, returning to the given page", () => {
    render(<AccountMenu auth={auth()} returnTo="/matchup/Aatrox/Darius" />);

    const link = screen.getByRole("link", { name: "編集者ログイン" });
    const url = new URL(link.getAttribute("href") ?? "");
    expect(url.pathname).toBe("/api/v1/auth/google/login");
    expect(url.searchParams.get("returnTo")).toBe("/matchup/Aatrox/Darius");
  });

  it("tells a pending user that approval is needed and offers no admin link", () => {
    render(
      <AccountMenu
        auth={auth({ user: { displayName: "Friend", email: "f@example.com", role: "pending" } })}
      />,
    );

    expect(screen.getByText(/承認待ち/)).toBeInTheDocument();
    expect(screen.getByText("管理者の承認後に編集できます")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "ユーザー管理" })).not.toBeInTheDocument();
  });

  it("shows the user management link to the admin only", () => {
    const { rerender } = render(
      <AccountMenu
        auth={auth({
          canEdit: true,
          user: { displayName: "Boss", email: "b@example.com", role: "admin" },
        })}
      />,
    );
    expect(screen.getByRole("link", { name: "ユーザー管理" })).toHaveAttribute("href", "/admin");

    rerender(
      <AccountMenu
        auth={auth({
          canEdit: true,
          user: { displayName: "Ed", email: "e@example.com", role: "editor" },
        })}
      />,
    );
    expect(screen.queryByRole("link", { name: "ユーザー管理" })).not.toBeInTheDocument();
  });

  it("logs out and refreshes the account state", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    const refresh = vi.fn();
    render(
      <AccountMenu
        auth={auth({
          refresh,
          user: { displayName: "Ed", email: "e@example.com", role: "editor" },
        })}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "ログアウト" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", credentials: "include" });
    expect(refresh).toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
