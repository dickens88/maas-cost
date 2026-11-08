import datetime as dt
from collections import defaultdict

from app import config, live
from app.hwclient import HwApiError
from app.live import UNATTRIBUTED

UNATTRIBUTED_NAME = "未归属（在线体验 + 无标签 Key）"
TZ = dt.timedelta(hours=config.TZ_OFFSET_HOURS)
MAX_HOURLY_SPAN = dt.timedelta(days=2)


class RangeError(ValueError):
    pass


def utc_range(start: dt.date, end: dt.date):
    """Inclusive local dates -> UTC [start, end), clamped to now."""
    s = dt.datetime.combine(start, dt.time()) - TZ
    e = min(dt.datetime.combine(end + dt.timedelta(days=1), dt.time()) - TZ, live.open_end())
    if e <= s:
        raise RangeError("时间范围为空")
    if s < live.open_end() - live.MAX_SPAN:
        raise RangeError("MaaS 只保留最近 30 天的统计数据")
    return s, e


def _keep(items, model):
    return [it for it in items if not model or it["service_name"] == model]


def summarize(items):
    t = defaultdict(float)
    for it in items:
        req = it.get("request_count") or 0
        t["req"] += req
        t["err"] += it.get("error_count") or 0
        t["prompt"] += it.get("prompt_token") or 0
        t["completion"] += it.get("completion_token") or 0
        t["cache"] += it.get("cache_token") or 0
        t["total"] += it.get("total_token") or 0
        t["lat_w"] += (it.get("avg_latency") or 0) * req
    # Token fields are thousands of tokens; prompt already includes cache hits
    return {
        "requests": int(t["req"]), "errors": int(t["err"]),
        "error_rate": t["err"] / t["req"] if t["req"] else 0,
        "prompt_kt": round(t["prompt"], 3), "completion_kt": round(t["completion"], 3),
        "cache_kt": round(t["cache"], 3), "total_kt": round(t["total"], 3),
        "cache_hit_ratio": t["cache"] / t["prompt"] if t["prompt"] else 0,
        "avg_kt_per_request": t["total"] / t["req"] if t["req"] else 0,
        "output_input_ratio": t["completion"] / t["prompt"] if t["prompt"] else 0,
        "avg_latency_ms": t["lat_w"] / t["req"] if t["req"] else 0,
    }


def overview(start, end, model=None):
    s, e = utc_range(start, end)
    data = live.by_label(s, e)
    items = [it for v in data.values() for it in _keep(v, model)]
    cur = summarize(items)
    prev = None
    # Shift by whole days so a range ending "now" compares to the same time of day
    shift = dt.timedelta(days=(end - start).days + 1)
    # Previous period is only comparable when it is still retained
    if s - shift >= live.open_end() - live.MAX_SPAN:
        prev = summarize(_keep(live.window(s - shift, e - shift), model))
    un = summarize(_keep(data[UNATTRIBUTED], model))
    return {
        "current": cur, "previous": prev,
        "unattributed_share": un["total_kt"] / cur["total_kt"] if cur["total_kt"] else 0,
        "active_keys": sum(1 for k, v in data.items() if k != UNATTRIBUTED and summarize(_keep(v, model))["requests"]),
        "range": {"start_utc": s, "end_utc": e},
    }


