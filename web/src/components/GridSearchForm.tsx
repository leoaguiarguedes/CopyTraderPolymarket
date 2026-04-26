"use client";

import { useState } from "react";
import { startGridSearch, type GridSearchRequest, type GridSearchResult, fetchGridSearch } from "@/lib/api";
import { fmtUsd, fmtPct } from "@/lib/utils";

const STRATEGIES = ["whale_copy", "consensus", "momentum_odds"];

const DEFAULT_GRIDS: Record<string, string> = {
  whale_copy: JSON.stringify({
    min_trade_size_usd: [1, 10, 50],
    tp_pct: [0.10, 0.15, 0.20],
    sl_pct: [0.05, 0.07, 0.10],
  }, null, 2),
  consensus: JSON.stringify({
    min_wallets: [1, 2],
    tp_pct: [0.10, 0.15],
    sl_pct: [0.05, 0.07],
  }, null, 2),
  momentum_odds: JSON.stringify({
    min_odds_move_pct: [3, 5, 8],
    tp_pct: [0.08, 0.12],
    sl_pct: [0.04, 0.06],
  }, null, 2),
};

export default function GridSearchForm() {
  const [strategy, setStrategy] = useState("whale_copy");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [capital, setCapital] = useState("10000");
  const [gridJson, setGridJson] = useState(DEFAULT_GRIDS.whale_copy);
  const [topN, setTopN] = useState("10");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<GridSearchResult | null>(null);
  const [polling, setPolling] = useState(false);

  function onStrategyChange(s: string) {
    setStrategy(s);
    setGridJson(DEFAULT_GRIDS[s] ?? "{}");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const parsed = JSON.parse(gridJson);
      const req: GridSearchRequest = {
        strategy,
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate).toISOString(),
        capital_usd: parseFloat(capital) || 10000,
        top_n: parseInt(topN) || 10,
        param_grid: parsed,
      };
      const { run_id } = await startGridSearch(req);
      setPolling(true);
      // Poll until done
      const iv = setInterval(async () => {
        try {
          const r = await fetchGridSearch(run_id);
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
      setError(err instanceof Error ? err.message : "JSON inválido ou erro na requisição");
    } finally {
      setLoading(false);
    }
  }

  const totalCombos = (() => {
    try {
      const g = JSON.parse(gridJson);
      return Object.values(g as Record<string, unknown[]>).reduce((acc, v) => acc * v.length, 1);
    } catch {
      return "?";
    }
  })();

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-zinc-400">Estratégia</span>
            <select
              value={strategy}
              onChange={(e) => onStrategyChange(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-zinc-400">Data início</span>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-zinc-400">Data fim</span>
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
            Grade de parâmetros (JSON) —{" "}
            <span className={typeof totalCombos === "number" && totalCombos > 200 ? "text-red-400" : "text-zinc-400"}>
              {totalCombos} combinações
            </span>
            {" "}(máx 200)
          </span>
          <textarea
            value={gridJson}
            onChange={(e) => setGridJson(e.target.value)}
            rows={6}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
          />
        </label>

        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-xs text-zinc-400">
            Top N configs:
            <input type="number" min={1} max={50} value={topN} onChange={(e) => setTopN(e.target.value)}
              className="w-16 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100 focus:outline-none" />
          </label>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" disabled={loading || polling}
            className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-semibold text-white transition-colors ml-auto">
            {polling ? "Executando…" : loading ? "Iniciando…" : "Iniciar grid search"}
          </button>
        </div>
      </form>

      {polling && (
        <p className="text-yellow-400 text-xs animate-pulse">
          Grid search em execução — aguardando resultados…
        </p>
      )}

      {result && (
        <div className="flex flex-col gap-3 mt-2">
          <div className="flex items-center gap-3">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${result.status === "done" ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"}`}>
              {result.status}
            </span>
            <span className="text-zinc-400 text-xs">
              {result.completed}/{result.total_combinations} combinações concluídas
            </span>
            {result.error && <span className="text-red-400 text-xs">{result.error}</span>}
          </div>

          {result.top_configs.length === 0 ? (
            <p className="text-zinc-500 text-sm italic">Nenhuma configuração gerou trades.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-zinc-700">
                    <th className="text-left px-2 py-1.5 text-zinc-400 font-medium">#</th>
                    <th className="text-left px-2 py-1.5 text-zinc-400 font-medium">Parâmetros</th>
                    <th className="text-right px-2 py-1.5 text-zinc-400 font-medium">Trades</th>
                    <th className="text-right px-2 py-1.5 text-zinc-400 font-medium">Sharpe</th>
                    <th className="text-right px-2 py-1.5 text-zinc-400 font-medium">ROI</th>
                    <th className="text-right px-2 py-1.5 text-zinc-400 font-medium">Win %</th>
                    <th className="text-right px-2 py-1.5 text-zinc-400 font-medium">P/L</th>
                    <th className="text-right px-2 py-1.5 text-zinc-400 font-medium">Max DD</th>
                    <th className="text-right px-2 py-1.5 text-zinc-400 font-medium">Timeout %</th>
                  </tr>
                </thead>
                <tbody>
                  {result.top_configs.map((c, i) => (
                    <tr key={i} className="border-b border-zinc-800 hover:bg-zinc-800/40">
                      <td className="px-2 py-1.5 text-zinc-500">{i + 1}</td>
                      <td className="px-2 py-1.5 font-mono text-zinc-300 max-w-xs truncate">
                        {Object.entries(c.params).map(([k, v]) => `${k}=${v}`).join(", ")}
                      </td>
                      <td className="px-2 py-1.5 text-right text-zinc-200">{c.n_trades}</td>
                      <td className={`px-2 py-1.5 text-right font-semibold ${c.sharpe >= 1 ? "text-green-400" : c.sharpe >= 0 ? "text-zinc-200" : "text-red-400"}`}>
                        {c.sharpe.toFixed(3)}
                      </td>
                      <td className={`px-2 py-1.5 text-right ${c.roi >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {fmtPct(c.roi)}
                      </td>
                      <td className="px-2 py-1.5 text-right text-zinc-200">{fmtPct(c.win_rate)}</td>
                      <td className={`px-2 py-1.5 text-right font-semibold ${c.total_pnl_usd >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {fmtUsd(c.total_pnl_usd)}
                      </td>
                      <td className="px-2 py-1.5 text-right text-zinc-200">{fmtPct(c.max_drawdown)}</td>
                      <td className={`px-2 py-1.5 text-right ${c.pct_timeout_exits > 0.5 ? "text-orange-400" : "text-zinc-400"}`}>
                        {fmtPct(c.pct_timeout_exits)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
