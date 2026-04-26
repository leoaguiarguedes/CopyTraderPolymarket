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
  address: z.string(),
  proxy_address: z.string().nullable().optional(),
  label: z.string().nullable().optional(),
  is_tracked: z.boolean().optional(),
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

export function fetchWallets(limit = 200) {
  return get<WalletScore[]>("/wallets", { limit });
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

// ── Control ───────────────────────────────────────────────────────────────────

export type WorkerStatus = {
  name: string;
  running: boolean;
  pid: number | null;
  cmd: string[];
};

export async function fetchWorkersStatus() {
  return get<WorkerStatus[]>("/control/workers");
}

export async function startWorkers(which?: Array<"collector" | "tracker" | "signal" | "execution">) {
  const qs = which?.length ? `?${which.map((w) => `which=${encodeURIComponent(w)}`).join("&")}` : "";
  return post<{ started: WorkerStatus[]; already_running: WorkerStatus[] }>(
    `/control/workers/start${qs}`
  );
}

export async function stopWorkers(which?: Array<"collector" | "tracker" | "signal" | "execution">) {
  const qs = which?.length ? `?${which.map((w) => `which=${encodeURIComponent(w)}`).join("&")}` : "";
  return post<WorkerStatus[]>(`/control/workers/stop${qs}`);
}

export async function runDiscoverWallets(days: number, limit: number, source: "orderbook" | "pnl" = "orderbook") {
  return post<{
    command: string;
    exit_code: number;
    stdout: string;
    stderr: string;
  }>(`/control/discover-wallets?days=${days}&limit=${limit}&source=${source}`);
}

export async function fetchWorkerLogs(name: "collector" | "tracker" | "signal" | "execution", tail = 120) {
  return get<{
    name: string;
    running: boolean;
    pid: number | null;
    log_started_at: string | null;
    lines: string[];
  }>("/control/workers/logs", { name, tail });
}

// ── Backtest ──────────────────────────────────────────────────────────────────

export type BacktestRunSummary = {
  run_id: string;
  strategy: string;
  start_date: string;
  end_date: string;
  status: string;
  n_wallets: number;
  n_trades: number | null;
  total_pnl_usd: number | null;
  roi: number | null;
  sharpe: number | null;
  win_rate: number | null;
  max_drawdown: number | null;
  pct_timeout_exits: number | null;
  error: string;
  created_at: string;
  finished_at: string | null;
};

export type BacktestMetrics = {
  n_trades: number;
  n_wins: number;
  n_losses: number;
  win_rate: number;
  total_pnl_usd: number;
  roi: number;
  avg_pnl_usd: number;
  avg_win_usd: number;
  avg_loss_usd: number;
  profit_factor: number;
  expectancy_usd: number;
  sharpe: number;
  max_drawdown: number;
  avg_holding_minutes: number;
  median_holding_minutes: number;
  pct_tp_exits: number;
  pct_sl_exits: number;
  pct_timeout_exits: number;
  equity_curve: number[];
};

export type BacktestRunRequest = {
  strategy: string;
  start_date: string;
  end_date: string;
  wallets?: string[];
  params?: Record<string, unknown>;
  capital_usd?: number;
};

export function fetchBacktestRuns(limit = 20, strategy?: string) {
  return get<BacktestRunSummary[]>("/backtest/runs", { limit, strategy });
}

export function fetchBacktestRun(run_id: string) {
  return get<BacktestRunSummary>(`/backtest/runs/${run_id}`);
}

export function fetchBacktestMetrics(run_id: string) {
  return get<BacktestMetrics | { error: string }>(`/backtest/runs/${run_id}/metrics`);
}

export function startBacktest(req: BacktestRunRequest) {
  return post<{ run_id: string; status: string }>("/backtest/run", req);
}

export function deleteBacktestRun(run_id: string) {
  const url = new URL(`/backtest/runs/${run_id}`, BASE);
  return fetch(url.toString(), { method: "DELETE" });
}

export const BACKTEST_REPORT_URL = (run_id: string) =>
  `${BASE}/backtest/runs/${run_id}/report`;

export const BACKTEST_CSV_URL = (run_id: string) =>
  `${BASE}/backtest/runs/${run_id}/csv`;

// ── Grid Search ───────────────────────────────────────────────────────────────

export type GridConfig = {
  params: Record<string, unknown>;
  n_trades: number;
  sharpe: number;
  roi: number;
  win_rate: number;
  total_pnl_usd: number;
  max_drawdown: number;
  profit_factor: number;
  pct_timeout_exits: number;
};

export type GridSearchResult = {
  run_id: string;
  strategy: string;
  start_date: string;
  end_date: string;
  param_grid: Record<string, unknown[]>;
  total_combinations: number;
  completed: number;
  status: string;
  error: string;
  finished_at: string | null;
  top_configs: GridConfig[];
};

export type GridSearchRequest = {
  strategy: string;
  start_date: string;
  end_date: string;
  wallets?: string[];
  param_grid: Record<string, unknown[]>;
  capital_usd?: number;
  top_n?: number;
};

export function startGridSearch(req: GridSearchRequest) {
  return post<{ run_id: string; status: string }>("/backtest/grid-search", req);
}

export function fetchGridSearch(run_id: string) {
  return get<GridSearchResult>(`/backtest/grid-search/${run_id}`);
}

// ── Walk-Forward ──────────────────────────────────────────────────────────────

export type WalkForwardMetrics = {
  n_trades: number;
  win_rate: number;
  total_pnl_usd: number;
  roi: number;
  sharpe: number;
  max_drawdown: number;
  profit_factor: number;
  expectancy_usd: number;
  avg_holding_minutes: number;
  pct_tp_exits: number;
  pct_sl_exits: number;
  pct_timeout_exits: number;
  equity_curve: number[];
} | null;

export type WalkForwardResult = {
  run_id: string;
  strategy: string;
  full_start: string;
  full_end: string;
  split_date: string;
  in_start: string;
  in_end: string;
  out_start: string;
  out_end: string;
  params: Record<string, unknown>;
  status: string;
  error: string;
  finished_at: string | null;
  overfit_flag: boolean;
  divergence: number;
  in_signals: number;
  out_signals: number;
  in_positions: number;
  out_positions: number;
  in_sample: WalkForwardMetrics;
  out_sample: WalkForwardMetrics;
};

export type WalkForwardRequest = {
  strategy: string;
  start_date: string;
  end_date: string;
  wallets?: string[];
  params?: Record<string, unknown>;
  capital_usd?: number;
};

export function startWalkForward(req: WalkForwardRequest) {
  return post<{ run_id: string; status: string }>("/backtest/walk-forward", req);
}

export function fetchWalkForward(run_id: string) {
  return get<WalkForwardResult>(`/backtest/walk-forward/${run_id}`);
}
