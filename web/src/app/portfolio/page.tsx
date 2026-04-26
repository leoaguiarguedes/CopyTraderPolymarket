import { fetchPositions } from "@/lib/api";
import { cn, fmtUsd, fmtMinutes, fmtTime, shortAddr } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function PortfolioPage() {
  const [open, closed] = await Promise.all([
    fetchPositions("open", 200),
    fetchPositions("closed", 100),
  ]);

  return (
    <div className="flex flex-col gap-6">
      {/* ── Open Positions ───────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-lg font-bold text-zinc-100">Posições abertas</h1>
          <span className="text-xs text-zinc-500">{open.length} abertas</span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-zinc-500 text-xs uppercase tracking-wide bg-zinc-900 border-b border-zinc-800">
                <th className="px-4 py-3 text-left">Mercado</th>
                <th className="px-4 py-3 text-left">Estratégia</th>
                <th className="px-4 py-3 text-left">Lado</th>
                <th className="px-4 py-3 text-right">Entrada</th>
                <th className="px-4 py-3 text-right">Tamanho</th>
                <th className="px-4 py-3 text-right">TP</th>
                <th className="px-4 py-3 text-right">SL</th>
                <th className="px-4 py-3 text-right">Idade</th>
                <th className="px-4 py-3 text-right">Saída em</th>
                <th className="px-4 py-3 text-left">Aberta em</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800 bg-zinc-950">
              {open.length === 0 && (
                <tr>
                  <td
                    colSpan={10}
                    className="px-4 py-8 text-center text-zinc-500 italic"
                  >
                    Nenhuma posição aberta
                  </td>
                </tr>
              )}
              {open.map((p) => {
                const urgentExit =
                  p.time_to_force_exit_minutes != null &&
                  p.time_to_force_exit_minutes < 10;
                return (
                  <tr
                    key={p.position_id}
                    className={cn(
                      "hover:bg-zinc-900/60 transition",
                      urgentExit && "bg-red-950/30"
                    )}
                  >
                    <td
                      className="px-4 py-3 font-mono text-xs text-zinc-300 max-w-[120px] truncate"
                      title={p.market_id}
                    >
                      {shortAddr(p.market_id)}
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-xs">
                      {p.strategy}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-xs font-bold",
                          p.side === "YES"
                            ? "bg-green-900/40 text-green-400"
                            : "bg-red-900/40 text-red-400"
                        )}
                      >
                        {p.side}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-zinc-300">
                      {p.entry_price.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-300">
                      {fmtUsd(p.size_usd)}
                    </td>
                    <td className="px-4 py-3 text-right text-green-600 font-mono text-xs">
                      {p.tp_price.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right text-red-600 font-mono text-xs">
                      {p.sl_price.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-400 text-xs">
                      {fmtMinutes(p.age_minutes)}
                    </td>
                    <td
                      className={cn(
                        "px-4 py-3 text-right text-xs font-semibold",
                        urgentExit ? "text-red-400 animate-pulse" : "text-zinc-400"
                      )}
                    >
                      {p.time_to_force_exit_minutes != null
                        ? fmtMinutes(p.time_to_force_exit_minutes)
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">
                      {p.opened_at ? fmtTime(p.opened_at) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Closed Positions ─────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-lg font-bold text-zinc-100">Posições fechadas</h1>
          <span className="text-xs text-zinc-500">
            {closed.length} exibidas (últimas 100)
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-zinc-500 text-xs uppercase tracking-wide bg-zinc-900 border-b border-zinc-800">
                <th className="px-4 py-3 text-left">Mercado</th>
                <th className="px-4 py-3 text-left">Estratégia</th>
                <th className="px-4 py-3 text-left">Lado</th>
                <th className="px-4 py-3 text-right">Entrada</th>
                <th className="px-4 py-3 text-right">Saída</th>
                <th className="px-4 py-3 text-right">Tamanho</th>
                <th className="px-4 py-3 text-right">P/L</th>
                <th className="px-4 py-3 text-left">Motivo</th>
                <th className="px-4 py-3 text-left">Fechada em</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800 bg-zinc-950">
              {closed.length === 0 && (
                <tr>
                  <td
                    colSpan={9}
                    className="px-4 py-8 text-center text-zinc-500 italic"
                  >
                    Ainda não há posições fechadas
                  </td>
                </tr>
              )}
              {closed.map((p) => {
                const pnl = p.realized_pnl_usd ?? 0;
                return (
                  <tr
                    key={p.position_id}
                    className="hover:bg-zinc-900/60 transition"
                  >
                    <td
                      className="px-4 py-3 font-mono text-xs text-zinc-300 max-w-[120px] truncate"
                      title={p.market_id}
                    >
                      {shortAddr(p.market_id)}
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-xs">
                      {p.strategy}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-xs font-bold",
                          p.side === "YES"
                            ? "bg-green-900/40 text-green-400"
                            : "bg-red-900/40 text-red-400"
                        )}
                      >
                        {p.side}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-zinc-300 text-xs">
                      {p.entry_price.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-zinc-300 text-xs">
                      {p.exit_price != null ? p.exit_price.toFixed(4) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-300">
                      {fmtUsd(p.size_usd)}
                    </td>
                    <td
                      className={cn(
                        "px-4 py-3 text-right font-semibold",
                        pnl >= 0 ? "text-green-400" : "text-red-400"
                      )}
                    >
                      {pnl >= 0 ? "+" : ""}
                      {fmtUsd(pnl)}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded",
                          p.exit_reason === "tp"
                            ? "bg-green-900/40 text-green-400"
                            : p.exit_reason === "sl"
                            ? "bg-red-900/40 text-red-400"
                            : p.exit_reason === "timeout"
                            ? "bg-yellow-900/40 text-yellow-400"
                            : "bg-zinc-800 text-zinc-400"
                        )}
                      >
                        {p.exit_reason ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">
                      {p.closed_at ? fmtTime(p.closed_at) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
