# QuantumAlpha India

## Technical Architecture Specification v1.0

**Project Codename:** QuantumAlpha India  
**Version:** 1.0  
**Architecture Type:** Institutional-Grade Autonomous Equity Research Platform  
**Target Market:** Indian Equity Markets (NSE/BSE)  
**Primary Objective:** Detect hidden alpha opportunities before institutional accumulation.

---

# 1. System Overview

QuantumAlpha India is an AI-native institutional-grade research engine designed to discover asymmetric opportunities in Indian equity markets before broad market recognition.

The system combines:

* Quantitative factor investing
* Financial statement analysis
* Market microstructure analysis
* Alternative data ingestion
* Large Language Model (LLM) research automation
* Portfolio optimization
* Historical backtesting
* Machine learning adaptive modeling
* Autonomous multi-agent research workflows

The platform is designed as a continuously learning autonomous research organization.

Core objective:

```text
Identify future outperformers before institutions accumulate.
```

---

# 2. Design Principles

System architecture follows these principles.

## 2.1 Modular Architecture

Every component must be replaceable independently.

Example:

```text
Change LLM provider without changing pipeline.
```

---

## 2.2 Free Infrastructure First

Use low-cost or free infrastructure whenever possible.

Allowed providers:

* Groq API
* Cloudflare Workers AI
* Yahoo Finance
* NSE India
* BSE India
* Self-hosted PostgreSQL

Avoid expensive dependencies.

---

## 2.3 No Vendor Lock-in

All providers require abstraction layers.

Example:

```text
LLM Router → provider independent.
```

---

## 2.4 Fully Automated Research

System should function without manual intervention.

Goal:

```text
Daily autonomous market research.
```

---

## 2.5 Institutional Quality Standards

Every stock recommendation requires:

* Data validation
* Confidence scoring
* Historical testing
* Explainability

No black-box outputs allowed.

---

# 3. High-Level Architecture

System flow:

```text
External Data Sources
        ↓
Ingestion Layer
        ↓
Normalized Database
        ↓
Quant Engine
        ↓
Microstructure Engine
        ↓
Alternative Data Engine
        ↓
LLM Intelligence Engine
        ↓
Portfolio Construction Engine
        ↓
Backtesting Engine
        ↓
Machine Learning Engine
        ↓
Autonomous Agent Layer
        ↓
API Layer
        ↓
Frontend Dashboard
```

---

# 4. Repository Structure

```text
quantumalpha-india/

backend/
│
├── app/
│   ├── api/
│   ├── core/
│   ├── ingestion/
│   ├── quant_engine/
│   ├── microstructure/
│   ├── alternative_data/
│   ├── llm_engine/
│   ├── portfolio/
│   ├── backtesting/
│   ├── ml/
│   ├── agents/
│   ├── scheduler/
│   └── utils/
│
frontend/
│
workers/
│
database/
│
docker/
│
infra/
│
docs/
│
tests/
```

---

# 5. Technology Stack

## Backend

```text
Python 3.12
FastAPI
Uvicorn
Pydantic
SQLAlchemy
Alembic
```

---

## Database

```text
PostgreSQL
Redis
DuckDB
```

---

## Data Processing

```text
Pandas
Polars
NumPy
PyArrow
```

---

## Scheduling

```text
Celery
Redis Queue
Cron
```

---

## Machine Learning

```text
XGBoost
LightGBM
Scikit-learn
Optuna
```

---

## LLM Layer

```text
Groq API
Cloudflare Workers AI
Local fallback model
```

---

## Deployment

```text
Docker
Docker Compose
Nginx
Railway
Render
VPS
```

---

# 6. Infrastructure Architecture

System architecture:

```text
                           ┌──────────────┐
                           │ Frontend UI  │
                           └──────┬───────┘
                                  │
                           ┌──────▼───────┐
                           │ FastAPI API  │
                           └──────┬───────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
 ┌───────▼────────┐     ┌────────▼────────┐     ┌────────▼────────┐
 │ PostgreSQL DB  │     │ Celery Workers  │     │ Redis Queue     │
 └────────────────┘     └─────────────────┘     └─────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
            ┌───────▼───────┐ ┌───▼────────┐ ┌──▼─────────┐
            │ ETL Pipeline  │ │ ML Engine  │ │ LLM Engine │
            └───────────────┘ └────────────┘ └────────────┘
```

---

# 7. Data Ingestion Layer

Purpose:

Collect all raw market data.

Folder:

```text
backend/app/ingestion/
```

Modules:

```text
nse_ingestion.py
bse_ingestion.py
price_fetcher.py
financial_fetcher.py
shareholding_fetcher.py
bulkdeal_fetcher.py
corporate_action_fetcher.py
symbol_master.py
```

---

# 8. Data Sources

Primary sources:

## NSE Data

Used for:

* Price data
* Delivery percentage
* Corporate filings

---

## BSE Data

Used for:

* Exchange announcements
* Corporate disclosures

---

## Yahoo Finance

Used for:

* Historical OHLCV
* Dividend history
* Benchmark comparison

---

## Company filings

Used for:

* Quarterly reports
* Annual reports
* Investor presentations

---

# 9. Database Schema

Primary database:

PostgreSQL

---

## stocks

```sql
CREATE TABLE stocks (

    id SERIAL PRIMARY KEY,

    symbol VARCHAR(20),

    company_name TEXT,

    sector VARCHAR(100),

    industry VARCHAR(100),

    market_cap BIGINT
);
```

---

## daily_prices

```sql
CREATE TABLE daily_prices (

    id SERIAL PRIMARY KEY,

    symbol VARCHAR(20),

    date DATE,

    open NUMERIC,

    high NUMERIC,

    low NUMERIC,

    close NUMERIC,

    volume BIGINT
);
```

---

## quarterly_results

```sql
CREATE TABLE quarterly_results (

    id SERIAL PRIMARY KEY,

    symbol VARCHAR(20),

    quarter DATE,

    revenue NUMERIC,

    ebitda NUMERIC,

    pat NUMERIC,

    eps NUMERIC
);
```

---

## shareholding_patterns

```sql
CREATE TABLE shareholding_patterns (

    id SERIAL PRIMARY KEY,

    symbol VARCHAR(20),

    quarter DATE,

    promoter NUMERIC,

    fii NUMERIC,

    dii NUMERIC,

    public NUMERIC
);
```

---

# 10. Scheduler Architecture

Folder:

```text
backend/app/scheduler/
```

Jobs:

```text
Daily price update

Weekly alternative data update

Monthly market structure scan

Quarterly earnings ingestion

Quarterly retrain ML model
```

Schedule:

```text
00:30 Daily → Price updates

03:00 Daily → Corporate actions

Sunday → Alternative data refresh

Quarterly → Earnings pipeline

Quarterly → Portfolio rebalance

Quarterly → ML retraining
```

---

# 11. ETL Pipeline

Pipeline stages.

```text
Extract
        ↓
Validate
        ↓
Normalize
        ↓
Transform
        ↓
Load database
        ↓
Trigger downstream engines
```

Example:

```text
Quarterly results released
        ↓
Parse PDF
        ↓
Extract financials
        ↓
Store quarterly_results table
        ↓
Trigger Quant Engine
```

---

# 12. API Architecture

Folder:

```text
backend/app/api/
```

Endpoints.

```text
GET /stocks

GET /stock/{symbol}

GET /scan/run

GET /portfolio/current

GET /backtest/run

GET /agents/status

GET /ml/predictions

GET /signals/latest
```

Example:

```python
@app.get("/stock/{symbol}")

async def stock(symbol):

    return get_stock(symbol)
```

---

# 13. Quant Engine

Folder:

```text
backend/app/quant_engine/
```

Modules:

```text
quality_score.py
growth_score.py
fundamental_score.py
technical_score.py
forensic_penalty.py
ranking_engine.py
```

Inputs:

```text
Quarterly results

Annual financials

Price history
```

Outputs:

```text
Alpha score
```

---

# 14. Market Microstructure Engine

## Objective

Detect hidden institutional accumulation before broad market price discovery.

Core question:

```text
Is smart money accumulating shares before breakout?
```

Folder:

```text
backend/app/microstructure/
```

Modules:

```text
delivery_analyzer.py
vwap_analyzer.py
float_absorption.py
volume_anomaly.py
price_compression.py
bulk_deal_tracker.py
microstructure_score.py
```

---

## Inputs

```text
Daily OHLCV data

Delivery percentage data

Bulk deals data

Block deals data

Promoter transactions
```

---

## Signals Detected

### Delivery Percentage Expansion

Formula:

```python
delivery_ratio = current_delivery / 20_day_average
```

Signal:

```text
Delivery ratio > 1.5
```

Indicates accumulation.

---

### VWAP Defense

Institutional buyers often defend price near VWAP.

Logic:

```python
if close_price > intraday_vwap:

    signal += 20
```

---

### Float Absorption

Question:

```text
Are shares disappearing from free float?
```

Logic:

```python
if volume_high and price_flat:

    accumulation_signal = True
```

---

### Price Compression

Example:

```text
Price range tightens for 20 sessions.
```

Possible pre-breakout.

---

## Microstructure Score Formula

```python
microstructure_score = (

    delivery_score * 0.30 +

    vwap_score * 0.20 +

    float_absorption * 0.25 +

    volume_anomaly * 0.15 +

    compression_score * 0.10
)
```

---

# 15. Alternative Data Engine

## Objective

Capture signals unavailable in financial statements.

Folder:

```text
backend/app/alternative_data/
```

Modules:

```text
google_trends.py
patent_tracker.py
job_tracker.py
government_contracts.py
news_velocity.py
import_export_tracker.py
alternative_score.py
```

---

## Data Sources

Sources:

* Google Trends
* Government e-Marketplace (GeM)

---

## Alternative Signals

### Hiring Expansion

Question:

```text
Is company hiring aggressively?
```

Proxy for growth.

Track:

```text
LinkedIn jobs

Career pages
```

---

### Government Contracts

Track:

```text
Defense contracts

Infrastructure tenders

Healthcare procurement
```

Signal:

```text
Increasing contract wins
```

---

### News Velocity

Question:

```text
Is news activity accelerating?
```

Formula:

```python
velocity = current_news_count / historical_average
```

---

## Alternative Score Formula

```python
alternative_score = (

    hiring_score * 0.30 +

    contracts_score * 0.30 +

    patent_score * 0.10 +

    news_velocity * 0.20 +

    trend_score * 0.10
)
```

---

# 16. LLM Intelligence Engine

## Objective

Analyze unstructured qualitative information.

Question:

```text
What is management signaling that numbers do not reveal yet?
```

Folder:

```text
backend/app/llm_engine/
```

Modules:

```text
llm_router.py
document_parser.py
chunker.py
annual_report_analyzer.py
concall_analyzer.py
management_sentiment.py
governance_analyzer.py
narrative_shift.py
risk_detector.py
llm_engine.py
prompt_library.py
```

---

## Providers

Primary:

* Groq API

Fallback:

* Cloudflare Workers AI

---

## Annual Report Analysis

Need detect:

```text
Capex plans

Growth initiatives

Margin expansion plans

Business risks

Management confidence
```

Prompt:

```text
Analyze annual report.

Extract future growth signals.
Return structured JSON.
```

---

## Concall Comparison Engine

Need compare quarter-to-quarter narrative.

Question:

```text
Did management tone improve?
```

Detect:

```text
Demand optimism

Future confidence

Margin commentary change

Expansion commentary
```

---

## Governance Analyzer

