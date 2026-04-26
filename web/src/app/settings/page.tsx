"use client";
import { useState } from "react";
import { toggleKillSwitch } from "@/lib/api";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SettingsPage() {
  const [ksLoading, setKsLoading] = useState(false);
  const [ksMsg, setKsMsg] = useState<string | null>(null);

  async function handleKillSwitch(active: boolean) {
    setKsLoading(true);
    setKsMsg(null);
    try {
      const r = await toggleKillSwitch(active);
      setKsMsg(
        r.kill_switch
          ? "Kill switch ACTIVATED — all trading halted."
          : "Kill switch deactivated — trading resumed."
      );
    } catch (e) {
      setKsMsg(`Error: ${e}`);
    } finally {
      setKsLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <h1 className="text-lg font-bold text-zinc-100">Settings</h1>

      {/* Kill switch */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-1">
          Kill Switch
        </h2>
        <p className="text-xs text-zinc-500 mb-4">
          Immediately halt all signal execution and prevent new positions from
          being opened. Existing positions continue to be monitored for
          TP/SL/timeout exits.
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => handleKillSwitch(true)}
            disabled={ksLoading}
            className="px-4 py-2 rounded bg-red-700 hover:bg-red-600 text-white text-sm font-medium transition disabled:opacity-50"
          >
            {ksLoading ? "…" : "Activate Kill Switch"}
          </button>
          <button
            onClick={() => handleKillSwitch(false)}
            disabled={ksLoading}
            className="px-4 py-2 rounded bg-green-700 hover:bg-green-600 text-white text-sm font-medium transition disabled:opacity-50"
          >
            {ksLoading ? "…" : "Deactivate"}
          </button>
        </div>
        {ksMsg && (
          <p className="mt-3 text-xs text-zinc-400 bg-zinc-800 rounded px-3 py-2">
            {ksMsg}
          </p>
        )}
      </div>

      {/* API info */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">
          Backend API
        </h2>
        <div className="flex flex-col gap-2 text-xs font-mono">
          <Row label="URL" value={API_URL} />
          <Row label="Docs" value={`${API_URL}/docs`} link />
          <Row label="Metrics" value={`${API_URL}/metrics`} link />
          <Row label="Health" value={`${API_URL}/health`} link />
        </div>
      </div>

      {/* Config files */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-3">
          Configuration Files
        </h2>
        <div className="text-xs text-zinc-500 flex flex-col gap-2">
          <p>
            Edit these files and restart the relevant worker to apply changes:
          </p>
          <ul className="list-disc list-inside gap-1 flex flex-col">
            <li>
              <code className="text-zinc-300">config/strategies.yaml</code> —
              strategy parameters (thresholds, sizes, weights)
            </li>
            <li>
              <code className="text-zinc-300">config/tracked_wallets.yaml</code>{" "}
              — list of monitored wallets
            </li>
            <li>
              <code className="text-zinc-300">.env</code> — secrets and
              environment variables
            </li>
          </ul>
          <p className="mt-2">
            Run{" "}
            <code className="text-zinc-300">
              python scripts/discover_wallets.py
            </code>{" "}
            to refresh the tracked wallets list.
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
            Start workers with:{" "}
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
