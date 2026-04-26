/**
 * WebSocket client for live position/signal events pushed by the backend.
 * Usage: const cleanup = subscribeToLiveFeed(handler);  // call cleanup() to disconnect
 */

// WebSocket always runs in the browser — use the public-facing URL.
const WS_URL =
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    .replace(/^https?/, "ws") + "/ws/live";

export type LiveEvent = {
  event: "opened" | "closed";
  position_id: string;
  strategy: string;
  market_id: string;
  side: string;
  entry_price: string;
  size_usd: string;
  tp_price: string;
  sl_price: string;
  max_holding_minutes: number;
  opened_at: string;
  closed_at: string | null;
  exit_price: string | null;
  realized_pnl_usd: string | null;
  exit_reason: string | null;
};

export function subscribeToLiveFeed(
  onMessage: (evt: LiveEvent) => void,
  onError?: (e: Event) => void
): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    ws = new WebSocket(WS_URL);

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data as string) as LiveEvent;
        onMessage(data);
      } catch {
        /* ignore malformed */
      }
    };

    ws.onerror = (e) => {
      onError?.(e);
    };

    ws.onclose = () => {
      if (!closed) {
        // Reconnect after 3s
        retryTimer = setTimeout(connect, 3000);
      }
    };
  }

  connect();

  return () => {
    closed = true;
    if (retryTimer) clearTimeout(retryTimer);
    ws?.close();
  };
}
