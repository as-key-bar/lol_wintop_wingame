"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AccountMenu } from "@/components/AccountMenu";
import { RiotFooter } from "@/components/RiotFooter";
import { apiBaseUrl, putAsEditor } from "@/lib/api";
import { useAuth, type UserRole } from "@/lib/auth";
import styles from "@/app/page.module.css";

type UserSummary = {
  id: number;
  displayName: string;
  email: string;
  role: UserRole;
  createdAt: string;
};

const ROLE_LABEL: Record<UserRole, string> = {
  admin: "管理者",
  editor: "編集者",
  pending: "承認待ち",
};

export default function AdminPage() {
  const auth = useAuth();
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [error, setError] = useState("");
  const isAdmin = auth.user?.role === "admin";

  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    if (!isAdmin) {
      return undefined;
    }
    const controller = new AbortController();
    fetch(new URL("/api/v1/admin/users", apiBaseUrl), {
      credentials: "include",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("ユーザー一覧を取得できませんでした。");
        }
        setUsers((await response.json()) as UserSummary[]);
        setError("");
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : "取得に失敗しました。");
        }
      });
    return () => controller.abort();
  }, [isAdmin, reloads]);

  async function changeRole(user: UserSummary, role: "editor" | "pending") {
    setError("");
    try {
      await putAsEditor<UserSummary>(
        new URL(`/api/v1/admin/users/${user.id}/role`, apiBaseUrl),
        { role },
        "権限を変更できませんでした。",
      );
      setReloads((value) => value + 1);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "変更に失敗しました。");
    }
  }

  return (
    <main className={styles.creditSection}>
      <header className={styles.adminHeader}>
        <Link className={styles.backLink} href="/">
          ← トップへ
        </Link>
        <AccountMenu auth={auth} returnTo="/admin" />
      </header>
      <h1>ユーザー管理</h1>

      {auth.loading ? (
        <p>読み込み中...</p>
      ) : !isAdmin ? (
        <p>このページは、管理者だけが利用できます。</p>
      ) : (
        <>
          <p>
            Google でログインした人は、最初は「承認待ち」です。編集を許可する人を「編集者にする」で承認してください。いつでも「承認を取り消す」で、次の操作から編集できなくできます。
          </p>
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <ul className={styles.userList}>
            {users.map((user) => (
              <li key={user.id} className={styles.userRow}>
                <span>
                  <strong>{user.displayName}</strong>
                  <br />
                  <small>{user.email}</small>
                </span>
                <span>{ROLE_LABEL[user.role]}</span>
                {user.role === "pending" && (
                  <button
                    type="button"
                    className={styles.loadCandidatesButton}
                    onClick={() => changeRole(user, "editor")}
                  >
                    編集者にする
                  </button>
                )}
                {user.role === "editor" && (
                  <button
                    type="button"
                    className={styles.loadCandidatesButton}
                    onClick={() => changeRole(user, "pending")}
                  >
                    承認を取り消す
                  </button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      <RiotFooter />
    </main>
  );
}
