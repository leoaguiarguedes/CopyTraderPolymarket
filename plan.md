# Plano — CopyTrader Polymarket

## Contexto

O repositório `CopyTraderPolymarket` está vazio (apenas `PRD.md` e `spec.md`). O objetivo é construir um bot que identifica traders consistentes na Polymarket, copia entradas relevantes com filtros de qualidade/timing, e executa trades de curto prazo com risk management. O PRD/spec definem as 4 fases (MVP → Signals → Execução → Backtest/otimização), stack Python e arquitetura orientada a eventos.

Decisões confirmadas com o usuário:
- **Escopo**: sistema completo (Fases 1-4) com sugestões de melhoria sobre o spec original.
- **Execução**: paper trading primeiro (sem ordens on-chain até validar edge).
- **Dados**: híbrido — REST oficial (Gamma + CLOB) para tempo real + Subgraph (The Graph) para histórico/ranking.
- **Repositório remoto**: https://github.com/leoaguiarguedes/CopyTraderPolymarket — commits irão pra lá.
- **Holding period curto (CONSTRAINT CRÍTICA)**: scalping/swing curto, **nunca** segurar até resolução semanal/mensal do mercado. Alvo: posições fecham em **minutos a poucas horas, máximo 24-48h**. Isso muda profundamente: seleção de mercados, scoring de wallets, exit manager e risk manager — detalhes nas seções relevantes.

---

## Constraint: short holding period

Como esse princípio toca várias camadas, consolidação centralizada (cada item será aplicado na seção da fase correspondente):

- **Seleção de mercados (data layer)**: filtrar mercados com `time_to_resolution > 7d` por padrão. Preferir mercados com volume diário alto (rotatividade = saída fácil). Evitar mercados com `endDate` muito próximo (<6h) — risco de execução travada por baixa liquidez no fim.
- **Wallet scoring**: adicionar métrica `avg_holding_period` no scoring. **Filtrar wallets com holding médio > 48h** — copiar swing trader longo destrói a estratégia. Preferir wallets com holding mediano de minutos a horas.
- **Estratégias**: cada estratégia define `max_holding_minutes` próprio (ex: whale_copy=240min, momentum=60min). Sem isso, o sinal só é gerado se o trader-fonte mostra padrão de saída rápida.
- **Exit manager**: além de TP/SL, **time-based exit obrigatório**: força saída ao atingir `max_holding_minutes`, mesmo que sem TP/SL. Evita "esquecer" posição.
- **Risk manager**: rejeita signal se `time_to_resolution < max_holding_minutes` (não daria pra sair antes de virar binário). Rejeita se mercado tem orderbook depth insuficiente pra desfazer a posição.
- **Backtest**: sempre simular saída por timeout além de TP/SL — métrica `% trades exited by timeout` deve ser visível no relatório.
- **Frontend**: cada posição em `/portfolio` mostra "age" + "time to forced exit" — banner vermelho se passar limite.

---

## Sugestões de melhoria sobre o spec original

Antes do plano de execução, ajustes que aumentam edge/robustez e custam pouco extra:

1. **WebSocket > polling**: o spec usa polling (`while True: get_recent_trades()`). O CLOB da Polymarket expõe `wss://ws-subscriptions-clob.polymarket.com` com canal `market` e `user`. Usar WebSocket reduz latência de detecção de trades de ~5-30s para <1s — isso é literalmente o "delay-aware" do PRD.
2. **Proxy wallets**: Polymarket usa Gnosis Safe proxy por usuário. A wallet visível na UI não é a EOA assinante; é o proxy. O tracker precisa mapear `proxy → owner` corretamente, senão monitora o endereço errado.
3. **Trader scoring real (não ROI bruto)**: ranking por ROI puro favorece sorte (wallet com 1 trade vencedor de $50). Mínimo: filtro de N trades, janela móvel 30/90d, Sharpe simplificado, max drawdown, taxa de acerto vs. tamanho médio. PRD já menciona "Score de qualidade", spec não implementa — vamos implementar.
4. **Redis Streams ao invés de Pub/Sub**: pub/sub do Redis perde mensagens se o consumidor cair. Streams com consumer groups dão entrega persistente + replay — essencial para backtest e debugging.
5. **CLOB-aware**: Polymarket migrou de AMM para CLOB (Central Limit Order Book). Spec não menciona — afeta como ler liquidez (orderbook depth), simular execução (slippage real via book) e calcular preço justo.
6. **Resolução binária**: posições Polymarket resolvem em 0 ou 1 no vencimento. "Time-based exit" do spec precisa ser ciente do `endDate` do mercado — fechar antes da resolução pra evitar risco binário se a confiança caiu.
7. **Observability**: structured logging (JSON) + métricas Prometheus desde dia 1. Sem isso é impossível debugar por que uma estratégia perdeu.
8. **Tests**: spec tem zero menção a testes. Adicionar pytest + factories desde o início. Backtest é teste.
9. **Config-as-code**: estratégias e parâmetros em YAML versionado, não hardcoded em Python — facilita iterar sem deploy.
10. **Front-running awareness**: PRD lista o risco mas spec ignora. Mitigações concretas: confidence threshold elevado, size pequeno em mercados de baixa liquidez, evitar mercados com volume <$X (spread mata).
11. **Frontend dedicado**: spec só sugere API JSON. Adicionar SPA Next.js com páginas de Dashboard, Traders, Portfolio, Signals e Backtest — fundamental pra acompanhar performance, debugar decisões e (futuramente) virar SaaS.

