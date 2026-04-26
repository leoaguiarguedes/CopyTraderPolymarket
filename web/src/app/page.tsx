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
          label="Total PnL"
          value={fmtUsd(summary.total_pnl_usd)}
          sub="All time, closed"
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
          label="Win Rate"
          value={fmtPct(summary.win_rate)}
          sub={`${summary.n_closed_positions} closed trades`}
        />
        <StatCard
          label="Open Positions"
          value={String(summary.open_positions)}
          sub={fmtUsd(summary.open_exposure_usd) + " exposure"}
        />
        <StatCard
          label="Volume"
          value={fmtUsd(summary.total_volume_usd)}
          sub="Closed positions"
        />
        <StatCard
          label="Closed Trades"
          value={String(summary.n_closed_positions)}
        />
      </div>

      {/* Equity curve */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-zinc-300">
            Equity Curve (30d)
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
            No closed positions yet — run the bot to see data here.
          </p>
        )}
      </div>

      {/* Live feed */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">
          Live Position Feed
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
        <div className="text-zinc-500 text-sm italic">Loading dashboard…</div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
