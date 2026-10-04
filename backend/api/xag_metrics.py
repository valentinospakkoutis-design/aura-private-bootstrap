"""
api/xag_metrics.py — Operational metrics for the XAG data pipeline.

Exposes a single endpoint:
    GET /api/xag/metrics

No Prometheus dependency — returns plain JSON so it works out of the box
on Railway without a sidecar. Wire it to a Grafana HTTP data source or
poll it from an uptime monitor (UptimeRobot, Better Stack, etc.).

Metrics collected:
    snapshot_requests_total   — total calls to /api/xag/snapshot
    snapshot_cache_hits       — served from cache (no yfinance call)
    snapshot_cache_misses     — triggered a real fetch
    snapshot_errors_total     — upstream failures (HTTP 502)
    snapshot_provider_latency_ms_last — last successful fetch duration (ms)
    snapshot_consecutive_failures     — how many fetches in a row failed
    snapshot_last_ok_at       — ISO-8601 of last successful fetch

    ohlc_requests_total       — total calls to /api/xag/ohlc
    ohlc_cache_hits
    ohlc_cache_misses
    ohlc_errors_total
    ohlc_provider_latency_ms_last
    ohlc_consecutive_failures

    invalid_bars_dropped_total — OHLC bars that failed sanity check
    rsi_null_total             — how many snapshot responses had rsi_1m=None

    uptime_seconds             — seconds since the metrics module was imported
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Lock
from fastapi import APIRouter

router = APIRouter(prefix="/api/xag", tags=["xag-metrics"])

# ── Internal counters ─────────────────────────────────────────────────────────
_lock = Lock()
_boot_ts = time.monotonic()

_counters: dict = {
    # Snapshot
    "snapshot_requests_total":        0,
    "snapshot_cache_hits":            0,
    "snapshot_cache_misses":          0,
    "snapshot_errors_total":          0,
    "snapshot_provider_latency_ms_last": None,
    "snapshot_consecutive_failures":  0,
    "snapshot_last_ok_at":            None,

    # OHLC
    "ohlc_requests_total":            0,
    "ohlc_cache_hits":                0,
    "ohlc_cache_misses":              0,
    "ohlc_errors_total":              0,
    "ohlc_provider_latency_ms_last":  None,
    "ohlc_consecutive_failures":      0,

    # Data quality
    "invalid_bars_dropped_total":     0,
    "rsi_null_total":                 0,
}


# ── Public increment helpers (called from xag.py) ─────────────────────────────

def inc_snapshot_request() -> None:
    with _lock:
        _counters["snapshot_requests_total"] += 1


def inc_snapshot_cache_hit() -> None:
    with _lock:
        _counters["snapshot_cache_hits"] += 1


def inc_snapshot_cache_miss() -> None:
    with _lock:
        _counters["snapshot_cache_misses"] += 1


def record_snapshot_ok(latency_ms: float, rsi_1m_is_none: bool) -> None:
    with _lock:
        _counters["snapshot_provider_latency_ms_last"] = round(latency_ms, 1)
        _counters["snapshot_consecutive_failures"] = 0
        _counters["snapshot_last_ok_at"] = datetime.now(timezone.utc).isoformat()
        if rsi_1m_is_none:
            _counters["rsi_null_total"] += 1


def record_snapshot_error() -> None:
    with _lock:
        _counters["snapshot_errors_total"] += 1
        _counters["snapshot_consecutive_failures"] += 1


def inc_ohlc_request() -> None:
    with _lock:
        _counters["ohlc_requests_total"] += 1


def inc_ohlc_cache_hit() -> None:
    with _lock:
        _counters["ohlc_cache_hits"] += 1


def inc_ohlc_cache_miss() -> None:
    with _lock:
        _counters["ohlc_cache_misses"] += 1


def record_ohlc_ok(latency_ms: float) -> None:
    with _lock:
        _counters["ohlc_provider_latency_ms_last"] = round(latency_ms, 1)
        _counters["ohlc_consecutive_failures"] = 0


def record_ohlc_error() -> None:
    with _lock:
        _counters["ohlc_errors_total"] += 1
        _counters["ohlc_consecutive_failures"] += 1


def inc_invalid_bars(n: int = 1) -> None:
    with _lock:
        _counters["invalid_bars_dropped_total"] += n


# ── Derived / alert helpers ───────────────────────────────────────────────────

def _is_market_hour() -> bool:
    """
    Silver futures (CME SI) trade Sun 18:00 – Fri 17:00 CT with a daily
    60-min break (16:00–17:00 CT).  This is a lightweight approximation
    in UTC: market is broadly open Mon–Fri 23:00–22:00 UTC (next day).
    Good enough to suppress false stale-data alerts on weekends.
    """
    now = datetime.now(timezone.utc)
    weekday = now.weekday()          # 0=Mon … 6=Sun
    hour    = now.hour
    # Weekend: Sat all day (5), Sun before 22:00 UTC
    if weekday == 5:
        return False
    if weekday == 6 and hour < 22:
        return False
    # Daily maintenance break: ~22:00–23:00 UTC (16:00–17:00 CT)
    if hour == 22:
        return False
    return True


def _build_alerts(c: dict, uptime: float) -> list[dict]:
    alerts = []

    # ── Consecutive provider failures ─────────────────────────────────────────
    if c["snapshot_consecutive_failures"] >= 3:
        alerts.append({
            "name":    "snapshot_provider_down",
            "message": f"{c['snapshot_consecutive_failures']} consecutive snapshot fetch failures",
            "severity": "critical" if c["snapshot_consecutive_failures"] >= 5 else "warning",
        })

    if c["ohlc_consecutive_failures"] >= 3:
        alerts.append({
            "name":    "ohlc_provider_down",
            "message": f"{c['ohlc_consecutive_failures']} consecutive OHLC fetch failures",
            "severity": "critical" if c["ohlc_consecutive_failures"] >= 5 else "warning",
        })

    # ── Stale data during market hours ────────────────────────────────────────
    last_ok = c.get("snapshot_last_ok_at")
    if last_ok and _is_market_hour():
        try:
            last_ok_dt = datetime.fromisoformat(last_ok)
            age_s = (datetime.now(timezone.utc) - last_ok_dt).total_seconds()
            if age_s > 120:   # >2 min without a successful snapshot during market hours
                alerts.append({
                    "name":    "snapshot_stale_market_hours",
                    "message": f"No successful snapshot for {int(age_s)}s during market hours",
                    "severity": "warning",
                })
        except Exception:
            pass

    # ── High error rate (>25% of requests in this session) ───────────────────
    total = c["snapshot_requests_total"]
    errors = c["snapshot_errors_total"]
    if total >= 10 and errors / total > 0.25:
        alerts.append({
            "name":    "snapshot_high_error_rate",
            "message": f"Snapshot error rate {errors}/{total} ({100*errors//total}%)",
            "severity": "warning",
        })

    return alerts


# ── Metrics endpoint ──────────────────────────────────────────────────────────

@router.get("/metrics")
def get_metrics():
    """
    Return operational counters for the XAG data pipeline.
    Usable as a Grafana HTTP JSON data source or a simple uptime-monitor target.

    Cache hit ratio = cache_hits / requests_total  (higher = better)
    Consecutive failures > 0 during market hours = provider issue to investigate.
    """
    with _lock:
        c = dict(_counters)   # snapshot under lock

    uptime = round(time.monotonic() - _boot_ts, 1)
    alerts = _build_alerts(c, uptime)

    # Cache hit ratios
    snap_total = c["snapshot_requests_total"]
    ohlc_total = c["ohlc_requests_total"]

    return {
        "snapshot": {
            "requests_total":           c["snapshot_requests_total"],
            "cache_hits":               c["snapshot_cache_hits"],
            "cache_misses":             c["snapshot_cache_misses"],
            "cache_hit_ratio":          round(c["snapshot_cache_hits"] / snap_total, 3) if snap_total else None,
            "errors_total":             c["snapshot_errors_total"],
            "consecutive_failures":     c["snapshot_consecutive_failures"],
            "provider_latency_ms_last": c["snapshot_provider_latency_ms_last"],
            "last_ok_at":               c["snapshot_last_ok_at"],
        },
        "ohlc": {
            "requests_total":           c["ohlc_requests_total"],
            "cache_hits":               c["ohlc_cache_hits"],
            "cache_misses":             c["ohlc_cache_misses"],
            "cache_hit_ratio":          round(c["ohlc_cache_hits"] / ohlc_total, 3) if ohlc_total else None,
            "errors_total":             c["ohlc_errors_total"],
            "consecutive_failures":     c["ohlc_consecutive_failures"],
            "provider_latency_ms_last": c["ohlc_provider_latency_ms_last"],
        },
        "data_quality": {
            "invalid_bars_dropped_total": c["invalid_bars_dropped_total"],
            "rsi_null_total":             c["rsi_null_total"],
        },
        "process": {
            "uptime_seconds":  uptime,
            "market_open_now": _is_market_hour(),
        },
        "alerts": alerts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
