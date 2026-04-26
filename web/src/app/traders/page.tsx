import { fetchWallets } from "@/lib/api";
import { fmtPct, fmtMinutes, shortAddr, fmtUsd } from "@/lib/utils";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function TradersPage() {
  let wallets = await fetchWallets().catch(() => []);
  // Sort by sharpe desc, fallback to roi
  wallets = wallets.sort(
    (a, b) => (b.sharpe ?? 0) - (a.sharpe ?? 0)
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-zinc-100">Traders rastreados</h1>
        <span className="text-xs text-zinc-500">{wallets.length} carteiras</span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-zinc-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-zinc-500 text-xs uppercase tracking-wide bg-zinc-900 border-b border-zinc-800">
              <th className="px-4 py-3 text-left">#</th>
              <th className="px-4 py-3 text-left">Carteira</th>
              <th className="px-4 py-3 text-right">Negócios</th>
              <th className="px-4 py-3 text-right">Sharpe</th>
              <th className="px-4 py-3 text-right">ROI</th>
              <th className="px-4 py-3 text-right">Taxa de acerto</th>
              <th className="px-4 py-3 text-right">Máx. DD</th>
              <th className="px-4 py-3 text-right">Tempo médio</th>
              <th className="px-4 py-3 text-right">Volume</th>
              <th className="px-4 py-3 text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 bg-zinc-950">
            {wallets.length === 0 && (
              <tr>
                <td
                  colSpan={10}
                  className="px-4 py-8 text-center text-zinc-500 italic"
                >
                  Nenhuma carteira rastreada ainda. Execute{" "}
                  <code className="text-zinc-400">
                    python scripts/discover_wallets.py
                  </code>{" "}
                  primeiro.
                </td>
              </tr>
            )}
            {wallets.map((w, i) => (
              <tr
                key={w.wallet}
                className="hover:bg-zinc-900/60 transition"
              >
                <td className="px-4 py-3 text-zinc-500">{i + 1}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  <span className="text-zinc-200" title={w.wallet}>
                    {shortAddr(w.wallet)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-zinc-300">
                  {w.n_trades ?? "—"}
                </td>
                <td
                  className={cn(
                    "px-4 py-3 text-right font-semibold",
                    (w.sharpe ?? 0) >= 0.5
                      ? "text-green-400"
                      : "text-zinc-400"
                  )}
                >
                  {w.sharpe != null ? w.sharpe.toFixed(2) : "—"}
                </td>
                <td
                  className={cn(
                    "px-4 py-3 text-right font-semibold",
                    (w.roi ?? 0) >= 0 ? "text-green-400" : "text-red-400"
                  )}
                >
                  {w.roi != null ? fmtPct(w.roi) : "—"}
                </td>
                <td className="px-4 py-3 text-right text-zinc-300">
                  {w.win_rate != null ? fmtPct(w.win_rate) : "—"}
                </td>
                <td
                  className={cn(
                    "px-4 py-3 text-right",
                    (w.max_drawdown ?? 0) > 0.3
                      ? "text-red-400"
                      : "text-zinc-300"
                  )}
                >
                  {w.max_drawdown != null ? fmtPct(w.max_drawdown) : "—"}
                </td>
                <td className="px-4 py-3 text-right text-zinc-300">
                  {w.median_holding_minutes != null
                    ? fmtMinutes(w.median_holding_minutes)
                    : "—"}
                </td>
                <td className="px-4 py-3 text-right text-zinc-300">
                  {w.total_volume_usd != null
                    ? fmtUsd(w.total_volume_usd)
                    : "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-xs font-medium",
                      w.is_active
                        ? "bg-green-900/40 text-green-400"
                        : "bg-zinc-800 text-zinc-500"
                    )}
                  >
                    {w.is_active ? "ativo" : "rastreado"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
