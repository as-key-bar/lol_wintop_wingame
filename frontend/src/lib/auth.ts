"use client";

import { useCallback, useEffect, useState } from "react";
import { apiBaseUrl } from "@/lib/api";

export type UserRole = "admin" | "editor" | "pending";

export type CurrentUser = {
  displayName: string;
  email: string;
  role: UserRole;
};

export type AuthState = {
  loading: boolean;
  loginEnabled: boolean;
  user: CurrentUser | null;
  canEdit: boolean;
  refresh: () => void;
};

export function canEditRole(role: UserRole | undefined): boolean {
  return role === "admin" || role === "editor";
}

export function loginUrl(returnTo: string): string {
  const url = new URL("/api/v1/auth/google/login", apiBaseUrl);
  url.searchParams.set("returnTo", returnTo);
  return url.toString();
}

export async function logout(): Promise<void> {
  await fetch(new URL("/api/v1/auth/logout", apiBaseUrl), {
    method: "POST",
    credentials: "include",
  });
}

// Who is logged in. Viewing never needs this: it only decides whether to show the edit buttons.
export function useAuth(): AuthState {
  const [state, setState] = useState<Omit<AuthState, "refresh" | "canEdit">>({
    loading: true,
    loginEnabled: false,
    user: null,
  });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(new URL("/api/v1/auth/me", apiBaseUrl), {
          credentials: "include",
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("auth/me failed");
        }
        const data = (await response.json()) as {
          loginEnabled: boolean;
          user: CurrentUser | null;
        };
        setState({ loading: false, loginEnabled: data.loginEnabled, user: data.user });
      } catch {
        if (!controller.signal.aborted) {
          setState({ loading: false, loginEnabled: false, user: null });
        }
      }
    }
    void load();
    return () => controller.abort();
  }, [version]);

  const refresh = useCallback(() => setVersion((value) => value + 1), []);
  return { ...state, canEdit: canEditRole(state.user?.role), refresh };
}
