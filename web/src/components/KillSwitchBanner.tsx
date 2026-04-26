"use client";
import { useState, useEffect } from "react";
import { fetchKillSwitch, toggleKillSwitch } from "@/lib/api";

export default function KillSwitchBanner() {
  const [active, setActive] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchKillSwitch()
      .then((r) => setActive(r.kill_switch))
      .catch(() => {});
  }, []);

  async function toggle() {
    setLoading(true);
    try {
      const r = await toggleKillSwitch(!active);
      setActive(r.kill_switch);
    } finally {
      setLoading(false);
    }
  }

  if (!active) {
    return (
      <div className="flex items-center justify-end gap-2 px-4 py-1">
        <span className="text-xs text-green-400">● Bot running</span>
        <button
          onClick={toggle}
          disabled={loading}
          className="text-xs px-2 py-0.5 rounded bg-red-800/60 hover:bg-red-700 text-red-200 transition"
        >
          Kill
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between bg-red-900/80 border-b border-red-500 px-4 py-2 text-red-100">
      <span className="font-semibold text-sm">⛔ KILL SWITCH ACTIVE — all trading halted</span>
      <button
        onClick={toggle}
        disabled={loading}
        className="text-xs px-3 py-1 rounded bg-green-700 hover:bg-green-600 text-white transition"
      >
        {loading ? "…" : "Resume"}
      </button>
    </div>
  );
}
