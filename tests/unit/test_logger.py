"""Smoke test for logging configuration."""
from __future__ import annotations

from app.utils.logger import configure_logging, get_logger


def test_logger_configures_and_emits(capsys) -> None:  # type: ignore[no-untyped-def]
    configure_logging()
    log = get_logger("test")
    log.info("hello", foo="bar")
    captured = capsys.readouterr()
    # JSON renderer writes structured line; just assert key fragments present.
    assert "hello" in captured.out
    assert "foo" in captured.out
