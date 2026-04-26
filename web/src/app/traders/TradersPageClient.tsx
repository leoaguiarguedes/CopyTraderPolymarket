"use client";

import { useMemo, useState } from "react";
import InfoTip from "@/components/InfoTip";
import { PaginationControls, SortHeader, type SortDirection } from "@/components/TableControls";
import type { WalletScore } from "@/lib/api";
import { cn, fmtMinutes, fmtPct, fmtUsd, shortAddr } from "@/lib/utils";

type SortKey =
  | "address"
  | "n_trades"
  | "sharpe"
  | "roi"
  | "win_rate"
  | "max_drawdown"
  | "median_holding_minutes"
  | "total_volume_usd"
  | "is_active";

function compareValues(a: WalletScore, b: WalletScore, key: SortKey) {
  if (key === "address") return a.address.localeCompare(b.address);
  if (key === "is_active") return Number(Boolean(a.is_active)) - Number(Boolean(b.is_active));
  return Number(a[key] ?? 0) - Number(b[key] ?? 0);
}

export default function TradersPageClient({ initialWallets }: { initialWallets: WalletScore[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("sharpe");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const sortedWallets = useMemo(() => {
    const next = [...initialWallets].sort((a, b) => compareValues(a, b, sortKey));
    return sortDirection === "asc" ? next : next.reverse();
  }, [initialWallets, sortDirection, sortKey]);

  const pagedWallets = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sortedWallets.slice(start, start + pageSize);
  }, [page, pageSize, sortedWallets]);

  function toggleSort(nextKey: SortKey) {
    setPage(1);
    if (nextKey === sortKey) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "address" ? "asc" : "desc");
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-zinc-100">Traders rastreados</h1>
        <span className="text-xs text-zinc-500">{initialWallets.length} carteiras</span>
      </div>

      <PaginationControls
        total={sortedWallets.length}
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
              <th className="px-4 py-3 text-left">
                <span className="inline-flex items-center gap-1">
                  # <InfoTip text="Posição no ranking atual da ordenação/paginação." />
                </span>
              </th>
              <th className="px-4 py-3 text-left">
                <SortHeader
                  label={<span className="inline-flex items-center gap-1">Carteira <InfoTip text="Endereço da carteira rastreada (encurtado)." /></span>}
                  active={sortKey === "address"}
                  direction={sortDirection}
                  onClick={() => toggleSort("address")}
                />
              </th>
              <th className="px-4 py-3 text-right">
                <SortHeader
                  label={<span className="inline-flex items-center gap-1">Negócios <InfoTip text="Número de trades usados no score mais recente." /></span>}
                  active={sortKey === "n_trades"}
                  direction={sortDirection}
                  onClick={() => toggleSort("n_trades")}
                  align="right"
                />
              </th>
              <th className="px-4 py-3 text-right">
                <SortHeader
                  label={<span className="inline-flex items-center gap-1">Sharpe <InfoTip text="Sharpe do período do score." /></span>}
                  active={sortKey === "sharpe"}
                  direction={sortDirection}
                  onClick={() => toggleSort("sharpe")}
                  align="right"
                />
              </th>
              <th className="px-4 py-3 text-right">
                <SortHeader
                  label={<span className="inline-flex items-center gap-1">ROI <InfoTip text="Retorno sobre capital no período do score." /></span>}
                  active={sortKey === "roi"}
                  direction={sortDirection}
                  onClick={() => toggleSort("roi")}
                  align="right"
                />
              </th>
              <th className="px-4 py-3 text-right">
                <SortHeader
                  label={<span className="inline-flex items-center gap-1">Taxa de acerto <InfoTip text="Percentual de trades vencedores." /></span>}
                  active={sortKey === "win_rate"}
                  direction={sortDirection}
                  onClick={() => toggleSort("win_rate")}
                  align="right"
                />
              </th>
              <th className="px-4 py-3 text-right">
                <SortHeader
                  label={<span className="inline-flex items-center gap-1">Máx. DD <InfoTip text="Máximo drawdown observado." /></span>}
                  active={sortKey === "max_drawdown"}
                  direction={sortDirection}
                  onClick={() => toggleSort("max_drawdown")}
                  align="right"
                />
              </th>
              <th className="px-4 py-3 text-right">
                <SortHeader
                  label={<span className="inline-flex items-center gap-1">Tempo médio <InfoTip text="Tempo mediano/médio de holding." /></span>}
                  active={sortKey === "median_holding_minutes"}
                  direction={sortDirection}
                  onClick={() => toggleSort("median_holding_minutes")}
                  align="right"
                />
              </th>
              <th className="px-4 py-3 text-right">
                <SortHeader
                  label={<span className="inline-flex items-center gap-1">Volume <InfoTip text="Volume total em USD." /></span>}
                  active={sortKey === "total_volume_usd"}
                  direction={sortDirection}
                  onClick={() => toggleSort("total_volume_usd")}
                  align="right"
                />
              </th>
              <th className="px-4 py-3 text-right">
                <SortHeader
                  label={<span className="inline-flex items-center gap-1">Status <InfoTip text="Se a carteira está ativa no recorte." /></span>}
                  active={sortKey === "is_active"}
                  direction={sortDirection}
                  onClick={() => toggleSort("is_active")}
                  align="right"
                />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 bg-zinc-950">
            {sortedWallets.length === 0 && (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-zinc-500 italic">
                  Nenhuma carteira rastreada ainda. Execute <code className="text-zinc-400">python scripts/discover_wallets.py</code> primeiro.
                </td>
              </tr>
            )}
            {pagedWallets.map((w, index) => (
              <tr key={w.address} className="hover:bg-zinc-900/60 transition">
                <td className="px-4 py-3 text-zinc-500">{(page - 1) * pageSize + index + 1}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  <span className="text-zinc-200" title={w.address}>{shortAddr(w.address)}</span>
                </td>
                <td className="px-4 py-3 text-right text-zinc-300">{w.n_trades ?? "—"}</td>
                <td className={cn("px-4 py-3 text-right font-semibold", (w.sharpe ?? 0) >= 0.5 ? "text-green-400" : "text-zinc-400")}>
                  {w.sharpe != null ? w.sharpe.toFixed(2) : "—"}
                </td>
                <td className={cn("px-4 py-3 text-right font-semibold", (w.roi ?? 0) >= 0 ? "text-green-400" : "text-red-400")}>
                  {w.roi != null ? fmtPct(w.roi) : "—"}
                </td>
                <td className="px-4 py-3 text-right text-zinc-300">{w.win_rate != null ? fmtPct(w.win_rate) : "—"}</td>
                <td className={cn("px-4 py-3 text-right", (w.max_drawdown ?? 0) > 0.3 ? "text-red-400" : "text-zinc-300")}>
                  {w.max_drawdown != null ? fmtPct(w.max_drawdown) : "—"}
                </td>
                <td className="px-4 py-3 text-right text-zinc-300">{w.median_holding_minutes != null ? fmtMinutes(w.median_holding_minutes) : "—"}</td>
                <td className="px-4 py-3 text-right text-zinc-300">{w.total_volume_usd != null ? fmtUsd(w.total_volume_usd) : "—"}</td>
                <td className="px-4 py-3 text-right">
                  <span className={cn("px-2 py-0.5 rounded text-xs font-medium", w.is_active ? "bg-green-900/40 text-green-400" : "bg-zinc-800 text-zinc-500")}>
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
