import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app import analytics, live
from app.hwclient import sign_request
from app.live import UNATTRIBUTED
from app.main import app

KEYS = [
    {"id": "k1", "label": "team-alpha", "description": "Alpha 团队", "ip_whitelist": []},
    {"id": "k2", "label": "team-beta", "description": "Beta 团队", "ip_whitelist": ["1.2.3.4"]},
    {"id": "k3", "description": "门户系统调用 Key", "ip_whitelist": None},
]


def item(name, req, prompt, completion, cache=0.0, err=0):
    return {"service_id": name, "service_name": name, "generation_type": "Text Generation", "request_count": req,
            "error_count": err, "prompt_token": prompt, "completion_token": completion, "cache_token": cache,
            "total_token": prompt + completion, "avg_latency": 100}


USAGE = {
    "team-alpha": [item("GLM", 10, 100, 10, 60, err=1)],
    "team-beta": [],
    UNATTRIBUTED: [item("GLM", 5, 20, 2), item("Kimi", 5, 50, 5)],
}


@pytest.fixture(autouse=True)
def fake_live(monkeypatch):
    calls = []

    def window(start, end, label=None):
        calls.append((start, end, label))
        if label is None:
            return [it for v in USAGE.values() for it in v]
        return USAGE.get(label, [])

    monkeypatch.setattr(live, "api_keys", lambda: KEYS)
    monkeypatch.setattr(live, "window", window)
    monkeypatch.setattr(live, "windows", lambda specs: [window(*s) for s in specs])
    monkeypatch.setattr(live, "open_end", lambda: dt.datetime(2026, 11, 8, 12, 0))
    return calls


def test_sign_request_is_deterministic():
    now = dt.datetime(2026, 11, 8, 1, 2, 3, tzinfo=dt.timezone.utc)
    h = sign_request("GET", "https://x.example.com/v3/projects?name=a", {}, b"", "AK", "SK", now)
    assert h["x-sdk-date"] == "20261108T010203Z"
    assert h["authorization"].startswith("SDK-HMAC-SHA256 Access=AK, SignedHeaders=host;x-sdk-date, Signature=")
    assert h == sign_request("GET", "https://x.example.com/v3/projects?name=a", {}, b"", "AK", "SK", now)


def test_utc_range_clamps_and_rejects_old_data():
    s, e = analytics.utc_range(dt.date(2026, 11, 8), dt.date(2026, 11, 8))
    assert s == dt.datetime(2026, 11, 7, 16) and e == dt.datetime(2026, 11, 8, 12)
    with pytest.raises(analytics.RangeError):
        analytics.utc_range(dt.date(2026, 10, 1), dt.date(2026, 11, 8))


def test_day_buckets_follow_local_midnight():
    b = analytics._buckets(dt.datetime(2026, 11, 6, 16), dt.datetime(2026, 11, 8, 12), "day")
    assert [x[0] for x in b] == ["11-07", "11-08"]
    assert b[1][1] == dt.datetime(2026, 11, 7, 16) and b[1][2] == dt.datetime(2026, 11, 8, 12)
    assert len(analytics._buckets(dt.datetime(2026, 11, 7, 16), dt.datetime(2026, 11, 8, 12), "hour")) == 20


def test_overview_and_unattributed_share():
    ov = analytics.overview(dt.date(2026, 11, 8), dt.date(2026, 11, 8))
    c = ov["current"]
    assert c["requests"] == 20 and c["total_kt"] == 187
    assert c["cache_hit_ratio"] == pytest.approx(60 / 170)
    assert ov["unattributed_share"] == pytest.approx(77 / 187)
    assert ov["active_keys"] == 1
    assert ov["previous"]["requests"] == 20


def test_key_ranking_marks_unlabeled_and_idle_keys():
    rows = analytics.key_ranking(dt.date(2026, 11, 8), dt.date(2026, 11, 8))
    by = {r["key"]: r for r in rows}
    assert rows[0]["key"] == "team-alpha"
    assert by[UNATTRIBUTED]["unlabeled_keys"] == ["门户系统调用 Key"]
    assert by["team-beta"]["requests"] == 0 and not by["team-beta"]["open_access"]
    assert by["team-alpha"]["open_access"]


def test_model_filter_and_label_scope():
    ov = analytics.overview(dt.date(2026, 11, 8), dt.date(2026, 11, 8), model="Kimi")
    assert ov["current"]["requests"] == 5 and ov["unattributed_share"] == 1
    models = analytics.model_ranking(dt.date(2026, 11, 8), dt.date(2026, 11, 8), label=UNATTRIBUTED)
    assert [m["key"] for m in models] == ["Kimi", "GLM"]


def test_trend_one_call_per_bucket(fake_live):
    tr = analytics.trend(dt.date(2026, 11, 7), dt.date(2026, 11, 8), "day", "requests", label="team-alpha")
    assert tr["axis"] == ["11-07", "11-08"]
    assert tr["series"] == [{"name": "GLM", "data": [10, 10], "other": False}]
    assert [c[2] for c in fake_live] == ["team-alpha"] * 2


def test_api_errors_map_to_400():
    c = TestClient(app)
    assert c.get("/api/trend?start=2026-11-01&end=2026-11-08&granularity=hour").status_code == 400
    assert c.get("/api/overview?start=2026-09-01&end=2026-11-08").status_code == 400
    assert c.get("/api/overview?start=2026-11-08&end=2026-11-07").status_code == 400
    assert c.get("/api/usage/keys?start=2026-11-08&end=2026-11-08").status_code == 200


def test_windows_serves_cache_hits_without_pool(monkeypatch):
    import importlib
    real = importlib.reload(live)
    s, e = dt.datetime(2026, 11, 1), dt.datetime(2026, 11, 2)
    real._cache[("win", s, e, "a")] = (float("inf"), ["hit"])
    fetched = []
    monkeypatch.setattr(real.client, "service_statistics", lambda a, b, keys=None: fetched.append(keys) or ["miss"])
    assert real.windows([(s, e, "a"), (s, e, "b")]) == [["hit"], ["miss"]]
    assert fetched == [["b"]]


def test_concurrent_requests_share_one_call(monkeypatch):
    import importlib
    import threading
    import time as _time
    real = importlib.reload(live)
    s, e = dt.datetime(2026, 11, 1), dt.datetime(2026, 11, 2)
    calls = []

    def slow(a, b, keys=None):
        calls.append(keys)
        _time.sleep(0.2)
        return ["v"]

    monkeypatch.setattr(real.client, "service_statistics", slow)
    out = []
    ts = [threading.Thread(target=lambda: out.append(real.windows([(s, e, "a"), (s, e, "b")]))) for _ in range(5)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert out == [[["v"], ["v"]]] * 5
    assert sorted(calls) == [["a"], ["b"]]
