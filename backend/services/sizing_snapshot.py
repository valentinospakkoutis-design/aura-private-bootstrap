"""Trusted adapter contract for auto-entry risk; no synthetic fallback data."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class SizingSnapshot:
    user_id: int
    broker: object  # Exact currently bound account adapter, not a shared global.
    paper_mode: bool
    observed_at: datetime
    equity_usd: float
    peak_equity_usd: float  # Cash-flow adjusted, persisted account high-water mark.
    available_cash_usd: float
    exposure_by_symbol: Mapping[str, float]  # Gross MTM + pending reservations.
    complete: bool  # Provider confirms full account reconciliation.


def validate_snapshot(state, user_id, broker, paper_mode):
    if not isinstance(state, SizingSnapshot) or state.complete is not True:
        raise ValueError("incomplete_risk_snapshot")
    if type(state.user_id) is not int or state.user_id != user_id or state.broker is not broker:
        raise ValueError("risk_snapshot_account_mismatch")
    if type(state.paper_mode) is not bool or state.paper_mode != paper_mode:
        raise ValueError("risk_snapshot_mode_mismatch")
    if not isinstance(state.observed_at, datetime) or state.observed_at.tzinfo is None:
        raise ValueError("risk_snapshot_timestamp_unverified")
    age = (datetime.now(timezone.utc) - state.observed_at).total_seconds()
    if not 0 <= age <= 60:
        raise ValueError("risk_snapshot_stale_or_future")
    def number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("invalid_snapshot_number")
        return float(value)
    equity, peak, cash = map(number, (state.equity_usd, state.peak_equity_usd, state.available_cash_usd))
    if equity <= 0 or peak < equity or cash > equity:
        raise ValueError("inconsistent_snapshot_equity")
    if not isinstance(state.exposure_by_symbol, Mapping):
        raise ValueError("missing_exposure_map")
    exposures = {}
    for symbol, value in state.exposure_by_symbol.items():
        if not isinstance(symbol, str) or not symbol or symbol != symbol.upper():
            raise ValueError("invalid_exposure_symbol")
        exposures[symbol] = number(value)
    if not math.isfinite(sum(exposures.values())):
        raise ValueError("invalid_total_exposure")
    return SizingSnapshot(user_id, broker, paper_mode, state.observed_at,
                          equity, peak, cash, MappingProxyType(exposures), True)
