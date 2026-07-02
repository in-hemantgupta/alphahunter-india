"""Rule 3: every external HTTP call gets a timeout, retry+backoff, and
circuit-breaker status recorded in data_source_health - failures must be
loud and visible, never swallowed into a fake success.
"""
import time
import requests

from app.services.data_freshness import DataFreshnessMonitor


class CircuitOpenError(Exception):
    """Raised without attempting a request when a source has failed too
    many times recently - stops hammering a dead endpoint."""


def resilient_get(url, source_name, headers=None, params=None, cookies=None,
                   timeout=30, max_retries=3, backoff_base=2.0,
                   circuit_breaker_threshold=5):
    """GET with timeout + exponential backoff, recording every outcome to
    data_source_health. Raises on final failure - callers must not catch
    this and substitute a default value; the caller's job is to treat the
    factor as unavailable (None), not to guess."""
    freshness = DataFreshnessMonitor()
    from app.models.data_source_health import DataSourceHealth
    health = freshness.session.query(DataSourceHealth).filter_by(source_name=source_name).first()
    if health and (health.consecutive_failures or 0) >= circuit_breaker_threshold:
        freshness.close()
        raise CircuitOpenError(
            f"{source_name}: circuit open after {health.consecutive_failures} consecutive failures"
        )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            start = time.monotonic()
            resp = requests.get(url, headers=headers, params=params, cookies=cookies, timeout=timeout)
            resp.raise_for_status()
            latency_ms = (time.monotonic() - start) * 1000
            freshness.record_success(source_name, latency_ms=latency_ms)
            freshness.close()
            return resp
        except Exception as e:
            last_error = e
            freshness.record_failure(source_name, str(e))
            if attempt < max_retries:
                time.sleep(backoff_base ** attempt)

    freshness.close()
    raise RuntimeError(f"{source_name}: failed after {max_retries} attempts: {last_error}") from last_error
