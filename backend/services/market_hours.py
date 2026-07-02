"""
Market-hours gate for auto-trading (Phase 2 of non-crypto paper trading).

`is_tradeable_now(symbol)` answers "can we open an entry for this symbol right
now?" purely on a *time* basis (session / weekend / holiday / DST):

  - Crypto (USDC/USDT pairs, or anything in ALLOWED_AUTO_TRADE_SYMBOLS) trades
    24/7 → always True. The crypto path never touches an exchange calendar, so a
    broken calendar lib can never block crypto.
  - Non-crypto symbols map to the exchange whose price we actually consult
    (see market_data.symbol_map): stocks to NYSE, index prices to LSE/Xetra,
    futures to their CME/COMEX Globex calendar. Session, weekend, holiday and
    DST handling all come from pandas_market_calendars.

This module is corrective/inert in Φ2: the whitelist in place_auto_order still
admits only crypto, so this gate only starts affecting non-crypto in Φ3.
"""

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# AURA non-crypto symbol -> pandas_market_calendars calendar name.
#
# The calendar must match the *price source* (market_data.symbol_map), not the
# instrument's nominal exchange:
#   BAC / JPM   -> yfinance BAC / JPM       (NYSE cash)          -> "NYSE"
#   ES1! / YM1! -> yfinance ES=F / YM=F     (CME equity futures) -> "CME_Equity"
#   SI1!        -> yfinance SI=F            (COMEX silver fut)   -> "CMEGlobex_SI"
#   HG1!        -> yfinance HG=F            (COMEX copper fut)   -> "CMEGlobex_HG"
#   FTSE1!      -> yfinance ^FTSE           (LSE cash index)     -> "LSE"
#   DAX1!       -> yfinance ^GDAXI          (Xetra cash index)   -> "XETR"
#
# NOTE (CME trade-off): the 4 futures use their native near-24h Globex calendars,
# so the gate is deliberately permissive for them — it blocks only weekends, the
# daily maintenance break and full holiday closures, and *keeps them open on the
# shortened sessions* that CME runs on US cash holidays (e.g. July 4). The cash
# venues (NYSE/LSE/XETR) close fully on their holidays. This is real-world-accurate
# given we price the futures off ES=F/YM=F/SI=F/HG=F.
EXCHANGE_CALENDAR = {
    "BAC": "NYSE",
    "JPM": "NYSE",
    "ES1!": "CME_Equity",
    "YM1!": "CME_Equity",
    "SI1!": "CMEGlobex_SI",
    "HG1!": "CMEGlobex_HG",
    "FTSE1!": "LSE",
    "DAX1!": "XETR",
}


def _is_crypto(symbol: str) -> bool:
    """Crypto trades 24/7. USDC/USDT suffix covers all auto-trade pairs; the
    ALLOWED_AUTO_TRADE_SYMBOLS membership check is a lazy belt-and-suspenders
    (imported inside the function to avoid a circular import with the engine)."""
    if symbol.endswith("USDC") or symbol.endswith("USDT"):
        return True
    try:
        from services.auto_trading_engine import ALLOWED_AUTO_TRADE_SYMBOLS
        return symbol in ALLOWED_AUTO_TRADE_SYMBOLS
    except Exception:
        return False


@lru_cache(maxsize=16)
def _get_calendar(name: str):
    import pandas_market_calendars as mcal
    return mcal.get_calendar(name)


def _to_utc_timestamp(now: Optional[datetime]):
    import pandas as pd
    if now is None:
        now = datetime.now(timezone.utc)
    ts = pd.Timestamp(now)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts


def is_tradeable_now(symbol: str, now: Optional[datetime] = None) -> bool:
    """
    True if an entry may be opened for `symbol` at `now` (UTC; defaults to the
    current time) on a market-hours basis.

    Crypto → always True. Non-crypto → open only during its exchange session
    (weekends, holidays and DST handled by pandas_market_calendars).

    Fail-closed for non-crypto: an unknown symbol or any calendar error returns
    False, so we never open a stock/futures position when we cannot verify the
    session is actually open — that is exactly the data-integrity leak this gate
    exists to prevent.
    """
    symbol = (symbol or "").upper().strip()
    if not symbol:
        return False

    if _is_crypto(symbol):
        return True

    cal_name = EXCHANGE_CALENDAR.get(symbol)
    if cal_name is None:
        logger.warning("[market_hours] no exchange calendar for %s — treating as closed", symbol)
        return False

    try:
        import pandas as pd

        ts = _to_utc_timestamp(now)
        cal = _get_calendar(cal_name)
        # Build a small window around `now` so open_at_time always has trading
        # days to reference even when `now` itself lands on a weekend/holiday.
        sched = cal.schedule(
            start_date=(ts - pd.Timedelta(days=4)).date().isoformat(),
            end_date=(ts + pd.Timedelta(days=4)).date().isoformat(),
        )
        return bool(cal.open_at_time(sched, ts))
    except Exception as exc:
        logger.warning(
            "[market_hours] calendar check failed for %s (%s) — treating as closed: %s",
            symbol, cal_name, exc,
        )
        return False
