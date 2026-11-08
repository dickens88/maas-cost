import datetime as dt
import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import analytics, config
from app.hwclient import HwApiError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title="MaaS Token Usage")


def _range(start: dt.date | None, end: dt.date | None):
    today = (analytics.live.utcnow() + analytics.TZ).date()
    end = end or today
    start = start or end - dt.timedelta(days=6)
    if start > end:
        raise HTTPException(400, "start must not be after end")
    return start, end


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except analytics.RangeError as e:
        raise HTTPException(400, str(e)) from e
    except HwApiError as e:
        raise HTTPException(502, f"MaaS API error: {e}") from e


@app.get("/api/overview")
def get_overview(start: dt.date | None = None, end: dt.date | None = None, model: str | None = None):
    return _run(analytics.overview, *_range(start, end), model or None)


@app.get("/api/trend")
def get_trend(start: dt.date | None = None, end: dt.date | None = None,
              granularity: Literal["hour", "day", "week"] = "day",
              metric: Literal["tokens", "requests"] = "tokens",
              label: str | None = None, model: str | None = None):
    return _run(analytics.trend, *_range(start, end), granularity, metric, label, model or None)


@app.get("/api/usage/keys")
def get_key_usage(start: dt.date | None = None, end: dt.date | None = None, model: str | None = None):
    return _run(analytics.key_ranking, *_range(start, end), model or None)


@app.get("/api/usage/models")
def get_model_usage(start: dt.date | None = None, end: dt.date | None = None, label: str | None = None):
    return _run(analytics.model_ranking, *_range(start, end), label)


@app.get("/api/usage-matrix")
def get_matrix(start: dt.date | None = None, end: dt.date | None = None, model: str | None = None):
    return _run(analytics.matrix, *_range(start, end), model or None)


if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = config.FRONTEND_DIST / path
        if path and f.is_file() and config.FRONTEND_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
