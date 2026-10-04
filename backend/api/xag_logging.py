"""
api/xag_logging.py — Structured JSON logging helpers for XAG endpoints.

Phase 7: all XAG endpoint activity emits JSON log lines to stdout.
         Compatible with CloudWatch Logs Insights, DataDog, and any
         JSON-aware log aggregator.

Usage
-----
    from api.xag_logging import xag_log

    xag_log("order.placed", ticket=12345, side="buy", volume=0.5,
             symbol="XAGUSD-STD", fill_price=30.123)

    xag_log("position.closed", ticket=11001, pnl=-42.50)

    xag_log("ws.reconnect", attempt=3, backoff_s=4.8)

Log line shape
--------------
{
  "ts":      "<ISO 8601 UTC>",
  "lvl":     "INFO" | "WARNING" | "ERROR",
  "subsys":  "xag",
  "event":   "<dotted.event.name>",
  "k1":      v1,
  ...
}
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any


def xag_log(
    event: str,
    *,
    lvl: str = "INFO",
    **fields: Any,
) -> None:
    """
    Emit a single structured JSON log line to stdout.

    Parameters
    ----------
    event   : dotted event name, e.g. "order.placed", "healthz.stale"
    lvl     : "INFO" | "WARNING" | "ERROR"
    **fields: arbitrary key=value context added to the log record
    """
    record = {
        "ts":     datetime.now(timezone.utc).isoformat(),
        "lvl":    lvl,
        "subsys": "xag",
        "event":  event,
        **fields,
    }
    print(json.dumps(record, default=str), file=sys.stdout, flush=True)


def xag_warn(event: str, **fields: Any) -> None:
    xag_log(event, lvl="WARNING", **fields)


def xag_error(event: str, **fields: Any) -> None:
    xag_log(event, lvl="ERROR", **fields)