---

## Arquitetura final (revisada)

```
[Polymarket REST + WebSocket CLOB]    [The Graph Subgraph]
              │                                │
              ▼                                ▼
     [data.live_collector]            [data.history_collector]
              │                                │
              └──────────┬─────────────────────┘
                         ▼
                 [Redis Streams: raw_trades]
                         │
                         ▼
                [tracker.wallet_filter] ──► PostgreSQL (trades, wallets)
                         │
                         ▼
                 [Redis Streams: tracked_trades]
                         │
                         ▼
                [signals.signal_engine] (whale_copy, consensus, fade, momentum)
                         │
                         ▼
                 [Redis Streams: signals]
                         │
                         ▼
            [risk.risk_manager] ──► reject / approve
                         │
                         ▼
         [execution.paper_executor]  (Fase 1-3)
         [execution.live_executor]   (Fase 4, opcional)
                         │
                         ▼
                  PostgreSQL (positions, pnl)
                         │
                         ▼
              [api.fastapi]  ◄────── REST + WebSocket (real-time updates)
                         ▲
                         │
              [web/  Next.js SPA]
              ├─ /dashboard   (PnL, equity curve, KPIs)
              ├─ /traders     (ranking, scores, drill-down)
              ├─ /portfolio   (posições abertas/fechadas)
              ├─ /signals     (feed live + reasons)
              ├─ /backtest    (relatórios + comparação)
              └─ /settings    (estratégias, risk, wallets)
```

---

## Estrutura de diretórios

