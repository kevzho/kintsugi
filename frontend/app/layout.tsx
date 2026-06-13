import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kintsugi",
  description:
    "Review CSV quality, leakage risk, missingness, outliers, and class balance before model work begins.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
