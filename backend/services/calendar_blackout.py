"""Calendar Blackout — block trades around high-impact macro events.

Hardcoded 2025-2027 schedule for FOMC, CPI, NFP, GDP.
Blocks new entries 30 minutes before and 30 minutes after each event.
Falls back silently on any error.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_EVENTS = [
    # FOMC 2025
    ("FOMC", "2025-01-29 19:00"), ("FOMC", "2025-03-19 18:00"),
    ("FOMC", "2025-05-07 18:00"), ("FOMC", "2025-06-18 18:00"),
    ("FOMC", "2025-07-30 18:00"), ("FOMC", "2025-09-17 18:00"),
    ("FOMC", "2025-11-05 19:00"), ("FOMC", "2025-12-17 19:00"),
    # FOMC 2026
    ("FOMC", "2026-01-28 19:00"), ("FOMC", "2026-03-18 18:00"),
    ("FOMC", "2026-05-06 18:00"), ("FOMC", "2026-06-17 18:00"),
    ("FOMC", "2026-07-29 18:00"), ("FOMC", "2026-09-16 18:00"),
    ("FOMC", "2026-11-04 19:00"), ("FOMC", "2026-12-16 19:00"),
    # FOMC 2027
    ("FOMC", "2027-01-27 19:00"), ("FOMC", "2027-03-17 18:00"),
    ("FOMC", "2027-05-05 18:00"), ("FOMC", "2027-06-16 18:00"),
    # CPI 2025
    ("CPI", "2025-01-15 13:30"), ("CPI", "2025-02-12 13:30"),
    ("CPI", "2025-03-12 13:30"), ("CPI", "2025-04-10 13:30"),
    ("CPI", "2025-05-13 13:30"), ("CPI", "2025-06-11 13:30"),
    ("CPI", "2025-07-15 13:30"), ("CPI", "2025-08-13 13:30"),
    ("CPI", "2025-09-10 13:30"), ("CPI", "2025-10-15 13:30"),
    ("CPI", "2025-11-13 13:30"), ("CPI", "2025-12-10 13:30"),
    # CPI 2026
    ("CPI", "2026-01-14 13:30"), ("CPI", "2026-02-11 13:30"),
    ("CPI", "2026-03-11 13:30"), ("CPI", "2026-04-09 13:30"),
    ("CPI", "2026-05-13 13:30"), ("CPI", "2026-06-10 13:30"),
    ("CPI", "2026-07-15 13:30"), ("CPI", "2026-08-12 13:30"),
    ("CPI", "2026-09-09 13:30"), ("CPI", "2026-10-14 13:30"),
    ("CPI", "2026-11-12 13:30"), ("CPI", "2026-12-09 13:30"),
    # NFP 2025
    ("NFP", "2025-01-10 13:30"), ("NFP", "2025-02-07 13:30"),
    ("NFP", "2025-03-07 13:30"), ("NFP", "2025-04-04 13:30"),
    ("NFP", "2025-05-02 13:30"), ("NFP", "2025-06-06 13:30"),
    ("NFP", "2025-07-03 13:30"), ("NFP", "2025-08-01 13:30"),
    ("NFP", "2025-09-05 13:30"), ("NFP", "2025-10-03 13:30"),
    ("NFP", "2025-11-07 13:30"), ("NFP", "2025-12-05 13:30"),
    # NFP 2026
    ("NFP", "2026-01-09 13:30"), ("NFP", "2026-02-06 13:30"),
    ("NFP", "2026-03-06 13:30"), ("NFP", "2026-04-03 13:30"),
    ("NFP", "2026-05-08 13:30"), ("NFP", "2026-06-05 13:30"),
    ("NFP", "2026-07-10 13:30"), ("NFP", "2026-08-07 13:30"),
    ("NFP", "2026-09-04 13:30"), ("NFP", "2026-10-02 13:30"),
    ("NFP", "2026-11-06 13:30"), ("NFP", "2026-12-04 13:30"),
    # GDP advance 2025-2026
    ("GDP", "2025-01-30 13:30"), ("GDP", "2025-04-30 13:30"),
    ("GDP", "2025-07-30 13:30"), ("GDP", "2025-10-30 13:30"),
    ("GDP", "2026-01-29 13:30"), ("GDP", "2026-04-29 13:30"),
    ("GDP", "2026-07-29 13:30"), ("GDP", "2026-10-29 13:30"),
]

_PARSED = []
for _label, _dt_str in _EVENTS:
    try:
        _dt = datetime.strptime(_dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        _PARSED.append((_label, _dt))
    except Exception:
        pass

_BLACKOUT_MINUTES = 30


def is_calendar_blackout(now=None):
    """Return {blackout: bool, reason: str, event: str|None, minutes_to_event: float|None}."""
    try:
        if now is None:
            now = datetime.now(timezone.utc)
        for label, event_dt in _PARSED:
            diff = (event_dt - now).total_seconds() / 60.0
            if -_BLACKOUT_MINUTES <= diff <= _BLACKOUT_MINUTES:
                if diff >= 0:
                    reason = f"{label} in {diff:.0f}min — blackout window"
                else:
                    reason = f"{label} was {-diff:.0f}min ago — blackout window"
                return {"blackout": True, "reason": reason, "event": label, "minutes_to_event": round(diff, 1)}
        return {"blackout": False, "reason": None, "event": None, "minutes_to_event": None}
    except Exception as _e:
        logger.debug(f"[calendar_blackout] check failed: {_e}")
        return {"blackout": False, "reason": None, "event": None, "minutes_to_event": None}
