import { fetchPnLSummary, fetchEquityCurve } from "@/lib/api";
import EquityCurveChart from "@/components/EquityCurve";
import StatCard from "@/components/StatCard";
import { fmtUsd, fmtPct } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function BacktestPage() {
  const [summary7d, summary30d, summaryAll, curve7d, curve30d] =
    await Promise.all([
      fetchPnLSummary("7d"),
      fetchPnLSummary("30d"),
      fetchPnLSummary("all"),
      fetchEquityCurve("7d", "1h"),
      fetchEquityCurve("30d", "6h"),
    ]);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-lg font-bold text-zinc-100">Backtest / Performance</h1>

      {/* Comparison table */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: "Last 7 days", s: summary7d },
          { label: "Last 30 days", s: summary30d },
          { label: "All time", s: summaryAll },
        ].map(({ label, s }) => (
          <div
            key={label}
            className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col gap-3"
          >
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">
              {label}
            </h2>
            <div className="grid grid-cols-2 gap-2">
              <StatCard
                label="PnL"
                value={fmtUsd(s.total_pnl_usd)}
                positive={s.total_pnl_usd >= 0}
                negative={s.total_pnl_usd < 0}
              />
              <StatCard
                label="ROI"
                value={fmtPct(s.roi)}
                positive={s.roi >= 0}
                negative={s.roi < 0}
              />
              <StatCard
                label="Win Rate"
                value={fmtPct(s.win_rate)}
                sub={`${s.n_closed_positions} trades`}
              />
              <StatCard
                label="Volume"
                value={fmtUsd(s.total_volume_usd)}
              />
            </div>
          </div>
        ))}
      </div>

      {/* 30d equity curve */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">
          30-day Equity Curve (6h buckets)
        </h2>
        {curve30d.points.length > 0 ? (
          <EquityCurveChart data={curve30d} />
        ) : (
          <p className="text-zinc-500 text-sm italic py-8 text-center">
            No closed positions in the last 30 days.
          </p>
        )}
      </div>

      {/* 7d equity curve */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">
          7-day Equity Curve (1h buckets)
        </h2>
        {curve7d.points.length > 0 ? (
          <EquityCurveChart data={curve7d} />
        ) : (
          <p className="text-zinc-500 text-sm italic py-8 text-center">
            No closed positions in the last 7 days.
          </p>
        )}
      </div>

      {/* Future: run backtest form */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-sm font-semibold text-zinc-300 mb-2">
          Historical Backtest (Phase 3)
        </h2>
        <p className="text-zinc-500 text-sm">
          Full event-replay backtest engine coming in Phase 3. The metrics above
          reflect live paper-trading performance.
        </p>
      </div>
    </div>
  );
}
