"""Backtest report generator — produces HTML (with embedded chart) and CSV.

Usage:
    result  = await engine.run(...)
    metrics = compute_metrics(result.positions)
    html    = generate_html_report(result, metrics)
    csv_str = generate_csv(result.positions)
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.backtest.engine import BacktestResult
    from app.backtest.metrics import BacktestMetrics


def generate_csv(positions: list) -> str:
    """Return CSV string of all closed positions."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "position_id", "strategy", "market_id", "side",
        "entry_price", "exit_price", "size_usd", "realized_pnl_usd",
        "exit_reason", "opened_at", "closed_at", "holding_minutes",
    ])
    for p in positions:
        if p.closed_at is None or p.realized_pnl_usd is None:
            continue
        holding = (p.closed_at - p.opened_at).total_seconds() / 60 if p.opened_at else ""
        writer.writerow([
            p.position_id,
            p.strategy,
            p.market_id,
            p.side,
            f"{float(p.entry_price):.6f}",
            f"{float(p.exit_price):.6f}" if p.exit_price else "",
            f"{float(p.size_usd):.2f}",
            f"{float(p.realized_pnl_usd):.4f}",
            p.exit_reason,
            p.opened_at.isoformat() if p.opened_at else "",
            p.closed_at.isoformat() if p.closed_at else "",
            f"{holding:.1f}" if isinstance(holding, float) else "",
        ])
    return buf.getvalue()


def _fmt_pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def _fmt_usd(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}${v:,.2f}"


def _color(v: float, reverse: bool = False) -> str:
    positive = v > 0 if not reverse else v < 0
    return "#4ade80" if positive else ("#f87171" if (v < 0 if not reverse else v > 0) else "#a1a1aa")


