SPEC TÉCNICO — CopyTrader Polymarket (Python)

1\. 🧠 Visão Geral da Arquitetura



Arquitetura orientada a eventos (quase real-time):



\[Data Collector] → \[Wallet Tracker] → \[Signal Engine] → \[Execution Engine]

&#x20;                             ↓

&#x20;                       \[Risk Manager]

&#x20;                             ↓

&#x20;                        \[Database]

&#x20;                             ↓

&#x20;                        \[Dashboard/API]

2\. 📦 Estrutura do Projeto

polymarket-bot/

│

├── app/

│   ├── main.py

│   ├── config.py

│

│   ├── data/

│   │   ├── polymarket\_client.py

│   │   ├── scraper.py

│

│   ├── tracker/

│   │   ├── wallet\_tracker.py

│

│   ├── signals/

│   │   ├── signal\_engine.py

│   │   ├── strategies.py

│

│   ├── execution/

│   │   ├── executor.py

│   │   ├── order\_manager.py

│

│   ├── risk/

│   │   ├── risk\_manager.py

│

│   ├── storage/

│   │   ├── db.py

│   │   ├── models.py

│

│   ├── utils/

│   │   ├── logger.py

│   │   ├── time.py

│

├── workers/

│   ├── tracker\_worker.py

│   ├── signal\_worker.py

│   ├── execution\_worker.py

│

├── docker-compose.yml

├── requirements.txt

└── README.md

3\. ⚙️ Stack Técnico

Python 3.11+

FastAPI → API + dashboard

PostgreSQL → persistência

Redis → fila/cache

Web3.py → interação com Polygon (Polymarket)

asyncio → concorrência leve

SQLAlchemy → ORM

4\. 📡 Data Layer

4.1 polymarket\_client.py



Responsável por:



Buscar mercados

Buscar trades recentes

Buscar histórico de wallet

class PolymarketClient:

&#x20;   async def get\_recent\_trades(self) -> list:

&#x20;       ...



&#x20;   async def get\_wallet\_trades(self, wallet: str) -> list:

&#x20;       ...



&#x20;   async def get\_markets(self) -> list:

&#x20;       ...



📌 Fonte:



API pública / subgraph (The Graph)

5\. 👀 Wallet Tracker

wallet\_tracker.py



Responsável por:



Monitorar wallets top

Detectar novos trades relevantes

class WalletTracker:

&#x20;   def \_\_init\_\_(self, client):

&#x20;       self.client = client

&#x20;       self.tracked\_wallets = \[]



&#x20;   async def track(self):

&#x20;       trades = await self.client.get\_recent\_trades()



&#x20;       for trade in trades:

&#x20;           if trade.wallet in self.tracked\_wallets:

&#x20;               yield trade

6\. 🧠 Signal Engine

signal\_engine.py



Transforma trades em sinais



class Signal:

&#x20;   def \_\_init\_\_(self, market\_id, side, confidence, size):

&#x20;       self.market\_id = market\_id

&#x20;       self.side = side

&#x20;       self.confidence = confidence

&#x20;       self.size = size

strategies.py

Estratégia 1 — Whale Copy

def whale\_copy\_strategy(trade):

&#x20;   if trade.size\_usd > 1000:

&#x20;       return Signal(

&#x20;           market\_id=trade.market\_id,

&#x20;           side=trade.side,

&#x20;           confidence=0.7,

&#x20;           size=0.02  # 2% do capital

&#x20;       )

Estratégia 2 — Consensus

def consensus\_strategy(trades):

&#x20;   grouped = group\_by\_market(trades)



&#x20;   for market, t in grouped.items():

&#x20;       if len(t) >= 2:

&#x20;           yield Signal(...)

7\. 💸 Execution Engine

executor.py

class Executor:

&#x20;   def \_\_init\_\_(self, web3, wallet):

&#x20;       self.web3 = web3

&#x20;       self.wallet = wallet



&#x20;   async def execute(self, signal):

&#x20;       if signal.side == "YES":

&#x20;           await self.buy(signal)

&#x20;       else:

&#x20;           await self.sell(signal)



&#x20;   async def buy(self, signal):

&#x20;       ...



&#x20;   async def sell(self, signal):

&#x20;       ...

8\. 🛡️ Risk Manager

risk\_manager.py

class RiskManager:

&#x20;   def \_\_init\_\_(self, capital):

&#x20;       self.capital = capital



&#x20;   def validate(self, signal):

&#x20;       if signal.size > 0.05:

&#x20;           return False



&#x20;       if self.current\_drawdown() > 0.1:

&#x20;           return False



&#x20;       return True

9\. 🗄️ Storage

models.py

class Trade(Base):

&#x20;   \_\_tablename\_\_ = "trades"



&#x20;   id = Column(String, primary\_key=True)

&#x20;   wallet = Column(String)

&#x20;   market\_id = Column(String)

&#x20;   side = Column(String)

&#x20;   price = Column(Float)

&#x20;   size = Column(Float)

&#x20;   timestamp = Column(DateTime)

10\. 🔁 Workers (Core do sistema)

tracker\_worker.py

async def run():

&#x20;   tracker = WalletTracker(client)



&#x20;   async for trade in tracker.track():

&#x20;       await redis.publish("trades", trade.json())

signal\_worker.py

async def run():

&#x20;   async for trade in redis.subscribe("trades"):

&#x20;       signal = whale\_copy\_strategy(trade)



&#x20;       if signal:

&#x20;           await redis.publish("signals", signal.json())

execution\_worker.py

async def run():

&#x20;   async for signal in redis.subscribe("signals"):

&#x20;       if risk.validate(signal):

&#x20;           await executor.execute(signal)

11\. 🔌 API (FastAPI)

main.py

from fastapi import FastAPI



app = FastAPI()



@app.get("/health")

def health():

&#x20;   return {"status": "ok"}



@app.get("/pnl")

def pnl():

&#x20;   return get\_pnl()

12\. 🐳 Docker Setup

docker-compose.yml

version: "3.9"



services:

&#x20; api:

&#x20;   build: .

&#x20;   ports:

&#x20;     - "8000:8000"



&#x20; redis:

&#x20;   image: redis:7



&#x20; postgres:

&#x20;   image: postgres:15

&#x20;   environment:

&#x20;     POSTGRES\_PASSWORD: postgres

13\. ⚡ Loop Principal

async def main():

&#x20;   await asyncio.gather(

&#x20;       tracker\_worker.run(),

&#x20;       signal\_worker.run(),

&#x20;       execution\_worker.run()

&#x20;   )

14\. 📊 Métricas essenciais



Você precisa trackear:



ROI por trade

ROI por trader copiado

Tempo de entrada (delay)

Slippage médio

Drawdown

15\. 🚀 Próximos upgrades (alto impacto)

Score de trader (Sharpe + consistência)

Machine Learning leve (classificação de sinal)

Latência ultra baixa (WebSocket + mempool)

Estratégia contrária (fade traders ruins)

16\. ⚠️ Pontos críticos (onde você ganha ou perde dinheiro)



Se você errar isso → perde:



Entrar atrasado

Copiar trader ruim (ranking enganoso)

Não controlar risco

Ignorar liquidez



Se acertar isso → edge real:



Timing + filtragem de trader

Execução rápida

Gestão de risco rígida

