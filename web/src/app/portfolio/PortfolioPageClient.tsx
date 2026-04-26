"use client";

import { useMemo, useState } from "react";
import InfoTip from "@/components/InfoTip";
import { PaginationControls, SortHeader, type SortDirection } from "@/components/TableControls";
import type { Position } from "@/lib/api";
import { cn, fmtMinutes, fmtTime, fmtUsd, shortAddr } from "@/lib/utils";

type OpenSortKey =
  | "market_id"
  | "strategy"
  | "side"
  | "entry_price"
  | "size_usd"
  | "tp_price"
  | "sl_price"
  | "age_minutes"
  | "time_to_force_exit_minutes"
  | "opened_at";

type ClosedSortKey =
  | "market_id"
  | "strategy"
  | "side"
  | "entry_price"
  | "exit_price"
  | "size_usd"
  | "realized_pnl_usd"
  | "exit_reason"
  | "closed_at";

function compareOpen(a: Position, b: Position, key: OpenSortKey) {
  if (key === "market_id" || key === "strategy" || key === "side") return String(a[key]).localeCompare(String(b[key]));
  if (key === "opened_at") return new Date(a.opened_at).getTime() - new Date(b.opened_at).getTime();
  return Number(a[key] ?? 0) - Number(b[key] ?? 0);
}

function compareClosed(a: Position, b: Position, key: ClosedSortKey) {
  if (key === "market_id" || key === "strategy" || key === "side" || key === "exit_reason") return String(a[key] ?? "").localeCompare(String(b[key] ?? ""));
  if (key === "closed_at") return new Date(a.closed_at ?? 0).getTime() - new Date(b.closed_at ?? 0).getTime();
  return Number(a[key] ?? 0) - Number(b[key] ?? 0);
}

