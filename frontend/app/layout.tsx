import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Data Quality IQ — know what's wrong before you train",
  description:
    "Upload a CSV and get a 0-100 data-quality health score, target-leakage detection, and an executive summary in seconds.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
