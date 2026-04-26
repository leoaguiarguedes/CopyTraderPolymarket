"use client";

import { useState } from "react";
import {
  startWalkForward,
  fetchWalkForward,
  type WalkForwardRequest,
  type WalkForwardResult,
  type WalkForwardMetrics,
} from "@/lib/api";
import { fmtUsd, fmtPct } from "@/lib/utils";

const STRATEGIES = ["whale_copy", "consensus", "momentum_odds"];

function MetricRow({ label, inVal, outVal, highlight }: {
  label: string;
  inVal: string;
  outVal: string;
  highlight?: "good" | "bad" | "neutral";
}) {
  const outColor = highlight === "bad" ? "text-red-400" : highlight === "good" ? "text-green-400" : "text-zinc-200";
  return (
    <tr className="border-b border-zinc-800">
      <td className="px-3 py-1.5 text-zinc-400 text-xs">{label}</td>
      <td className="px-3 py-1.5 text-right text-zinc-200 text-xs">{inVal}</td>
      <td className={`px-3 py-1.5 text-right text-xs font-medium ${outColor}`}>{outVal}</td>
    </tr>
  );
}

function WalkForwardResults({ r }: { r: WalkForwardResult }) {
  const ins = r.in_sample;
  const out = r.out_sample;

  const pf = (m: WalkForwardMetrics) =>
    m ? (m.profit_factor >= 9999 ? "∞" : m.profit_factor.toFixed(2)) : "—";

  return (
    <div className="flex flex-col gap-4 mt-2">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${r.status === "done" ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"}`}>
          {r.status}
        </span>
        <span className="text-zinc-400 text-xs">
          In-sample: {r.in_start?.slice(0, 10)} → {r.in_end?.slice(0, 10)}
        </span>
        <span className="text-zinc-400 text-xs">
          Out-of-sample: {r.out_start?.slice(0, 10)} → {r.out_end?.slice(0, 10)}
        </span>
        {r.error && <span className="text-red-400 text-xs">{r.error}</span>}
      </div>

      {/* Overfit banner */}
      {r.overfit_flag && (
        <div className="bg-orange-900/30 border border-orange-700 rounded-lg px-4 py-2 text-sm text-orange-300">
          ⚠ <strong>Overfitting detectado</strong> — divergência entre in-sample e out-of-sample:{" "}
          <strong>{(r.divergence * 100).toFixed(0)}%</strong> (limite: 30%). Os parâmetros não generalizam.
        </div>
      )}
      {!r.overfit_flag && r.status === "done" && (
        <div className="bg-green-900/20 border border-green-800 rounded-lg px-4 py-2 text-sm text-green-300">
          ✓ Estratégia passa no walk-forward — divergência de {(r.divergence * 100).toFixed(0)}% (abaixo de 30%).
        </div>
      )}

      {/* Comparison table */}
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-zinc-700">
            <th className="text-left px-3 py-2 text-zinc-400 text-xs font-medium">Métrica</th>
            <th className="text-right px-3 py-2 text-zinc-400 text-xs font-medium">In-sample (60%)</th>
            <th className="text-right px-3 py-2 text-zinc-400 text-xs font-medium">Out-of-sample (40%)</th>
          </tr>
        </thead>
        <tbody>
          <MetricRow
            label="Trades"
            inVal={ins ? String(ins.n_trades) : "—"}
            outVal={out ? String(out.n_trades) : "—"}
          />
          <MetricRow
            label="Sharpe"
            inVal={ins ? ins.sharpe.toFixed(3) : "—"}
            outVal={out ? out.sharpe.toFixed(3) : "—"}
            highlight={
              ins && out
                ? out.sharpe >= ins.sharpe * 0.7 ? "good" : "bad"
                : "neutral"
            }
          />
          <MetricRow
            label="ROI"
            inVal={ins ? fmtPct(ins.roi) : "—"}
            outVal={out ? fmtPct(out.roi) : "—"}
            highlight={out ? (out.roi >= 0 ? "good" : "bad") : "neutral"}
          />
          <MetricRow
            label="Taxa de acerto"
            inVal={ins ? fmtPct(ins.win_rate) : "—"}
            outVal={out ? fmtPct(out.win_rate) : "—"}
          />
          <MetricRow
            label="P/L total"
            inVal={ins ? fmtUsd(ins.total_pnl_usd) : "—"}
            outVal={out ? fmtUsd(out.total_pnl_usd) : "—"}
            highlight={out ? (out.total_pnl_usd >= 0 ? "good" : "bad") : "neutral"}
          />
          <MetricRow
            label="Max Drawdown"
            inVal={ins ? fmtPct(ins.max_drawdown) : "—"}
            outVal={out ? fmtPct(out.max_drawdown) : "—"}
          />
          <MetricRow
            label="Fator de lucro"
            inVal={pf(ins)}
            outVal={pf(out)}
          />
          <MetricRow
            label="Expectativa/trade"
            inVal={ins ? fmtUsd(ins.expectancy_usd) : "—"}
            outVal={out ? fmtUsd(out.expectancy_usd) : "—"}
            highlight={out ? (out.expectancy_usd >= 0 ? "good" : "bad") : "neutral"}
          />
          <MetricRow
            label="Holding médio"
            inVal={ins ? `${ins.avg_holding_minutes.toFixed(0)} min` : "—"}
            outVal={out ? `${out.avg_holding_minutes.toFixed(0)} min` : "—"}
          />
          <MetricRow
            label="Saídas por timeout"
            inVal={ins ? fmtPct(ins.pct_timeout_exits) : "—"}
            outVal={out ? fmtPct(out.pct_timeout_exits) : "—"}
            highlight={
              out ? (out.pct_timeout_exits > 0.5 ? "bad" : "good") : "neutral"
            }
          />
        </tbody>
      </table>
    </div>
  );
}

export default function WalkForwardForm() {
  const [strategy, setStrategy] = useState("whale_copy");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 90);
    return d.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [capital, setCapital] = useState("10000");
  const [paramsJson, setParamsJson] = useState('{"min_trade_size_usd": 1}');
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<WalkForwardResult | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const params = JSON.parse(paramsJson);
      const req: WalkForwardRequest = {
        strategy,
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate).toISOString(),
        capital_usd: parseFloat(capital) || 10000,
        params,
      };
      const { run_id } = await startWalkForward(req);
      setPolling(true);
      const iv = setInterval(async () => {
        try {
          const r = await fetchWalkForward(run_id);
          if (r.status === "done" || r.status === "error") {
            clearInterval(iv);
            setPolling(false);
            setResult(r);
          }
        } catch {
          clearInterval(iv);
          setPolling(false);
          setError("Erro ao buscar resultado");
        }
      }, 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-zinc-400">Estratégia</span>
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500">
              {STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-zinc-400">Início (janela completa)</span>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-zinc-400">Fim</span>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-zinc-400">Capital ($)</span>
            <input type="number" min={100} value={capital} onChange={(e) => setCapital(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
          </label>
        </div>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-zinc-400">
            Parâmetros (JSON) — split automático: 60% in-sample / 40% out-of-sample
          </span>
          <textarea value={paramsJson} onChange={(e) => setParamsJson(e.target.value)} rows={3}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none" />
        </label>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button type="submit" disabled={loading || polling}
          className="self-start px-5 py-2 rounded-lg bg-purple-700 hover:bg-purple-600 disabled:opacity-50 text-sm font-semibold text-white transition-colors">
          {polling ? "Executando…" : loading ? "Iniciando…" : "Iniciar walk-forward"}
        </button>
      </form>

      {polling && (
        <p className="text-yellow-400 text-xs animate-pulse">
          Rodando in-sample + out-of-sample…
        </p>
      )}

      {result && <WalkForwardResults r={result} />}
    </div>
  );
}
