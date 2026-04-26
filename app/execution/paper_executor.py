"""Paper executor — simulates order execution against the real CLOB orderbook.

Execution model:
  - Uses the live CLOB orderbook to estimate the fill price including slippage
  - Simulates a market order walking the book (best-ask for BUY, best-bid for SELL)
  - No real capital is spent; positions are tracked in-memory and in the DB
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.data.models import OrderSide
from app.data.polymarket_rest import PolymarketRestClient
from app.execution.base import BaseExecutor, Position
from app.signals.models import Signal
from app.utils.logger import get_logger

log = get_logger(__name__)

_SLIPPAGE_SPREAD = Decimal("0.003")   # add 0.3% slippage on top of best price


class PaperExecutor(BaseExecutor):
    """Simulates market-order execution against the real orderbook."""

    def __init__(self, rest_client: PolymarketRestClient) -> None:
        self._rest = rest_client

    async def open_position(self, signal: Signal, capital_usd: float) -> Position:
        trade_usd = min(signal.size_pct, 0.05) * capital_usd  # cap at 5% safety
        trade_usd = max(trade_usd, 1.0)

        current_price = await self.get_current_price(signal.asset_id)
        if current_price is None:
            current_price = signal.entry_price

        # Simulate market-order slippage
        if signal.side == OrderSide.BUY:
            fill_price = current_price * (1 + _SLIPPAGE_SPREAD)
        else:
            fill_price = current_price * (1 - _SLIPPAGE_SPREAD)

        fill_price = min(Decimal("0.9999"), max(Decimal("0.0001"), fill_price))

        size_tokens = Decimal(str(trade_usd)) / fill_price

        # TP / SL prices in token probability space
        if signal.side == OrderSide.BUY:
            tp_price = fill_price * Decimal(str(1 + signal.tp_pct))
            sl_price = fill_price * Decimal(str(1 - signal.sl_pct))
        else:
            # For SELL positions (shorting): profit if price drops
            tp_price = fill_price * Decimal(str(1 - signal.tp_pct))
            sl_price = fill_price * Decimal(str(1 + signal.sl_pct))

        position = Position(
            position_id=str(uuid.uuid4()),
            signal_id=signal.signal_id,
            strategy=signal.strategy,
            market_id=signal.market_id,
            asset_id=signal.asset_id,
            side=signal.side.value,
            entry_price=fill_price,
            size_usd=Decimal(str(round(trade_usd, 6))),
            size_tokens=size_tokens,
            tp_price=min(Decimal("1.0"), tp_price),
            sl_price=max(Decimal("0.0001"), sl_price),
            max_holding_minutes=signal.max_holding_minutes,
            opened_at=datetime.now(tz=timezone.utc),
        )

        log.info(
            "paper.opened",
            position_id=position.position_id[:8],
            strategy=signal.strategy,
            market=signal.market_id[:10],
            side=signal.side.value,
            entry=f"{float(fill_price):.4f}",
            size_usd=f"{float(trade_usd):.2f}",
            tp=f"{float(position.tp_price):.4f}",
            sl=f"{float(position.sl_price):.4f}",
        )
        return position

    async def close_position(self, position: Position, reason: str) -> Position:
        current_price = await self.get_current_price(position.asset_id)
        if current_price is None:
            current_price = position.entry_price

        # Simulate market-order exit slippage (adverse)
        if position.side == "BUY":
            exit_price = current_price * (1 - _SLIPPAGE_SPREAD)
        else:
            exit_price = current_price * (1 + _SLIPPAGE_SPREAD)
        exit_price = min(Decimal("0.9999"), max(Decimal("0.0001"), exit_price))

        if position.side == "BUY":
            pnl = (exit_price - position.entry_price) * position.size_tokens
        else:
            pnl = (position.entry_price - exit_price) * position.size_tokens

        from dataclasses import replace

        closed = replace(
            position,
            closed_at=datetime.now(tz=timezone.utc),
            exit_price=exit_price,
            realized_pnl_usd=pnl,
            exit_reason=reason,
        )
        log.info(
            "paper.closed",
            position_id=position.position_id[:8],
            strategy=position.strategy,
            reason=reason,
            exit=f"{float(exit_price):.4f}",
            pnl_usd=f"{float(pnl):+.4f}",
        )
        return closed

    async def get_current_price(self, asset_id: str) -> Decimal | None:
        """Fetch best ask/bid mid from the CLOB orderbook."""
        try:
            book = await self._rest.get_orderbook(asset_id)
            best_ask = book.best_ask()
            best_bid = book.best_bid()
            if best_ask is not None and best_bid is not None:
                return (best_ask + best_bid) / 2
            return best_ask or best_bid
        except Exception as exc:
            log.warning("paper.price_fetch_failed", asset=asset_id[:10], error=str(exc)[:60])
            return None