Need detect hidden risk.

Signals:

```text
Auditor resignation

Related party transactions

Aggressive accounting

Capital allocation problems
```

---

## Narrative Shift Detection

Example.

Last quarter:

```text
Demand remains weak
```

Current quarter:

```text
Demand improving strongly
```

Signal:

```text
Narrative shift positive
```

---

## LLM Score Formula

```python
llm_score = (

    annual_report_score * 0.25 +

    concall_score * 0.30 +

    governance_score * 0.20 +

    sentiment_score * 0.15 +

    narrative_shift * 0.10
)
```

---

# 17. Portfolio Construction Engine

Folder:

```text
backend/app/portfolio/
```

Modules:

```text
risk_engine.py
volatility_engine.py
correlation_engine.py
position_sizing.py
sector_allocator.py
optimizer.py
stop_loss_engine.py
rebalance_engine.py
portfolio_engine.py
```

---

## Position Sizing Logic

Method:

```text
Volatility adjusted allocation
```

Formula:

```python
allocation = score / volatility
```

---

## Sector Caps

Rule:

```text
No sector > 25%
```

Example:

```python
SECTOR_LIMITS = {

    "Defense": 0.25,

    "Healthcare": 0.20,

    "Manufacturing": 0.20
}
```

---

## Liquidity Filter

Never overweight illiquid names.

Rule:

```text
Minimum daily traded value threshold.
```

---

# 18. Backtesting Engine

Folder:

```text
backend/app/backtesting/
```

Modules:

```text
historical_snapshot.py
strategy_runner.py
portfolio_simulator.py
benchmark_engine.py
transaction_cost.py
factor_attribution.py
metrics.py
drawdown_engine.py
walk_forward.py
backtest_engine.py
```

---

## Core Rule

```text
No lookahead bias.
```

Historical simulation must use only historical information.

---

## Simulation Flow

```text
Load historical quarter
        ↓
Run scoring engine
        ↓
Select top stocks
        ↓
Build portfolio
        ↓
Hold for quarter
        ↓
Measure returns
        ↓
Rebalance
```

---

## Performance Metrics

Track:

```text
CAGR

Sharpe ratio

Sortino ratio

Volatility

Win rate

Max drawdown

Recovery time
```

Benchmarks:

* NIFTY 50
* NIFTY Smallcap 250

---

# 19. Machine Learning Engine

Folder:

```text
backend/app/ml/
```

Modules:

```text
feature_builder.py
label_engine.py
dataset_builder.py
train_xgboost.py
train_lightgbm.py
feature_importance.py
ranking_model.py
dynamic_weight_engine.py
regime_detector.py
prediction_engine.py
ml_engine.py
```

---

## Objective

Learn historical characteristics of future multibaggers.

Question:

```text
What factors historically predicted future 3x winners?
```

---

## Features

Examples:

```text
ROCE

Revenue growth

PAT growth

Promoter change

Delivery trend

Microstructure score

Alternative score

LLM score
```

---

## Models

Primary:

* XGBoost

Secondary:

* LightGBM

---

## Output

Prediction:

```text
Probability stock becomes future outperformer.
```

Example:

```text
Probability = 87%
```

---

# 20. Autonomous Agent Architecture

## Objective

Create a continuously learning autonomous research organization.

The system transitions from static pipeline execution into agent-driven intelligence.

Core loop:

```text
Observe
   ↓
Think
   ↓
Research
   ↓
Validate
   ↓
Decide
   ↓
Act
   ↓
Learn
```

Folder:

```text
backend/app/agents/
```

Structure:

```text
agents/

orchestrator.py

market_observer.py

hypothesis_generator.py

research_agent.py

validation_agent.py

portfolio_agent.py

learning_agent.py

memory_engine.py

planner_agent.py

agent_router.py
```

---

# 21. Agent Responsibilities

## 21.1 Market Observer Agent

Purpose:

Detect unusual market behavior.

File:

```text
market_observer.py
```

Track:

```text
Sector rotation

Delivery spikes

Volume anomalies

Bulk deals

Block deals

Breakout candidates
```

Example:

```python
def observe_market():

    anomalies = []

    if delivery_ratio > 2:

        anomalies.append(

            "possible_accumulation"
        )

    return anomalies
```

---

## 21.2 Hypothesis Generator Agent

Purpose:

Generate research hypotheses.

Question:

```text
Why is unusual behavior happening?
```

File:

```text
hypothesis_generator.py
```

Example:

Observation:

```text
Defense stocks volume increasing.
```

Hypothesis:

```text
Government spending cycle may begin.
```

Uses LLM provider.

---

## 21.3 Research Agent

Purpose:

Investigate hypothesis.

File:

```text
research_agent.py
```

Tasks:

```text
Read filings

Check quarterly numbers

Check management commentary

Analyze alternative data
```

---

## 21.4 Validation Agent

Purpose:

Score confidence.

File:

```text
validation_agent.py
```

Output:

```text
Confidence = 84%
```

Example:

```python
if confidence > 80:

    approve = True
```

---

## 21.5 Portfolio Agent

Purpose:

Convert research into portfolio action.

File:

```text
portfolio_agent.py
```

Example:

```python
if sector_score > 90:

    increase_sector_weight()
```

---

## 21.6 Learning Agent

Purpose:

Evaluate historical prediction quality.

File:

```text
learning_agent.py
```

Question:

```text
Was prediction correct?
```

Adjust model weights.

---

## 21.7 Memory Engine

Purpose:

Store historical intelligence.

File:

```text
memory_engine.py
```

Stores:

```text
Past hypotheses

Winning patterns

 Failed patterns

 Sector cycle behavior
```

Use vector storage.

Recommended:

Qdrant Vector Database

---

## 21.8 Planner Agent

Purpose:

Generate future research tasks.

File:

```text
planner_agent.py
```

Example:

```python
Power sector showing strength.

Analyze suppliers next.
```

---

## 21.9 Orchestrator

Purpose:

Coordinate all agents.

File:

```text
orchestrator.py
```

---

# 22. Agent Execution Flow

System flow.

```text
Market Observer detects anomaly
        ↓
Hypothesis Generator creates thesis
        ↓
Research Agent investigates
        ↓
Validation Agent scores confidence
        ↓
Portfolio Agent reallocates capital
        ↓
Learning Agent evaluates prediction
        ↓
Memory Engine stores knowledge
```

---

# 23. Caching Architecture

Purpose:

Reduce expensive API calls.

Primary cache:

```text
Redis
```

Cache duration.

```text
Stock prices → 15 minutes

Quarterly financials → 90 days

 Annual reports → Permanent

 LLM outputs → 180 days

 Alternative data → 7 days
```

Example:

```python
cache.set(

    key,

    value,

    expiry=86400
)
```

---

# 24. Monitoring Architecture

Need production observability.

Track:

```text
API failures

Worker failures

Data ingestion failures

Database latency

Scheduler health

LLM API failures
```

Tools:

* Prometheus
* Grafana

---

## Metrics

```text
API response time

Worker queue length

 Failed ingestion jobs

 Model inference time
```

---

# 25. Logging Architecture

Need centralized logs.

Folder:

```text
backend/logs/
```

Example:

```text
application.log

worker.log

scheduler.log

ml.log

agent.log
```

Python:

```python
import logging

logger = logging.getLogger()
```

---

# 26. Failure Recovery Strategy

System must survive partial failure.

Principles:

```text
No single point of failure
```

---

## Data Source Failure

Example:

```text
NSE unavailable
```

Fallback:

```text
Yahoo Finance
```

---

## LLM Provider Failure

Primary fails:

```text
Groq API unavailable
```

Fallback:

```text
Cloudflare Workers AI
```

---

## Database Failure

Primary:

```text
PostgreSQL
```

