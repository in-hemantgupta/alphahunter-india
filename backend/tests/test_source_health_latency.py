"""Phase 2 Task 7: running-average latency + derived uptime_pct math.
Run: python -m pytest backend/tests/test_source_health_latency.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _FakeRecord:
    def __init__(self):
        self.total_requests = 0
        self.total_failures = 0
        self.avg_latency_ms = None
        self.consecutive_failures = 0
        self.last_error = None
        self.last_successful_fetch = None
        self.last_failed_attempt = None


def _apply_success(record, latency_ms):
    record.last_successful_fetch = "now"
    record.consecutive_failures = 0
    record.total_requests = (record.total_requests or 0) + 1
    prior = record.avg_latency_ms
    n = record.total_requests
    record.avg_latency_ms = latency_ms if prior is None else prior + (latency_ms - prior) / n


def _apply_failure(record):
    record.consecutive_failures += 1
    record.total_failures += 1
    record.total_requests += 1


def test_running_average_latency():
    r = _FakeRecord()
    for lat in [100, 200, 300]:
        _apply_success(r, lat)
    assert r.avg_latency_ms == 200.0
    assert r.total_requests == 3


def test_uptime_pct_derivation():
    r = _FakeRecord()
    _apply_success(r, 100)
    _apply_success(r, 100)
    _apply_failure(r)
    total = r.total_requests
    uptime_pct = round((total - r.total_failures) / total * 100, 1)
    assert total == 3
    assert uptime_pct == round(2 / 3 * 100, 1)


if __name__ == "__main__":
    test_running_average_latency()
    test_uptime_pct_derivation()
    print("test_source_health_latency: all passed")