```
CopyTraderPolymarket/
├── app/
│   ├── __init__.py
│   ├── main.py                    # entry point
│   ├── config.py                  # pydantic-settings, lê .env + strategies.yaml
│   │
│   ├── data/
│   │   ├── polymarket_rest.py     # Gamma + CLOB REST
│   │   ├── polymarket_ws.py       # WebSocket CLOB
│   │   ├── subgraph_client.py     # GraphQL → The Graph
│   │   └── models.py              # dataclasses puros (Trade, Market, Wallet)
│   │
│   ├── tracker/
│   │   ├── wallet_tracker.py      # filtra trades de wallets monitoradas
│   │   ├── proxy_resolver.py      # proxy ↔ owner
│   │   └── scoring.py             # Sharpe, drawdown, win rate, consistência
│   │
│   ├── signals/
│   │   ├── signal_engine.py       # orquestração
│   │   ├── strategies/
│   │   │   ├── whale_copy.py
│   │   │   ├── consensus.py
│   │   │   ├── fade_late.py
│   │   │   └── momentum_odds.py
│   │   └── confidence.py          # cálculo do score 0-1
│   │
│   ├── execution/
│   │   ├── base.py                # interface Executor
│   │   ├── paper_executor.py      # simula contra orderbook real
│   │   ├── live_executor.py       # py-clob-client (Fase 4)
│   │   └── exit_manager.py        # TP/SL/time-based/expiry-aware
│   │
│   ├── risk/
│   │   ├── risk_manager.py        # max% por trade, drawdown global, expo por mercado
│   │   └── kill_switch.py         # stop diário
│   │
│   ├── backtest/
│   │   ├── engine.py              # event replay sobre trades históricos
│   │   ├── metrics.py             # ROI, Sharpe, max DD, win rate
│   │   └── reports.py             # gera HTML/CSV
│   │
│   ├── storage/
│   │   ├── db.py                  # SQLAlchemy async
│   │   ├── models.py              # ORM
│   │   └── migrations/            # Alembic
│   │
│   ├── api/
│   │   ├── main.py                # FastAPI
│   │   └── routes/
│   │       ├── health.py
│   │       ├── pnl.py
│   │       ├── wallets.py
│   │       └── trades.py
│   │
│   └── utils/
│       ├── logger.py              # structlog JSON
│       ├── metrics.py             # prometheus_client
│       └── time.py
│
├── workers/
│   ├── collector_worker.py
│   ├── tracker_worker.py
│   ├── signal_worker.py
│   └── execution_worker.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── config/
│   ├── strategies.yaml
│   └── tracked_wallets.yaml
│
├── web/                           # frontend Next.js (App Router + TS)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx               # /dashboard
│   │   ├── traders/page.tsx
│   │   ├── traders/[wallet]/page.tsx
│   │   ├── portfolio/page.tsx
│   │   ├── signals/page.tsx
│   │   ├── backtest/page.tsx
│   │   └── settings/page.tsx
│   ├── components/
│   │   ├── EquityCurve.tsx
│   │   ├── PnLCard.tsx
│   │   ├── TradersTable.tsx
│   │   ├── PositionsTable.tsx
│   │   ├── SignalFeed.tsx         # live via WebSocket
│   │   └── KillSwitchBanner.tsx
│   ├── lib/
│   │   ├── api.ts                 # fetcher tipado (zod) p/ FastAPI
│   │   └── ws.ts                  # cliente WebSocket
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── next.config.mjs
│
├── docker-compose.yml             # inclui serviço `web`
├── Dockerfile                     # backend
├── web/Dockerfile                 # frontend
├── pyproject.toml                 # uv
├── .env.example
├── .gitignore
├── README.md
└── Makefile                       # make dev/test/lint/migrate/web-dev
```

---

## Plano por fases

### Fase 0 — Setup (1-2 dias)

**Objetivo**: fundação técnica antes de qualquer feature.

- `git init` + `git remote add origin https://github.com/leoaguiarguedes/CopyTraderPolymarket.git`
- `pyproject.toml` com `uv` (mais rápido que poetry); deps: `httpx`, `websockets`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `redis`, `structlog`, `prometheus-client`, `fastapi`, `uvicorn`, `pytest`, `pytest-asyncio`, `respx`, `gql`, `pyyaml`, `py-clob-client` (preparar pra Fase 4)
- `docker-compose.yml`: postgres 15, redis 7, app, prometheus opcional
- `Dockerfile` multi-stage
- `.env.example` (sem secrets reais)
- `.gitignore` (Python + .env + .venv + __pycache__ + .pytest_cache)
- Estrutura de pastas com `__init__.py`
- `app/utils/logger.py` (structlog JSON) + `app/utils/metrics.py`
- `app/config.py` com Settings pydantic
- Setup CI mínimo: GitHub Actions (.github/workflows/ci.yml) rodando ruff + pytest
- Alembic init + 1ª migration vazia

**Deliverables**: `make dev` sobe stack local; `make test` roda testes; CI verde no push pro GitHub.

---

### Fase 1 — MVP: Discovery + Tracking (2 semanas)

**Objetivo**: identificar wallets boas e logar trades delas em tempo real. Sem signals, sem execução.

#### 1.1 Data clients
- `app/data/polymarket_rest.py`:
  - `get_markets(active=True)` → Gamma `/markets`
  - `get_market(condition_id)` → detalhes + resolução
  - `get_orderbook(market_id)` → CLOB `/book` (pra Fase 2)
  - rate limiting + retry com backoff exponencial (`tenacity`)
- `app/data/polymarket_ws.py`:
  - conecta `wss://ws-subscriptions-clob.polymarket.com/ws/market`
  - subscribe ao canal `market` para markets ativos
  - emite eventos pra Redis Stream `raw_trades`
- `app/data/subgraph_client.py`:
  - GraphQL via `gql`
  - query `userPositions` e `marketTrades` por wallet
  - paginação automática

#### 1.2 Storage
- `models.py`: `Wallet`, `Market`, `Trade`, `WalletScore`
- Migration inicial Alembic
- Índices em `wallet`, `market_id`, `timestamp`

