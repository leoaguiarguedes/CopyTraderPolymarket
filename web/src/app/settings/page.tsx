"use client";
import { useState, useEffect } from "react";
import { toggleKillSwitch, fetchMarketTags, updateMarketTags, fetchEnvStatus, updateEnvVars, resetData } from "@/lib/api";
import type { MarketTag, EnvStatus, ResetEntity } from "@/lib/api";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SettingsPage() {
  const [ksLoading, setKsLoading] = useState(false);
  const [ksMsg, setKsMsg] = useState<string | null>(null);

  // ── Reset / danger zone ─────────────────────────────────────────────────────
  const [resetConfirm, setResetConfirm] = useState<ResetEntity | null>(null);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);

  async function handleReset(entity: ResetEntity) {
    setResetLoading(true);
    setResetMsg(null);
    setResetConfirm(null);
    try {
      const r = await resetData(entity);
      const counts = Object.entries(r.deleted)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
      setResetMsg(`Resetado "${entity}" — ${counts || "nenhum registro apagado"}.`);
    } catch (e) {
      setResetMsg(`Erro: ${e}`);
    } finally {
      setResetLoading(false);
    }
  }

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

  // ── Env vars ────────────────────────────────────────────────────────────────
  const [envStatus, setEnvStatus] = useState<EnvStatus | null>(null);
  const [envLoading, setEnvLoading] = useState(true);
  const [envSaving, setEnvSaving] = useState(false);
  const [envMsg, setEnvMsg] = useState<string | null>(null);

  // Form fields (local edits before saving)
  const [isLiveMode, setIsLiveMode] = useState(false);
  const [walletAddress, setWalletAddress] = useState("");
  const [privateKey, setPrivateKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [discordUrl, setDiscordUrl] = useState("");

  useEffect(() => {
    fetchEnvStatus()
      .then((s) => {
        setEnvStatus(s);
        setIsLiveMode(s.execution_mode === "live");
        setWalletAddress(s.wallet_address ?? "");
        setDiscordUrl(s.discord_webhook_url ?? "");
      })
      .catch(() => setEnvMsg("Erro ao carregar variáveis de ambiente."))
      .finally(() => setEnvLoading(false));
  }, []);

  async function handleEnvSave() {
    setEnvSaving(true);
    setEnvMsg(null);
    const vars: Record<string, string> = {
      EXECUTION_MODE: isLiveMode ? "live" : "paper",
      WALLET_ADDRESS: walletAddress,
      DISCORD_WEBHOOK_URL: discordUrl,
    };
    if (privateKey.trim()) vars["WALLET_PRIVATE_KEY"] = privateKey;
    try {
      const updated = await updateEnvVars(vars);
      setEnvStatus(updated);
      setPrivateKey(""); // clear after save
      setEnvMsg(
        isLiveMode
          ? "Salvo. Reinicie os workers para aplicar o modo LIVE."
          : "Salvo. Reinicie os workers para aplicar o modo Paper Trading."
      );
    } catch (e) {
      setEnvMsg(`Erro ao salvar: ${e}`);
    } finally {
      setEnvSaving(false);
    }
  }

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

      {/* Execution environment */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-1">Variáveis de execução</h2>
        <p className="text-xs text-zinc-500 mb-4">
          Configura as variáveis de ambiente gravadas no arquivo <code className="text-zinc-300">.env</code>.
          As alterações têm efeito após reiniciar os workers.
        </p>

        {envLoading ? (
          <p className="text-xs text-zinc-500 italic">Carregando…</p>
        ) : (
          <div className="flex flex-col gap-4">
            {/* EXECUTION_MODE toggle */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-200 font-medium">Modo de execução</p>
                <p className="text-xs text-zinc-500 mt-0.5">
                  {isLiveMode
                    ? "LIVE — ordens reais na blockchain. Use com cuidado."
                    : "Paper Trading — simulação sem capital real."}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400">{isLiveMode ? "LIVE" : "Paper"}</span>
                <button
                  onClick={() => setIsLiveMode((v) => !v)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${isLiveMode ? "bg-red-600" : "bg-zinc-600"}`}
                >
                  <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${isLiveMode ? "translate-x-6" : "translate-x-1"}`} />
                </button>
              </div>
            </div>

            {isLiveMode && (
              <div className="rounded-lg bg-red-950/40 border border-red-800/50 px-3 py-2 text-xs text-red-300">
                Modo LIVE ativo: ordens serão executadas com capital real. Certifique-se de configurar corretamente a chave privada e o endereço da carteira.
              </div>
            )}

            {/* WALLET_ADDRESS */}
            <div className="flex flex-col gap-1">
              <label className="text-xs text-zinc-400">
                WALLET_ADDRESS <span className="text-zinc-600">(endereço da carteira/proxy)</span>
              </label>
              <input
                type="text"
                placeholder="0x..."
                value={walletAddress}
                onChange={(e) => setWalletAddress(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-200 font-mono"
              />
            </div>

            {/* WALLET_PRIVATE_KEY (write-only / masked) */}
            <div className="flex flex-col gap-1">
              <label className="text-xs text-zinc-400">
                WALLET_PRIVATE_KEY{" "}
                <span className="text-zinc-600">
                  {envStatus?.wallet_private_key_set ? "(já configurada — deixe em branco para manter)" : "(não configurada)"}
                </span>
              </label>
              <div className="relative">
                <input
                  type={showKey ? "text" : "password"}
                  placeholder={envStatus?.wallet_private_key_set ? "••••••••••••••••••••" : "0x..."}
                  value={privateKey}
                  onChange={(e) => setPrivateKey(e.target.value)}
                  autoComplete="new-password"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 pr-20 text-sm text-zinc-200 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowKey((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-zinc-500 hover:text-zinc-300 transition px-1"
                >
                  {showKey ? "Ocultar" : "Mostrar"}
                </button>
              </div>
              <p className="text-[10px] text-zinc-600">Nunca exposta na resposta da API. Gravada apenas no arquivo .env local.</p>
            </div>

            {/* DISCORD_WEBHOOK_URL */}
            <div className="flex flex-col gap-1">
              <label className="text-xs text-zinc-400">
                DISCORD_WEBHOOK_URL <span className="text-zinc-600">(opcional)</span>
              </label>
              <input
                type="url"
                placeholder="https://discord.com/api/webhooks/..."
                value={discordUrl}
                onChange={(e) => setDiscordUrl(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-200 font-mono"
              />
            </div>

            <div className="flex gap-3 items-center">
              <button
                onClick={handleEnvSave}
                disabled={envSaving}
                className="px-4 py-2 rounded bg-cyan-700 hover:bg-cyan-600 text-white text-sm font-medium transition disabled:opacity-50"
              >
                {envSaving ? "Salvando…" : "Salvar variáveis"}
              </button>
              {envMsg && (
                <p className="text-xs text-zinc-400 bg-zinc-800 rounded px-3 py-2 flex-1">
                  {envMsg}
                </p>
              )}
            </div>
          </div>
        )}
      </div>

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

      {/* Zona de perigo — reset */}
      <div className="bg-zinc-900 border border-red-900/40 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-red-400 mb-1">Zona de perigo</h2>
        <p className="text-xs text-zinc-500 mb-4">
          Apaga permanentemente os dados do banco. Não há desfazer.
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {(
            [
              { entity: "trades", label: "Trades", desc: "Histórico de trades on-chain" },
              { entity: "wallets", label: "Carteiras", desc: "Carteiras, scores e trades" },
              { entity: "signals", label: "Sinais", desc: "Sinais e posições" },
              { entity: "backtest", label: "Backtest", desc: "Todas as execuções de backtest" },
            ] as { entity: ResetEntity; label: string; desc: string }[]
          ).map(({ entity, label, desc }) => (
            <button
              key={entity}
              onClick={() => setResetConfirm(entity)}
              disabled={resetLoading}
              className="flex flex-col gap-0.5 px-3 py-2 rounded-lg border border-zinc-700 hover:border-red-700 bg-zinc-950 text-left transition disabled:opacity-50"
            >
              <span className="text-xs font-semibold text-zinc-300">Resetar {label}</span>
              <span className="text-[10px] text-zinc-500">{desc}</span>
            </button>
          ))}

          <button
            onClick={() => setResetConfirm("all")}
            disabled={resetLoading}
            className="flex flex-col gap-0.5 px-3 py-2 rounded-lg border border-red-800 hover:border-red-600 bg-red-950/20 text-left transition disabled:opacity-50 col-span-2 sm:col-span-1"
          >
            <span className="text-xs font-semibold text-red-400">Resetar tudo</span>
            <span className="text-[10px] text-zinc-500">Apaga todos os dados acima</span>
          </button>
        </div>

        {resetMsg && (
          <p className="mt-3 text-xs text-zinc-400 bg-zinc-800 rounded px-3 py-2">{resetMsg}</p>
        )}
      </div>

      {/* Confirmation modal */}
      {resetConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-zinc-900 border border-red-800 rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl">
            <h3 className="text-sm font-bold text-red-400 mb-2">Confirmar reset</h3>
            <p className="text-xs text-zinc-400 mb-5">
              Você está prestes a apagar permanentemente{" "}
              <span className="text-zinc-200 font-semibold">
                {resetConfirm === "all" ? "todos os dados" : `"${resetConfirm}"`}
              </span>
              . Esta ação não pode ser desfeita.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => handleReset(resetConfirm)}
                disabled={resetLoading}
                className="flex-1 px-4 py-2 rounded bg-red-700 hover:bg-red-600 text-white text-sm font-medium transition disabled:opacity-50"
              >
                {resetLoading ? "Apagando…" : "Confirmar"}
              </button>
              <button
                onClick={() => setResetConfirm(null)}
                disabled={resetLoading}
                className="flex-1 px-4 py-2 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-sm font-medium transition disabled:opacity-50"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

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
