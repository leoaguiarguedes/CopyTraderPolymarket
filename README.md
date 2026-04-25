# CopyTrader Polymarket

Bot automatizado de copytrading para a [Polymarket](https://polymarket.com), focado em **scalping/swing curto**: posições abertas por minutos a poucas horas, nunca seguradas até resolução semanal/mensal do mercado.

> **Status**: Fase 0 (setup técnico). Próxima: Fase 1 (discovery + tracking).

Veja [`PRD.md`](PRD.md) e [`spec.md`](spec.md) para a visão completa do produto e o spec técnico, e o plano detalhado em `~/.claude/plans/`.

---

## Princípios

1. **Holding curto, sempre**: time-based exit obrigatório em todas as estratégias. Não copiamos swing trader longo.
2. **Paper trading primeiro**: zero ordem on-chain até validar Sharpe > 1.5 em backtest + 30d em paper com PnL+.
3. **Score real de trader**: ranking por Sharpe + drawdown + holding period, **não** por ROI bruto.
4. **WebSocket > polling**: latência baixa é o edge; polling perde a janela.

## Arquitetura (alvo)

```
[Polymarket WS/REST] + [Subgraph]
            │
            ▼
  collector → Redis Streams (raw_trades)
            │
            ▼
  tracker  → Postgres (trades) + Streams (tracked_trades)
            │
            ▼
  signal_engine (whale_copy / consensus / fade / momentum)
            │
            ▼
  risk_manager → reject / approve
            │
            ▼
  paper_executor (Fase 1-3) | live_executor (Fase 4)
            │
            ▼
  Postgres (positions, pnl) → FastAPI → Next.js dashboard
```

## Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy async, asyncpg, Redis (Streams)
- **Data**: httpx, websockets, gql (The Graph), tenacity
- **Observability**: structlog (JSON), prometheus-client
- **Frontend** (Fase 2): Next.js 15 + TypeScript + Tailwind + shadcn/ui + TanStack Query + Recharts
- **Infra**: Docker Compose, Alembic, GitHub Actions

## Setup

Pré-requisitos: Docker + Docker Compose. Para desenvolvimento local fora do container, [uv](https://github.com/astral-sh/uv) (`pip install uv`).

```bash
git clone https://github.com/leoaguiarguedes/CopyTraderPolymarket.git
cd CopyTraderPolymarket
cp .env.example .env

# instala deps locais (opcional — só pra rodar tests/lint fora do container)
make install

# sobe stack (postgres + redis + api + workers)
make dev

# aplica migrations
make migrate

# health check
curl http://localhost:8000/health
```

## Comandos comuns

| Comando | O que faz |
|---|---|
| `make dev` | Sobe stack via docker compose |
| `make down` | Para stack |
| `make logs` | Tail de logs |
| `make test` | Roda pytest |
| `make lint` | Lint com ruff |
| `make format` | Formata com ruff |
| `make typecheck` | mypy |
| `make migrate` | Aplica migrations |
| `make migrate-create m="msg"` | Cria nova migration autogen |

## Estrutura do projeto

```
app/
├── config.py              # Settings (pydantic-settings)
├── data/                  # Polymarket REST + WS + Subgraph clients
├── tracker/               # Wallet discovery, scoring, tracking
├── signals/               # Signal engine + estratégias
├── execution/             # Paper / live executors + exit manager
├── risk/                  # Risk manager + kill switch
├── backtest/              # Replay engine + métricas + relatórios
├── storage/               # SQLAlchemy models + Alembic migrations
├── api/                   # FastAPI app + rotas
└── utils/                 # logger, metrics, time
workers/                   # collector, tracker, signal, execution
tests/                     # unit + integration + fixtures
config/                    # strategies.yaml, tracked_wallets.yaml
web/                       # Next.js frontend (Fase 2)
```

## Roadmap

- **Fase 0** ✅ Setup técnico
- **Fase 1** 🚧 MVP: discovery + tracking (2 semanas)
- **Fase 2** Signal engine + paper execution + dashboard web (3-4 semanas)
- **Fase 3** Backtest engine (1-2 semanas)
- **Fase 4** Live execution (após validação)

## Riscos conhecidos

- Edge pode não existir na prática → backtest brutal antes de capital real.
- Front-running por bots mais rápidos → confidence threshold alto + size pequeno.
- Polymarket muda API → camada `data/` isola; testes de contrato.

## Licença

Proprietário. Não distribuir sem autorização.
