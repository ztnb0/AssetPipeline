import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Asset Pipeline",
  description: "AI Video Factory 素材资产中心",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