#### 1.3 Wallet discovery + scoring
- `app/tracker/scoring.py`:
  - input: lista de trades de uma wallet (do subgraph) com timestamps de open/close
  - calcula: ROI, Sharpe simplificado (ROI/std_returns), win rate, max drawdown, n_trades, volume, consistência (ROI positivo em quantos meses), **`avg_holding_minutes`** e **`median_holding_minutes`**, **% de trades fechados em <24h**
  - retorna `WalletScore` persistido em DB
- `app/tracker/proxy_resolver.py`:
  - mapa proxy ↔ owner via Polymarket Gamma `/proxy-wallet/{address}` ou eventos do contrato proxy factory
- Script `scripts/discover_wallets.py`:
  - puxa top 500 wallets do leaderboard, score, persiste, filtra: `n_trades >= 50 AND sharpe > 1 AND max_dd < 0.3 AND median_holding_minutes < 2880 AND pct_closed_under_24h > 0.6`
  - **rejeita swing traders longos** — copiar wallet com holding mediano de 5d destrói a estratégia de scalping
  - output: `config/tracked_wallets.yaml`

#### 1.4 Worker de tracking
- `workers/collector_worker.py`: roda `polymarket_ws` → Stream `raw_trades`
- `workers/tracker_worker.py`: consome `raw_trades`, filtra por wallet em `tracked_wallets.yaml`, persiste em DB, publica em Stream `tracked_trades`

#### 1.5 API mínima
- `GET /health`
- `GET /wallets` → lista wallets monitoradas + score
- `GET /trades?wallet=X&limit=N`

**Deliverables**: rodar `make dev`, ver trades de wallets top entrando no DB em tempo real, query via API.

---

### Fase 2 — Signal Engine + Paper Execution (2-3 semanas)

**Objetivo**: transformar trades rastreados em sinais com confidence score, e simular execução contra orderbook real (paper trading).

#### 2.1 Signal Engine
- `app/signals/signal_engine.py`: consome `tracked_trades`, dispara estratégias configuradas
- 4 estratégias do PRD em `app/signals/strategies/`, **cada uma com `max_holding_minutes` próprio**:
  - **whale_copy** (`max_holding=240min`): trade > $1k de wallet com score >= X **e median_holding_minutes < 720** → signal
  - **consensus** (`max_holding=180min`): ≥2 wallets top no mesmo lado em janela de 10min → signal
  - **fade_late** (`max_holding=120min`): wallet com score baixo entrando em mercado já movimentado → signal oposto
  - **momentum_odds** (`max_holding=60min`): odds movendo >5% em 30min + whale confirma → signal
- **Filtro global**: rejeitar signal se `market.time_to_resolution < max_holding_minutes + buffer` (não dá tempo de sair antes da resolução binária)
- `app/signals/confidence.py`: combina `wallet_score × strategy_weight × liquidity_factor × timing_factor` → 0-1
- Estratégias parametrizadas via `config/strategies.yaml` (thresholds, sizes, weights)
- Publica em Stream `signals`

#### 2.2 Risk Manager
- `app/risk/risk_manager.py`:
  - max % por trade (default 2%)
  - max exposição por mercado
  - max exposição total
  - drawdown global diário (kill switch)
  - validação de liquidez mínima (orderbook depth) — **deve ter depth suficiente pra desfazer a posição em <5min**
  - **rejeita se `market.time_to_resolution < signal.max_holding_minutes + 30min buffer`**
  - **rejeita se já existe posição aberta no mesmo mercado há mais de N minutos** (evita pirâmide em mercado morto)
- `app/risk/kill_switch.py`: flag persistida em Redis, checada por todos os workers

#### 2.3 Paper executor
- `app/execution/paper_executor.py`:
  - lê orderbook real via REST (não simula book sintético)
  - calcula preço de execução simulando market order contra book → captura slippage realista
  - persiste posição em `positions` table
  - subtrai fees (Polymarket cobra 0% atualmente, mas registrar p/ futuro)
- `app/execution/exit_manager.py`:
  - polling de posições abertas a cada 10s
  - **time-based exit OBRIGATÓRIO**: força saída ao atingir `signal.max_holding_minutes` (mesmo sem TP/SL hit) — esse é o mecanismo que garante a constraint de holding curto
  - TP (default +15%) / SL (default -7%) / expiry-aware (fecha 6h antes do `endDate` mesmo se dentro do holding window)
  - **trailing stop opcional**: se posição >+10%, ativa trailing de 5% pra capturar momentum sem segurar muito tempo
  - log structured de motivo de saída (TP/SL/timeout/expiry/trailing)
