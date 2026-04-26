"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchBacktestRuns,
  fetchBacktestMetrics,
  deleteBacktestRun,
  BACKTEST_REPORT_URL,
  BACKTEST_CSV_URL,
  type BacktestRunSummary,
  type BacktestMetrics,
} from "@/lib/api";
import { fmtUsd, fmtPct } from "@/lib/utils";

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "bg-yellow-500/20 text-yellow-300",
    done: "bg-green-500/20 text-green-300",
    error: "bg-red-500/20 text-red-300",
    pending: "bg-zinc-500/20 text-zinc-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] ?? colors.pending}`}>
      {status}
    </span>
  );
}

function MetricsPanel({ runId }: { runId: string }) {
  const [metrics, setMetrics] = useState<BacktestMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBacktestMetrics(runId).then((m) => {
      if ("n_trades" in m) setMetrics(m as BacktestMetrics);
    }).finally(() => setLoading(false));
  }, [runId]);

  if (loading) return <p className="text-zinc-500 text-sm py-2">Carregando métricas…</p>;
  if (!metrics) return <p className="text-zinc-500 text-sm py-2">Sem métricas disponíveis.</p>;

  const pf = metrics.profit_factor >= 9999 ? "∞" : metrics.profit_factor.toFixed(2);

  const rows = [
    ["Trades", `${metrics.n_trades} (${metrics.n_wins}W / ${metrics.n_losses}L)`],
    ["Taxa de acerto", fmtPct(metrics.win_rate)],
    ["P/L total", fmtUsd(metrics.total_pnl_usd)],
    ["ROI", fmtPct(metrics.roi)],
    ["Sharpe", metrics.sharpe.toFixed(3)],
    ["Max drawdown", fmtPct(metrics.max_drawdown)],
    ["Fator de lucro", pf],
    ["Expectativa/trade", fmtUsd(metrics.expectancy_usd)],
    ["Holding médio", `${metrics.avg_holding_minutes.toFixed(0)} min`],
    ["Saídas TP / SL / Timeout", `${fmtPct(metrics.pct_tp_exits)} / ${fmtPct(metrics.pct_sl_exits)} / ${fmtPct(metrics.pct_timeout_exits)}`],
  ];

  return (
    <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-1">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between text-xs border-b border-zinc-800 py-1 px-1">
          <span className="text-zinc-400">{label}</span>
          <span className="text-zinc-200 font-medium">{value}</span>
        </div>
      ))}
    </div>
  );
}

export default function BacktestRunsTable({
  initialRuns,
  newRunId,
}: {
  initialRuns: BacktestRunSummary[];
  newRunId?: string;
}) {
  const [runs, setRuns] = useState(initialRuns);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const fresh = await fetchBacktestRuns(20);
      setRuns(fresh);
    } catch {
      // ignore
    }
  }, []);

  // Poll while any run is "running" or if we just started one
  useEffect(() => {
    const hasRunning = runs.some((r) => r.status === "running" || r.status === "pending");
    if (!hasRunning && !newRunId) return;

    setPolling(true);
    const id = setInterval(refresh, 3000);
    return () => {
      clearInterval(id);
      setPolling(false);
    };
  }, [runs, newRunId, refresh]);

  // Auto-expand new run
  useEffect(() => {
    if (newRunId) {
      setExpanded(newRunId);
      refresh();
    }
  }, [newRunId, refresh]);

  async function handleDelete(runId: string, e: React.MouseEvent) {
    e.stopPropagation();
    await deleteBacktestRun(runId);
    setRuns((prev) => prev.filter((r) => r.run_id !== runId));
    if (expanded === runId) setExpanded(null);
  }

  if (runs.length === 0) {
    return <p className="text-zinc-500 text-sm italic">Nenhum backtest executado ainda.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {polling && (
        <p className="text-xs text-yellow-400 animate-pulse">Aguardando conclusão…</p>
      )}
      {runs.map((run) => {
        const isOpen = expanded === run.run_id;
        const isDone = run.status === "done";
        return (
          <div
            key={run.run_id}
            className="border border-zinc-800 rounded-xl overflow-hidden"
          >
            <button
              className="w-full flex items-center gap-3 px-4 py-3 bg-zinc-900 hover:bg-zinc-800 transition-colors text-left"
              onClick={() => setExpanded(isOpen ? null : run.run_id)}
            >
              <StatusBadge status={run.status} />
              <span className="font-medium text-zinc-200 text-sm">{run.strategy}</span>
              <span className="text-zinc-500 text-xs">
                {run.start_date.slice(0, 10)} → {run.end_date.slice(0, 10)}
              </span>
              {isDone && run.total_pnl_usd != null && (
                <span className={`ml-auto text-sm font-semibold ${run.total_pnl_usd >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {fmtUsd(run.total_pnl_usd)}
                </span>
              )}
              {isDone && run.sharpe != null && (
                <span className="text-zinc-500 text-xs ml-2">Sharpe {run.sharpe.toFixed(2)}</span>
              )}
              {isDone && run.win_rate != null && (
                <span className="text-zinc-500 text-xs ml-2">{fmtPct(run.win_rate)} WR</span>
              )}
              <svg
                className={`w-4 h-4 text-zinc-500 ml-2 shrink-0 transition-transform ${isOpen ? "rotate-180" : ""}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {isOpen && (
              <div className="px-4 pb-4 bg-zinc-950">
                <div className="flex gap-2 mt-3 flex-wrap">
                  <span className="text-xs text-zinc-500">{run.n_wallets} wallets</span>
                  {run.n_trades != null && (
                    <span className="text-xs text-zinc-500">{run.n_trades} trades</span>
                  )}
                  {run.pct_timeout_exits != null && (
                    <span className={`text-xs ${run.pct_timeout_exits > 0.5 ? "text-orange-400" : "text-zinc-500"}`}>
                      {fmtPct(run.pct_timeout_exits)} timeouts
                      {run.pct_timeout_exits > 0.5 && " ⚠ estratégia mal calibrada"}
                    </span>
                  )}
                  {run.error && <span className="text-xs text-red-400">Erro: {run.error}</span>}
                </div>

                {isDone && <MetricsPanel runId={run.run_id} />}

                <div className="flex gap-2 mt-3 flex-wrap">
                  {isDone && (
                    <>
                      <a
                        href={BACKTEST_REPORT_URL(run.run_id)}
                        target="_blank"
                        rel="noreferrer"
                        className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white"
                      >
                        Relatório HTML
                      </a>
                      <a
                        href={BACKTEST_CSV_URL(run.run_id)}
                        className="px-3 py-1.5 rounded-lg bg-zinc-700 hover:bg-zinc-600 text-xs font-medium text-zinc-200"
                      >
                        Exportar CSV
                      </a>
                    </>
                  )}
                  <button
                    onClick={(e) => handleDelete(run.run_id, e)}
                    className="px-3 py-1.5 rounded-lg bg-red-900/40 hover:bg-red-800/60 text-xs font-medium text-red-400 ml-auto"
                  >
                    Excluir
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
