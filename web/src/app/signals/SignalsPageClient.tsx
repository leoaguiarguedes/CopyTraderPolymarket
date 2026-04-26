"use client";

import { useMemo, useState } from "react";
import InfoTip from "@/components/InfoTip";
import { PaginationControls, SortHeader, type SortDirection } from "@/components/TableControls";
import type { Signal } from "@/lib/api";
import { cn, fmtMinutes, fmtPct, fmtTime, shortAddr } from "@/lib/utils";

type SortKey =
  | "created_at"
  | "strategy"
  | "market_question"
  | "side"
  | "confidence"
  | "entry_price"
  | "size_pct"
  | "max_holding_minutes"
  | "source_wallet"
  | "status";

function compareValues(a: Signal, b: Signal, key: SortKey) {
  if (key === "created_at") return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  if (key === "confidence" || key === "entry_price" || key === "size_pct" || key === "max_holding_minutes") {
    return Number(a[key]) - Number(b[key]);
  }
  return String(a[key] ?? "").localeCompare(String(b[key] ?? ""));
}

export default function SignalsPageClient({ initialSignals }: { initialSignals: Signal[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const approved = initialSignals.filter((s) => s.status === "approved" || s.status === "executed");
  const rejected = initialSignals.filter((s) => s.status === "rejected");

  const sortedSignals = useMemo(() => {
    const next = [...initialSignals].sort((a, b) => compareValues(a, b, sortKey));
    return sortDirection === "asc" ? next : next.reverse();
  }, [initialSignals, sortDirection, sortKey]);

  const pagedSignals = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sortedSignals.slice(start, start + pageSize);
  }, [page, pageSize, sortedSignals]);

  function toggleSort(nextKey: SortKey) {
    setPage(1);
    if (nextKey === sortKey) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "strategy" || nextKey === "market_question" || nextKey === "source_wallet" || nextKey === "status" || nextKey === "side" ? "asc" : "desc");
  }

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
          <span className="text-green-400 font-semibold">{approved.length} aprovados</span>
          <span className="text-red-400 font-semibold">{rejected.length} rejeitados</span>
        </div>
      </div>

      <PaginationControls
        total={sortedSignals.length}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(next) => {
          setPageSize(next);
          setPage(1);
        }}
      />

      <div className="overflow-x-auto rounded-xl border border-zinc-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-zinc-500 text-xs uppercase tracking-wide bg-zinc-900 border-b border-zinc-800">
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Hora <InfoTip text="Timestamp de criação do sinal." /></span>} active={sortKey === "created_at"} direction={sortDirection} onClick={() => toggleSort("created_at")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Estratégia <InfoTip text="Nome da estratégia." /></span>} active={sortKey === "strategy"} direction={sortDirection} onClick={() => toggleSort("strategy")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Mercado <InfoTip text="Mercado/questão alvo do sinal." /></span>} active={sortKey === "market_question"} direction={sortDirection} onClick={() => toggleSort("market_question")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Lado <InfoTip text="YES/NO sugerido." /></span>} active={sortKey === "side"} direction={sortDirection} onClick={() => toggleSort("side")} /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Conf <InfoTip text="Confiança do sinal." /></span>} active={sortKey === "confidence"} direction={sortDirection} onClick={() => toggleSort("confidence")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Entrada <InfoTip text="Preço de entrada sugerido." /></span>} active={sortKey === "entry_price"} direction={sortDirection} onClick={() => toggleSort("entry_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Tamanho% <InfoTip text="Percentual do capital sugerido." /></span>} active={sortKey === "size_pct"} direction={sortDirection} onClick={() => toggleSort("size_pct")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Máx. espera <InfoTip text="Holding máximo antes de forçar saída." /></span>} active={sortKey === "max_holding_minutes"} direction={sortDirection} onClick={() => toggleSort("max_holding_minutes")} align="right" /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Origem <InfoTip text="Carteira que originou o sinal." /></span>} active={sortKey === "source_wallet"} direction={sortDirection} onClick={() => toggleSort("source_wallet")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Status <InfoTip text="Estado do sinal." /></span>} active={sortKey === "status"} direction={sortDirection} onClick={() => toggleSort("status")} /></th>
              <th className="px-4 py-3 text-left"><span className="inline-flex items-center gap-1">Decisão <InfoTip text="Motivo/decisão do risk manager." /></span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 bg-zinc-950">
            {sortedSignals.length === 0 && (
              <tr>
                <td colSpan={11} className="px-4 py-8 text-center text-zinc-500 italic">
                  Ainda não há sinais — execute o worker de sinais para ver dados aqui.
                </td>
              </tr>
            )}
            {pagedSignals.map((s) => (
              <tr key={s.signal_id} className={cn("hover:bg-zinc-900/60 transition", s.status === "rejected" && "opacity-60")}>
                <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap">{fmtTime(s.created_at)}</td>
                <td className="px-4 py-3 text-zinc-300 text-xs">{s.strategy}</td>
                <td className="px-4 py-3 font-mono text-xs text-zinc-300 max-w-[140px] truncate" title={s.market_question || s.market_id}>
                  {s.market_question ? s.market_question.slice(0, 40) + (s.market_question.length > 40 ? "…" : "") : shortAddr(s.market_id)}
                </td>
                <td className="px-4 py-3">
                  <span className={cn("px-2 py-0.5 rounded text-xs font-bold", s.side === "YES" ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400")}>{s.side}</span>
                </td>
                <td className="px-4 py-3 text-right font-semibold text-xs">
                  <span className={cn(s.confidence >= 0.7 ? "text-green-400" : s.confidence >= 0.5 ? "text-yellow-400" : "text-zinc-400")}>{fmtPct(s.confidence)}</span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-xs text-zinc-300">{s.entry_price.toFixed(4)}</td>
                <td className="px-4 py-3 text-right text-xs text-zinc-400">{fmtPct(s.size_pct)}</td>
                <td className="px-4 py-3 text-right text-xs text-zinc-400">{fmtMinutes(s.max_holding_minutes)}</td>
                <td className="px-4 py-3 font-mono text-xs text-zinc-400" title={s.source_wallet}>{shortAddr(s.source_wallet)}</td>
                <td className="px-4 py-3">
                  <span className={cn("px-2 py-0.5 rounded text-xs font-medium", s.status === "executed" ? "bg-blue-900/40 text-blue-400" : s.status === "approved" ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400")}>
                    {statusMap[s.status as keyof typeof statusMap] ?? s.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-zinc-500 max-w-[200px] truncate" title={s.reject_reason || s.reason}>
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
