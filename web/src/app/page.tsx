"use client";

import { useEffect, useState } from "react";
import { fetchPnLSummary, fetchEquityCurve, fetchSystemStatus } from "@/lib/api";
import type { PnLSummary, EquityCurve, SystemStatus } from "@/lib/api";
import StatCard from "@/components/StatCard";
import EquityCurveChart from "@/components/EquityCurve";
import SignalFeed from "@/components/SignalFeed";
import { fmtUsd, fmtPct } from "@/lib/utils";
import { useTradeConfig } from "@/lib/useTradeConfig";

const POLL_INTERVAL = 30_000;

export default function DashboardPage() {
  const [summary, setSummary] = useState<PnLSummary | null>(null);
  const [curve, setCurve] = useState<EquityCurve | null>(null);
  const [sys, setSys] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const { config } = useTradeConfig();

  async function load() {
    try {
      const [s, c, st] = await Promise.all([
        fetchPnLSummary("all"),
        fetchEquityCurve("30d", "1h"),
        fetchSystemStatus().catch(() => null),
      ]);
      setSummary(s);
      setCurve(c);
      setSys(st);
    } catch {}
    setLoading(false);
  }

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL);
    return () => clearInterval(id);
  }, []);

  if (loading) {
    return <div className="text-zinc-500 text-sm italic">Carregando painel…</div>;
  }

  if (!summary || !curve) {
    return <div className="text-red-400 text-sm">Erro ao carregar dados. Verifique se o backend está online.</div>;
  }

  const pnlPositive = summary.total_pnl_usd >= 0;
  const isLive = sys?.execution_mode === "live";
  const cbConsecutive = sys?.circuit_breaker_consecutive ?? 0;
  const cbMax = sys?.circuit_breaker_max ?? 3;
  const cbRatio = cbMax > 0 ? cbConsecutive / cbMax : 0;

  // Saldo simulado = capital inicial + P&L realizado - exposição em aberto
  const simulatedBalance = config.capitalUsd + summary.total_pnl_usd - summary.open_exposure_usd;
  const simulatedBalancePositive = simulatedBalance >= config.capitalUsd;

  // Balance safety: effective balance and whether a new position can be opened
  const effectiveBalance = isLive
    ? (sys?.usdc_balance ?? 0)
    : simulatedBalance;
  const canOpenPosition = effectiveBalance >= config.positionSizeUsd && effectiveBalance > 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Execution mode banner */}
      {sys && (
        <div
          className={`flex items-center justify-between rounded-xl px-4 py-2.5 text-sm font-medium border ${
            isLive
              ? "bg-red-950/60 border-red-700/60 text-red-300"
              : "bg-zinc-900 border-zinc-700 text-zinc-400"
          }`}
        >
          <span>
            Modo de execução:{" "}
            <span className={`font-bold ${isLive ? "text-red-400 uppercase" : "text-zinc-300"}`}>
              {isLive ? "🔴 LIVE" : "🟡 Paper Trading"}
            </span>
          </span>
          {sys.kill_switch_active && (
            <span className="text-red-400 font-semibold animate-pulse">
              ⛔ Kill Switch Ativo
            </span>
          )}
          {isLive && sys.usdc_balance !== null && (
            <span className="text-zinc-300 font-mono">
              Saldo USDC: <span className="text-white font-bold">{fmtUsd(sys.usdc_balance)}</span>
            </span>
          )}
          <span className="text-[11px] text-zinc-500 ml-auto pl-4">
            Atualiza a cada 30s
          </span>
        </div>
      )}

      {/* Insufficient balance warning */}
      {!canOpenPosition && (
        <div className="flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium bg-amber-950/60 border border-amber-700/60 text-amber-300">
          <span className="text-lg">⚠️</span>
          <span>
            <span className="font-bold">Saldo insuficiente</span> — novas posições bloqueadas.{" "}
            {isLive
              ? `Saldo USDC (${fmtUsd(effectiveBalance)}) é menor que o tamanho de posição configurado (${fmtUsd(config.positionSizeUsd)}).`
              : `Saldo simulado (${fmtUsd(effectiveBalance)}) é menor que o tamanho de posição configurado (${fmtUsd(config.positionSizeUsd)}).`}
          </span>
        </div>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3">
        <StatCard
          label="P/L Total"
          value={fmtUsd(summary.total_pnl_usd)}
          sub="Todo o período, fechado"
          positive={pnlPositive}
          negative={!pnlPositive}
        />
        <StatCard
          label="ROI"
          value={fmtPct(summary.roi)}
          positive={summary.roi >= 0}
          negative={summary.roi < 0}
        />
        <StatCard
          label="Taxa de acerto"
          value={fmtPct(summary.win_rate)}
          sub={`${summary.n_closed_positions} negócios fechados`}
        />
        <StatCard
          label="Posições abertas"
          value={`${summary.open_positions}/${config.maxOpenPositions}`}
          sub={fmtUsd(summary.open_exposure_usd) + " em exposição"}
          negative={summary.open_positions >= config.maxOpenPositions}
          positive={summary.open_positions === 0}
        />
        <StatCard
          label={isLive ? "Saldo da carteira" : "Saldo simulado"}
          value={isLive && sys?.usdc_balance != null ? fmtUsd(sys.usdc_balance) : fmtUsd(simulatedBalance)}
          sub={
            isLive
              ? "Saldo real USDC na carteira"
              : `Capital: ${fmtUsd(config.capitalUsd)} · P&L: ${summary.total_pnl_usd >= 0 ? "+" : ""}${fmtUsd(summary.total_pnl_usd)}`
          }
          positive={isLive ? (sys?.usdc_balance ?? 0) > 0 : simulatedBalancePositive}
          negative={isLive ? false : !simulatedBalancePositive}
        />
        <StatCard
          label="Capital inicial"
          value={fmtUsd(config.capitalUsd)}
          sub={`Posição: ${fmtUsd(config.positionSizeUsd)} · Máx. ${config.maxHoldingHours}h`}
        />
        <StatCard
          label="Circuit Breaker"
          value={`${cbConsecutive}/${cbMax}`}
          sub={cbConsecutive === 0 ? "Sem perdas consecutivas" : `${cbConsecutive} perda(s) seguida(s)`}
          negative={cbRatio >= 0.67}
          positive={cbConsecutive === 0}
        />
      </div>

      {/* Equity curve */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-zinc-300">
            Curva de patrimônio (30 dias)
          </h2>
          <span
            className={
              curve.final_pnl >= 0
                ? "text-green-400 text-sm font-mono"
                : "text-red-400 text-sm font-mono"
            }
          >
            {curve.final_pnl >= 0 ? "+" : ""}
            {fmtUsd(curve.final_pnl)}
          </span>
        </div>
        {curve.points.length > 0 ? (
          <EquityCurveChart data={curve} />
        ) : (
          <p className="text-zinc-500 text-sm italic py-8 text-center">
            Ainda não há posições fechadas — execute o bot para ver dados aqui.
          </p>
        )}
      </div>

      {/* Live feed */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">
          Feed de posições ao vivo
        </h2>
        <SignalFeed />
      </div>
    </div>
  );
}