function OpenPositionsTable({ positions }: { positions: Position[] }) {
  const [sortKey, setSortKey] = useState<OpenSortKey>("opened_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const sorted = useMemo(() => {
    const next = [...positions].sort((a, b) => compareOpen(a, b, sortKey));
    return sortDirection === "asc" ? next : next.reverse();
  }, [positions, sortDirection, sortKey]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [page, pageSize, sorted]);

  function toggleSort(nextKey: OpenSortKey) {
    setPage(1);
    if (nextKey === sortKey) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "market_id" || nextKey === "strategy" || nextKey === "side" ? "asc" : "desc");
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-lg font-bold text-zinc-100">Posições abertas</h1>
        <span className="text-xs text-zinc-500">{positions.length} abertas</span>
      </div>
      <PaginationControls total={sorted.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={(next) => { setPageSize(next); setPage(1); }} />
      <div className="overflow-x-auto rounded-xl border border-zinc-800 mt-3">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-zinc-500 text-xs uppercase tracking-wide bg-zinc-900 border-b border-zinc-800">
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Mercado <InfoTip text="Mercado da posição." /></span>} active={sortKey === "market_id"} direction={sortDirection} onClick={() => toggleSort("market_id")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Estratégia <InfoTip text="Estratégia que originou a posição." /></span>} active={sortKey === "strategy"} direction={sortDirection} onClick={() => toggleSort("strategy")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Lado <InfoTip text="YES/NO da posição." /></span>} active={sortKey === "side"} direction={sortDirection} onClick={() => toggleSort("side")} /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Entrada <InfoTip text="Preço de entrada executado." /></span>} active={sortKey === "entry_price"} direction={sortDirection} onClick={() => toggleSort("entry_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Tamanho <InfoTip text="Tamanho em USD." /></span>} active={sortKey === "size_usd"} direction={sortDirection} onClick={() => toggleSort("size_usd")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">TP <InfoTip text="Take-profit." /></span>} active={sortKey === "tp_price"} direction={sortDirection} onClick={() => toggleSort("tp_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">SL <InfoTip text="Stop-loss." /></span>} active={sortKey === "sl_price"} direction={sortDirection} onClick={() => toggleSort("sl_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Idade <InfoTip text="Tempo desde abertura." /></span>} active={sortKey === "age_minutes"} direction={sortDirection} onClick={() => toggleSort("age_minutes")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Saída em <InfoTip text="Tempo restante até timeout." /></span>} active={sortKey === "time_to_force_exit_minutes"} direction={sortDirection} onClick={() => toggleSort("time_to_force_exit_minutes")} align="right" /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Aberta em <InfoTip text="Timestamp de abertura." /></span>} active={sortKey === "opened_at"} direction={sortDirection} onClick={() => toggleSort("opened_at")} /></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 bg-zinc-950">
            {sorted.length === 0 && (
              <tr><td colSpan={10} className="px-4 py-8 text-center text-zinc-500 italic">Nenhuma posição aberta</td></tr>
            )}
            {paged.map((p) => {
              const urgentExit = p.time_to_force_exit_minutes != null && p.time_to_force_exit_minutes < 10;
              return (
                <tr key={p.position_id} className={cn("hover:bg-zinc-900/60 transition", urgentExit && "bg-red-950/30")}>
                  <td className="px-4 py-3 font-mono text-xs text-zinc-300 max-w-[120px] truncate" title={p.market_id}>{shortAddr(p.market_id)}</td>
                  <td className="px-4 py-3 text-zinc-400 text-xs">{p.strategy}</td>
                  <td className="px-4 py-3"><span className={cn("px-2 py-0.5 rounded text-xs font-bold", p.side === "YES" ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400")}>{p.side}</span></td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300">{p.entry_price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{fmtUsd(p.size_usd)}</td>
                  <td className="px-4 py-3 text-right text-green-600 font-mono text-xs">{p.tp_price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right text-red-600 font-mono text-xs">{p.sl_price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right text-zinc-400 text-xs">{fmtMinutes(p.age_minutes)}</td>
                  <td className={cn("px-4 py-3 text-right text-xs font-semibold", urgentExit ? "text-red-400 animate-pulse" : "text-zinc-400")}>
                    {p.time_to_force_exit_minutes != null ? fmtMinutes(p.time_to_force_exit_minutes) : "—"}
                  </td>
                  <td className="px-4 py-3 text-zinc-500 text-xs">{p.opened_at ? fmtTime(p.opened_at) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ClosedPositionsTable({ positions }: { positions: Position[] }) {
  const [sortKey, setSortKey] = useState<ClosedSortKey>("closed_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const sorted = useMemo(() => {
    const next = [...positions].sort((a, b) => compareClosed(a, b, sortKey));
    return sortDirection === "asc" ? next : next.reverse();
  }, [positions, sortDirection, sortKey]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [page, pageSize, sorted]);

  function toggleSort(nextKey: ClosedSortKey) {
    setPage(1);
    if (nextKey === sortKey) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "market_id" || nextKey === "strategy" || nextKey === "side" || nextKey === "exit_reason" ? "asc" : "desc");
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-lg font-bold text-zinc-100">Posições fechadas</h1>
        <span className="text-xs text-zinc-500">{positions.length} exibidas</span>
      </div>
      <PaginationControls total={sorted.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={(next) => { setPageSize(next); setPage(1); }} />
      <div className="overflow-x-auto rounded-xl border border-zinc-800 mt-3">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-zinc-500 text-xs uppercase tracking-wide bg-zinc-900 border-b border-zinc-800">
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Mercado <InfoTip text="Mercado da posição." /></span>} active={sortKey === "market_id"} direction={sortDirection} onClick={() => toggleSort("market_id")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Estratégia <InfoTip text="Estratégia que originou a posição." /></span>} active={sortKey === "strategy"} direction={sortDirection} onClick={() => toggleSort("strategy")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Lado <InfoTip text="YES/NO da posição." /></span>} active={sortKey === "side"} direction={sortDirection} onClick={() => toggleSort("side")} /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Entrada <InfoTip text="Preço de entrada." /></span>} active={sortKey === "entry_price"} direction={sortDirection} onClick={() => toggleSort("entry_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Saída <InfoTip text="Preço de saída." /></span>} active={sortKey === "exit_price"} direction={sortDirection} onClick={() => toggleSort("exit_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Tamanho <InfoTip text="Tamanho em USD." /></span>} active={sortKey === "size_usd"} direction={sortDirection} onClick={() => toggleSort("size_usd")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">P/L <InfoTip text="Lucro/prejuízo realizado." /></span>} active={sortKey === "realized_pnl_usd"} direction={sortDirection} onClick={() => toggleSort("realized_pnl_usd")} align="right" /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Motivo <InfoTip text="Motivo do fechamento." /></span>} active={sortKey === "exit_reason"} direction={sortDirection} onClick={() => toggleSort("exit_reason")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Fechada em <InfoTip text="Timestamp de fechamento." /></span>} active={sortKey === "closed_at"} direction={sortDirection} onClick={() => toggleSort("closed_at")} /></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 bg-zinc-950">
            {sorted.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-zinc-500 italic">Ainda não há posições fechadas</td></tr>
            )}
            {paged.map((p) => {
              const pnl = p.realized_pnl_usd ?? 0;
              return (
                <tr key={p.position_id} className="hover:bg-zinc-900/60 transition">
                  <td className="px-4 py-3 font-mono text-xs text-zinc-300 max-w-[120px] truncate" title={p.market_id}>{shortAddr(p.market_id)}</td>
                  <td className="px-4 py-3 text-zinc-400 text-xs">{p.strategy}</td>
                  <td className="px-4 py-3"><span className={cn("px-2 py-0.5 rounded text-xs font-bold", p.side === "YES" ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400")}>{p.side}</span></td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300 text-xs">{p.entry_price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300 text-xs">{p.exit_price != null ? p.exit_price.toFixed(4) : "—"}</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{fmtUsd(p.size_usd)}</td>
                  <td className={cn("px-4 py-3 text-right font-semibold", pnl >= 0 ? "text-green-400" : "text-red-400")}>{pnl >= 0 ? "+" : ""}{fmtUsd(pnl)}</td>
                  <td className="px-4 py-3 text-xs">
                    <span className={cn("px-2 py-0.5 rounded", p.exit_reason === "tp" ? "bg-green-900/40 text-green-400" : p.exit_reason === "sl" ? "bg-red-900/40 text-red-400" : p.exit_reason === "timeout" ? "bg-yellow-900/40 text-yellow-400" : "bg-zinc-800 text-zinc-400")}>
                      {p.exit_reason ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-500 text-xs">{p.closed_at ? fmtTime(p.closed_at) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function PortfolioPageClient({
  openPositions,
  closedPositions,
}: {
  openPositions: Position[];
  closedPositions: Position[];
}) {
  return (
    <div className="flex flex-col gap-6">
      <OpenPositionsTable positions={openPositions} />
      <ClosedPositionsTable positions={closedPositions} />
    </div>
  );
}
