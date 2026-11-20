"use client";

import Link from "next/link";
import styles from "@/app/page.module.css";
import { loginUrl, logout, type AuthState, type UserRole } from "@/lib/auth";

const ROLE_LABEL: Record<UserRole, string> = {
  admin: "管理者",
  editor: "編集者",
  pending: "承認待ち",
};

type AccountMenuProps = {
  auth: AuthState;
  // Where to come back to after logging in; defaults to the current page.
  returnTo?: string;
};

// Viewing needs no login, so this only offers "login for editing" and shows the current role.
export function AccountMenu({ auth, returnTo }: AccountMenuProps) {
  if (auth.loading || !auth.loginEnabled) {
    return null;
  }

  if (!auth.user) {
    const back = returnTo ?? `${window.location.pathname}${window.location.search}`;
    return (
      <a className={styles.accountButton} href={loginUrl(back)}>
        編集者ログイン
      </a>
    );
  }

  const { user } = auth;
  return (
    <div className={styles.accountMenu}>
      <span
        className={`${styles.accountRole} ${
          user.role === "pending" ? styles.accountRolePending : ""
        }`}
        title={user.email}
      >
        {user.displayName}（{ROLE_LABEL[user.role]}）
      </span>
      {user.role === "pending" && (
        <span className={styles.accountHint}>管理者の承認後に編集できます</span>
      )}
      {user.role === "admin" && (
        <Link className={styles.accountButton} href="/admin">
          ユーザー管理
        </Link>
      )}
      <button
        type="button"
        className={styles.accountButton}
        onClick={async () => {
          await logout();
          auth.refresh();
        }}
      >
        ログアウト
      </button>
    </div>
  );
}