def generate_html_report(result: "BacktestResult", metrics: "BacktestMetrics | None") -> str:
    """Generate a self-contained HTML backtest report (no external dependencies)."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    start = result.start_date.strftime("%Y-%m-%d")
    end = result.end_date.strftime("%Y-%m-%d")

    # Equity curve data for Chart.js via CDN
    equity_labels_js = "[]"
    equity_data_js = "[]"
    if metrics and metrics.equity_curve:
        labels = list(range(1, len(metrics.equity_curve) + 1))
        equity_labels_js = json.dumps(labels)
        equity_data_js = json.dumps([round(v, 4) for v in metrics.equity_curve])

    if metrics is None:
        metrics_html = "<p style='color:#a1a1aa'>Nenhuma posição fechada — sem métricas.</p>"
    else:
        pf = f"{metrics.profit_factor:.2f}" if metrics.profit_factor != float("inf") else "∞"
        rows = [
            ("Trades", str(metrics.n_trades)),
            ("Ganhos / Perdas", f"{metrics.n_wins} / {metrics.n_losses}"),
            ("Taxa de acerto", _fmt_pct(metrics.win_rate)),
            ("P/L total", _fmt_usd(metrics.total_pnl_usd)),
            ("ROI", _fmt_pct(metrics.roi)),
            ("Sharpe (simplificado)", f"{metrics.sharpe:.3f}"),
            ("Max drawdown", _fmt_pct(metrics.max_drawdown)),
            ("Ganho médio", _fmt_usd(metrics.avg_win_usd)),
            ("Perda média", _fmt_usd(-metrics.avg_loss_usd)),
            ("Fator de lucro", pf),
            ("Expectativa/trade", _fmt_usd(metrics.expectancy_usd)),
            ("Holding médio (min)", f"{metrics.avg_holding_minutes:.1f}"),
            ("Holding mediano (min)", f"{metrics.median_holding_minutes:.1f}"),
            ("Saídas por TP", _fmt_pct(metrics.pct_tp_exits)),
            ("Saídas por SL", _fmt_pct(metrics.pct_sl_exits)),
            ("Saídas por timeout", _fmt_pct(metrics.pct_timeout_exits)),
        ]
        rows_html = "\n".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows
        )
        metrics_html = f"""
        <table class="metrics-table">
          <tbody>{rows_html}</tbody>
        </table>
        """

    # Positions table (last 50)
    positions_rows = ""
    closed = sorted(
        [p for p in result.positions if p.closed_at and p.realized_pnl_usd is not None],
        key=lambda p: p.closed_at,  # type: ignore[arg-type]
        reverse=True,
    )[:50]
    for p in closed:
        pnl = float(p.realized_pnl_usd)  # type: ignore[arg-type]
        color = _color(pnl)
        holding = f"{(p.closed_at - p.opened_at).total_seconds() / 60:.0f}m" if p.closed_at and p.opened_at else ""
        positions_rows += f"""
        <tr>
          <td>{p.strategy}</td>
          <td style="font-size:0.75em">{p.market_id[:16]}…</td>
          <td>{p.side}</td>
          <td>{float(p.entry_price):.4f}</td>
          <td>{float(p.exit_price):.4f if p.exit_price else ""}</td>
          <td>{float(p.size_usd):.2f}</td>
          <td style="color:{color};font-weight:600">{_fmt_usd(pnl)}</td>
          <td>{p.exit_reason}</td>
          <td>{holding}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Backtest — {result.strategy} ({start} → {end})</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #09090b; color: #e4e4e7; font-family: 'Inter', system-ui, sans-serif; padding: 2rem; }}
    h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; }}
    .meta {{ color: #71717a; font-size: 0.875rem; margin-bottom: 2rem; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
    .card {{ background: #18181b; border: 1px solid #27272a; border-radius: 0.75rem; padding: 1.25rem; }}
    .card h2 {{ font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; color: #a1a1aa; margin-bottom: 1rem; }}
    .metrics-table {{ width: 100%; border-collapse: collapse; }}
    .metrics-table td {{ padding: 0.35rem 0.5rem; border-bottom: 1px solid #27272a; font-size: 0.875rem; }}
    .metrics-table td:first-child {{ color: #a1a1aa; }}
    .metrics-table td:last-child {{ text-align: right; font-weight: 500; }}
    .signals-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-bottom: 2rem; }}
    .stat {{ background: #18181b; border: 1px solid #27272a; border-radius: 0.5rem; padding: 1rem; }}
    .stat .label {{ font-size: 0.75rem; color: #71717a; margin-bottom: 0.25rem; }}
    .stat .value {{ font-size: 1.5rem; font-weight: 700; }}
    .chart-wrap {{ width: 100%; height: 300px; }}
    table.positions {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
    table.positions th {{ text-align: left; padding: 0.5rem; border-bottom: 1px solid #27272a; color: #71717a; font-weight: 500; }}
    table.positions td {{ padding: 0.4rem 0.5rem; border-bottom: 1px solid #18181b; }}
    @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} .signals-grid {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <h1>Backtest — {result.strategy}</h1>
  <p class="meta">Janela: {start} → {end} &nbsp;|&nbsp; Wallets: {len(result.wallets)} &nbsp;|&nbsp; Gerado: {now}</p>

  <div class="signals-grid">
    <div class="stat"><div class="label">Sinais gerados</div><div class="value">{result.signals_total}</div></div>
    <div class="stat"><div class="label">Aprovados</div><div class="value" style="color:#4ade80">{result.signals_approved}</div></div>
    <div class="stat"><div class="label">Rejeitados</div><div class="value" style="color:#f87171">{result.signals_rejected}</div></div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Métricas</h2>
      {metrics_html}
    </div>
    <div class="card">
      <h2>Curva de patrimônio (P/L cumulativo por trade)</h2>
      <div class="chart-wrap">
        <canvas id="equityCurve"></canvas>
      </div>
    </div>
  </div>

  <div class="card" style="margin-bottom:2rem">
    <h2>Últimas posições (máx. 50)</h2>
    <table class="positions">
      <thead>
        <tr>
          <th>Estratégia</th><th>Market</th><th>Lado</th><th>Entrada</th>
          <th>Saída</th><th>Size $</th><th>P/L</th><th>Motivo</th><th>Holding</th>
        </tr>
      </thead>
      <tbody>
        {positions_rows or '<tr><td colspan="9" style="color:#71717a;text-align:center;padding:1rem">Nenhuma posição fechada</td></tr>'}
      </tbody>
    </table>
  </div>

  <script>
    const ctx = document.getElementById('equityCurve').getContext('2d');
    const labels = {equity_labels_js};
    const data = {equity_data_js};
    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels,
        datasets: [{{
          label: 'P/L cumulativo ($)',
          data,
          borderColor: data.length > 0 && data[data.length-1] >= 0 ? '#4ade80' : '#f87171',
          backgroundColor: 'transparent',
          pointRadius: data.length <= 50 ? 3 : 0,
          tension: 0.2,
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{
          x: {{ ticks: {{ color: '#71717a' }}, grid: {{ color: '#27272a' }} }},
          y: {{ ticks: {{ color: '#71717a' }}, grid: {{ color: '#27272a' }} }},
        }},
        plugins: {{ legend: {{ labels: {{ color: '#e4e4e7' }} }} }},
      }}
    }});
  </script>
</body>
</html>"""
    return html
