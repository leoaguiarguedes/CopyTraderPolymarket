"use client";
import { useEffect, useState } from "react";
import { subscribeToLiveFeed, type LiveEvent } from "@/lib/ws";
import { cn, fmtUsd, shortAddr } from "@/lib/utils";

export default function SignalFeed() {
  const [events, setEvents] = useState<LiveEvent[]>([]);

  useEffect(() => {
    const cleanup = subscribeToLiveFeed((evt) => {
      setEvents((prev) => [evt, ...prev].slice(0, 50));
    });
    return cleanup;
  }, []);

  if (events.length === 0) {
    return (
      <div className="text-zinc-500 text-sm italic p-4">
        Waiting for live events…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 overflow-y-auto max-h-80">
      {events.map((e) => (
        <div
          key={`${e.position_id}-${e.event}`}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded text-xs font-mono",
            e.event === "opened"
              ? "bg-blue-950/50 border border-blue-900"
              : "bg-zinc-900 border border-zinc-800"
          )}
        >
          <span
            className={cn(
              "w-14 text-center rounded px-1 py-0.5 font-semibold",
              e.event === "opened"
                ? "bg-blue-600/40 text-blue-300"
                : "bg-zinc-700 text-zinc-300"
            )}
          >
            {e.event.toUpperCase()}
          </span>
          <span className="text-zinc-400">{e.strategy}</span>
          <span
            className={cn(
              "font-bold",
              e.side === "YES" ? "text-green-400" : "text-red-400"
            )}
          >
            {e.side}
          </span>
          <span className="text-zinc-300 flex-1 truncate" title={e.market_id}>
            {shortAddr(e.market_id)}
          </span>
          {e.event === "closed" && e.realized_pnl_usd && (
            <span
              className={cn(
                "font-semibold",
                parseFloat(e.realized_pnl_usd) >= 0
                  ? "text-green-400"
                  : "text-red-400"
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
      ))}
    </div>
  );
}
