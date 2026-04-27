"use client";
import { useState, useEffect } from "react";
import { toggleKillSwitch, fetchMarketTags, updateMarketTags } from "@/lib/api";
import type { MarketTag } from "@/lib/api";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SettingsPage() {
  const [ksLoading, setKsLoading] = useState(false);
  const [ksMsg, setKsMsg] = useState<string | null>(null);

  const [tags, setTags] = useState<MarketTag[]>([]);
  const [trackedIds, setTrackedIds] = useState<number[]>([]);
  const [tagsLoading, setTagsLoading] = useState(true);
  const [tagsMsg, setTagsMsg] = useState<string | null>(null);
  const [tagsSaving, setTagsSaving] = useState(false);

  useEffect(() => {
    fetchMarketTags()
      .then((res) => {
        setTags(res.tags);
        setTrackedIds(res.tracked_tag_ids);
      })
      .catch(() => setTagsMsg("Erro ao carregar categorias de mercado."))
      .finally(() => setTagsLoading(false));
  }, []);

  async function handleTagToggle(id: number, checked: boolean) {
    const next = checked ? [...trackedIds, id] : trackedIds.filter((t) => t !== id);
    setTrackedIds(next);
    setTagsSaving(true);
    setTagsMsg(null);
    try {
      await updateMarketTags(next);
      setTagsMsg(
        next.length === 0
          ? "Filtro removido — rastreando todos os mercados."
          : "Categorias salvas. O coletor atualizará na próxima verificação (até 5 min)."
      );
    } catch {
      setTagsMsg("Erro ao salvar categorias.");
    } finally {
      setTagsSaving(false);
    }
  }

  async function handleKillSwitch(active: boolean) {
    setKsLoading(true);
    setKsMsg(null);
    try {
      const r = await toggleKillSwitch(active);
      setKsMsg(
        r.kill_switch
          ? "Kill switch ATIVADO — todas as negociações interrompidas."
          : "Kill switch desativado — negociações retomadas."
      );
    } catch (e) {
      setKsMsg(`Error: ${e}`);
    } finally {
      setKsLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <h1 className="text-lg font-bold text-zinc-100">Configurações</h1>

      {/* Kill switch */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-1">
          Kill Switch
        </h2>
        <p className="text-xs text-zinc-500 mb-4">
          Interrompe imediatamente toda execução de sinais e impede que novas
          posições sejam abertas. Posições existentes continuam sendo monitoradas
          para TP/SL/saídas por tempo.
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => handleKillSwitch(true)}
            disabled={ksLoading}
            className="px-4 py-2 rounded bg-red-700 hover:bg-red-600 text-white text-sm font-medium transition disabled:opacity-50"
          >
            {ksLoading ? "…" : "Ativar Kill Switch"}
          </button>
          <button
            onClick={() => handleKillSwitch(false)}
            disabled={ksLoading}
            className="px-4 py-2 rounded bg-green-700 hover:bg-green-600 text-white text-sm font-medium transition disabled:opacity-50"
          >
            {ksLoading ? "…" : "Desativar"}
          </button>
        </div>
        {ksMsg && (
          <p className="mt-3 text-xs text-zinc-400 bg-zinc-800 rounded px-3 py-2">
            {ksMsg}
          </p>
        )}
      </div>

      {/* Market category filter */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-1">
          Filtro de categorias de mercado
        </h2>
        <p className="text-xs text-zinc-500 mb-4">
          Selecione quais categorias de mercado o coletor deve rastrear. Deixar tudo desmarcado
          significa rastrear todos os mercados sem filtro de categoria.
        </p>
        {tagsLoading ? (
          <p className="text-xs text-zinc-500 italic">Carregando categorias…</p>
        ) : (
          <div className="flex flex-col gap-2">
            {tags.map((tag) => (
              <label key={tag.id} className="flex items-start gap-3 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={trackedIds.includes(tag.id)}
                  disabled={tagsSaving}
                  onChange={(e) => handleTagToggle(tag.id, e.target.checked)}
                  className="mt-0.5 accent-cyan-500 w-4 h-4 cursor-pointer"
                />
                <div>
                  <span className="text-sm text-zinc-200 group-hover:text-white transition">
                    {tag.label}
                  </span>
                  {tag.description && (
                    <p className="text-xs text-zinc-500 mt-0.5">{tag.description}</p>
                  )}
                </div>
              </label>
            ))}
          </div>
        )}
        {tagsMsg && (
          <p className="mt-3 text-xs text-zinc-400 bg-zinc-800 rounded px-3 py-2">
            {tagsMsg}
          </p>
        )}
        {trackedIds.length > 0 && !tagsLoading && (
          <p className="mt-3 text-xs text-zinc-500">
            Rastreando {trackedIds.length} categoria(s) — somente mercados dessas categorias serão coletados.
          </p>
        )}
        {trackedIds.length === 0 && !tagsLoading && (
          <p className="mt-3 text-xs text-zinc-500">
            Nenhuma categoria selecionada — todos os mercados serão coletados.
          </p>
        )}
      </div>

      {/* API info */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">
          API Backend
        </h2>
        <div className="flex flex-col gap-2 text-xs font-mono">
          <Row label="URL" value={API_URL} />
          <Row label="Docs" value={`${API_URL}/docs`} link />
          <Row label="Métricas" value={`${API_URL}/metrics`} link />
          <Row label="Saúde" value={`${API_URL}/health`} link />
        </div>
      </div>

      {/* Config files */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">
          Arquivos de configuração
        </h2>
        <div className="text-xs text-zinc-500 flex flex-col gap-2">
          <p>
            Edite estes arquivos e reinicie o worker relevante para aplicar as alterações:
          </p>
          <ul className="list-disc list-inside gap-1 flex flex-col">
            <li>
              <code className="text-zinc-300">config/strategies.yaml</code> —
              parâmetros de estratégia (limiares, tamanhos, pesos)
            </li>
            <li>
              <code className="text-zinc-300">config/tracked_wallets.yaml</code>{" "}
              — lista de carteiras monitoradas
            </li>
            <li>
              <code className="text-zinc-300">config/market_filters.yaml</code>{" "}
              — filtro de categorias de mercado (também editável pela UI acima)
            </li>
            <li>
              <code className="text-zinc-300">.env</code> — segredos e
              variáveis de ambiente
            </li>
          </ul>
          <p className="mt-2">
            Execute{" "}
            <code className="text-zinc-300">
              python scripts/discover_wallets.py
            </code>{" "}
            para atualizar a lista de carteiras rastreadas.
          </p>
        </div>
      </div>

      {/* Workers status */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">Workers</h2>
        <div className="text-xs text-zinc-500 flex flex-col gap-1">
          {[
            "collector_worker",
            "tracker_worker",
            "signal_worker",
            "execution_worker",
          ].map((w) => (
            <div key={w} className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-zinc-600" />
              <code className="text-zinc-400">workers/{w}.py</code>
            </div>
          ))}
          <p className="mt-2">
            Inicie os workers com:{" "}
            <code className="text-zinc-300">
              docker compose up execution_worker signal_worker tracker_worker
              collector_worker
            </code>
          </p>
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  link,
}: {
  label: string;
  value: string;
  link?: boolean;
}) {
  return (
    <div className="flex items-center gap-4">
      <span className="w-16 text-zinc-500">{label}</span>
      {link ? (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-400 hover:underline"
        >
          {value}
        </a>
      ) : (
        <span className="text-zinc-300">{value}</span>
      )}
    </div>
  );
}
