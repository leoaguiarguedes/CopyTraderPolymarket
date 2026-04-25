"""Wallet tracker — filters incoming TradeEvents to tracked wallets only."""
from __future__ import annotations

from app.data.models import TradeEvent
from app.tracker.proxy_resolver import ProxyResolver
from app.utils.logger import get_logger
from app.utils.metrics import tracked_trades_total, tracked_wallets_gauge

log = get_logger(__name__)


class WalletTracker:
    """Checks whether a trade's taker/maker address belongs to a tracked wallet."""

    def __init__(
        self,
        tracked_addresses: set[str],
        resolver: ProxyResolver | None = None,
        min_size_usd: float = 50.0,
    ) -> None:
        # normalise to lowercase
        self._tracked = {a.lower() for a in tracked_addresses}
        self._resolver = resolver
        self._min_size_usd = min_size_usd
        tracked_wallets_gauge.set(len(self._tracked))

    def add_wallet(self, address: str) -> None:
        self._tracked.add(address.lower())
        tracked_wallets_gauge.set(len(self._tracked))

    def remove_wallet(self, address: str) -> None:
        self._tracked.discard(address.lower())
        tracked_wallets_gauge.set(len(self._tracked))

    def reload(self, addresses: set[str]) -> None:
        self._tracked = {a.lower() for a in addresses}
        tracked_wallets_gauge.set(len(self._tracked))
        log.info("tracker.wallets_reloaded", count=len(self._tracked))

    @property
    def tracked_count(self) -> int:
        return len(self._tracked)

    def is_relevant(self, event: TradeEvent) -> str | None:
        """Return the tracked wallet address if this trade involves one, else None.

        Checks both taker and maker; taker takes priority (more actionable signal).
        Returns the matching tracked address (owner form, not necessarily proxy).
        """
        if float(event.size_usd) < self._min_size_usd:
            return None

        taker = event.taker_address.lower()
        maker = event.maker_address.lower()

        if taker in self._tracked:
            return taker
        if maker in self._tracked:
            return maker
        return None

    async def is_relevant_async(self, event: TradeEvent) -> str | None:
        """Async version — also checks proxy addresses via resolver."""
        direct = self.is_relevant(event)
        if direct:
            return direct

        if self._resolver is None:
            return None

        # Check if taker/maker is a proxy of a tracked owner
        proxies = self._resolver.known_proxies()
        taker = event.taker_address.lower()
        maker = event.maker_address.lower()

        for addr in (taker, maker):
            if addr in proxies:
                owner = await self._resolver.proxy_to_owner(addr)
                if owner in self._tracked:
                    tracked_trades_total.labels(wallet=owner[:10]).inc()
                    return owner
        return None

    def filter_batch(self, events: list[TradeEvent]) -> list[tuple[TradeEvent, str]]:
        """Return (event, tracked_wallet) pairs from a batch of events."""
        result: list[tuple[TradeEvent, str]] = []
        for ev in events:
            wallet = self.is_relevant(ev)
            if wallet:
                tracked_trades_total.labels(wallet=wallet[:10]).inc()
                result.append((ev, wallet))
        return result
