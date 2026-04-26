"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Painel" },
  { href: "/traders", label: "Traders" },
  { href: "/portfolio", label: "Carteira" },
  { href: "/signals", label: "Sinais" },
  { href: "/backtest", label: "Backtest" },
  { href: "/settings", label: "Configurações" },
];

export default function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="bg-zinc-900 border-b border-zinc-800 px-4 flex items-center gap-1 h-12">
      <span className="font-bold text-sm text-zinc-100 mr-4">CopyTrader</span>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={cn(
            "px-3 py-1.5 rounded text-sm font-medium transition",
            pathname === l.href
              ? "bg-zinc-700 text-white"
              : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
          )}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
