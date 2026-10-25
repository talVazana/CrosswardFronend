import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Crossword Arena",
  description: "Competitive crossword game",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
