"""Backtest API routes.

POST /backtest/run              — start a backtest (runs in background task)
GET  /backtest/runs             — list all runs (newest first)
GET  /backtest/runs/{run_id}    — get full result for a run
GET  /backtest/runs/{run_id}/report  — HTML report
GET  /backtest/runs/{run_id}/csv     — CSV of positions
DELETE /backtest/runs/{run_id}  — delete a run

POST /backtest/grid-search      — parameter sweep, returns top configs by Sharpe
GET  /backtest/grid-search/{run_id}

POST /backtest/walk-forward     — 60/40 temporal split validation
GET  /backtest/walk-forward/{run_id}
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.backtest.engine import BacktestEngine, BacktestResult
from app.backtest.grid_search import GridSearchEngine, GridSearchResult
from app.backtest.metrics import BacktestMetrics, compute_metrics
from app.backtest.reports import generate_csv, generate_html_report
from app.backtest.walk_forward import WalkForwardEngine, WalkForwardResult
from app.execution.base import Position
from app.storage.db import AsyncSessionFactory
from app.storage.models import BacktestRun
from app.utils.logger import get_logger
from sqlalchemy import select, delete

log = get_logger(__name__)
router = APIRouter(prefix="/backtest", tags=["backtest"])

# In-memory store of results (complements DB row — holds full positions list)
_results: dict[str, BacktestResult] = {}


class RunRequest(BaseModel):
    strategy: str = Field(..., description="Strategy name: whale_copy | consensus | momentum_odds")
    start_date: datetime
    end_date: datetime
    wallets: list[str] = Field(default_factory=list, description="Wallet addresses (empty = use tracked_wallets.yaml)")
    params: dict[str, Any] = Field(default_factory=dict, description="Strategy param overrides")
    capital_usd: float = Field(default=10_000.0, ge=100.0)


class RunSummary(BaseModel):
    run_id: str
    strategy: str
    start_date: datetime
    end_date: datetime
    status: str
    n_wallets: int
    n_trades: int | None
    total_pnl_usd: float | None
    roi: float | None
    sharpe: float | None
    win_rate: float | None
    max_drawdown: float | None
    pct_timeout_exits: float | None
    error: str
    created_at: datetime
    finished_at: datetime | None


def _row_to_summary(row: BacktestRun) -> RunSummary:
    wallets = json.loads(row.wallets_json or "[]")
    return RunSummary(
        run_id=row.run_id,
        strategy=row.strategy,
        start_date=row.start_date,
        end_date=row.end_date,
        status=row.status,
        n_wallets=len(wallets),
        n_trades=row.n_trades,
        total_pnl_usd=float(row.total_pnl_usd) if row.total_pnl_usd is not None else None,
        roi=float(row.roi) if row.roi is not None else None,
        sharpe=float(row.sharpe) if row.sharpe is not None else None,
        win_rate=float(row.win_rate) if row.win_rate is not None else None,
        max_drawdown=float(row.max_drawdown) if row.max_drawdown is not None else None,
        pct_timeout_exits=float(row.pct_timeout_exits) if row.pct_timeout_exits is not None else None,
        error=row.error or "",
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


def _position_to_dict(position: Position) -> dict[str, Any]:
    return {
        "position_id": position.position_id,
        "signal_id": position.signal_id,
        "strategy": position.strategy,
        "market_id": position.market_id,
        "asset_id": position.asset_id,
        "side": position.side,
        "entry_price": str(position.entry_price),
        "size_usd": str(position.size_usd),
        "size_tokens": str(position.size_tokens),
        "tp_price": str(position.tp_price),
        "sl_price": str(position.sl_price),
        "max_holding_minutes": position.max_holding_minutes,
        "opened_at": position.opened_at.isoformat(),
        "closed_at": position.closed_at.isoformat() if position.closed_at else None,
        "exit_price": str(position.exit_price) if position.exit_price is not None else None,
        "realized_pnl_usd": str(position.realized_pnl_usd) if position.realized_pnl_usd is not None else None,
        "exit_reason": position.exit_reason,
    }


def _position_from_dict(data: dict[str, Any]) -> Position:
    return Position(
        position_id=data["position_id"],
        signal_id=data["signal_id"],
        strategy=data["strategy"],
        market_id=data["market_id"],
        asset_id=data["asset_id"],
        side=data["side"],
        entry_price=Decimal(str(data["entry_price"])),
        size_usd=Decimal(str(data["size_usd"])),
        size_tokens=Decimal(str(data["size_tokens"])),
        tp_price=Decimal(str(data["tp_price"])),
        sl_price=Decimal(str(data["sl_price"])),
        max_holding_minutes=int(data["max_holding_minutes"]),
        opened_at=datetime.fromisoformat(data["opened_at"]),
        closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
        exit_price=Decimal(str(data["exit_price"])) if data.get("exit_price") is not None else None,
        realized_pnl_usd=Decimal(str(data["realized_pnl_usd"])) if data.get("realized_pnl_usd") is not None else None,
        exit_reason=data.get("exit_reason", ""),
    )


def _result_from_row(row: BacktestRun) -> BacktestResult:
    return BacktestResult(
        run_id=row.run_id,
        strategy=row.strategy,
        start_date=row.start_date,
        end_date=row.end_date,
        wallets=json.loads(row.wallets_json or "[]"),
        params=json.loads(row.params_json or "{}"),
        positions=[_position_from_dict(item) for item in json.loads(row.positions_json or "[]")],
        signals_total=row.signals_total,
        signals_approved=row.signals_approved,
        signals_rejected=row.signals_rejected,
        error=row.error or "",
        finished_at=row.finished_at,
    )


async def _load_result(run_id: str) -> BacktestResult | None:
    cached = _results.get(run_id)
    if cached is not None:
        return cached

    async with AsyncSessionFactory() as session:
        row = await session.get(BacktestRun, run_id)
    if row is None or not row.positions_json:
        return None
    return _result_from_row(row)


async def _persist_run(result: BacktestResult, metrics: BacktestMetrics | None) -> None:
    """Upsert a BacktestRun row in the DB."""
    try:
        async with AsyncSessionFactory() as session:
            existing = await session.get(BacktestRun, result.run_id)
            if existing is None:
                row = BacktestRun(run_id=result.run_id)
                session.add(row)
            else:
                row = existing

            row.strategy = result.strategy
            row.start_date = result.start_date
            row.end_date = result.end_date
            row.wallets_json = json.dumps(result.wallets)
            row.params_json = json.dumps(result.params)
            row.status = "error" if result.error else "done"
            row.error = result.error
            row.finished_at = result.finished_at
            row.signals_total = result.signals_total
            row.signals_approved = result.signals_approved
            row.signals_rejected = result.signals_rejected
            row.positions_json = json.dumps([_position_to_dict(p) for p in result.positions])

            if metrics:
                row.n_trades = metrics.n_trades
                row.total_pnl_usd = Decimal(str(round(metrics.total_pnl_usd, 4)))
                row.roi = Decimal(str(round(metrics.roi, 8)))
                row.sharpe = Decimal(str(round(metrics.sharpe, 8)))
                row.max_drawdown = Decimal(str(round(metrics.max_drawdown, 6)))
                row.win_rate = Decimal(str(round(metrics.win_rate, 6)))
                row.pct_timeout_exits = Decimal(str(round(metrics.pct_timeout_exits, 6)))
                row.metrics_json = json.dumps({
                    "n_trades": metrics.n_trades,
                    "n_wins": metrics.n_wins,
                    "n_losses": metrics.n_losses,
                    "win_rate": metrics.win_rate,
                    "total_pnl_usd": metrics.total_pnl_usd,
                    "roi": metrics.roi,
                    "avg_pnl_usd": metrics.avg_pnl_usd,
                    "avg_win_usd": metrics.avg_win_usd,
                    "avg_loss_usd": metrics.avg_loss_usd,
                    "profit_factor": metrics.profit_factor if metrics.profit_factor != float("inf") else 9999.0,
                    "expectancy_usd": metrics.expectancy_usd,
                    "sharpe": metrics.sharpe,
                    "max_drawdown": metrics.max_drawdown,
                    "avg_holding_minutes": metrics.avg_holding_minutes,
                    "median_holding_minutes": metrics.median_holding_minutes,
                    "pct_tp_exits": metrics.pct_tp_exits,
                    "pct_sl_exits": metrics.pct_sl_exits,
                    "pct_timeout_exits": metrics.pct_timeout_exits,
                    "equity_curve": metrics.equity_curve,
                })

            await session.commit()
    except Exception as exc:
        log.error("backtest.persist_error", run_id=result.run_id[:8], error=str(exc)[:100])


async def _run_backtest(req: RunRequest, run_id: str) -> None:
    """Background task that executes the backtest and persists results."""
    wallets = req.wallets
    if not wallets:
        try:
            import yaml
            with open("config/tracked_wallets.yaml") as f:
                data = yaml.safe_load(f) or {}
            wallets = [w["address"] for w in data.get("wallets", [])]
        except Exception as exc:
            log.warning("backtest.no_wallets", error=str(exc)[:60])

    if not wallets:
        result = BacktestResult(
            run_id=run_id,
            strategy=req.strategy,
            start_date=req.start_date,
            end_date=req.end_date,
            wallets=[],
            params=req.params,
            error="no tracked wallets configured",
            finished_at=datetime.now(tz=timezone.utc),
        )
        _results[run_id] = result
        await _persist_run(result, None)
        return

    engine = BacktestEngine()
    result = await engine.run(
        strategy=req.strategy,
        start_date=req.start_date,
        end_date=req.end_date,
        wallets=wallets,
        params=req.params,
        capital_usd=req.capital_usd,
        run_id=run_id,
    )
    result.wallets = wallets
    _results[run_id] = result

    metrics = compute_metrics(result.positions)
    await _persist_run(result, metrics)
    log.info("backtest.background_done", run_id=run_id[:8])


async def _create_pending_row(run_id: str, req: RunRequest) -> None:
    try:
        async with AsyncSessionFactory() as session:
            row = BacktestRun(
                run_id=run_id,
                strategy=req.strategy,
                start_date=req.start_date,
                end_date=req.end_date,
                wallets_json=json.dumps(req.wallets),
                params_json=json.dumps(req.params),
                status="running",
                created_at=datetime.now(tz=timezone.utc),
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        log.warning("backtest.pending_row_error", error=str(exc)[:60])


@router.post("/run", status_code=202)
async def start_backtest(req: RunRequest, bg: BackgroundTasks):
    """Enqueue a backtest run. Returns immediately with run_id."""
    import uuid
    run_id = str(uuid.uuid4())
    await _create_pending_row(run_id, req)
    bg.add_task(_run_backtest, req, run_id)
    return {"run_id": run_id, "status": "running"}


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(limit: int = 20, strategy: str | None = None):
    """List backtest runs, newest first."""
    async with AsyncSessionFactory() as session:
        stmt = select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
        if strategy:
            stmt = stmt.where(BacktestRun.strategy == strategy)
        rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_summary(r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunSummary)
async def get_run(run_id: str):
    """Get summary for a single run."""
    async with AsyncSessionFactory() as session:
        row = await session.get(BacktestRun, run_id)
    if row is None:
        raise HTTPException(404, "run not found")
    return _row_to_summary(row)


@router.get("/runs/{run_id}/metrics")
async def get_run_metrics(run_id: str):
    """Get full metrics JSON for a run (includes equity_curve)."""
    # Try in-memory first (faster, has equity_curve)
    if run_id in _results:
        result = _results[run_id]
        metrics = compute_metrics(result.positions)
        if metrics is None:
            return {"error": "no closed positions"}
        return {
            "n_trades": metrics.n_trades,
            "n_wins": metrics.n_wins,
            "n_losses": metrics.n_losses,
            "win_rate": metrics.win_rate,
            "total_pnl_usd": metrics.total_pnl_usd,
            "roi": metrics.roi,
            "avg_pnl_usd": metrics.avg_pnl_usd,
            "avg_win_usd": metrics.avg_win_usd,
            "avg_loss_usd": metrics.avg_loss_usd,
            "profit_factor": metrics.profit_factor if metrics.profit_factor != float("inf") else 9999.0,
            "expectancy_usd": metrics.expectancy_usd,
            "sharpe": metrics.sharpe,
            "max_drawdown": metrics.max_drawdown,
            "avg_holding_minutes": metrics.avg_holding_minutes,
            "median_holding_minutes": metrics.median_holding_minutes,
            "pct_tp_exits": metrics.pct_tp_exits,
            "pct_sl_exits": metrics.pct_sl_exits,
            "pct_timeout_exits": metrics.pct_timeout_exits,
            "equity_curve": metrics.equity_curve,
        }

    # Fall back to DB
    async with AsyncSessionFactory() as session:
        row = await session.get(BacktestRun, run_id)
    if row is None:
        raise HTTPException(404, "run not found")
    if row.metrics_json:
        return json.loads(row.metrics_json)
    return {"error": "metrics not yet computed"}


@router.get("/runs/{run_id}/report", response_class=HTMLResponse)
async def get_run_report(run_id: str):
    """Return self-contained HTML report for a run."""
    result = await _load_result(run_id)
    if result is None:
        raise HTTPException(404, "run not found")
    metrics = compute_metrics(result.positions)
    html = generate_html_report(result, metrics)
    return HTMLResponse(content=html)


@router.get("/runs/{run_id}/csv")
async def get_run_csv(run_id: str):
    """Return CSV of all positions for a run."""
    result = await _load_result(run_id)
    if result is None:
        raise HTTPException(404, "run not found")
    csv_str = generate_csv(result.positions)
    return PlainTextResponse(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="backtest_{run_id[:8]}.csv"'},
    )


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: str):
    """Delete a backtest run."""
    _results.pop(run_id, None)
    async with AsyncSessionFactory() as session:
        await session.execute(delete(BacktestRun).where(BacktestRun.run_id == run_id))
        await session.commit()


# ── Grid Search ───────────────────────────────────────────────────────────────

_grid_results: dict[str, GridSearchResult] = {}


class GridSearchRequest(BaseModel):
    strategy: str
    start_date: datetime
    end_date: datetime
    wallets: list[str] = Field(default_factory=list)
    param_grid: dict[str, list[Any]] = Field(
        ...,
        description="Map of param name → list of values to sweep",
        example={
            "min_trade_size_usd": [50, 100, 250],
            "tp_pct": [0.10, 0.15, 0.20],
            "sl_pct": [0.05, 0.07],
        },
    )
    capital_usd: float = Field(default=10_000.0, ge=100.0)
    top_n: int = Field(default=10, ge=1, le=50)


def _metrics_dict(m: BacktestMetrics | None) -> dict | None:
    if m is None:
        return None
    return {
        "n_trades": m.n_trades,
        "win_rate": m.win_rate,
        "total_pnl_usd": m.total_pnl_usd,
        "roi": m.roi,
        "sharpe": m.sharpe,
        "max_drawdown": m.max_drawdown,
        "profit_factor": m.profit_factor if m.profit_factor != float("inf") else 9999.0,
        "expectancy_usd": m.expectancy_usd,
        "avg_holding_minutes": m.avg_holding_minutes,
        "pct_tp_exits": m.pct_tp_exits,
        "pct_sl_exits": m.pct_sl_exits,
        "pct_timeout_exits": m.pct_timeout_exits,
        "equity_curve": m.equity_curve,
    }


async def _run_grid_search(req: GridSearchRequest, run_id: str) -> None:
    wallets = req.wallets
    if not wallets:
        try:
            import yaml
            with open("config/tracked_wallets.yaml") as f:
                data = yaml.safe_load(f) or {}
            wallets = [w["address"] for w in data.get("wallets", [])]
        except Exception:
            pass

    engine = GridSearchEngine()
    result = await engine.run(
        strategy=req.strategy,
        start_date=req.start_date,
        end_date=req.end_date,
        wallets=wallets,
        param_grid=req.param_grid,
        capital_usd=req.capital_usd,
        top_n=req.top_n,
    )
    result.run_id = run_id
    result.wallets = wallets
    _grid_results[run_id] = result


@router.post("/grid-search", status_code=202)
async def start_grid_search(req: GridSearchRequest, bg: BackgroundTasks):
    """Enqueue a grid search. Returns run_id immediately."""
    import uuid as _uuid
    run_id = str(_uuid.uuid4())
    _grid_results[run_id] = GridSearchResult(
        run_id=run_id,
        strategy=req.strategy,
        start_date=req.start_date,
        end_date=req.end_date,
        wallets=req.wallets,
        param_grid=req.param_grid,
        total_combinations=0,
        completed=0,
    )
    bg.add_task(_run_grid_search, req, run_id)
    return {"run_id": run_id, "status": "running"}


@router.get("/grid-search/{run_id}")
async def get_grid_search(run_id: str):
    """Get grid search result."""
    result = _grid_results.get(run_id)
    if result is None:
        raise HTTPException(404, "grid search not found or still running")

    return {
        "run_id": result.run_id,
        "strategy": result.strategy,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "param_grid": result.param_grid,
        "total_combinations": result.total_combinations,
        "completed": result.completed,
        "status": "error" if result.error else ("running" if result.finished_at is None else "done"),
        "error": result.error,
        "finished_at": result.finished_at,
        "top_configs": [
            {
                "params": c.params,
                "n_trades": c.n_trades,
                "sharpe": c.sharpe,
                "roi": c.roi,
                "win_rate": c.win_rate,
                "total_pnl_usd": c.total_pnl_usd,
                "max_drawdown": c.max_drawdown,
                "profit_factor": c.profit_factor,
                "pct_timeout_exits": c.pct_timeout_exits,
            }
            for c in result.top_configs
        ],
    }


# ── Walk-Forward ──────────────────────────────────────────────────────────────

_wf_results: dict[str, WalkForwardResult] = {}


class WalkForwardRequest(BaseModel):
    strategy: str
    start_date: datetime
    end_date: datetime
    wallets: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    capital_usd: float = Field(default=10_000.0, ge=100.0)


async def _run_walk_forward(req: WalkForwardRequest, run_id: str) -> None:
    wallets = req.wallets
    if not wallets:
        try:
            import yaml
            with open("config/tracked_wallets.yaml") as f:
                data = yaml.safe_load(f) or {}
            wallets = [w["address"] for w in data.get("wallets", [])]
        except Exception:
            pass

    engine = WalkForwardEngine()
    result = await engine.run(
        strategy=req.strategy,
        start_date=req.start_date,
        end_date=req.end_date,
        wallets=wallets,
        params=req.params,
        capital_usd=req.capital_usd,
    )
    result.run_id = run_id
    result.wallets = wallets
    _wf_results[run_id] = result


@router.post("/walk-forward", status_code=202)
async def start_walk_forward(req: WalkForwardRequest, bg: BackgroundTasks):
    """Enqueue a walk-forward validation run."""
    import uuid as _uuid
    run_id = str(_uuid.uuid4())
    _wf_results[run_id] = WalkForwardResult(
        run_id=run_id,
        strategy=req.strategy,
        full_start=req.start_date,
        full_end=req.end_date,
        split_date=req.start_date,
        wallets=req.wallets,
        params=req.params,
    )
    bg.add_task(_run_walk_forward, req, run_id)
    return {"run_id": run_id, "status": "running"}


@router.get("/walk-forward/{run_id}")
async def get_walk_forward(run_id: str):
    """Get walk-forward result."""
    result = _wf_results.get(run_id)
    if result is None:
        raise HTTPException(404, "walk-forward not found or still running")

    return {
        "run_id": result.run_id,
        "strategy": result.strategy,
        "full_start": result.full_start,
        "full_end": result.full_end,
        "split_date": result.split_date,
        "in_start": result.in_start,
        "in_end": result.in_end,
        "out_start": result.out_start,
        "out_end": result.out_end,
        "params": result.params,
        "status": "error" if result.error else ("running" if result.finished_at is None else "done"),
        "error": result.error,
        "finished_at": result.finished_at,
        "overfit_flag": result.overfit_flag,
        "divergence": result.divergence,
        "in_signals": result.in_signals,
        "out_signals": result.out_signals,
        "in_positions": result.in_positions,
        "out_positions": result.out_positions,
        "in_sample": _metrics_dict(result.in_sample),
        "out_sample": _metrics_dict(result.out_sample),
    }
