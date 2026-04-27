"use client";

import { useEffect, useState } from "react";
import { fetchPositions } from "@/lib/api";
import { subscribeToLiveFeed, type LiveEvent } from "@/lib/ws";
import CopyButton from "@/components/CopyButton";
import Modal, { DetailRow } from "@/components/Modal";
import { cn, fmtMinutes, fmtTime, fmtUsd, shortAddr } from "@/lib/utils";

function positionToEvent(position: {
  position_id: string;
  strategy: string;
  market_id: string;
  market_category?: string | null;
  side: string;
  entry_price: number;
  size_usd: number;
  tp_price: number;
  sl_price: number;
  max_holding_minutes: number;
  opened_at: string;
  closed_at: string | null;
  exit_price: number | null;
  realized_pnl_usd: number | null;
  exit_reason: string | null;
}): LiveEvent {
  return {
    event: position.closed_at ? "closed" : "opened",
    position_id: position.position_id,
    strategy: position.strategy,
    market_id: position.market_id,
    market_category: position.market_category,
    side: position.side,
    entry_price: String(position.entry_price),
    size_usd: String(position.size_usd),
    tp_price: String(position.tp_price),
    sl_price: String(position.sl_price),
    max_holding_minutes: position.max_holding_minutes,
    opened_at: position.opened_at,
    closed_at: position.closed_at,
    exit_price: position.exit_price != null ? String(position.exit_price) : null,
    realized_pnl_usd: position.realized_pnl_usd != null ? String(position.realized_pnl_usd) : null,
    exit_reason: position.exit_reason,
  };
}

function EventDetailModal({ evt, onClose }: { evt: LiveEvent; onClose: () => void }) {
  const pnl = evt.realized_pnl_usd != null ? parseFloat(evt.realized_pnl_usd) : null;
  const isBuy = evt.side === "YES" || evt.side === "BUY";

  return (
    <Modal open title={`${evt.event === "opened" ? "Posição Aberta" : "Posição Fechada"} — ${evt.strategy}`} onClose={onClose}>
      <div className="flex flex-col gap-0.5">
        <DetailRow label="ID da posição" value={evt.position_id} mono />
        <DetailRow label="Estratégia" value={evt.strategy} />
        <DetailRow label="Mercado" value={
          <span className="flex items-center gap-1">
            {shortAddr(evt.market_id)}
            <CopyButton text={evt.market_id} />
          </span>
        } mono />
        {evt.market_category && (
          <DetailRow label="Categoria" value={<span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 text-xs">{evt.market_category}</span>} />
        )}
        <DetailRow label="Market ID completo" value={
          <span className="flex items-center gap-1 break-all">
            {evt.market_id}
            <CopyButton text={evt.market_id} />
          </span>
        } mono />
        <DetailRow label="Lado" value={
          <span className={cn("px-2 py-0.5 rounded text-xs font-bold", isBuy ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400")}>
            {evt.side}
          </span>
        } />
        <DetailRow label="Preço de entrada" value={parseFloat(evt.entry_price).toFixed(6)} mono />
        <DetailRow label="Tamanho" value={fmtUsd(parseFloat(evt.size_usd))} />
        <DetailRow label="Take-profit" value={parseFloat(evt.tp_price).toFixed(6)} mono />
        <DetailRow label="Stop-loss" value={parseFloat(evt.sl_price).toFixed(6)} mono />
        <DetailRow label="Máx. holding" value={fmtMinutes(evt.max_holding_minutes)} />
        <DetailRow label="Aberta em" value={fmtTime(evt.opened_at)} />
        {evt.closed_at && <DetailRow label="Fechada em" value={fmtTime(evt.closed_at)} />}
        {evt.exit_price && <DetailRow label="Preço de saída" value={parseFloat(evt.exit_price).toFixed(6)} mono />}
        {pnl !== null && (
          <DetailRow
            label="P/L realizado"
            value={
              <span className={cn("font-semibold", pnl >= 0 ? "text-green-400" : "text-red-400")}>
                {pnl >= 0 ? "+" : ""}{fmtUsd(pnl)}
              </span>
            }
          />
        )}
        {evt.exit_reason && <DetailRow label="Motivo de saída" value={evt.exit_reason} />}
      </div>
    </Modal>
  );
}

export default function SignalFeed() {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [status, setStatus] = useState("Conectando ao feed ao vivo…");
  const [selected, setSelected] = useState<LiveEvent | null>(null);

  useEffect(() => {
    let alive = true;

    fetchPositions("all", 20)
      .then((positions) => {
        if (!alive || positions.length === 0) return;
        setEvents((prev) => (prev.length > 0 ? prev : positions.map(positionToEvent)));
        setStatus("Exibindo posições recentes enquanto aguarda novos eventos.");
      })
      .catch(() => {});

    const cleanup = subscribeToLiveFeed(
      (evt) => {
        setStatus("Recebendo eventos ao vivo.");
        setEvents((prev) => {
          const next = [evt, ...prev.filter((item) => !(item.position_id === evt.position_id && item.event === evt.event))];
          return next.slice(0, 50);
        });
      },
      () => {
        setStatus("Conexão ao vivo indisponível. Exibindo histórico recente.");
      }
    );

    return () => {
      alive = false;
      cleanup();
    };
  }, []);

  if (events.length === 0) {
    return <div className="text-zinc-500 text-sm italic p-4">{status}</div>;
  }

  return (
    <div className="flex flex-col gap-2">
      {selected && <EventDetailModal evt={selected} onClose={() => setSelected(null)} />}

      <p className="text-[11px] text-zinc-500">{status} — clique em uma linha para ver detalhes</p>
      <div className="flex flex-col gap-1 overflow-y-auto max-h-80">
        {events.map((e) => {
          const label = e.event === "opened" ? "ABERTO" : "FECHADO";
          const isBuy = e.side === "YES" || e.side === "BUY";
          return (
            <div
              key={`${e.position_id}-${e.event}`}
              onClick={() => setSelected(e)}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded text-xs font-mono cursor-pointer transition-opacity hover:opacity-80",
                e.event === "opened"
                  ? "bg-blue-950/50 border border-blue-900"
                  : "bg-zinc-900 border border-zinc-800"
              )}
            >
              <span className={cn(
                "w-14 text-center rounded px-1 py-0.5 font-semibold shrink-0",
                e.event === "opened" ? "bg-blue-600/40 text-blue-300" : "bg-zinc-700 text-zinc-300"
              )}>
                {label}
              </span>
              <span className="text-zinc-400 shrink-0">{e.strategy}</span>
              <span className={cn("font-bold shrink-0", isBuy ? "text-green-400" : "text-red-400")}>
                {e.side}
              </span>
              <span className="text-zinc-300 flex-1 truncate" title={e.market_id}>
                {shortAddr(e.market_id)}
              </span>
              {e.event === "closed" && e.realized_pnl_usd && (
                <span className={cn("font-semibold shrink-0", parseFloat(e.realized_pnl_usd) >= 0 ? "text-green-400" : "text-red-400")}>
                  {parseFloat(e.realized_pnl_usd) >= 0 ? "+" : ""}
                  {fmtUsd(parseFloat(e.realized_pnl_usd))}
                </span>
              )}
              {e.event === "closed" && e.exit_reason && (
                <span className="text-zinc-500 shrink-0">[{e.exit_reason}]</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
