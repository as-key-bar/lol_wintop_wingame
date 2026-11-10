import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "wintop-wingame",
  description: "League of Legendsのトップレーン向けマッチアップ攻略ツール",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
