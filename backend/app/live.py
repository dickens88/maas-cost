import datetime as dt
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

from app import config
from app.hwclient import MaasClient

# Bucket for calls without a label: online playground + unlabeled keys
UNATTRIBUTED = ""
# MaaS keeps ~31 days and rejects spans over 30 days
MAX_SPAN = dt.timedelta(days=30)
BUCKET = dt.timedelta(minutes=5)

client = MaasClient()
pool = ThreadPoolExecutor(max_workers=config.API_CONCURRENCY)
_cache = {}
# Single-flight: concurrent requests for the same key share one API call
_inflight = {}
_cache_lock = threading.Lock()


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def open_end():
    """Current time floored to 5 minutes so repeated queries share cache."""
    now = utcnow()
    return now - (now - dt.datetime.min) % BUCKET


def to_ms(t):
    return int(t.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def peek(key):
    with _cache_lock:
        hit = _cache.get(key)
        return hit[1] if hit and hit[0] > time.monotonic() else None


def _claim(key):
    """Return ('hit', value), ('wait', future) or ('own', future)."""
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > time.monotonic():
            return "hit", hit[1]
        if key in _inflight:
            return "wait", _inflight[key]
        fut = _inflight[key] = Future()
        return "own", fut


def _fill(key, ttl, fut, fn):
    try:
        value = fn()
    except BaseException as e:
        with _cache_lock:
            _inflight.pop(key, None)
        fut.set_exception(e)
        raise
    now = time.monotonic()
    with _cache_lock:
        _cache[key] = (now + ttl, value)
        _inflight.pop(key, None)
        if len(_cache) > 5000:
            for k in [k for k, v in _cache.items() if v[0] <= now]:
                _cache.pop(k, None)
    fut.set_result(value)
    return value


def cached(key, ttl, fn):
    state, v = _claim(key)
    if state == "hit":
        return v
    if state == "wait":
        return v.result()
    return _fill(key, ttl, v, fn)


def _ttl(end):
    return config.CACHE_TTL_CLOSED_SEC if end <= utcnow() - dt.timedelta(hours=1) else config.CACHE_TTL_OPEN_SEC


def api_keys():
    return cached(("keys",), config.CACHE_TTL_OPEN_SEC, client.list_api_keys)


def labels():
    return sorted({k["label"] for k in api_keys() if k.get("label")}) + [UNATTRIBUTED]


def _fetch(start, end, label, ip=None):
    return client.service_statistics(to_ms(start), to_ms(end), None if label is None else [label],
                                     None if ip is None else [ip])


def service_ids():
    return {s["service_id"] for s in cached(("services",), config.CACHE_TTL_CLOSED_SEC, client.list_services)}


def error_chart(service_id, start, end, granularity, timezone):
    return cached(("errchart", service_id, start, end, granularity), _ttl(end),
                  lambda: client.error_code_chart(service_id, to_ms(start), to_ms(end), granularity, timezone))


def source_ips(start, end, label=None):
    """IPs that called in [start, end), optionally only through one key label."""
    return cached(("ips", start, end, label), _ttl(end),
                  lambda: client.source_ips(to_ms(start), to_ms(end), None if label is None else [label]))


def windows(specs):
    """Fetch (start, end, label[, ip]) windows; pool workers only run calls this request owns, never wait."""
    out, owned, waiting = [None] * len(specs), [], []
    for i, spec in enumerate(specs):
        state, v = _claim(("win", *spec))
        if state == "hit":
            out[i] = v
        elif state == "wait":
            waiting.append((i, v))
        else:
            owned.append((i, spec, v))
    results = pool.map(lambda o: _fill(("win", *o[1]), _ttl(o[1][1]), o[2], lambda: _fetch(*o[1])), owned)
    for (i, _, _), v in zip(owned, results):
        out[i] = v
    for i, fut in waiting:
        out[i] = fut.result()
    return out


def window(start, end, label=None):
    """Per-service usage in [start, end); label=None means all callers."""
    return windows([(start, end, label)])[0]


def by_label(start, end):
    ls = labels()
    return dict(zip(ls, windows([(start, end, label) for label in ls])))
