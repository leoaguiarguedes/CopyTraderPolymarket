/**
 * Typed API client for the CopyTrader FastAPI backend.
 * All fetchers throw on HTTP errors and return typed data.
 */
import { z } from "zod";

// Server-side (SSR inside Docker): use API_URL (internal network, runtime).
// Client-side (browser): use NEXT_PUBLIC_API_URL (baked at build time → localhost).
const BASE =
  typeof window === "undefined"
    ? (process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

// ── helpers ──────────────────────────────────────────────────────────────────

async function get<T>(
  path: string,
  params?: Record<string, string | number | undefined>
): Promise<T> {
  const url = new URL(path, BASE);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} → ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const url = new URL(path, BASE);
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ── Zod schemas ───────────────────────────────────────────────────────────────

export const PnLSummarySchema = z.object({
  range: z.string(),
  total_pnl_usd: z.number(),
  total_volume_usd: z.number(),
  n_closed_positions: z.number(),
  win_rate: z.number(),
  roi: z.number(),
  open_positions: z.number(),
  open_exposure_usd: z.number(),
});
export type PnLSummary = z.infer<typeof PnLSummarySchema>;

export const EquityPointSchema = z.object({
  ts: z.string(),
  pnl: z.number(),
  cumulative: z.number(),
  exit_reason: z.string().nullable(),
});
export const EquityCurveSchema = z.object({
  range: z.string(),
  points: z.array(EquityPointSchema),
  final_pnl: z.number(),
});
export type EquityCurve = z.infer<typeof EquityCurveSchema>;

export const PositionSchema = z.object({
  position_id: z.string(),
  signal_id: z.string(),
  strategy: z.string(),
  market_id: z.string(),
  side: z.string(),
  entry_price: z.number(),
  size_usd: z.number(),
  tp_price: z.number(),
  sl_price: z.number(),
  max_holding_minutes: z.number(),
  opened_at: z.string(),
  age_minutes: z.number(),
  time_to_force_exit_minutes: z.number().nullable(),
  closed_at: z.string().nullable(),
  exit_price: z.number().nullable(),
  realized_pnl_usd: z.number().nullable(),
  exit_reason: z.string().nullable(),
  execution_mode: z.string(),
});
export type Position = z.infer<typeof PositionSchema>;

export const SignalSchema = z.object({
  signal_id: z.string(),
  strategy: z.string(),
  market_id: z.string(),
  market_question: z.string(),
  side: z.string(),
  confidence: z.number(),
  entry_price: z.number(),
  size_pct: z.number(),
  tp_pct: z.number(),
  sl_pct: z.number(),
  max_holding_minutes: z.number(),
  source_wallet: z.string(),
  status: z.string(),
  reject_reason: z.string(),
  reason: z.string(),
  created_at: z.string(),
});
export type Signal = z.infer<typeof SignalSchema>;

export const WalletScoreSchema = z.object({
  wallet: z.string(),
  score: z.number().optional(),
  n_trades: z.number().optional(),
  sharpe: z.number().optional(),
  roi: z.number().optional(),
  win_rate: z.number().optional(),
  max_drawdown: z.number().optional(),
  avg_holding_minutes: z.number().optional(),
  median_holding_minutes: z.number().optional(),
  pct_under_24h: z.number().optional(),
  total_volume_usd: z.number().optional(),
  is_active: z.boolean().optional(),
  last_seen: z.string().nullable().optional(),
});
export type WalletScore = z.infer<typeof WalletScoreSchema>;

export const KillSwitchSchema = z.object({ kill_switch: z.boolean() });
export type KillSwitch = z.infer<typeof KillSwitchSchema>;

// ── API functions ─────────────────────────────────────────────────────────────

export function fetchPnLSummary(range = "all") {
  return get<PnLSummary>("/pnl/summary", { range });
}

export function fetchEquityCurve(range = "30d", bucket = "1h") {
  return get<EquityCurve>("/pnl/equity-curve", { range, bucket });
}

export function fetchPositions(
  status: "open" | "closed" | "all" = "open",
  limit = 200,
  strategy?: string
) {
  return get<Position[]>("/positions", { status, limit, strategy });
}

export function fetchSignals(
  limit = 50,
  strategy?: string,
  status?: string
) {
  return get<Signal[]>("/signals", { limit, strategy, status });
}

export function fetchWallets() {
  return get<WalletScore[]>("/wallets");
}

export function fetchKillSwitch() {
  return get<KillSwitch>("/kill-switch");
}

export function toggleKillSwitch(active: boolean) {
  return post<KillSwitch>(`/kill-switch?active=${active}`);
}

export function fetchHealth() {
  return get<{ status: string }>("/health");
}
