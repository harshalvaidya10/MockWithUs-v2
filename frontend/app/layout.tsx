import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MockWithUs",
  description: "AI Interview Copilot scaffold",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
