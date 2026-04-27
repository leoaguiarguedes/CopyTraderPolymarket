"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchWorkerLogs,
  fetchWorkersStatus,
  runDiscoverWallets,
  startWorkers,
  stopWorkers,
  type WorkerStatus,
} from "@/lib/api";

export default function ControlPage() {
  const [loading, setLoading] = useState(false);
  const [workers, setWorkers] = useState<WorkerStatus[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [logs, setLogs] = useState<Record<string, string[]>>({});

  // Discover wallets — manual
  const [days, setDays] = useState(60);
  const [limit, setLimit] = useState(30);
  const [source, setSource] = useState<"orderbook" | "pnl">("orderbook");
  const [output, setOutput] = useState<{ command: string; exit_code: number; stdout: string; stderr: string } | null>(null);
  const [discoverRunning, setDiscoverRunning] = useState(false);
  const discoverLogRef = useRef<HTMLPreElement>(null);

  // Scheduled discover
  const [schedEnabled, setSchedEnabled] = useState(false);
  const [schedIntervalHours, setSchedIntervalHours] = useState(6);
  const [schedNextRun, setSchedNextRun] = useState<Date | null>(null);
  const [schedRunCount, setSchedRunCount] = useState(0);
  const schedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const anyRunning = useMemo(() => (workers ?? []).some((w) => w.running), [workers]);

  async function refresh() {
    const s = await fetchWorkersStatus();
    setWorkers(s);
  }

  useEffect(() => {
    let alive = true;
    async function tick() {
      try { await refresh(); } catch (e) { if (alive) setMsg(`Error: ${String(e)}`); }
    }
    tick();
    const id = window.setInterval(tick, 1000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);

  useEffect(() => {
    let alive = true;
    async function pullLogs() {
      const list = workers ?? [];
      if (!list.length) return;
      try {
        const results = await Promise.all(
          list.map((w) => fetchWorkerLogs(w.name as "collector" | "tracker" | "signal" | "execution", 80).catch(() => null))
        );
        const next: Record<string, string[]> = {};
        for (const r of results) { if (!r) continue; next[r.name] = r.lines; }
        if (alive) setLogs(next);
      } catch {}
    }
    pullLogs();
    const id = window.setInterval(pullLogs, 1000);
    return () => { alive = false; window.clearInterval(id); };
  }, [workers]);

  // Scheduled discover logic
  useEffect(() => {
    if (schedTimerRef.current) clearTimeout(schedTimerRef.current);
    if (!schedEnabled) { setSchedNextRun(null); return; }

    const intervalMs = schedIntervalHours * 60 * 60 * 1000;
    const next = new Date(Date.now() + intervalMs);
    setSchedNextRun(next);

    async function runScheduled() {
      try {
        const r = await runDiscoverWallets(days, limit, source);
        setSchedRunCount((c) => c + 1);
        setOutput(r);
        setMsg(`[Agendado] discover_wallets: ${r.exit_code === 0 ? "OK" : `exit_code=${r.exit_code}`}`);
      } catch (e) {
        setMsg(`[Agendado] Erro: ${String(e)}`);
      }
      if (schedEnabled) {
        const nextNext = new Date(Date.now() + intervalMs);
        setSchedNextRun(nextNext);
        schedTimerRef.current = setTimeout(runScheduled, intervalMs);
      }
    }

    schedTimerRef.current = setTimeout(runScheduled, intervalMs);
    return () => { if (schedTimerRef.current) clearTimeout(schedTimerRef.current); };
  }, [schedEnabled, schedIntervalHours, days, limit, source]);

  async function handleStart() {
    setLoading(true); setMsg(null);
    try {
      const r = await startWorkers();
      const started = r.started.map((w) => `${w.name}(pid=${w.pid ?? "?"})`).join(", ");
      const already = r.already_running.map((w) => w.name).join(", ");
      setMsg(`Workers: ${started || "nenhum iniciado"}${already ? ` | já rodando: ${already}` : ""}`);
      await refresh();
    } catch (e) { setMsg(`Error: ${String(e)}`); }
    finally { setLoading(false); }
  }

  async function handleStop() {
    setLoading(true); setMsg(null);
    try {
      await stopWorkers();
      setMsg("Workers: stop solicitado.");
      await refresh();
    } catch (e) { setMsg(`Error: ${String(e)}`); }
    finally { setLoading(false); }
  }

  async function handleDiscover() {
    setLoading(true);
    setDiscoverRunning(true);
    setMsg(null);
    setOutput(null);
    try {
      const r = await runDiscoverWallets(days, limit, source);
      setOutput(r);
      setMsg(r.exit_code === 0 ? "discover_wallets: OK" : `discover_wallets: exit_code=${r.exit_code}`);
      await refresh();
    } catch (e) { setMsg(`Error: ${String(e)}`); }
    finally { setLoading(false); setDiscoverRunning(false); }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <h1 className="text-lg font-bold text-zinc-100">Control Panel</h1>

      {/* Workers */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-zinc-300 mb-1">Workers</h2>
            <p className="text-xs text-zinc-500">
              Inicia/para workers como subprocessos dentro do container <code className="text-zinc-300">api</code>. Logs
              aparecem em tempo real abaixo.
            </p>
          </div>
          <div className="flex gap-3">
            <button onClick={handleStart} disabled={loading} className="px-4 py-2 rounded bg-cyan-700 hover:bg-cyan-600 text-white text-sm font-medium transition disabled:opacity-50">
              {loading ? "…" : "Start workers"}
            </button>
            <button onClick={handleStop} disabled={loading || !anyRunning} className="px-4 py-2 rounded bg-zinc-700 hover:bg-zinc-600 text-white text-sm font-medium transition disabled:opacity-50">
              {loading ? "…" : "Stop workers"}
            </button>
            <button
              onClick={() => { setLoading(true); setMsg(null); refresh().catch((e) => setMsg(`Error: ${String(e)}`)).finally(() => setLoading(false)); }}
              disabled={loading}
              className="px-4 py-2 rounded bg-zinc-800 hover:bg-zinc-700 text-white text-sm font-medium transition disabled:opacity-50 border border-zinc-700"
            >
              {loading ? "…" : "Refresh"}
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-3">
          {(workers ?? []).map((w) => (
            <div key={w.name} className="bg-zinc-950/40 border border-zinc-800 rounded-lg px-3 py-2">
              <div className="flex items-center gap-3">
                <span className={w.running ? "w-2 h-2 rounded-full bg-green-500" : "w-2 h-2 rounded-full bg-zinc-600"} />
                <div className="flex flex-col">
                  <code className="text-zinc-200 text-xs">{w.name}</code>
                  <span className="text-[11px] text-zinc-500 font-mono">{w.running ? `pid=${w.pid ?? "?"}` : "stopped"}</span>
                </div>
              </div>
              <div className="mt-2 bg-zinc-950 border border-zinc-800 rounded p-2">
                <pre className="whitespace-pre-wrap text-[11px] leading-4 text-zinc-300 min-h-[72px] max-h-[240px] overflow-auto">
                  {(logs[w.name] ?? []).join("\n") || "(sem logs ainda)"}
                </pre>
              </div>
            </div>
          ))}
          {!workers && <div className="text-xs text-zinc-500 italic">Carregando status…</div>}
        </div>
      </div>

      {/* discover_wallets */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-1">Discover wallets</h2>
        <p className="text-xs text-zinc-500 mb-4">
          Executa <code className="text-zinc-300">python -m scripts.discover_wallets</code> com parâmetros configuráveis.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label="days">
            <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(Number(e.target.value))}
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-200" />
          </Field>
          <Field label="limit">
            <input type="number" min={1} max={5000} value={limit} onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-200" />
          </Field>
          <Field label="source">
            <select value={source} onChange={(e) => setSource(e.target.value as "orderbook" | "pnl")}
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-200">
              <option value="orderbook">orderbook</option>
              <option value="pnl">pnl</option>
            </select>
          </Field>
        </div>

        <div className="mt-4 flex gap-3">
          <button onClick={handleDiscover} disabled={loading}
            className="px-4 py-2 rounded bg-purple-700 hover:bg-purple-600 text-white text-sm font-medium transition disabled:opacity-50">
            {loading ? "…" : "Executar agora"}
          </button>
        </div>

        {/* Scheduled discovery */}
        <div className="mt-5 border-t border-zinc-800 pt-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-xs font-semibold text-zinc-300">Descoberta agendada</h3>
              <p className="text-xs text-zinc-500 mt-0.5">
                Executa automaticamente em intervalos regulares com os mesmos parâmetros acima.
              </p>
            </div>
            <button
              onClick={() => setSchedEnabled((v) => !v)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${schedEnabled ? "bg-purple-600" : "bg-zinc-700"}`}
            >
              <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${schedEnabled ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          </div>

          {schedEnabled && (
            <div className="flex flex-col gap-3">
              <Field label="Intervalo (horas)">
                <input
                  type="number" min={1} max={168} value={schedIntervalHours}
                  onChange={(e) => setSchedIntervalHours(Math.max(1, Number(e.target.value)))}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm text-zinc-200"
                />
              </Field>
              <div className="text-xs text-zinc-400 bg-zinc-950 border border-zinc-800 rounded px-3 py-2 flex flex-col gap-1">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Status</span>
                  <span className="text-purple-400 font-semibold">Ativo</span>
                </div>
                {schedNextRun && (
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Próxima execução</span>
                    <span>{schedNextRun.toLocaleString("pt-BR")}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-zinc-500">Execuções concluídas</span>
                  <span>{schedRunCount}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Log panel — shown as soon as discover runs */}
        {(discoverRunning || output) && (
          <div className="mt-4 bg-zinc-950/40 border border-zinc-800 rounded-lg px-3 py-2">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <span className={discoverRunning
                  ? "w-2 h-2 rounded-full bg-yellow-400 animate-pulse"
                  : output?.exit_code === 0
                    ? "w-2 h-2 rounded-full bg-green-500"
                    : "w-2 h-2 rounded-full bg-red-500"
                } />
                <div className="flex flex-col">
                  <code className="text-zinc-200 text-xs">discover_wallets</code>
                  <span className="text-[11px] text-zinc-500 font-mono">
                    {discoverRunning
                      ? "executando…"
                      : output
                        ? `exit_code=${output.exit_code}`
                        : ""}
                  </span>
                </div>
              </div>
              {output && (
                <span className={`text-[11px] font-mono px-2 py-0.5 rounded ${output.exit_code === 0 ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"}`}>
                  {output.exit_code === 0 ? "✓ OK" : `✗ exit ${output.exit_code}`}
                </span>
              )}
            </div>

            {output && (
              <p className="text-[10px] text-zinc-600 font-mono mb-1 truncate" title={output.command}>
                $ {output.command}
              </p>
            )}

            <div className="bg-zinc-950 border border-zinc-800 rounded p-2">
              <pre ref={discoverLogRef} className="whitespace-pre-wrap text-[11px] leading-4 min-h-[80px] max-h-[320px] overflow-auto">
                {discoverRunning && !output && (
                  <span className="text-yellow-400">Aguardando resposta do servidor…{"\n"}</span>
                )}
                {output?.stdout && (
                  <span className="text-zinc-300">{output.stdout}</span>
                )}
                {output?.stderr && (
                  <>
                    {output.stdout && <span className="text-zinc-600">{"\n"}--- stderr ---{"\n"}</span>}
                    <span className="text-red-300">{output.stderr}</span>
                  </>
                )}
                {output && !output.stdout && !output.stderr && (
                  <span className="text-zinc-600">(sem saída)</span>
                )}
              </pre>
            </div>
          </div>
        )}
      </div>

      {msg && (
        <p className="text-xs text-zinc-300 bg-zinc-900 border border-zinc-800 rounded px-3 py-2">
          {msg}
        </p>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-zinc-500">{label}</span>
      {children}
    </label>
  );
}
