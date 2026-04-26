from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from starlette.requests import Request

from app.api.routes import control


def _req(token: str | None = None) -> Request:
    headers = []
    if token is not None:
        headers.append((b"x-control-token", token.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/control/workers",
        "headers": headers,
        "query_string": b"",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_workers_status_no_token_required(monkeypatch):
    monkeypatch.setattr(control, "get_settings", lambda: SimpleNamespace(control_token=None))
    r = await control.workers_status(_req())
    assert {w.name for w in r} == {"collector", "tracker", "signal", "execution"}


@pytest.mark.asyncio
async def test_workers_status_requires_token(monkeypatch):
    monkeypatch.setattr(control, "get_settings", lambda: SimpleNamespace(control_token=SecretStr("tok")))
    with pytest.raises(Exception) as excinfo:
        await control.workers_status(_req())
    # FastAPI raises HTTPException internally; just assert status_code-like detail exists.
    assert "401" in str(excinfo.value) or "invalid" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_workers_start_and_stop(monkeypatch):
    monkeypatch.setattr(control, "get_settings", lambda: SimpleNamespace(control_token=None))

    pid_seq = {"v": 100}

    class FakeStdout:
        def __init__(self) -> None:
            self._lines = iter(["boot\n", "tick\n", ""])

        def readline(self) -> str:
            return next(self._lines)

    class FakePopen:
        def __init__(self, *_args, **_kwargs):
            pid_seq["v"] += 1
            self.pid = pid_seq["v"]
            self._returncode = None
            self.terminated = False
            self.stdout = FakeStdout()

        def poll(self):
            return self._returncode

        def terminate(self):
            self.terminated = True
            self._returncode = 0

    # isolate global worker table
    local_workers = {
        "collector": control._Proc("collector", ["python", "-m", "workers.collector_worker"]),
        "tracker": control._Proc("tracker", ["python", "-m", "workers.tracker_worker"]),
    }
    monkeypatch.setattr(control, "_WORKERS", local_workers, raising=False)
    monkeypatch.setattr(control.subprocess, "Popen", FakePopen)

    resp = await control.workers_start(_req(), which=["collector", "tracker"])
    assert {w.name for w in resp.started} == {"collector", "tracker"}
    assert all(w.running for w in resp.started)
    assert all(w.pid is not None for w in resp.started)

    stopped = await control.workers_stop(_req(), which=["collector", "tracker"])
    assert {w.name for w in stopped} == {"collector", "tracker"}
    assert all(w.running is False for w in stopped)


@pytest.mark.asyncio
async def test_discover_wallets_runs_command_and_returns_output(monkeypatch):
    monkeypatch.setattr(control, "get_settings", lambda: SimpleNamespace(control_token=None))

    class FakeProc:
        def __init__(self):
            self.returncode = 0

        async def communicate(self):
            await asyncio.sleep(0)
            return (b"hello\n", b"")

    async def fake_create_subprocess_exec(*_cmd, **_kwargs):
        return FakeProc()

    monkeypatch.setattr(control.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    r = await control.run_discover_wallets(_req(), days=60, limit=30, source="orderbook")
    assert r.exit_code == 0
    assert "scripts.discover_wallets" in r.command
    assert "hello" in r.stdout