- `workers/execution_worker.py`: consome `signals`, valida com risk, executa

#### 2.4 API expandida (suporte ao frontend)
Endpoints REST tipados com Pydantic + WebSocket pra updates em tempo real:
- `GET /pnl?range=1d|7d|30d|all` → realizado + não-realizado + equity curve por bucket
- `GET /positions?status=open|closed` → posições com market metadata embedded
- `GET /signals?limit=N&strategy=X` → sinais + decisão do risk + reason
- `GET /traders?sort=sharpe&min_trades=50` → ranking com paginação
- `GET /traders/{wallet}` → drill-down: trades, score breakdown, PnL histórico
- `GET /strategies` / `PATCH /strategies/{name}` → ler/editar `strategies.yaml`
- `GET /risk` / `PATCH /risk` → parâmetros do risk manager
- `POST /kill-switch` → toggle parada global
- `WS /ws/live` → push de novos signals, fills, alertas (consumido pelo `SignalFeed`)

#### 2.5 Web Dashboard (Next.js + TypeScript)
**Stack**: Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui + TanStack Query (data fetching/cache) + Recharts (gráficos) + zod (validação de schemas da API).

**Por que Next.js e não Streamlit**: PRD menciona produto SaaS futuro; Streamlit não escala pra isso. Next.js dá SSR, deploy fácil (Vercel), e separação clara API/UI — muda só o backend pra multi-tenant depois.

