import { fetchSignals } from "@/lib/api";
import { cn, fmtTime, fmtPct, shortAddr, fmtMinutes } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function SignalsPage() {
  const signals = await fetchSignals(100).catch(() => []);

  const approved = signals.filter((s) => s.status === "approved" || s.status === "executed");
  const rejected = signals.filter((s) => s.status === "rejected");
  const statusMap = {
    approved: "aprovado",
    executed: "executado",
    rejected: "rejeitado",
  } as const;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-zinc-100">Feed de sinais</h1>
        <div className="flex gap-3 text-xs text-zinc-500">
          <span className="text-green-400 font-semibold">
            {approved.length} aprovados
          </span>
          <span className="text-red-400 font-semibold">
            {rejected.length} rejeitados
          </span>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-zinc-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-zinc-500 text-xs uppercase tracking-wide bg-zinc-900 border-b border-zinc-800">
              <th className="px-4 py-3 text-left">Hora</th>
              <th className="px-4 py-3 text-left">Estratégia</th>
              <th className="px-4 py-3 text-left">Mercado</th>
              <th className="px-4 py-3 text-left">Lado</th>
              <th className="px-4 py-3 text-right">Conf</th>
              <th className="px-4 py-3 text-right">Entrada</th>
              <th className="px-4 py-3 text-right">Tamanho%</th>
              <th className="px-4 py-3 text-right">Máx. espera</th>
              <th className="px-4 py-3 text-left">Origem</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left">Decisão</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 bg-zinc-950">
            {signals.length === 0 && (
              <tr>
                <td
                  colSpan={11}
                  className="px-4 py-8 text-center text-zinc-500 italic"
                >
                  Ainda não há sinais — execute o worker de sinais para ver dados aqui.
                </td>
              </tr>
            )}
            {signals.map((s) => (
              <tr
                key={s.signal_id}
                className={cn(
                  "hover:bg-zinc-900/60 transition",
                  s.status === "rejected" && "opacity-60"
                )}
              >
                <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap">
                  {fmtTime(s.created_at)}
                </td>
                <td className="px-4 py-3 text-zinc-300 text-xs">
                  {s.strategy}
                </td>
                <td
                  className="px-4 py-3 font-mono text-xs text-zinc-300 max-w-[140px] truncate"
                  title={s.market_question || s.market_id}
                >
                  {s.market_question
                    ? s.market_question.slice(0, 40) +
                      (s.market_question.length > 40 ? "…" : "")
                    : shortAddr(s.market_id)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-xs font-bold",
                      s.side === "YES"
                        ? "bg-green-900/40 text-green-400"
                        : "bg-red-900/40 text-red-400"
                    )}
                  >
                    {s.side}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-semibold text-xs">
                  <span
                    className={cn(
                      s.confidence >= 0.7
                        ? "text-green-400"
                        : s.confidence >= 0.5
                        ? "text-yellow-400"
                        : "text-zinc-400"
                    )}
                  >
                    {fmtPct(s.confidence)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-xs text-zinc-300">
                  {s.entry_price.toFixed(4)}
                </td>
                <td className="px-4 py-3 text-right text-xs text-zinc-400">
                  {fmtPct(s.size_pct)}
                </td>
                <td className="px-4 py-3 text-right text-xs text-zinc-400">
                  {fmtMinutes(s.max_holding_minutes)}
                </td>
                <td
                  className="px-4 py-3 font-mono text-xs text-zinc-400"
                  title={s.source_wallet}
                >
                  {shortAddr(s.source_wallet)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-xs font-medium",
                      s.status === "executed"
                        ? "bg-blue-900/40 text-blue-400"
                        : s.status === "approved"
                        ? "bg-green-900/40 text-green-400"
                        : "bg-red-900/40 text-red-400"
                    )}
                  >
                    {statusMap[s.status as keyof typeof statusMap] ?? s.status}
                  </span>
                </td>
                <td
                  className="px-4 py-3 text-xs text-zinc-500 max-w-[200px] truncate"
                  title={s.reject_reason || s.reason}
                >
                  {s.reject_reason || s.reason || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
