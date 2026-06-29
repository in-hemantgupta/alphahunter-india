from pathlib import Path

patches = {

"app/microstructure/oi_analysis.py": '''def oi_score(data):
    if data["oi_change"] > 10 and data["price_change"] > 2:
        return 100
    return 40
''',

"app/ingestion/validator.py": '''def validate_financials(data):
    if data["ebitda"] > data["revenue"]:
        return False
    if data["roe"] > 200:
        return False
    return True
''',

"app/ingestion/historical_loader.py": '''from concurrent.futures import ThreadPoolExecutor
from app.ingestion.price_ingestor import fetch_price_history

def load_all_history(symbols):
    with ThreadPoolExecutor(max_workers=20) as executor:
        executor.map(fetch_price_history, symbols)
''',

"app/ingestion/scheduler.py": '''from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def get_last_db_date(symbol):
    return None

def update_stock(symbol):
    last_date = get_last_db_date(symbol)
    pass

@scheduler.scheduled_job("cron", hour=18, minute=30)
def daily_update():
    pass

scheduler.start()
''',

"app/ingestion/normalizer.py": '''STANDARD_SCHEMA = {
    "sales": "revenue",
    "turnover": "revenue",
    "net_profit": "pat"
}

def normalize_data(data, source):
    normalized = {}
    for key, value in data.items():
        standard_key = STANDARD_SCHEMA.get(key, key)
        normalized[standard_key] = value
    return normalized
''',

"app/llm_engine/concall_analyzer.py": '''from app.llm_engine.llm_router import LLMRouter
from app.llm_engine.prompt_library import COMPARE_PROMPT

llm = LLMRouter()

async def compare_concalls(old, new):
    prompt = COMPARE_PROMPT + old + new
    return await llm.query(prompt)
''',

"app/llm_engine/governance_analyzer.py": '''from app.llm_engine.llm_router import LLMRouter
from app.llm_engine.prompt_library import GOVERNANCE_PROMPT

llm = LLMRouter()

async def analyze_governance(text):
    prompt = GOVERNANCE_PROMPT + text
    return await llm.query(prompt)
''',

"app/llm_engine/annual_report_analyzer.py": '''from app.llm_engine.llm_router import LLMRouter
from app.llm_engine.prompt_library import REPORT_PROMPT

llm = LLMRouter()

async def analyze_annual_report(text):
    prompt = REPORT_PROMPT + text
    response = await llm.query(prompt)
    return response
''',

"app/llm_engine/risk_detector.py": '''from app.llm_engine.llm_router import LLMRouter
from app.llm_engine.prompt_library import RISK_PROMPT

llm = LLMRouter()

async def detect_risks(text):
    prompt = RISK_PROMPT + text
    return await llm.query(prompt)
''',

"app/llm_engine/management_sentiment.py": '''POSITIVE_TERMS = [
    "expansion",
    "strong demand",
    "capacity increase",
    "new contracts",
    "margin improvement"
]

def sentiment_score(text):
    score = 0
    for word in POSITIVE_TERMS:
        if word in text:
            score += 20
    return score
''',

"app/llm_engine/narrative_shift.py": '''from app.llm_engine.llm_router import LLMRouter
from app.llm_engine.prompt_library import SHIFT_PROMPT

llm = LLMRouter()

async def compare_reports(old_report, new_report):
    prompt = SHIFT_PROMPT + old_report + new_report
    return await llm.query(prompt)
''',

"app/llm_engine/document_parser.py": '''import fitz

def extract_text(file):
    doc = fitz.open(file)
    text = ""
    for page in doc:
        text += page.get_text()
    return text
''',

"app/ml/label_engine.py": '''def create_label(stock_return, benchmark_return):
    alpha = stock_return - benchmark_return
    if alpha > 100:
        return 1
    return 0
''',

"app/portfolio/position_sizing.py": '''def size_position(score, volatility):
    allocation = score / volatility
    return allocation
''',

"app/portfolio/stop_loss_engine.py": '''def stop_loss(price, atr):
    return price - (2 * atr)
''',

"app/portfolio/portfolio_engine.py": '''from app.portfolio.risk_engine import risk_score
from app.portfolio.position_sizing import size_position

def build_portfolio(ranked_stocks):
    portfolio = []
    for stock in ranked_stocks:
        risk = risk_score(stock)
        allocation = size_position(stock["score"], risk)
        portfolio.append({
            "symbol": stock["symbol"],
            "allocation": allocation
        })
    return portfolio
''',

"app/portfolio/optimizer.py": '''def objective(weights):
    return -portfolio_sharpe(weights)
''',

"app/portfolio/correlation_engine.py": '''def correlation_matrix(price_data):
    returns = price_data.pct_change()
    return returns.corr()
'''
}

for file, content in patches.items():
    Path(file).write_text(content)

print("all corrupted files repaired")
