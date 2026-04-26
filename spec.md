# SPEC TÉCNICO — CopyTrader Polymarket (Python)

## 1. 🧠 Visão Geral da Arquitetura

Arquitetura orientada a eventos (quase real-time):

- Data Collector → Wallet Tracker → Signal Engine → Execution Engine
  - ↓
  - Risk Manager
    - ↓
    - Database
      - ↓
      - Dashboard/API

## 2. 📦 Estrutura do Projeto

```text
polymarket-bot/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── data/
│   │   ├── polymarket_client.py
│   │   ├── scraper.py
│   ├── tracker/
│   │   ├── wallet_tracker.py
│   ├── signals/
│   │   ├── signal_engine.py
│   │   ├── strategies.py
│   ├── execution/
│   │   ├── executor.py
│   │   ├── order_manager.py
│   ├── risk/
│   │   ├── risk_manager.py
│   ├── storage/
│   │   ├── db.py
│   │   ├── models.py
│   ├── utils/
│   │   ├── logger.py
│   │   ├── time.py
├── workers/
│   ├── tracker_worker.py
│   ├── signal_worker.py
│   ├── execution_worker.py
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 3. ⚙️ Stack Técnico

- Python 3.11+
- FastAPI → API + dashboard
- PostgreSQL → persistência
- Redis → fila/cache
- Web3.py → interação com Polygon (Polymarket)
- asyncio → concorrência leve
- SQLAlchemy → ORM

## 4. 📡 Data Layer

### `polymarket_client.py`

Responsável por:

- buscar mercados
- buscar trades recentes
- buscar histórico de wallet

```python
class PolymarketClient:
    async def get_recent_trades(self) -> list:
        ...

    async def get_wallet_trades(self, wallet: str) -> list:
        ...

    async def get_markets(self) -> list:
        ...
```

**Fonte:** API pública / subgraph (The Graph)

## 5. 👀 Wallet Tracker

### `wallet_tracker.py`

Responsável por:

- monitorar wallets top
- detectar novos trades relevantes

```python
class WalletTracker:
    def __init__(self, client):
        self.client = client
        self.tracked_wallets = []

    async def track(self):
        trades = await self.client.get_recent_trades()

        for trade in trades:
            if trade.wallet in self.tracked_wallets:
                yield trade
```

## 6. 🧠 Signal Engine

### `signal_engine.py`

Transforma trades em sinais.

```python
class Signal:
    def __init__(self, market_id, side, confidence, size):
        self.market_id = market_id
        self.side = side
        self.confidence = confidence
        self.size = size
```

### `strategies.py`

#### Estratégia 1 — Whale Copy

```python
def whale_copy_strategy(trade):
    if trade.size_usd > 1000:
        return Signal(
            market_id=trade.market_id,
            side=trade.side,
            confidence=0.7,
            size=0.02  # 2% do capital
        )
```

#### Estratégia 2 — Consensus

```python
def consensus_strategy(trades):
    grouped = group_by_market(trades)

    for market, t in grouped.items():
        if len(t) >= 2:
            yield Signal(...)
```

## 7. 💸 Execution Engine

### `executor.py`

```python
class Executor:
    def __init__(self, web3, wallet):
        self.web3 = web3
        self.wallet = wallet

    async def execute(self, signal):
        if signal.side == "YES":
            await self.buy(signal)
        else:
            await self.sell(signal)

    async def buy(self, signal):
        ...

    async def sell(self, signal):
        ...
```

## 8. 🛡️ Risk Manager

### `risk_manager.py`

```python
class RiskManager:
    def __init__(self, capital):
        self.capital = capital

    def validate(self, signal):
        if signal.size > 0.05:
            return False

        if self.current_drawdown() > 0.1:
            return False

        return True
```

## 9. 🗄️ Storage

### `models.py`

```python
class Trade(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True)
    wallet = Column(String)
    market_id = Column(String)
    side = Column(String)
    price = Column(Float)
    size = Column(Float)
    timestamp = Column(DateTime)
```

## 10. 🔁 Workers (Core do sistema)

### `tracker_worker.py`

```python
async def run():
    tracker = WalletTracker(client)

    async for trade in tracker.track():
        await redis.publish("trades", trade.json())
```

### `signal_worker.py`

```python
async def run():
    async for trade in redis.subscribe("trades"):
        signal = whale_copy_strategy(trade)

        if signal:
            await redis.publish("signals", signal.json())
```

### `execution_worker.py`

```python
async def run():
    async for signal in redis.subscribe("signals"):
        if risk.validate(signal):
            await executor.execute(signal)
```

## 11. 🔌 API (FastAPI)

### `main.py`

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/pnl")
def pnl():
    return get_pnl()
```

## 12. 🐳 Docker Setup

### `docker-compose.yml`

```yaml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"

  redis:
    image: redis:7

  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
```

## 13. ⚡ Loop Principal

```python
async def main():
    await asyncio.gather(
        tracker_worker.run(),
        signal_worker.run(),
        execution_worker.run()
    )
```

## 14. 📊 Métricas essenciais

Você precisa trackear:

- ROI por trade
- ROI por trader copiado
- tempo de entrada (delay)
- slippage médio
- drawdown

## 15. 🚀 Próximos upgrades (alto impacto)

- score de trader (Sharpe + consistência)
- machine learning leve (classificação de sinal)
- latência ultra baixa (WebSocket + mempool)
- estratégia contrária (fade traders ruins)

## 16. ⚠️ Pontos críticos

### Se você errar isso → perde:

- entrar atrasado
- copiar trader ruim (ranking enganoso)
- não controlar risco
- ignorar liquidez

### Se acertar isso → edge real:

- timing + filtragem de trader
- execução rápida
- gestão de risco rígida
