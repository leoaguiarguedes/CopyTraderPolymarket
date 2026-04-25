"""Smoke test for app.config — ensures Settings loads with defaults."""
from __future__ import annotations

from app.config import AppEnv, ExecutionMode, Settings


def test_settings_loads_with_defaults() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.app_env == AppEnv.development
    assert s.execution_mode == ExecutionMode.paper
    assert s.is_paper_trading is True
    assert s.max_pct_per_trade == 0.02
    assert 0 < s.max_drawdown_daily <= 1.0


def test_settings_validation_rejects_bad_values() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_pct_per_trade=1.5)  # type: ignore[call-arg]
