"""Time utilities — always UTC, never naive."""
from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def epoch_ms(dt: datetime | None = None) -> int:
    return int((dt or utcnow()).timestamp() * 1000)
