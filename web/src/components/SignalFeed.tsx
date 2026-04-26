"use client";

import { useEffect, useState } from "react";
import { fetchPositions } from "@/lib/api";
import { subscribeToLiveFeed, type LiveEvent } from "@/lib/ws";
import { cn, fmtUsd, shortAddr } from "@/lib/utils";

function positionToEvent(position: {
  position_id: string;
  strategy: string;
  market_id: string;
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

export default function SignalFeed() {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [status, setStatus] = useState("Conectando ao feed ao vivo…");

  useEffect(() => {
    let alive = true;

    fetchPositions("all", 20)
      .then((positions) => {
        if (!alive || positions.length === 0) return;
        setEvents((prev) => (prev.length > 0 ? prev : positions.map(positionToEvent)));
        setStatus("Exibindo posições recentes enquanto aguarda novos eventos.");
      })
      .catch(() => {
        // ignore fallback errors
      });

    const cleanup = subscribeToLiveFeed(
      (evt) => {
        setStatus("Recebendo eventos ao vivo.");
        setEvents((prev) => {
          const next = [evt, ...prev.filter((item) => !(item.position_id === evt.position_id && item.event === evt.event))];
          return next.slice(0, 50);
        });
      },
      () => {
        setStatus("Conexão ao vivo indisponível no momento. Exibindo histórico recente quando houver.");
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
      <p className="text-[11px] text-zinc-500">{status}</p>
      <div className="flex flex-col gap-1 overflow-y-auto max-h-80">
        {events.map((e) => {
          const label = e.event === "opened" ? "ABERTO" : "FECHADO";
          return (
            <div
              key={`${e.position_id}-${e.event}`}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded text-xs font-mono",
                e.event === "opened" ? "bg-blue-950/50 border border-blue-900" : "bg-zinc-900 border border-zinc-800"
              )}
            >
              <span
                className={cn(
                  "w-14 text-center rounded px-1 py-0.5 font-semibold",
                  e.event === "opened" ? "bg-blue-600/40 text-blue-300" : "bg-zinc-700 text-zinc-300"
                )}
              >
                {label}
              </span>
              <span className="text-zinc-400">{e.strategy}</span>
              <span className={cn("font-bold", e.side === "YES" ? "text-green-400" : "text-red-400")}>
                {e.side}
              </span>
              <span className="text-zinc-300 flex-1 truncate" title={e.market_id}>
                {shortAddr(e.market_id)}
              </span>
              {e.event === "closed" && e.realized_pnl_usd && (
                <span
                  className={cn(
                    "font-semibold",
                    parseFloat(e.realized_pnl_usd) >= 0 ? "text-green-400" : "text-red-400"
                  )}
                >
                  {parseFloat(e.realized_pnl_usd) >= 0 ? "+" : ""}
                  {fmtUsd(parseFloat(e.realized_pnl_usd))}
                </span>
              )}
              {e.event === "closed" && e.exit_reason && (
                <span className="text-zinc-500">[{e.exit_reason}]</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
