# PRD — CopyTrader Polymarket (Short-Term Alpha)

## 1. 🎯 Objetivo do Produto

Construir um sistema automatizado que:

- Identifique traders de alta performance na Polymarket
- Extraia padrões de entrada/saída
- Execute operações de curto prazo (scalping / swing curto)
- Maximize ROI com controle de risco

### Metas iniciais

- ROI mensal: 5–15%
- Drawdown máximo: < 10%
- Win rate: > 55% (com R/R favorável)

## 2. 🧠 Hipótese de Edge

Você não copia o trader — você copia o momento em que ele gera impacto no mercado.

### O edge vem de:

- Detectar wallets consistentes (não só ranking bruto)
- Identificar early entries (antes da massa)
- Filtrar mercados com:
  - baixa liquidez (mais edge)
  - alta assimetria de informação

## 3. 👤 Usuário alvo

- Você mesmo inicialmente (trader técnico)
- Depois: produto SaaS / copytrading

## 4. ⚙️ Funcionalidades Principais

### 4.1 Ranking Intelligence

- Scraping/API da Polymarket
- Identificar:
  - top traders por ROI
  - consistência (últimos 7d, 30d, 90d)
  - volume operado
  - Sharpe ratio simplificado

**Output:** lista de wallets “seguíveis”.

### 4.2 Wallet Tracker (Core)

Monitoramento em tempo real de:

- trades realizados
- odds de entrada
- volume

**Detecta:**

- entrada relevante (threshold volume)
- mudança de posição

### 4.3 Signal Engine

Transforma ação da wallet em sinal.

#### Exemplo de regra

- IF trader_top_5
- AND posição > $X
- AND mercado liquidez > Y
- AND odds < threshold
- THEN gerar sinal de entrada

#### Features

- delay-aware (evitar entrar tarde)
- confidence score (0–1)

### 4.4 Execution Engine

Executa trade automaticamente.

- Entrada: market ou limit inteligente
- Saída:
  - take profit (ex: +10–20%)
  - stop loss (ex: -5–8%)
  - time-based exit

### 4.5 Risk Manager (ESSENCIAL)

Sem isso você quebra.

- Max % por trade: 1–5%
- Max exposição por mercado
- Stop global diário

### 4.6 Backtesting Engine

Simula:

- histórico de trades das wallets
- performance do copy strategy

### 4.7 Dashboard

- PnL
- trades ativos
- performance por trader seguido

## 5. 🏗️ Arquitetura

Fluxo:

Polymarket Data → Wallet Tracker → Signal Engine → Execution → Risk Manager → Logs/Dashboard

## 6. 🧰 Stack recomendada

### Melhor escolha (pra você): Python

Porque:

- rápido pra testar estratégia
- ótimo pra data + backtest

### Stack principal

- Python
- FastAPI (API)
- Web3.py (interação blockchain)
- Pandas (análise)
- Redis (cache)
- PostgreSQL

### Alternativa (produção mais robusta)

- TypeScript (Node.js)
- NestJS
- ethers.js
- Redis + Postgres

### C# (menos ideal aqui)

- bom pra backend enterprise
- mais lento pra iterar estratégia

## 7. 📊 Estratégias iniciais

- **Estratégia 1 — Whale Copy Early**
  - copiar apenas entradas grandes
  - delay máximo: 30–60s
- **Estratégia 2 — Consensus Copy**
  - só entra se 2+ traders top entram no mesmo lado
- **Estratégia 3 — Fade Late Traders**
  - se trader entra tarde → fazer o oposto
- **Estratégia 4 — Momentum Odds**
  - entrar quando odds estão se movendo forte + whale confirmou

## 8. ⚠️ Riscos

- slippage alto
- liquidez baixa
- ranking enviesado (sorte ≠ skill)
- front-running: impossível competir com bots mais rápidos
- custos (fees + spread)

## 9. 📅 Roadmap

### Fase 1 — MVP (2 semanas)

- scraper ranking
- track wallets
- log de trades

### Fase 2 — Signals (2–3 semanas)

- regras básicas
- simulação manual

### Fase 3 — Execução (2 semanas)

- integração com carteira
- execução automatizada

### Fase 4 — Backtest + otimização

- ajuste de parâmetros
