"use client";

import { useEffect, useMemo, useState } from "react";
import InfoTip from "@/components/InfoTip";
import { PaginationControls, SortHeader, type SortDirection } from "@/components/TableControls";
import CopyButton from "@/components/CopyButton";
import Modal, { DetailRow } from "@/components/Modal";
import { fetchPositions, type Position } from "@/lib/api";
import { cn, fmtMinutes, fmtTime, fmtUsd, shortAddr, polymarketEventUrl } from "@/lib/utils";

const POLL_INTERVAL = 15_000;

function SideBadge({ side }: { side: string }) {
  const isBuy = side === "YES" || side === "BUY";
  return (
    <span className={cn(
      "px-2 py-0.5 rounded text-xs font-bold",
      isBuy ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"
    )}>
      {side}
    </span>
  );
}

function PositionDetailModal({ position, onClose }: { position: Position; onClose: () => void }) {
  const pnl = position.realized_pnl_usd ?? null;
  return (
    <Modal open title={`Posição — ${position.strategy}`} onClose={onClose}>
      <div className="flex flex-col gap-0.5">
        <DetailRow label="ID da posição" value={position.position_id} mono />
        <DetailRow label="Sinal ID" value={position.signal_id} mono />
        <DetailRow label="Estratégia" value={position.strategy} />
        <DetailRow label="Mercado" value={
          <span className="flex items-center gap-1 font-mono">
            {position.market_slug
              ? <a href={polymarketEventUrl(position.market_slug)} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">{shortAddr(position.market_id)}</a>
              : shortAddr(position.market_id)
            }
            <CopyButton text={position.market_id} />
          </span>
        } />
        <DetailRow label="Market ID completo" value={<span className="flex items-center gap-1 break-all">{position.market_id}<CopyButton text={position.market_id} /></span>} mono />
        {position.market_category && (
          <DetailRow label="Categoria" value={<span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 text-xs">{position.market_category}</span>} />
        )}
        <DetailRow label="Lado" value={<SideBadge side={position.side} />} />
        <DetailRow label="Modo" value={position.execution_mode} />
        <DetailRow label="Preço de entrada" value={position.entry_price.toFixed(6)} mono />
        <DetailRow label="Tamanho" value={fmtUsd(position.size_usd)} />
        <DetailRow label="Take-profit" value={position.tp_price.toFixed(6)} mono />
        <DetailRow label="Stop-loss" value={position.sl_price.toFixed(6)} mono />
        <DetailRow label="Máx. holding" value={fmtMinutes(position.max_holding_minutes)} />
        <DetailRow label="Idade" value={fmtMinutes(position.age_minutes)} />
        {position.time_to_force_exit_minutes != null && (
          <DetailRow label="Saída forçada em" value={fmtMinutes(position.time_to_force_exit_minutes)} />
        )}
        <DetailRow label="Aberta em" value={fmtTime(position.opened_at)} />
        {position.closed_at && <DetailRow label="Fechada em" value={fmtTime(position.closed_at)} />}
        {position.exit_price != null && <DetailRow label="Preço de saída" value={position.exit_price.toFixed(6)} mono />}
        {pnl !== null && (
          <DetailRow
            label="P/L realizado"
            value={
              <span className={pnl >= 0 ? "text-green-400 font-semibold" : "text-red-400 font-semibold"}>
                {pnl >= 0 ? "+" : ""}{fmtUsd(pnl)}
              </span>
            }
          />
        )}
        {position.exit_reason && <DetailRow label="Motivo de saída" value={position.exit_reason} />}
      </div>
    </Modal>
  );
}

type OpenSortKey =
  | "market_id" | "strategy" | "side" | "entry_price" | "size_usd"
  | "tp_price" | "sl_price" | "age_minutes" | "time_to_force_exit_minutes" | "opened_at";

type ClosedSortKey =
  | "market_id" | "strategy" | "side" | "entry_price" | "exit_price"
  | "size_usd" | "realized_pnl_usd" | "exit_reason" | "closed_at";

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
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [selected, setSelected] = useState<Position | null>(null);

  const sorted = useMemo(() => {
    const next = [...positions].sort((a, b) => compareOpen(a, b, sortKey));
    return sortDir === "asc" ? next : next.reverse();
  }, [positions, sortDir, sortKey]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [page, pageSize, sorted]);

  function toggleSort(nextKey: OpenSortKey) {
    setPage(1);
    if (nextKey === sortKey) { setSortDir((p) => (p === "asc" ? "desc" : "asc")); return; }
    setSortKey(nextKey);
    setSortDir(nextKey === "market_id" || nextKey === "strategy" || nextKey === "side" ? "asc" : "desc");
  }

  return (
    <section>
      {selected && <PositionDetailModal position={selected} onClose={() => setSelected(null)} />}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-bold text-zinc-100">Posições abertas</h2>
        <span className="text-xs text-zinc-500">{positions.length} abertas</span>
      </div>
      <PaginationControls total={sorted.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={(n) => { setPageSize(n); setPage(1); }} />
      <div className="overflow-x-auto rounded-xl border border-zinc-800 mt-3">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-zinc-500 text-xs uppercase tracking-wide bg-zinc-900 border-b border-zinc-800">
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Mercado <InfoTip text="Mercado da posição." /></span>} active={sortKey === "market_id"} direction={sortDir} onClick={() => toggleSort("market_id")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Estratégia <InfoTip text="Estratégia que originou a posição." /></span>} active={sortKey === "strategy"} direction={sortDir} onClick={() => toggleSort("strategy")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Lado <InfoTip text="Direção (YES/BUY ou NO/SELL)." /></span>} active={sortKey === "side"} direction={sortDir} onClick={() => toggleSort("side")} /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Entrada <InfoTip text="Preço de entrada executado." /></span>} active={sortKey === "entry_price"} direction={sortDir} onClick={() => toggleSort("entry_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Tamanho <InfoTip text="Tamanho em USD." /></span>} active={sortKey === "size_usd"} direction={sortDir} onClick={() => toggleSort("size_usd")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">TP <InfoTip text="Take-profit." /></span>} active={sortKey === "tp_price"} direction={sortDir} onClick={() => toggleSort("tp_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">SL <InfoTip text="Stop-loss." /></span>} active={sortKey === "sl_price"} direction={sortDir} onClick={() => toggleSort("sl_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Idade <InfoTip text="Tempo desde abertura." /></span>} active={sortKey === "age_minutes"} direction={sortDir} onClick={() => toggleSort("age_minutes")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Saída em <InfoTip text="Tempo restante até timeout." /></span>} active={sortKey === "time_to_force_exit_minutes"} direction={sortDir} onClick={() => toggleSort("time_to_force_exit_minutes")} align="right" /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Aberta em <InfoTip text="Timestamp de abertura." /></span>} active={sortKey === "opened_at"} direction={sortDir} onClick={() => toggleSort("opened_at")} /></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 bg-zinc-950">
            {sorted.length === 0 && <tr><td colSpan={10} className="px-4 py-8 text-center text-zinc-500 italic">Nenhuma posição aberta</td></tr>}
            {paged.map((p) => {
              const urgentExit = p.time_to_force_exit_minutes != null && p.time_to_force_exit_minutes < 10;
              return (
                <tr
                  key={p.position_id}
                  className={cn("hover:bg-zinc-900/60 transition cursor-pointer", urgentExit && "bg-red-950/30")}
                  onClick={() => setSelected(p)}
                >
                  <td className="px-4 py-3 text-xs text-zinc-300 max-w-[120px]">
                    <div className="flex items-center gap-1">
                      <span className="font-mono truncate" title={p.market_id}>{shortAddr(p.market_id)}</span>
                      <CopyButton text={p.market_id} />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-zinc-400 text-xs">{p.strategy}</td>
                  <td className="px-4 py-3"><SideBadge side={p.side} /></td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300 text-xs">{p.entry_price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right text-zinc-300 text-xs">{fmtUsd(p.size_usd)}</td>
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
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [selected, setSelected] = useState<Position | null>(null);

  const sorted = useMemo(() => {
    const next = [...positions].sort((a, b) => compareClosed(a, b, sortKey));
    return sortDir === "asc" ? next : next.reverse();
  }, [positions, sortDir, sortKey]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [page, pageSize, sorted]);

  function toggleSort(nextKey: ClosedSortKey) {
    setPage(1);
    if (nextKey === sortKey) { setSortDir((p) => (p === "asc" ? "desc" : "asc")); return; }
    setSortKey(nextKey);
    setSortDir(nextKey === "market_id" || nextKey === "strategy" || nextKey === "side" || nextKey === "exit_reason" ? "asc" : "desc");
  }

  return (
    <section>
      {selected && <PositionDetailModal position={selected} onClose={() => setSelected(null)} />}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-bold text-zinc-100">Posições fechadas</h2>
        <span className="text-xs text-zinc-500">{positions.length} exibidas</span>
      </div>
      <PaginationControls total={sorted.length} page={page} pageSize={pageSize} onPageChange={setPage} onPageSizeChange={(n) => { setPageSize(n); setPage(1); }} />
      <div className="overflow-x-auto rounded-xl border border-zinc-800 mt-3">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-zinc-500 text-xs uppercase tracking-wide bg-zinc-900 border-b border-zinc-800">
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Mercado <InfoTip text="Mercado da posição." /></span>} active={sortKey === "market_id"} direction={sortDir} onClick={() => toggleSort("market_id")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Estratégia <InfoTip text="Estratégia que originou a posição." /></span>} active={sortKey === "strategy"} direction={sortDir} onClick={() => toggleSort("strategy")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Lado <InfoTip text="Direção (YES/BUY ou NO/SELL)." /></span>} active={sortKey === "side"} direction={sortDir} onClick={() => toggleSort("side")} /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Entrada <InfoTip text="Preço de entrada." /></span>} active={sortKey === "entry_price"} direction={sortDir} onClick={() => toggleSort("entry_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Saída <InfoTip text="Preço de saída." /></span>} active={sortKey === "exit_price"} direction={sortDir} onClick={() => toggleSort("exit_price")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">Tamanho <InfoTip text="Tamanho em USD." /></span>} active={sortKey === "size_usd"} direction={sortDir} onClick={() => toggleSort("size_usd")} align="right" /></th>
              <th className="px-4 py-3 text-right"><SortHeader label={<span className="inline-flex items-center gap-1">P/L <InfoTip text="Lucro/prejuízo realizado." /></span>} active={sortKey === "realized_pnl_usd"} direction={sortDir} onClick={() => toggleSort("realized_pnl_usd")} align="right" /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Motivo <InfoTip text="Motivo do fechamento." /></span>} active={sortKey === "exit_reason"} direction={sortDir} onClick={() => toggleSort("exit_reason")} /></th>
              <th className="px-4 py-3 text-left"><SortHeader label={<span className="inline-flex items-center gap-1">Fechada em <InfoTip text="Timestamp de fechamento." /></span>} active={sortKey === "closed_at"} direction={sortDir} onClick={() => toggleSort("closed_at")} /></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 bg-zinc-950">
            {sorted.length === 0 && <tr><td colSpan={9} className="px-4 py-8 text-center text-zinc-500 italic">Ainda não há posições fechadas</td></tr>}
            {paged.map((p) => {
              const pnl = p.realized_pnl_usd ?? 0;
              return (
                <tr
                  key={p.position_id}
                  className="hover:bg-zinc-900/60 transition cursor-pointer"
                  onClick={() => setSelected(p)}
                >
                  <td className="px-4 py-3 text-xs text-zinc-300 max-w-[120px]">
                    <div className="flex items-center gap-1">
                      <span className="font-mono truncate" title={p.market_id}>{shortAddr(p.market_id)}</span>
                      <CopyButton text={p.market_id} />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-zinc-400 text-xs">{p.strategy}</td>
                  <td className="px-4 py-3"><SideBadge side={p.side} /></td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300 text-xs">{p.entry_price.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300 text-xs">{p.exit_price != null ? p.exit_price.toFixed(4) : "—"}</td>
                  <td className="px-4 py-3 text-right text-zinc-300 text-xs">{fmtUsd(p.size_usd)}</td>
                  <td className={cn("px-4 py-3 text-right font-semibold text-xs", pnl >= 0 ? "text-green-400" : "text-red-400")}>{pnl >= 0 ? "+" : ""}{fmtUsd(pnl)}</td>
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

export default function PortfolioPageClient() {
  const [open, setOpen] = useState<Position[]>([]);
  const [closed, setClosed] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  async function load() {
    try {
      const [o, c] = await Promise.all([
        fetchPositions("open", 500),
        fetchPositions("closed", 500),
      ]);
      setOpen(o);
      setClosed(c);
      setLastUpdate(new Date());
    } catch {}
    setLoading(false);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-zinc-100">Portfólio</h1>
        <div className="text-xs text-zinc-600 flex items-center gap-2">
          {lastUpdate && (
            <span>atualizado {lastUpdate.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
          )}
          {loading && <span className="italic">atualizando…</span>}
        </div>
      </div>
      <OpenPositionsTable positions={open} />
      <ClosedPositionsTable positions={closed} />
    </div>
  );
}
