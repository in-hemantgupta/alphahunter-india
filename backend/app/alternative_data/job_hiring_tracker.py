import httpx
import re

_FREEHIRE_API = "https://freehire.dev/api/v1/jobs/search"
_CACHE = {}
_TIMEOUT = 10.0
_SHARED_CLIENT = None


def _get_client():
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None:
        _SHARED_CLIENT = httpx.AsyncClient(timeout=_TIMEOUT)
    return _SHARED_CLIENT


async def close_client():
    global _SHARED_CLIENT
    if _SHARED_CLIENT:
        await _SHARED_CLIENT.aclose()
        _SHARED_CLIENT = None


def _normalize(s: str) -> str:
    """Lowercase, strip common suffixes."""
    s = s.lower().strip()
    s = re.sub(r'\b(private|limited|ltd|plc|inc|corp|corp\.|co\.|company)\b', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def _company_matches(company_field: str, search_name: str) -> bool:
    """Check if the API company field matches the target company name."""
    cf = _normalize(company_field)
    sn = _normalize(search_name)
    # Direct substring match
    if sn in cf or cf in sn:
        return True
    # Token overlap: check if >50% of significant tokens match
    cf_tokens = {w for w in cf.split() if len(w) > 2}
    sn_tokens = {w for w in sn.split() if len(w) > 2}
    if sn_tokens and cf_tokens:
        overlap = sn_tokens & cf_tokens
        if len(overlap) / max(len(sn_tokens), len(cf_tokens)) >= 0.5:
            return True
    return False


async def hiring_score(company_name: str) -> int | None:
    """Fetch active job posting count for a company via freehire.dev API.
    Returns a score 0-100 based on posting volume, or None on error."""
    if not company_name or len(company_name) < 3:
        return None

    cache_key = company_name.lower().strip()
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    # Use a meaningful search term: take first 2-3 significant words
    words = company_name.replace("Limited", "").replace("Ltd", "").replace("Private", "").split()
    words = [w for w in words if len(w) > 2]
    search_term = " ".join(words[:3]) if words else company_name.split()[0]

    try:
        client = _get_client()
        resp = await client.get(
            _FREEHIRE_API,
            params={"q": search_term, "limit": 50},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if resp.status_code != 200:
            _CACHE[cache_key] = None
            return None

        data = resp.json()
        results = data if isinstance(data, list) else data.get("data", data.get("results", []))

        if not isinstance(results, list) or len(results) == 0:
            _CACHE[cache_key] = 0
            return 0

        # Filter to only count jobs from the matching company
        count = 0
        for job in results:
            job_company = job.get("company", "")
            if _company_matches(job_company, company_name):
                count += 1

        if count >= 20:
            score = 100
        elif count >= 10:
            score = 80
        elif count >= 5:
            score = 60
        elif count >= 2:
            score = 40
        elif count >= 1:
            score = 20
        else:
            score = 0

        _CACHE[cache_key] = score
        return score

    except Exception:
        _CACHE[cache_key] = None
        return None
