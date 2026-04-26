"use client";

import { useState } from "react";
import { startBacktest, type BacktestRunRequest } from "@/lib/api";

const STRATEGIES = ["whale_copy", "consensus", "momentum_odds"];

export default function BacktestForm({ onStarted }: { onStarted: (run_id: string) => void }) {
  const [strategy, setStrategy] = useState("whale_copy");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [capital, setCapital] = useState("10000");
  const [wallets, setWallets] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const req: BacktestRunRequest = {
        strategy,
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate).toISOString(),
        capital_usd: parseFloat(capital) || 10000,
        wallets: wallets.trim()
          ? wallets.split(/[\s,]+/).map((w) => w.trim()).filter(Boolean)
          : [],
      };
      const res = await startBacktest(req);
      onStarted(res.run_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao iniciar backtest");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-zinc-400">Estratégia</span>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {STRATEGIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-zinc-400">Data início</span>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-zinc-400">Data fim</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-zinc-400">Capital ($)</span>
          <input
            type="number"
            min={100}
            step={100}
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </label>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-xs text-zinc-400">
          Wallets (opcional — separadas por vírgula ou nova linha; vazio = tracked_wallets.yaml)
        </span>
        <textarea
          value={wallets}
          onChange={(e) => setWallets(e.target.value)}
          rows={2}
          placeholder="0xabc..., 0xdef..."
          className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
        />
      </label>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="self-start px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-semibold text-white transition-colors"
      >
        {loading ? "Iniciando…" : "Iniciar backtest"}
      </button>
    </form>
  );
}
