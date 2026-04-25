PRD — CopyTrader Polymarket (Short-Term Alpha)

1\. 🎯 Objetivo do Produto



Construir um sistema automatizado que:



Identifique traders de alta performance na Polymarket

Extraia padrões de entrada/saída

Execute operações de curto prazo (scalping / swing curto)

Maximize ROI com controle de risco



Meta inicial:



ROI mensal: 5–15%

Drawdown máximo: <10%

Win rate: >55% (com R/R favorável)

2\. 🧠 Hipótese de Edge



Você não copia o trader — você copia o momento em que ele gera impacto no mercado.



Edge vem de:



Detectar wallets consistentes (não só ranking bruto)

Identificar early entries (antes da massa)

Filtrar mercados com:

baixa liquidez (mais edge)

alta assimetria de informação

3\. 👤 Usuário alvo

Você mesmo inicialmente (trader técnico)

Depois: produto SaaS / copytrading

4\. ⚙️ Funcionalidades Principais

4.1 Ranking Intelligence

Scraping/API da Polymarket

Identificar:

Top traders por ROI

Consistência (últimos 7d, 30d, 90d)

Volume operado

Sharpe ratio simplificado



📌 Output:



Lista de wallets “seguíveis”

4.2 Wallet Tracker (Core)



Monitoramento em tempo real:



Trades realizados

Odds de entrada

Volume



📌 Detecta:



Entrada relevante (threshold volume)

Mudança de posição

4.3 Signal Engine



Transforma ação da wallet em sinal:



Exemplo:



IF trader\_top\_5

AND posição > $X

AND mercado liquidez > Y

AND odds < threshold

THEN gerar sinal de entrada

Features:

Delay-aware (evitar entrar tarde)

Confidence score (0–1)

4.4 Execution Engine



Executa trade automaticamente:



Entrada:

Market ou limit inteligente

Saída:

Take profit (ex: +10–20%)

Stop loss (ex: -5–8%)

Time-based exit

4.5 Risk Manager (ESSENCIAL)



Sem isso você quebra.



Max % por trade: 1–5%

Max exposição por mercado

Stop global diário

4.6 Backtesting Engine



Simula:



Histórico de trades das wallets

Performance do copy strategy

4.7 Dashboard

PnL

Trades ativos

Performance por trader seguido

5\. 🏗️ Arquitetura

Fluxo:

Polymarket Data → Wallet Tracker → Signal Engine → Execution → Risk Manager → Logs/Dashboard

6\. 🧰 Stack recomendada

🔥 Melhor escolha (pra você): Python



Porque:



Rápido pra testar estratégia

Ótimo pra data + backtest



Stack:



Python

FastAPI (API)

Web3.py (interação blockchain)

Pandas (análise)

Redis (cache)

PostgreSQL

Alternativa (produção mais robusta):

TypeScript (Node.js)

NestJS

ethers.js

Redis + Postgres

C# (menos ideal aqui)

Bom pra backend enterprise

Mais lento pra iterar estratégia

7\. 📊 Estratégias iniciais

Estratégia 1 — Whale Copy Early

Copiar apenas entradas grandes

Delay máximo: 30–60s

Estratégia 2 — Consensus Copy

Só entra se 2+ traders top entram no mesmo lado

Estratégia 3 — Fade Late Traders

Se trader entra tarde → fazer o oposto

Estratégia 4 — Momentum Odds

Entrar quando odds estão se movendo forte + whale confirmou

8\. ⚠️ Riscos

Slippage alto

Liquidez baixa

Ranking enviesado (sorte ≠ skill)

Front-running impossível competir com bots mais rápidos

Custos (fees + spread)

9\. 📅 Roadmap

Fase 1 — MVP (2 semanas)

Scraper ranking

Track wallets

Log de trades

Fase 2 — Signals (2–3 semanas)

Regras básicas

Simulação manual

Fase 3 — Execução (2 semanas)

Integração com carteira

Execução automatizada

Fase 4 — Backtest + otimização

Ajuste de parâmetros

Filtrar traders bons de verdade

10\. 💡 Diferencial (onde você ganha dinheiro)



Se fizer só copy → perde



Se fizer isso → ganha:



Score de qualidade de trader (não ranking simples)

Timing de entrada (ESSENCIAL)

Combinação de múltiplos traders

Gestão de risco agressiva mas controlada

11\. 🧪 MVP técnico (pseudo fluxo)

while True:

&#x20;   trades = get\_recent\_trades()



&#x20;   for trade in trades:

&#x20;       if is\_top\_trader(trade.wallet):

&#x20;           signal = generate\_signal(trade)



&#x20;           if signal.confidence > 0.7:

&#x20;               execute\_trade(signal)

12\. Próximo nível (onde vira produto de verdade)

Copytrading como serviço (SaaS)

Ranking próprio (melhor que Polymarket)

AI para prever probabilidade real vs odds

13\. 💰 Monetização futura

% sobre lucro

Assinatura mensal

Copytrading pool