def _buckets(s, e, granularity):
    """Split [s, e) into local hour/day/week buckets."""
    out = []
    cur = s
    while cur < e:
        local = cur + TZ
        if granularity == "hour":
            nxt_local = local.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
            name = local.strftime("%m-%d %H:00")
        elif granularity == "week":
            monday = (local - dt.timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            nxt_local = monday + dt.timedelta(days=7)
            name = monday.strftime("%m-%d") + " 周"
        else:
            nxt_local = local.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(days=1)
            name = local.strftime("%m-%d")
        nxt = min(nxt_local - TZ, e)
        out.append((name, cur, nxt))
        cur = nxt
    return out


METRICS = {"tokens": "total_token", "requests": "request_count"}


def trend(start, end, granularity="day", metric="tokens", label=None, model=None, top=8):
    s, e = utc_range(start, end)
    if granularity == "hour" and e - s > MAX_HOURLY_SPAN:
        raise RangeError("小时粒度最多查询 2 天")
    buckets = _buckets(s, e, granularity)
    results = live.windows([(bs, be, label) for _, bs, be in buckets])
    field = METRICS[metric]
    totals = defaultdict(float)
    for items in results:
        for it in _keep(items, model):
            totals[it["service_name"]] += it.get(field) or 0
    ranked = [k for k, v in sorted(totals.items(), key=lambda kv: -kv[1]) if v > 0]
    keep = set(ranked[:top])
    series = defaultdict(lambda: [0.0] * len(buckets))
    for i, items in enumerate(results):
        for it in _keep(items, model):
            name = it["service_name"] if it["service_name"] in keep else "其他"
            series[name][i] += it.get(field) or 0
    order = ranked[:top] + (["其他"] if "其他" in series else [])
    return {
        "axis": [b[0] for b in buckets],
        "series": [{"name": k, "data": [round(v, 3) for v in series[k]], "other": k == "其他"} for k in order],
    }


def _key_meta():
    meta = {UNATTRIBUTED: {"description": "在线体验，以及未设置标签的 API Key", "keys": []}}
    for k in live.api_keys():
        if k.get("label"):
            meta.setdefault(k["label"], {"description": k.get("description"), "keys": []})["keys"].append(k)
        else:
            meta[UNATTRIBUTED]["keys"].append(k)
    return meta


def key_ranking(start, end, model=None):
    s, e = utc_range(start, end)
    data = live.by_label(s, e)
    grand = sum(summarize(_keep(v, model))["total_kt"] for v in data.values())
    meta = _key_meta()
    out = []
    for label, items in data.items():
        items = _keep(items, model)
        summ = summarize(items)
        top = max(items, key=lambda it: it.get("total_token") or 0, default=None)
        info = meta.get(label, {"description": None, "keys": []})
        out.append({
            "key": label, "name": UNATTRIBUTED_NAME if label == UNATTRIBUTED else label, **summ,
            "token_share": summ["total_kt"] / grand if grand else 0,
            "top_model": top["service_name"] if top and summ["requests"] else None,
            "models": sum(1 for it in items if it.get("request_count")),
            "description": info["description"],
            "key_ids": [k["id"] for k in info["keys"]],
            "open_access": any(not k.get("ip_whitelist") for k in info["keys"]),
            "unlabeled_keys": [k.get("description") or k["id"] for k in info["keys"] if not k.get("label")],
        })
    out.sort(key=lambda x: (-x["total_kt"], -x["requests"]))
    return out


def model_ranking(start, end, label=None):
    s, e = utc_range(start, end)
    data = live.by_label(s, e)
    if label is not None:
        data = {label: data.get(label, [])}
    groups, users = defaultdict(list), defaultdict(set)
    for lb, items in data.items():
        for it in items:
            groups[it["service_name"]].append(it)
            if it.get("request_count"):
                users[it["service_name"]].add(lb)
    out = [{"key": m, "service_id": items[0].get("service_id"), "generation_type": items[0].get("generation_type"),
            "keys": len(users[m]), **summarize(items)}
           for m, items in groups.items()]
    out.sort(key=lambda x: (-x["total_kt"], -x["requests"]))
    return [x for x in out if x["requests"]]


def matrix(start, end, model=None):
    s, e = utc_range(start, end)
    out = []
    for label, items in live.by_label(s, e).items():
        for it in _keep(items, model):
            if it.get("request_count"):
                out.append({"key": label, "name": UNATTRIBUTED_NAME if label == UNATTRIBUTED else label,
                            "model": it["service_name"], "total_kt": it.get("total_token") or 0,
                            "requests": it.get("request_count") or 0})
    return out


def ip_ranking(start, end, label=None, model=None):
    """Usage per client source IP; one statistics call per IP, so scope by label when possible."""
    s, e = utc_range(start, end)
    ips = live.source_ips(s, e, label)
    results = live.windows([(s, e, label, ip) for ip in ips])
    rows = []
    for ip, items in zip(ips, results):
        items = _keep(items, model)
        summ = summarize(items)
        if not summ["requests"]:
            continue
        top = max(items, key=lambda it: it.get("total_token") or 0)
        # Errors often come from a model with no tokens (failed calls), so name it separately
        worst = max(items, key=lambda it: it.get("error_count") or 0)
        rows.append({"key": ip, **summ, "top_model": top["service_name"],
                     "models": sum(1 for it in items if it.get("request_count")),
                     "top_error_model": worst["service_name"] if summ["errors"] else None,
                     "top_error_count": int(worst.get("error_count") or 0) if summ["errors"] else 0})
    grand = sum(r["total_kt"] for r in rows)
    for r in rows:
        r["token_share"] = r["total_kt"] / grand if grand else 0
    rows.sort(key=lambda x: (-x["total_kt"], -x["requests"]))
    return rows


# IANA zone for the display offset; Etc/GMT signs are inverted
MAAS_TZ = "Asia/Shanghai" if config.TZ_OFFSET_HOURS == 8 else f"Etc/GMT{-config.TZ_OFFSET_HOURS:+d}"
MAX_MINUTE_HOUR_SPAN = dt.timedelta(days=2)


def error_codes(start, end, service_id):
    """Error-code distribution of one model; MaaS only serves it for currently subscribed services."""
    s, e = utc_range(start, end)
    if service_id not in live.service_ids():
        return {"available": False}
    # MaaS: up to 2 days allows hour granularity, longer ranges only day
    hourly = e - s <= MAX_MINUTE_HOUR_SPAN
    try:
        d = live.error_chart(service_id, s, e, 2 if hourly else 3, MAAS_TZ)
    except HwApiError as ex:
        # ModelArts.6214: service taken offline after the service list was cached
        if "ModelArts.6214" in str(ex):
            return {"available": False}
        raise
    codes = (d.get("list_4xx") or []) + (d.get("list_5xx") or [])
    stamps = sorted({p["time"] for c in codes for p in c.get("list") or []})
    fmt = "%m-%d %H:00" if hourly else "%m-%d"
    axis = [(dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).replace(tzinfo=None) + TZ).strftime(fmt) for t in stamps]
    pos = {t: i for i, t in enumerate(stamps)}
    series = []
    for c in codes:
        data = [0] * len(stamps)
        for p in c.get("list") or []:
            data[pos[p["time"]]] += p.get("count") or 0
        if sum(data):
            series.append({"code": c["error_code"], "total": sum(data), "data": data})
    series.sort(key=lambda x: x["code"])
    return {"available": True, "granularity": "hour" if hourly else "day", "axis": axis,
            "series": series, "total": d.get("total") or 0}