Backup:

```text
Nightly snapshots
```

---

# 27. Docker Architecture

Directory:

```text
docker/
```

Files:

```text
Dockerfile.backend

Dockerfile.worker

docker-compose.yml
```

---

## Backend Container

```dockerfile
FROM python:3.12

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn","app.main:app"]
```

---

## Docker Compose

```yaml
services:

  api:

    build: .

  postgres:

    image: postgres

  redis:

    image: redis

  worker:

    build: .
```

---

# 28. API Security

Authentication.

Use:

```text
JWT Tokens
```

Implementation:

```text
Access token

Refresh token
```

---

## Rate Limiting

Need prevent abuse.

Example:

```text
100 requests/minute
```

Use:

* SlowAPI

---

## Secrets Management

Never hardcode credentials.

Use:

```text
.env file
```

Example:

```text
DATABASE_URL

REDIS_URL

GROQ_API_KEY

CLOUDFLARE_API_KEY
```

---

# 29. Deployment Architecture

Recommended architecture.

```text
Frontend → Next.js

Backend → FastAPI

Database → PostgreSQL

Workers → Celery

Queue → Redis

Reverse Proxy → Nginx
```

Infrastructure:

```text
Cloud VPS
```

Options:

* Railway
* Render

---

# 30. Production Deployment Flow

Pipeline.

```text
Git push
      ↓
GitHub Actions
      ↓
Docker build
      ↓
Container deploy
      ↓
Health check
      ↓
Restart failed workers
```

---

# 31. Testing Architecture

Need multiple test layers.

---

## Unit Tests

```text
Test functions individually.
```

Folder:

```text
tests/unit/
```

---

## Integration Tests

```text
Test pipeline interaction.
```

Folder:

```text
tests/integration/
```

---

## Historical Validation Tests

Need verify strategy.

Question:

```text
Did system outperform historical benchmarks?
```

---

# 32. Production Checklist

Before deployment verify.

Checklist:

```text
All ingestion jobs working

 Database indexes optimized

 Cache layer configured

 LLM fallback configured

 Monitoring dashboards active

 Backtesting validated

 ML models trained

 Agent orchestration stable

 Docker images tested

 API security verified
```

---

# 33. Performance Optimization

Large-scale scanning.

Target universe:

```text
3000+ NSE/BSE stocks
```

Optimization.

---

## Parallel Processing

Use:

```text
Asyncio
```

Example:

```python
await asyncio.gather(

    fetch_prices(),

    fetch_filings(),

    fetch_bulk_deals()
)
```

---

## Data Processing Engine

Prefer:

```text
Polars
```

Over:

```text
Pandas
```

Reason:

```text
Faster large dataframe processing.
```

---

# 34. Future Upgrade Roadmap

Version roadmap.

---

## V2

```text
Management forensic analysis
```

---

## V3

```text
Quarterly automated stock scanning
```

---

## V4

```text
Institutional accumulation detection
```

---

## V5

```text
Alternative data engine
```

---

## V6

```text
LLM qualitative intelligence
```

---

## V7

```text
Autonomous research organization
```

---

# 35. Final System Capability

QuantumAlpha India can:

```text
Scan 3000+ Indian stocks

Ingest quarterly financials automatically

Analyze management commentary

 Detect institutional accumulation

 Track alternative signals

 Build optimized portfolios

 Backtest historically

 Learn from historical winners

 Adapt factor weights

 Generate autonomous research hypotheses

 Operate continuously
```

---

# Final Architecture Statement

QuantumAlpha India is not a stock screener.

It is an autonomous institutional-grade research organization.

Mission:

```text
Identify asymmetric opportunities before institutional capital recognizes them.
```

System philosophy:

```text
Observe faster.

Think deeper.

 Validate rigorously.

 Act early.
```

---

END OF DOCUMENT

QuantumAlpha_India_Technical_Architecture_v1.md

Version 1 Complete.