**Páginas**:
- **`/dashboard`**: KPIs no topo (PnL hoje/7d/30d, equity total, drawdown atual, win rate, # trades abertos), `EquityCurve` (linha temporal), top 5 wallets contribuindo + bottom 5, banner se kill switch ativo.
- **`/traders`**: tabela ordenável (sharpe, ROI, win rate, # trades, último trade), filtros (min_trades, score), toggle "monitorar/parar". Click → drill-down `/traders/[wallet]` com trades históricos e equity curve da wallet.
- **`/portfolio`**: tabela posições abertas (market, side, entry, current, PnL, **age**, **time-to-forced-exit** com banner vermelho se <10min), motivo de saída previsto (TP/SL/timeout/expiry); tabela posições fechadas com filtros + coluna "exit reason" pra debugar (% timeouts é métrica chave); export CSV.
- **`/signals`**: feed live via WebSocket — cada signal mostra estratégia, wallet origem, market, confidence, decisão (executed ✓ / rejected com motivo do risk).
- **`/backtest`**: form pra disparar backtest (estratégia + janela + params), histórico de runs com métricas comparativas (Sharpe, DD, ROI), gráfico equity curve sobreposto.
- **`/settings`**: editor de `strategies.yaml` (form gerado a partir do schema), parâmetros do risk manager, gestão de wallets monitoradas (add/remove), botão kill switch.

**Auth**: na Fase 2 — basic auth single-user via env (`ADMIN_USER`/`ADMIN_PASS`); só você acessa. Refactor pra OAuth/multi-tenant fica pra Fase 5 (SaaS).

**Deploy**: `docker-compose` adiciona serviço `web` (Next standalone build), expõe `:3000`. Backend FastAPI continua `:8000`. Em produção: web atrás de nginx ou Vercel + API em VPS.

**Deliverables Fase 2**: rodando 24h em paper, abrir `http://localhost:3000/dashboard` e ver PnL atualizando em tempo real; signals chegando no feed; trocar uma estratégia em `/settings` reflete sem restart do worker.

---

### Fase 3 — Backtest Engine (1-2 semanas)

**Objetivo**: validar estratégias em dados históricos antes de gastar tempo (ou capital) com elas.

#### 3.1 Replay engine
- `app/backtest/engine.py`:
  - input: janela temporal + lista de wallets + estratégia + parâmetros
  - puxa todos os trades das wallets do Subgraph na janela
  - replay cronológico: para cada trade, dispara signal_engine → risk → paper_executor (modo backtest)
  - usa snapshot do orderbook na hora do trade — se não disponível, aproximação por preço médio do trade
- `app/backtest/metrics.py`: ROI total, ROI/trade, Sharpe, max DD, win rate, trade count, expectancy, profit factor, **avg holding time**, **% trades exited by timeout vs TP/SL** (métrica diagnóstica — se >50% sai por timeout, estratégia está mal calibrada)
- `app/backtest/reports.py`: HTML com matplotlib + tabela CSV

#### 3.2 Otimização de parâmetros
- Grid search simples sobre `strategies.yaml` (sem optuna ainda — premature)
- Output: top 10 configs por Sharpe

#### 3.3 Walk-forward validation
- Split temporal: treino em 60%, valida em 40% subsequente — evita overfitting

**Deliverables**: `python -m app.backtest.engine --strategy whale_copy --start 2025-01 --end 2025-04` gera relatório.

---

### Fase 4 — Live Execution (opcional, 2 semanas)

**Objetivo**: executar ordens reais na CLOB. **Só após backtest mostrar Sharpe > 1.5 consistente E paper trading 30d com PnL+.**

#### 4.1 Live executor
- `app/execution/live_executor.py` usando `py-clob-client`:
  - signing via private key (env var, **nunca commitada**)
  - valida saldo USDC antes de submit
  - submit via CLOB API
  - confirma fill via WebSocket canal `user`
- Refactor `Executor` interface pra trocar paper ↔ live via config

#### 4.2 Hardening
- Circuit breaker: se 3 trades consecutivos perdem >2σ do esperado → pause
- Reconciliação: cron 5min compara posições no DB vs. on-chain
- Alertas: webhook Discord/Telegram para fills, errors, kill switch

#### 4.3 Capital management
- Allocation diário máximo
- Position sizing por Kelly fracionário (0.25 Kelly inicial)

**Deliverables**: bot rodando com capital pequeno (~$100-500) em produção com monitoring.

---

## Verificação end-to-end

Cada fase tem um critério de "pronto":

- **Fase 0**: `docker compose up` sobe; `pytest` passa; commit pushed; CI verde.
- **Fase 1**: rodar 2h e ver ≥10 trades de wallets top no DB; `curl localhost:8000/wallets` retorna lista; testes de integração com mock httpx (`respx`) passam.
- **Fase 2**: rodar 24h em paper; abrir `http://localhost:3000/dashboard` e ver KPIs/equity atualizando; `/signals` mostra feed live via WS; `/portfolio` lista trades simulados; risk manager rejeita corretamente (testes unit + verificável em `/signals` com motivo).
- **Fase 3**: backtest reproduz manualmente um trade conhecido com PnL correto (±2%); walk-forward não diverge >30% de in-sample.
- **Fase 4**: testnet primeiro (Mumbai/Amoy se disponível); 1 trade de $10 manual confirmado on-chain; reconciliação bate.

---

## Critical files (a criar)

Top priority na Fase 0-1:
- `pyproject.toml`, `docker-compose.yml`, `Dockerfile`, `.env.example`, `.gitignore`
- `app/config.py`, `app/utils/logger.py`
- `app/data/polymarket_rest.py`, `app/data/polymarket_ws.py`, `app/data/subgraph_client.py`
- `app/storage/models.py`, `app/storage/db.py`, primeira migration Alembic
- `app/tracker/scoring.py`, `app/tracker/proxy_resolver.py`
- `workers/collector_worker.py`, `workers/tracker_worker.py`
- `app/api/main.py` + rotas básicas
- `tests/unit/test_scoring.py`, `tests/integration/test_tracker_flow.py`
- `.github/workflows/ci.yml`
- `README.md` com setup + arquitetura

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Subgraph desatualizado/down | Fallback pra REST + cache local |
| WebSocket desconecta | Reconexão automática com backoff + replay via REST |
| Polymarket muda API | Camada de abstração `data/` isola; testes de contrato |
| Edge não existe na prática | Backtest brutal antes de capital real; paper trading 30d mínimo |
| Front-running por bots | Confidence threshold alto + size pequeno + evitar markets <$10k volume |
| Vazamento de chave privada | Chave só em env var em prod; pre-commit hook bloqueia .env |
| Custo de The Graph / RPC | Cache agressivo; subgraph self-hosted como fallback futuro |

---

## Sequenciamento sugerido (cronograma realista)

- Semana 1: Fase 0 + início Fase 1 (data clients)
- Semana 2-3: Resto Fase 1 (tracking funcionando 24/7)
- Semana 4-5: Fase 2 backend (signals + paper + API expandida)
- Semana 5-6: Fase 2 frontend (Next.js dashboard + WS)
- Semana 7: Paper rodando + Fase 3 (backtest)
- Semana 8-9: Iteração de estratégias baseado em backtest
- Semana 10+: Decisão go/no-go pra Fase 4 baseado em Sharpe paper

Total: ~9-11 semanas de trabalho focado pra chegar em live execution responsável.