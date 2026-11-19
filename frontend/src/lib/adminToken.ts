// The admin token is kept for the browser tab only (sessionStorage) and shared by the build
// editor and the wave strip, so entering it once is enough.
const ADMIN_TOKEN_STORAGE_KEY = "wintop_admin_token";

export function readStoredAdminToken(): string {
  try {
    return window.sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function storeAdminToken(token: string): void {
  try {
    window.sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
  } catch {
    // sessionStorage may be unavailable; the token is simply not remembered.
  }
}
