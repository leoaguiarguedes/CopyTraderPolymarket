from datetime import datetime, timezone

from app.utils.time import epoch_ms, to_utc, utcnow


def test_utcnow_returns_aware_datetime() -> None:
    now = utcnow()
    assert now.tzinfo is not None


def test_to_utc_converts_naive_datetime() -> None:
    naive = datetime(2025, 1, 1, 0, 0)
    converted = to_utc(naive)
    assert converted.tzinfo == timezone.utc


def test_to_utc_preserves_aware_datetime() -> None:
    aware = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert to_utc(aware) == aware


def test_epoch_ms_returns_integer() -> None:
    assert isinstance(epoch_ms(), int)
