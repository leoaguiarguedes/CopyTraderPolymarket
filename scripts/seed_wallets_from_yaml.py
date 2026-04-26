"""One-shot script: reads config/tracked_wallets.yaml and persists wallets+scores to DB.

Usage (inside docker):
    docker compose exec api python scripts/seed_wallets_from_yaml.py
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from app.storage.db import AsyncSessionFactory
from app.storage import models as orm
from app.utils.logger import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


async def seed(yaml_path: str = "config/tracked_wallets.yaml") -> None:
    data = yaml.safe_load(open(yaml_path))
    wallets = data.get("wallets", [])
    if not wallets:
        print("⚠  No wallets found in YAML — run discover_wallets.py first.")
        return

    print(f"Seeding {len(wallets)} wallets into DB…")
    async with AsyncSessionFactory() as session:
        for w in wallets:
            address = w["address"]
            existing = await session.get(orm.Wallet, address)
            if existing is None:
                session.add(orm.Wallet(
                    address=address,
                    proxy_address=w.get("owner_address"),
                    label=w.get("label"),
                    is_tracked=True,
                ))
            else:
                existing.is_tracked = True

            session.add(orm.WalletScore(
                wallet_address=address,
                window_days=60,
                n_trades=int(w.get("n_trades", 0)),
                roi=Decimal(str(round(float(w.get("roi", 0)), 8))),
                sharpe=Decimal(str(round(float(w.get("sharpe", 0)), 8))),
                win_rate=Decimal(str(round(float(w.get("win_rate", 0)), 6))),
                max_drawdown=Decimal("0"),
                total_volume_usd=Decimal("0"),
                avg_holding_minutes=Decimal(str(round(float(w.get("median_holding_min", 0)), 2))),
                median_holding_minutes=Decimal(str(round(float(w.get("median_holding_min", 0)), 2))),
                pct_closed_under_24h=Decimal("0.8"),
            ))

        await session.commit()

    print(f"✓ {len(wallets)} wallets persisted to DB.")


if __name__ == "__main__":
    asyncio.run(seed())
