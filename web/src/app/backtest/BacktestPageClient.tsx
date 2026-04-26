"use client";

import { useState } from "react";
import BacktestForm from "@/components/BacktestForm";
import BacktestRunsTable from "@/components/BacktestRunsTable";
import GridSearchForm from "@/components/GridSearchForm";
import WalkForwardForm from "@/components/WalkForwardForm";
import type { BacktestRunSummary } from "@/lib/api";

type Tab = "run" | "grid" | "walkforward";

const TABS: { id: Tab; label: string; desc: string }[] = [
  { id: "run", label: "Simulação simples", desc: "Roda uma estratégia com parâmetros fixos" },
  { id: "grid", label: "Grid search", desc: "Varre combinações de parâmetros, retorna top configs por Sharpe" },
  { id: "walkforward", label: "Walk-forward", desc: "Split 60/40 temporal — detecta overfitting" },
];

export default function BacktestPageClient({
  initialRuns,
}: {
  initialRuns: BacktestRunSummary[];
}) {
  const [tab, setTab] = useState<Tab>("run");
  const [newRunId, setNewRunId] = useState<string | undefined>();

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-lg font-bold text-zinc-100">Backtest histórico</h1>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-zinc-800 pb-0">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            title={t.desc}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors border-b-2 -mb-px ${
              tab === t.id
                ? "border-indigo-500 text-indigo-400 bg-zinc-900"
                : "border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        {tab === "run" && (
          <>
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-4">
              Nova simulação
            </h2>
            <BacktestForm onStarted={(id) => setNewRunId(id)} />
          </>
        )}
        {tab === "grid" && (
          <>
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-1">
              Grid search de parâmetros
            </h2>
            <p className="text-zinc-500 text-xs mb-4">
              Define listas de valores para cada parâmetro — o sistema roda todas as combinações e
              retorna as top configs ordenadas por Sharpe. Limite de 200 combinações por execução.
            </p>
            <GridSearchForm />
          </>
        )}
        {tab === "walkforward" && (
          <>
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-1">
              Walk-forward validation
            </h2>
            <p className="text-zinc-500 text-xs mb-4">
              Divide a janela em 60% in-sample e 40% out-of-sample. Se a divergência de Sharpe
              entre os dois períodos for maior que 30%, a estratégia está overfitada para aqueles
              parâmetros.
            </p>
            <WalkForwardForm />
          </>
        )}
      </section>

      {/* Explanation box */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 text-sm text-zinc-400 leading-relaxed">
        <p className="font-medium text-zinc-300 mb-1">Como funciona o replay</p>
        <p>
          O motor puxa o histórico de trades das wallets rastreadas via Subgraph, constrói uma
          timeline de preços por token e reproduz cada evento cronologicamente pelo mesmo pipeline
          de signal engine que roda ao vivo — sem chamar a CLOB em tempo real. Posições são
          abertas/fechadas com os preços históricos reais + slippage simulado de 0,3%.
        </p>
        <p className="mt-2">
          <span className="text-orange-400 font-medium">⚠</span>{" "}
          Se <span className="font-mono text-zinc-300">% timeout exits &gt; 50%</span>, a
          estratégia está mal calibrada — aumente os targets de TP ou reduza{" "}
          <span className="font-mono text-zinc-300">max_holding_minutes</span>.
        </p>
      </div>

      {/* Runs history (only shown on "run" tab) */}
      {tab === "run" && (
        <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-4">
            Histórico de execuções
          </h2>
          <BacktestRunsTable initialRuns={initialRuns} newRunId={newRunId} />
        </section>
      )}
    </div>
  );
}
