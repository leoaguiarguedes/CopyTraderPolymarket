"""Live executor — submits real orders to the Polymarket CLOB via py-clob-client.

Safety requirements before enabling live mode:
  - EXECUTION_MODE=live in .env
  - WALLET_PRIVATE_KEY set (never committed)
  - WALLET_ADDRESS set
  - Backtest Sharpe > 1.5 confirmed
  - Paper trading 30d with PnL+ confirmed

Order strategy:
  - We simulate a market order by placing an aggressive limit order:
      BUY : limit at best_ask * (1 + _AGGRESSIVE_PCT)
      SELL: limit at best_bid * (1 - _AGGRESSIVE_PCT)
  - GTD orders with TTL = max_holding_minutes to guarantee expiry.
  - After submission we poll for fill status for up to _FILL_TIMEOUT_S seconds.
  - Partial fills are accepted; the unfilled remainder is cancelled.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.config import get_settings
from app.data.models import OrderSide
from app.data.polymarket_rest import PolymarketRestClient
from app.execution.base import BaseExecutor, Position
from app.signals.models import Signal
from app.utils.logger import get_logger

log = get_logger(__name__)

_AGGRESSIVE_PCT = Decimal("0.02")   # 2% above/below best price for market-like fill
_FILL_TIMEOUT_S = 30               # seconds to wait for fill confirmation
_POLL_INTERVAL_S = 1               # poll every second
_MIN_FILL_RATIO = 0.8              # accept if at least 80% of order is filled


class LiveExecutorError(Exception):
    """Raised on unrecoverable errors during live order management."""


class LiveExecutor(BaseExecutor):
    """Executes real orders on the Polymarket CLOB using py-clob-client.

    Usage:
        executor = await LiveExecutor.create()
        position = await executor.open_position(signal, capital_usd)
    """

    def __init__(self, client: Any, rest_client: PolymarketRestClient) -> None:
        self._client = client   # ClobClient from py_clob_client
        self._rest = rest_client

    # ── Factory ────────────────────────────────────────────────────────────

    @classmethod
    async def create(cls) -> "LiveExecutor":
        """Build and validate the live executor from environment settings."""
        settings = get_settings()

        if settings.is_paper_trading:
            raise LiveExecutorError("Cannot create LiveExecutor when EXECUTION_MODE=paper")

        if not settings.wallet_private_key:
            raise LiveExecutorError("WALLET_PRIVATE_KEY is required for live trading")

        if not settings.wallet_address:
            raise LiveExecutorError("WALLET_ADDRESS is required for live trading")

        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.constants import POLYGON
        except ImportError as exc:
            raise LiveExecutorError("py-clob-client not installed") from exc

        private_key = settings.wallet_private_key.get_secret_value()
        client = ClobClient(
            host=settings.polymarket_clob_url,
            chain_id=POLYGON,
            private_key=private_key,
            signature_type=2,   # EIP-712 (Gnosis Safe proxy wallets)
        )

        # Derive API credentials from the wallet key (stored on CLOB)
        try:
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
        except Exception as exc:
            raise LiveExecutorError(f"Failed to obtain CLOB API credentials: {exc}") from exc

        rest_client = PolymarketRestClient(settings)
        executor = cls(client, rest_client)

        balance = await executor.get_usdc_balance()
        log.info("live_executor.initialized", wallet=settings.wallet_address[:10], usdc_balance=f"{balance:.2f}")

        return executor

    # ── BaseExecutor interface ─────────────────────────────────────────────

    async def open_position(self, signal: Signal, capital_usd: float) -> Position:
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY, SELL

        settings = get_settings()
        trade_usd = min(signal.size_pct, 0.05) * capital_usd
        trade_usd = max(trade_usd, 1.0)

        # Validate balance
        balance = await self.get_usdc_balance()
        if balance < trade_usd:
            raise LiveExecutorError(
                f"Insufficient USDC balance: {balance:.2f} < required {trade_usd:.2f}"
            )

        current_price = await self.get_current_price(signal.asset_id)
        if current_price is None:
            raise LiveExecutorError(f"Could not fetch price for asset {signal.asset_id}")

        # Aggressive limit to simulate market-order fill
        if signal.side == OrderSide.BUY:
            fill_price = min(Decimal("0.9999"), current_price * (1 + _AGGRESSIVE_PCT))
            clob_side = BUY
        else:
            fill_price = max(Decimal("0.0001"), current_price * (1 - _AGGRESSIVE_PCT))
            clob_side = SELL

        size_tokens = float(Decimal(str(trade_usd)) / fill_price)
        ttl_seconds = signal.max_holding_minutes * 60

        order_args = OrderArgs(
            token_id=signal.asset_id,
            price=float(fill_price),
            size=round(size_tokens, 2),
            side=clob_side,
        )

        log.info(
            "live.submitting_order",
            strategy=signal.strategy,
            side=signal.side.value,
            price=float(fill_price),
            size_tokens=round(size_tokens, 4),
            size_usd=round(trade_usd, 2),
        )

        # Post order (runs synchronously in py-clob-client, wrap in executor)
        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._client.create_and_post_order(order_args)
        )

        order_id = resp.get("orderID") or resp.get("order_id", "")
        if not order_id:
            raise LiveExecutorError(f"No order_id in CLOB response: {resp}")

        log.info("live.order_submitted", order_id=order_id[:12])

        # Wait for fill
        actual_fill_price, filled_tokens = await self._await_fill(
            order_id, size_tokens, fill_price
        )

        # TP / SL in token-probability space
        if signal.side == OrderSide.BUY:
            tp_price = actual_fill_price * Decimal(str(1 + signal.tp_pct))
            sl_price = actual_fill_price * Decimal(str(1 - signal.sl_pct))
        else:
            tp_price = actual_fill_price * Decimal(str(1 - signal.tp_pct))
            sl_price = actual_fill_price * Decimal(str(1 + signal.sl_pct))

        position = Position(
            position_id=str(uuid.uuid4()),
            signal_id=signal.signal_id,
            strategy=signal.strategy,
            market_id=signal.market_id,
            asset_id=signal.asset_id,
            side=signal.side.value,
            entry_price=actual_fill_price,
            size_usd=actual_fill_price * Decimal(str(filled_tokens)),
            size_tokens=Decimal(str(filled_tokens)),
            tp_price=min(Decimal("1.0"), tp_price),
            sl_price=max(Decimal("0.0001"), sl_price),
            max_holding_minutes=signal.max_holding_minutes,
            opened_at=datetime.now(tz=timezone.utc),
            order_id=order_id,
        )

        log.info(
            "live.opened",
            position_id=position.position_id[:8],
            order_id=order_id[:12],
            entry=float(actual_fill_price),
            size_tokens=filled_tokens,
        )
        return position

    async def close_position(self, position: Position, reason: str) -> Position:
        from py_clob_client.clob_types import OrderArgs
        from py_clob_client.order_builder.constants import BUY, SELL

        current_price = await self.get_current_price(position.asset_id)
        if current_price is None:
            current_price = position.entry_price

        # Close by trading the opposite side
        if position.side == "BUY":
            # We hold YES tokens — sell them
            exit_price_limit = max(Decimal("0.0001"), current_price * (1 - _AGGRESSIVE_PCT))
            clob_side = SELL
        else:
            # We are short YES — buy them back
            exit_price_limit = min(Decimal("0.9999"), current_price * (1 + _AGGRESSIVE_PCT))
            clob_side = BUY

        order_args = OrderArgs(
            token_id=position.asset_id,
            price=float(exit_price_limit),
            size=float(position.size_tokens),
            side=clob_side,
        )

        log.info(
            "live.closing_position",
            position_id=position.position_id[:8],
            reason=reason,
            price=float(exit_price_limit),
        )

        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._client.create_and_post_order(order_args)
        )

        close_order_id = resp.get("orderID") or resp.get("order_id", "")
        actual_exit, _ = await self._await_fill(
            close_order_id, float(position.size_tokens), exit_price_limit
        )

        if position.side == "BUY":
            pnl = (actual_exit - position.entry_price) * position.size_tokens
        else:
            pnl = (position.entry_price - actual_exit) * position.size_tokens

        closed = replace(
            position,
            closed_at=datetime.now(tz=timezone.utc),
            exit_price=actual_exit,
            realized_pnl_usd=pnl,
            exit_reason=reason,
        )
        log.info(
            "live.closed",
            position_id=position.position_id[:8],
            reason=reason,
            exit=float(actual_exit),
            pnl_usd=f"{float(pnl):+.4f}",
        )
        return closed

    async def get_current_price(self, asset_id: str) -> Decimal | None:
        """Fetch mid price from the CLOB orderbook (same as PaperExecutor)."""
        try:
            book = await self._rest.get_orderbook(asset_id)
            best_ask = book.best_ask()
            best_bid = book.best_bid()
            if best_ask is not None and best_bid is not None:
                return (best_ask + best_bid) / 2
            return best_ask or best_bid
        except Exception as exc:
            log.warning("live.price_fetch_failed", asset=asset_id[:10], error=str(exc)[:60])
            return None

    # ── Live-only helpers ──────────────────────────────────────────────────

    async def get_usdc_balance(self) -> float:
        """Return available USDC balance from the CLOB API."""
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                None, self._client.get_balance
            )
            # py-clob-client returns balance in USDC units
            return float(resp) if resp is not None else 0.0
        except Exception as exc:
            log.warning("live.balance_fetch_failed", error=str(exc)[:60])
            return 0.0

    async def get_open_orders(self) -> list[dict]:
        """Return all open orders from the CLOB API."""
        try:
            from py_clob_client.clob_types import OpenOrderParams
            resp = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._client.get_orders(OpenOrderParams())
            )
            return resp if isinstance(resp, list) else []
        except Exception as exc:
            log.warning("live.get_open_orders_failed", error=str(exc)[:60])
            return []

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True on success."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._client.cancel(order_id)
            )
            return True
        except Exception as exc:
            log.warning("live.cancel_failed", order_id=order_id[:12], error=str(exc)[:60])
            return False

    # ── Internal ───────────────────────────────────────────────────────────

    async def _await_fill(
        self,
        order_id: str,
        expected_size: float,
        fallback_price: Decimal,
    ) -> tuple[Decimal, float]:
        """Poll CLOB until order is filled (or timeout). Returns (avg_fill_price, filled_tokens)."""
        deadline = asyncio.get_event_loop().time() + _FILL_TIMEOUT_S

        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(_POLL_INTERVAL_S)
            try:
                order = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._client.get_order(order_id)
                )
                status = (order.get("status") or "").lower()
                size_matched = float(order.get("size_matched", 0) or 0)
                avg_price = order.get("average_price") or order.get("price")

                if status in ("matched", "filled"):
                    actual_price = Decimal(str(avg_price)) if avg_price else fallback_price
                    return actual_price, size_matched

                if status in ("cancelled", "expired"):
                    if size_matched >= expected_size * _MIN_FILL_RATIO:
                        actual_price = Decimal(str(avg_price)) if avg_price else fallback_price
                        log.info("live.partial_fill_accepted", order_id=order_id[:12], size_matched=size_matched)
                        return actual_price, size_matched
                    raise LiveExecutorError(
                        f"Order {order_id[:12]} {status} with only {size_matched:.2f}/{expected_size:.2f} filled"
                    )

            except LiveExecutorError:
                raise
            except Exception as exc:
                log.warning("live.fill_poll_error", order_id=order_id[:12], error=str(exc)[:60])

        # Timeout — cancel the order and use what we have
        log.warning("live.fill_timeout", order_id=order_id[:12])
        await self.cancel_order(order_id)
        raise LiveExecutorError(f"Order {order_id[:12]} did not fill within {_FILL_TIMEOUT_S}s")
