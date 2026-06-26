# QuantumAlpha India

Institutional-grade autonomous equity research platform for Indian markets.

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Start database and Redis
docker-compose up -d db redis

# Wait for services to be ready
sleep 5

# Run migrations and start server
cd backend
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the setup script:
```bash
./setup.sh
```

### Option 2: Local Development

```bash
# Make sure PostgreSQL is running
brew services start postgresql  # macOS
# or
sudo systemctl start postgresql  # Linux

# Create database
psql -U postgres -c "CREATE DATABASE alphahunter;"

# Install dependencies
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the local setup script:
```bash
./local-setup.sh
```

## API Endpoints

- `GET /` - Health check
- `GET /stocks` - List all stocks
- `GET /stock/{symbol}` - Get stock details
- `GET /scan/run` - Run full pipeline (ingest → score → rank)
- `GET /portfolio/current` - Get current portfolio
- `GET /backtest/run` - Run backtest
- `GET /agents/status` - Agent system status
- `GET /ml/predictions` - ML predictions
- `GET /signals/latest` - Latest signals

## Configuration

Edit `backend/.env`:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/alphahunter
SUPABASE_URL=
SUPABASE_KEY=
GROQ_API_KEY=your_groq_key_here
CLOUDFLARE_API_KEY=your_cloudflare_key_here
QDRANT_HOST=localhost
QDRANT_PORT=6333
REDIS_URL=redis://localhost:6379
```

**Optional:**
- `GROQ_API_KEY` - For LLM intelligence (get from https://console.groq.com)
- `CLOUDFLARE_API_KEY` - Fallback LLM provider
- Qdrant - Vector database for agent memory (optional)

## Architecture

10-phase system:
1. Data Ingestion (NSE, BSE, Yahoo Finance)
2. FGQMATL Scoring Engine
3. Market Microstructure Detection
4. Alternative Data Signals
5. LLM Intelligence
6. Portfolio Construction
7. Backtesting Engine
8. Machine Learning (XGBoost/LightGBM)
9. Autonomous Agents
10. Adaptive Learning

## Documentation

- [Technical Architecture](docs/ARCHITECTURE_PART_A.md)
- [Research Bible](docs/RESEARCH_BIBLE.md)

## Development

```bash
# Run tests (when implemented)
pytest

# Format code
black backend/

# Type checking
mypy backend/
```

## License

Private - All rights reserved
