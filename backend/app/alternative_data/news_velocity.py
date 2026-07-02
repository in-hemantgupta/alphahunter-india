import httpx
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta

_RSS_FEEDS = [
    "https://www.moneycontrol.com/rss/market.xml",
    "https://www.moneycontrol.com/rss/business.xml",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
]

_TIMEOUT = 10.0
_CACHE = {}
_CACHE_TTL = timedelta(hours=1)
_CACHE_TIME = {}
_FEED_CACHE = {}
_FEED_CACHE_TIME = {}
_FEED_CACHE_TTL = timedelta(minutes=5)
_POSITIVE_WORDS = {"profit", "surge", "bullish", "upgrade", "growth", "record", "rally", "positive", "gain", "rise", "higher", "strong", "beat", "win", "approval", "contract", "expansion"}
_NEGATIVE_WORDS = {"loss", "decline", "bearish", "downgrade", "fall", "drop", "negative", "slump", "cut", "weak", "miss", "penalty", "scam", "probe", "investigation", "default", "down", "sell"}


def _fetch_rss(url: str) -> list[dict]:
    now = datetime.now()
    if url in _FEED_CACHE and (now - _FEED_CACHE_TIME.get(url, now - _FEED_CACHE_TTL * 2)) < _FEED_CACHE_TTL:
        return _FEED_CACHE[url]

    try:
        resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        results = []
        for item in items:
            title = item.findtext("title", "")
            desc = item.findtext("description", "")
            pub_date = item.findtext("pubDate", "")
            results.append({"title": title, "description": desc, "pub_date": pub_date})
        _FEED_CACHE[url] = results
        _FEED_CACHE_TIME[url] = now
        return results
    except Exception:
        return []


def _simple_sentiment(text: str) -> float:
    if not text:
        return 0.0
    words = set(re.findall(r'\w+', text.lower()))
    pos = len(words & _POSITIVE_WORDS)
    neg = len(words & _NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def news_score(company_name: str) -> int | None:
    """Fetch recent news mentions for a company from Indian financial RSS feeds.
    Returns a score 0-100 based on mention count and sentiment, or None on error."""
    if not company_name or len(company_name) < 3:
        return None

    now = datetime.now()
    cache_key = company_name.lower().strip()
    if cache_key in _CACHE and (now - _CACHE_TIME.get(cache_key, now - _CACHE_TTL * 2)) < _CACHE_TTL:
        return _CACHE[cache_key]

    search_terms = re.findall(r'\w+', company_name.lower())
    search_terms = [w for w in search_terms if len(w) > 2]

    mentions = 0
    sentiment_sum = 0.0
    total_days = 0

    for feed_url in _RSS_FEEDS:
        articles = _fetch_rss(feed_url)
        for article in articles:
            text = f"{article['title']} {article['description']}".lower()
            if any(term in text for term in search_terms):
                mentions += 1
                sentiment_sum += _simple_sentiment(text)
                pub_date = article.get("pub_date", "")
                if pub_date:
                    try:
                        parsed = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
                        days_ago = (now - parsed.replace(tzinfo=None)).days
                        total_days = max(total_days, days_ago)
                    except ValueError:
                        pass

    if mentions == 0:
        _CACHE[cache_key] = 0
        _CACHE_TIME[cache_key] = now
        return 0

    avg_sentiment = sentiment_sum / mentions if mentions > 0 else 0
    volume_score = min(100, mentions * 20)
    sentiment_score = max(0, min(100, (avg_sentiment + 1) * 50))
    score = int(volume_score * 0.6 + sentiment_score * 0.4)

    _CACHE[cache_key] = score
    _CACHE_TIME[cache_key] = now
    return score
