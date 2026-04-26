import type { Metadata } from "next";
import "./globals.css";
import NavBar from "@/components/NavBar";
import KillSwitchBanner from "@/components/KillSwitchBanner";

export const metadata: Metadata = {
  title: "CopyTrader Polymarket",
  description: "Automated copytrading dashboard for Polymarket",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        <KillSwitchBanner />
        <NavBar />
        <main className="p-4 md:p-6">{children}</main>
      </body>
    </html>
  );
}
