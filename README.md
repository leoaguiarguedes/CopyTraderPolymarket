# CopyTrader Polymarket

Bot automatizado de copytrading para a [Polymarket](https://polymarket.com), focado em **scalping/swing curto**: posições abertas por minutos a poucas horas, nunca seguradas até resolução semanal/mensal do mercado.

> **Status**: Fase 2+ em progresso. Backtest engine implementado. Frontend refatorado com paginação. Próximo passo: Fase 3 — validação histórica completa e live execution.

Veja [`PRD.md`](PRD.md), [`spec.md`](spec.md) e [`plan.md`](plan.md) para a visão do produto, o spec técnico e o plano detalhado.

---

## O que já está implementado

- Backend Python com FastAPI, Redis Streams, PostgreSQL e WebSocket live feed.
- Engine de sinais em `app/signals/` com múltiplas estratégias.
- `app/execution/paper_executor.py` para paper trading contra orderbook real.
- `app/execution/exit_manager.py` com TP/SL, timeout e sincronia com `endDate` do mercado.
- `app/risk/` com validações de exposição, drawdown e kill switch.
- **Backtest engine** em `app/backtest/` com replay de trades, métricas detalhadas e relatórios.
- Frontend Next.js em `web/` com cliente WebSocket para feed live e components refatorados com Client-side rendering.
- **Paginação e sorting** em tabelas (Portfolio, Signals, Traders) com suporte a múltiplos tamanhos de página.
- CI básico, testes e observabilidade via Prometheus.

## Princípios

1. **Holding curto, sempre**: time-based exit obrigatório em todas as estratégias.
2. **Paper trading primeiro**: ordens reais só depois de validação histórica e 30d de paper com PnL+.
3. **Score real de trader**: ranking por consistência, drawdown e holding period, não por ROI bruto.
4. **WebSocket > polling**: latência baixa é o edge.

## Arquitetura atual

```text
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
  paper_executor
            │
            ▼
  Postgres (positions, pnl) → FastAPI → Next.js dashboard
```

## Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy async, asyncpg, Redis Streams
- **Data**: httpx, websockets, gql (The Graph), tenacity
- **Observability**: structlog (JSON), prometheus-client
- **Frontend**: Next.js 15 + TypeScript + Tailwind + TanStack Query + Recharts
- **Infra**: Docker Compose, Alembic, GitHub Actions

## Setup

Pré-requisitos: Docker + Docker Compose.

```bash
git clone https://github.com/leoaguiarguedes/CopyTraderPolymarket.git
cd CopyTraderPolymarket
cp .env.example .env

make install
make dev
make migrate
curl http://localhost:8000/health
```

Frontend disponível em: `http://localhost:3000`
- Portfolio: `/portfolio` — Posições com paginação e sorting
- Signals: `/signals` — Sinais ativas com paginação e sorting
- Traders: `/traders` — Traders rastreados com paginação e sorting
- Backtest: `/backtest` — Histórico de execuções de backtest

## Comandos comuns

| Comando | O que faz |
|---|---|
| `make dev` | Sobe stack via docker compose |
| `make down` | Para stack |
| `make logs` | Tail de logs |
| `make test` | Roda pytest |
| `make lint` | Lint com ruff |
| `make format` | Formata com ruff |
| `make typecheck` | Executa mypy |
| `make migrate` | Aplica migrations |
| `make migrate-create m="msg"` | Cria nova migration |

## Estrutura do projeto

```text
app/
├── config.py              # Settings (pydantic-settings)
├── data/                  # Polymarket REST + WS + Subgraph clients
├── tracker/               # Wallet discovery, scoring, tracking
├── signals/               # Signal engine + estratégias
├── execution/             # Paper executor + exit manager
├── risk/                  # Risk manager + kill switch
├── backtest/              # Replay engine + métricas + relatórios (em desenvolvimento)
├── storage/               # SQLAlchemy models + Alembic migrations
├── api/                   # FastAPI app + rotas
└── utils/                 # logger, metrics, time
workers/                   # collector, tracker, signal, execution
tests/                     # unit + integration + fixtures
config/                    # strategies.yaml, tracked_wallets.yaml
web/                       # Next.js frontend
├── src/app/
│   ├── portfolio/         # PortfolioPageClient com paginação e sorting
│   ├── signals/           # SignalsPageClient com paginação e sorting
│   ├── traders/           # TradersPageClient com paginação e sorting
│   └── backtest/          # Backtest page com histórico de testes
├── src/components/
│   ├── TableControls.tsx  # Componentes reutilizáveis de paginação e sorting
│   └── ...
└── ...
```

## Roadmap

- **Fase 0** ✅ Setup técnico
- **Fase 1** ✅ MVP: discovery + tracking
- **Fase 2** ✅ Signal engine + paper execution + dashboard web + backtest engine
- **Fase 3** 🚧 Validação histórica completa + refinamento de estratégias
- **Fase 4** ⏳ Live execution (após validação completa)

## Próximo passo

- Executar validação histórica completa usando backtest engine.
- Refinar thresholds e parâmetros de estratégias baseado em resultados de backtest.
- Implementar mecanismos de live execution de forma segura.

## Mudanças Recentes (Abril 2026)

- **Frontend Refatorado**: Componentes movidos para Client-side rendering (PortfolioPageClient, SignalsPageClient, TradersPageClient)
- **Paginação Implementada**: Tabelas de posições, sinais e traders suportam paginação com opções de 25, 50, 100 ou 200 itens por página
- **Sorting Adicionado**: Headers de tabelas agora permitem ordenação por coluna (crescente/decrescente)
- **Novo Componente**: `TableControls.tsx` com componentes reutilizáveis para paginação e sorting
- **Backtest Persistence**: Adicionada migração para persistência de posições de backtest no banco de dados

## Riscos conhecidos

- Edge pode não existir na prática → backtest bruto antes de capital real.
- Front-running por bots mais rápidos → confidence threshold alto + size pequeno.
- Polymarket muda API → camada `data/` isola; testes de contrato obrigatórios.

## Licença

Proprietário. Não distribuir sem autorização.
