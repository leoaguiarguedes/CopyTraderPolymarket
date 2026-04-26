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
      <h1 className="text-lg font-bold text-zinc-100">Backtest / Desempenho</h1>

      {/* Tabela de comparação */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: "Últimos 7 dias", s: summary7d },
          { label: "Últimos 30 dias", s: summary30d },
          { label: "Todo o período", s: summaryAll },
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
                label="P/L"
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
                label="Taxa de acerto"
                value={fmtPct(s.win_rate)}
                sub={`${s.n_closed_positions} negócios`}
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
          Curva de patrimônio de 30 dias (intervalos de 6h)
        </h2>
        {curve30d.points.length > 0 ? (
          <EquityCurveChart data={curve30d} />
        ) : (
          <p className="text-zinc-500 text-sm italic py-8 text-center">
            Nenhuma posição fechada nos últimos 30 dias.
          </p>
        )}
      </div>

      {/* 7d equity curve */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">
          Curva de patrimônio de 7 dias (intervalos de 1h)
        </h2>
        {curve7d.points.length > 0 ? (
          <EquityCurveChart data={curve7d} />
        ) : (
          <p className="text-zinc-500 text-sm italic py-8 text-center">
            Nenhuma posição fechada nos últimos 7 dias.
          </p>
        )}
      </div>

      {/* Future: run backtest form */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-4">
        <h2 className="text-sm font-semibold text-zinc-300 mb-2">
          Backtest histórico (Fase 3)
        </h2>
        <p className="text-zinc-500 text-sm">
          Motor de backtest com replay de eventos será lançado na Fase 3. As métricas acima
          refletem desempenho de paper trading ao vivo.
        </p>
      </div>
    </div>
  );
}
