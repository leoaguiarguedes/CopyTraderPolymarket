"""Operational controls (start workers, run scripts) via HTTP.

This is intentionally simple and intended for single-user/dev setups.
For production, prefer an external process supervisor (Compose/K8s/systemd).
"""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/control", tags=["control"])


def _require_control_token(request: Request) -> None:
    """If CONTROL_TOKEN is set, require it via `X-Control-Token` header."""
    settings = get_settings()
    token = getattr(settings, "control_token", None)
    if token is None:
        return
    expected = token.get_secret_value()
    if not expected:
        return
    got = request.headers.get("x-control-token")
    if got != expected:
        raise HTTPException(status_code=401, detail="Missing/invalid X-Control-Token")


@dataclass
class _Proc:
    name: str
    cmd: list[str]
    p: subprocess.Popen[str] | None = None


_WORKERS: dict[str, _Proc] = {
    "collector": _Proc("collector", [sys.executable, "-m", "workers.collector_worker"]),
    "tracker": _Proc("tracker", [sys.executable, "-m", "workers.tracker_worker"]),
    "signal": _Proc("signal", [sys.executable, "-m", "workers.signal_worker"]),
    "execution": _Proc("execution", [sys.executable, "-m", "workers.execution_worker"]),
}


class WorkerStatus(BaseModel):
    name: str
    running: bool
    pid: int | None = None
    cmd: list[str]


class StartWorkersResponse(BaseModel):
    started: list[WorkerStatus]
    already_running: list[WorkerStatus]


def _status(proc: _Proc) -> WorkerStatus:
    running = proc.p is not None and proc.p.poll() is None
    pid = proc.p.pid if running and proc.p is not None else None
    return WorkerStatus(name=proc.name, running=running, pid=pid, cmd=proc.cmd)


@router.get("/workers", response_model=list[WorkerStatus])
async def workers_status(request: Request):
    _require_control_token(request)
    return [_status(p) for p in _WORKERS.values()]


@router.post("/workers/start", response_model=StartWorkersResponse)
async def workers_start(
    request: Request,
    which: list[Literal["collector", "tracker", "signal", "execution"]] | None = Query(
        default=None,
        description="Optional subset of workers to start. If omitted, starts all.",
    ),
):
    _require_control_token(request)

    started: list[WorkerStatus] = []
    already: list[WorkerStatus] = []

    keys = which or ["collector", "tracker", "signal", "execution"]
    for k in keys:
        proc = _WORKERS[k]
        if proc.p is not None and proc.p.poll() is None:
            already.append(_status(proc))
            continue

        # NOTE: we intentionally don't pipe stdout/stderr here to avoid deadlocks.
        # Logs go to container stdout (docker logs).
        proc.p = subprocess.Popen(
            proc.cmd,
            cwd=os.getcwd(),
            stdout=None,
            stderr=None,
            text=True,
            env=os.environ.copy(),
        )
        log.info("control.worker_started", worker=proc.name, pid=proc.p.pid)
        started.append(_status(proc))

    return StartWorkersResponse(started=started, already_running=already)


@router.post("/workers/stop", response_model=list[WorkerStatus])
async def workers_stop(
    request: Request,
    which: list[Literal["collector", "tracker", "signal", "execution"]] | None = Query(
        default=None,
        description="Optional subset of workers to stop. If omitted, stops all.",
    ),
):
    _require_control_token(request)

    keys = which or ["collector", "tracker", "signal", "execution"]
    for k in keys:
        proc = _WORKERS[k]
        if proc.p is None:
            continue
        if proc.p.poll() is None:
            proc.p.terminate()
    await asyncio.sleep(0.2)
    return [_status(_WORKERS[k]) for k in keys]


class DiscoverWalletsResponse(BaseModel):
    command: str
    exit_code: int
    stdout: str = Field(default="")
    stderr: str = Field(default="")


@router.post("/discover-wallets", response_model=DiscoverWalletsResponse)
async def run_discover_wallets(
    request: Request,
    days: int = Query(default=60, ge=1, le=365),
    limit: int = Query(default=30, ge=1, le=5000),
    source: Literal["orderbook", "pnl"] = Query(default="orderbook"),
):
    _require_control_token(request)

    cmd = [
        sys.executable,
        "-m",
        "scripts.discover_wallets",
        "--days",
        str(days),
        "--limit",
        str(limit),
        "--source",
        source,
    ]
    command_str = shlex.join(cmd)
    log.info("control.discover_wallets.start", cmd=command_str)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, err_b = await proc.communicate()
    out = (out_b or b"").decode(errors="replace")
    err = (err_b or b"").decode(errors="replace")

    log.info(
        "control.discover_wallets.done",
        exit_code=proc.returncode,
        stdout_len=len(out),
        stderr_len=len(err),
    )

    return DiscoverWalletsResponse(
        command=command_str,
        exit_code=int(proc.returncode or 0),
        stdout=out[-50_000:],
        stderr=err[-50_000:],
    )

