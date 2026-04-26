"""Wallet discovery script — finds top traders and scores them.

Usage:
    python -m scripts.discover_wallets [--days 90] [--limit 500] [--output config/tracked_wallets.yaml]

Steps:
  1. Fetches top wallets from Polymarket subgraph leaderboard
  2. For each wallet: fetches trade history and computes quality score
  3. Applies filters (n_trades, Sharpe, drawdown, holding time)
  4. Writes surviving wallets to YAML for the tracker to consume
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import yaml

from app.config import get_settings
from app.data.polymarket_rest import PolymarketRestClient
from app.data.subgraph_client import SubgraphClient
from app.tracker.proxy_resolver import ProxyResolver
from app.tracker.scoring import WalletScore, compute_score, score_is_finite
from app.utils.logger import configure_logging, get_logger

log = get_logger(__name__)


async def discover(
    days: int = 90,
    limit: int = 500,
    output: str = "config/tracked_wallets.yaml",
    min_volume_usd: float = 500.0,
    source: str = "orderbook",
) -> None:
    configure_logging()
    settings = get_settings()

    subgraph = SubgraphClient(settings)
    rest = PolymarketRestClient(settings)
    resolver = ProxyResolver(client=rest)

    log.info("discover.starting", days=days, limit=limit, source=source)

    # ── Step 1: wallet candidates ─────────────────────────────────────────
    if source == "orderbook":
        # Primary: discover from CLOB orderbook fills (current activity)
        log.info("discover.fetching_active_wallets_from_orderbook")
        top_wallets = await subgraph.get_active_wallets(
            days_back=days,
            min_fills=20,
            max_fills_in_sample=300,  # skip bots (>300 fills in sample = market maker)
            limit=limit,
        )
    else:
        # Fallback: pnl-subgraph leaderboard (historical, often inactive)
        log.info("discover.fetching_leaderboard")
        top_wallets = await subgraph.get_top_wallets(limit=limit, min_pnl_usd=min_volume_usd)
    log.info("discover.candidates_fetched", count=len(top_wallets))

    # ── Step 2: score each wallet ─────────────────────────────────────────
    scores: list[WalletScore] = []
    for i, w in enumerate(top_wallets):
        address = w.get("id", "").lower()
        if not address:
            continue

        if i % 50 == 0:
            log.info("discover.progress", processed=i, total=len(top_wallets))

        try:
            trades = await subgraph.get_wallet_trades(address, days_back=days)
            score = compute_score(trades, window_days=days)
            if score and score_is_finite(score):
                scores.append(score)
        except Exception as exc:
            log.warning("discover.wallet_score_failed", address=address[:10], error=str(exc))
            continue

    log.info("discover.scored", total_scored=len(scores))

    # ── Step 3: filter ────────────────────────────────────────────────────
    trackable = [s for s in scores if s.is_trackable()]
    trackable.sort(key=lambda s: s.sharpe, reverse=True)
    log.info("discover.filtered", trackable=len(trackable), total=len(scores))

    # ── Step 4: resolve proxy addresses ──────────────────────────────────
    await resolver.preload([s.wallet_address for s in trackable])

    # ── Step 5: write YAML ────────────────────────────────────────────────
    wallet_entries = []
    for score in trackable:
        proxy = resolver._reverse.get(score.wallet_address)
        entry: dict[str, object] = {
            "address": proxy or score.wallet_address,
            "owner_address": score.wallet_address if proxy else None,
            "label": None,
            "source": "discovery_script",
            "sharpe": round(score.sharpe, 3),
            "roi": round(score.roi, 4),
            "win_rate": round(score.win_rate, 3),
            "median_holding_min": round(score.median_holding_minutes, 1),
            "n_trades": score.n_trades,
        }
        wallet_entries.append(entry)

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        yaml.dump({"wallets": wallet_entries}, f, default_flow_style=False, allow_unicode=True)

    log.info("discover.done", output=str(out_path), wallets_written=len(wallet_entries))
    print(f"\n✓ {len(wallet_entries)} wallets written to {out_path}")

    # Print top 10 summary
    print("\nTop 10 by Sharpe:")
    print(f"{'Address':<20} {'Sharpe':>8} {'ROI':>8} {'WinRate':>8} {'MedHold':>10} {'Trades':>7}")
    print("-" * 65)
    for s in trackable[:10]:
        addr = (s.wallet_address[:18] + "..") if len(s.wallet_address) > 18 else s.wallet_address
        print(
            f"{addr:<20} {s.sharpe:>8.3f} {s.roi:>8.3%} "
            f"{s.win_rate:>8.1%} {s.median_holding_minutes:>10.0f}m {s.n_trades:>7}"
        )

    await rest.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover top Polymarket traders")
    parser.add_argument("--days", type=int, default=90, help="History window in days")
    parser.add_argument("--limit", type=int, default=500, help="Max wallets to evaluate")
    parser.add_argument("--output", default="config/tracked_wallets.yaml")
    parser.add_argument("--min-volume", type=float, default=500.0)
    parser.add_argument(
        "--source",
        choices=["orderbook", "pnl"],
        default="orderbook",
        help="orderbook = discover from recent CLOB fills (recommended); pnl = historical leaderboard",
    )
    args = parser.parse_args()
    asyncio.run(
        discover(
            days=args.days,
            limit=args.limit,
            output=args.output,
            min_volume_usd=args.min_volume,
            source=args.source,
        )
    )


if __name__ == "__main__":
    main()
