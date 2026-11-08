import datetime
import hashlib
import hmac
import json
import logging
import threading
import time
from urllib.parse import parse_qsl, quote, urlparse

import requests

from app import config

log = logging.getLogger(__name__)


class HwApiError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body


def _enc(s: str) -> str:
    return quote(s, safe="~")


def sign_request(method, url, headers, payload, ak, sk, now=None):
    """Add SDK-HMAC-SHA256 Authorization header; returns the header dict."""
    u = urlparse(url)
    t = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    h = {k.lower(): v for k, v in headers.items()}
    h["host"] = u.netloc
    h["x-sdk-date"] = t
    path = "/".join(_enc(p) for p in u.path.split("/"))
    if not path.endswith("/"):
        path += "/"
    query = "&".join(f"{_enc(k)}={_enc(v)}" for k, v in sorted(parse_qsl(u.query, keep_blank_values=True)))
    names = sorted(h)
    canonical_headers = "".join(f"{k}:{h[k].strip()}\n" for k in names)
    signed = ";".join(names)
    creq = "\n".join([method, path, query, canonical_headers, signed, hashlib.sha256(payload).hexdigest()])
    sts = "\n".join(["SDK-HMAC-SHA256", t, hashlib.sha256(creq.encode()).hexdigest()])
    sig = hmac.new(sk.encode(), sts.encode(), hashlib.sha256).hexdigest()
    h["authorization"] = f"SDK-HMAC-SHA256 Access={ak}, SignedHeaders={signed}, Signature={sig}"
    return h


class RateLimiter:
    """Sliding window (default one minute) shared by all threads."""

    def __init__(self, per_min, window=60):
        self.per_min = per_min
        self.window = window
        self.calls = []
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                self.calls = [c for c in self.calls if now - c < self.window]
                if len(self.calls) < self.per_min:
                    self.calls.append(now)
                    return
                wait = self.window - (now - self.calls[0])
            time.sleep(max(wait, 0.05))


_limiter = RateLimiter(config.RATE_LIMIT_PER_MIN)
# error-code-chart allows one call per 20 s per user; keep a second of margin
_error_chart_limiter = RateLimiter(1, 21)


class MaasClient:
    def __init__(self, ak=None, sk=None, project_id=None):
        self.ak = ak or config.HW_AK
        self.sk = sk or config.HW_SK
        self.session = requests.Session()
        self.limiter = _limiter
        self._project_id = project_id or config.HW_PROJECT_ID
        self.calls = 0
        self._calls_lock = threading.Lock()

    def _request(self, method, url, body=None, retries=3, limiter=None, wait_429=60):
        payload = json.dumps(body, ensure_ascii=False).encode() if body is not None else b""
        for attempt in range(retries + 1):
            (limiter or self.limiter).acquire()
            headers = sign_request(method, url, {"content-type": "application/json"}, payload, self.ak, self.sk)
            with self._calls_lock:
                self.calls += 1
            try:
                r = self.session.request(method, url, headers=headers, data=payload or None, timeout=30)
            except requests.RequestException as e:
                if attempt == retries:
                    raise
                log.warning("request error %s, retrying: %s", url, e)
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == retries:
                    raise HwApiError(r.status_code, r.text)
                wait = wait_429 if r.status_code == 429 else 5 * (attempt + 1)
                log.warning("HTTP %s from %s, retry in %ss: %s", r.status_code, url, wait, r.text[:200])
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                raise HwApiError(r.status_code, r.text)
            return r.json() if r.text else {}
        raise RuntimeError("unreachable")

    @property
    def project_id(self):
        if not self._project_id:
            d = self._request("GET", f"{config.IAM_ENDPOINT}/v3/projects?name={config.HW_REGION}")
            self._project_id = d["projects"][0]["id"]
        return self._project_id

    def _mon(self, path):
        return f"{config.MAAS_ENDPOINT}/v1/{self.project_id}/maas/monitoring{path}"

    def list_api_keys(self):
        items, offset = [], 0
        while True:
            url = f"{config.MAAS_ENDPOINT}/v2/{self.project_id}/maas/api-auth/api-keys?limit=100&offset={offset}"
            d = self._request("GET", url)
            page = (d.get("api_key_list") or {}).get("items") or []
            items.extend(page)
            total = (d.get("api_key_list") or {}).get("total") or 0
            offset += len(page)
            if not page or offset >= total:
                return items

    def service_statistics(self, start_ms, end_ms, api_keys=None, ips=None):
        """Per-service usage in [start, end); api_keys/ips=None means no filter (ips: at most 100)."""
        body = {"service_type": 2, "start_time": start_ms, "end_time": end_ms, "infer_type": "real_time"}
        if api_keys is not None:
            body["api_keys"] = api_keys
        if ips is not None:
            body["ips"] = ips
        d = self._request("POST", self._mon("/list-service-statistics"), body)
        return d.get("items") or []

    def source_ips(self, start_ms, end_ms, api_keys=None):
        """Client source IPs that made calls in [start, end); docs say Hong Kong only but cn-southwest-2 works."""
        items = []
        while True:
            body = {"service_type": 2, "limit": 100, "offset": len(items), "start_time": start_ms, "end_time": end_ms}
            if api_keys is not None:
                body["api_keys"] = api_keys
            d = self._request("POST", self._mon("/source-ips"), body)
            page = d.get("items") or []
            items.extend(page)
            if not page or len(items) >= (d.get("total") or 0):
                return items

    def list_services(self):
        """Services currently subscribed; models only seen in statistics may have been taken offline."""
        items = []
        while True:
            body = {"service_type": 2, "limit": 100, "offset": len(items)}
            d = self._request("POST", self._mon("/list-services"), body)
            page = d.get("items") or []
            items.extend(page)
            if not page or len(items) >= (d.get("total") or 0):
                return items

    def error_code_chart(self, service_id, start_ms, end_ms, granularity, timezone):
        """Error counts per code over time; granularity 1=minute, 2=hour, 3=day."""
        body = {"service_type": 2, "start_time": start_ms, "end_time": end_ms, "timezone": timezone,
                "time_granularity": granularity, "infer_type": "real_time"}
        return self._request("POST", self._mon(f"/{service_id}/error-code-chart"), body,
                             limiter=_error_chart_limiter, wait_429=21)
