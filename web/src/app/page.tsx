import { Suspense } from "react";
import { fetchPnLSummary, fetchEquityCurve } from "@/lib/api";
import StatCard from "@/components/StatCard";
import EquityCurveChart from "@/components/EquityCurve";
import SignalFeed from "@/components/SignalFeed";
import { fmtUsd, fmtPct } from "@/lib/utils";

export const dynamic = "force-dynamic";

async function DashboardContent() {
  const [summary, curve] = await Promise.all([
    fetchPnLSummary("all"),
    fetchEquityCurve("30d", "1h"),
  ]);

  const pnlPositive = summary.total_pnl_usd >= 0;

  return (
    <div className="flex flex-col gap-6">
      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
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
          value={String(summary.open_positions)}
          sub={fmtUsd(summary.open_exposure_usd) + " em exposição"}
        />
        <StatCard
          label="Volume"
          value={fmtUsd(summary.total_volume_usd)}
          sub="Posições fechadas"
        />
        <StatCard
          label="Negócios fechados"
          value={String(summary.n_closed_positions)}
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

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="text-zinc-500 text-sm italic">Carregando painel…</div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
