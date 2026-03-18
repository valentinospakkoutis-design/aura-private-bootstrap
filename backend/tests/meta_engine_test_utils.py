from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from meta_engine_v2.schemas import (
    MetaEngineV2Input,
    PerformancePoint,
    PortfolioContext,
    RegimeState,
    StrategyMetadata,
    StrategySnapshot,
)


FIXED_NOW = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)


def make_point(
    *,
    days_ago: int,
    regime: str = "TRENDING",
    pnl_pct: float = 0.0,
    win_rate: float = 0.5,
    drawdown_pct: float = 0.0,
    volatility_pct: float = 0.0,
    consistency: float = 0.5,
) -> PerformancePoint:
    return PerformancePoint(
        timestamp=FIXED_NOW - timedelta(days=days_ago),
        regime=regime,
        pnl_pct=pnl_pct,
        win_rate=win_rate,
        drawdown_pct=drawdown_pct,
        volatility_pct=volatility_pct,
        consistency=consistency,
    )


def make_snapshot(
    strategy_name: str,
    *,
    avg_return_pct: float = 3.0,
    drawdown_pct: float = 3.0,
    volatility_pct: float = 4.0,
    consistency: float = 0.6,
    trades_count: int = 12,
    risk_used_pct: float = 2.0,
    preferred_regimes: Sequence[str] | None = None,
    neutral_regimes: Sequence[str] | None = None,
    avoid_regimes: Sequence[str] | None = None,
    max_weight_pct: float = 30.0,
    history: Iterable[PerformancePoint] | None = None,
) -> StrategySnapshot:
    return StrategySnapshot(
        strategy_name=strategy_name,
        avg_return_pct=avg_return_pct,
        drawdown_pct=drawdown_pct,
        volatility_pct=volatility_pct,
        consistency=consistency,
        trades_count=trades_count,
        risk_used_pct=risk_used_pct,
        metadata=StrategyMetadata(
            strategy_name=strategy_name,
            preferred_regimes=list(preferred_regimes or []),
            neutral_regimes=list(neutral_regimes or []),
            avoid_regimes=list(avoid_regimes or []),
            max_weight_pct=max_weight_pct,
        ),
        history=list(history or []),
    )


def make_v2_input(
    strategies: Sequence[StrategySnapshot],
    *,
    regime_type: str = "TRENDING",
    confidence: float = 0.8,
    drawdown_pct: float = 0.0,
    previous_allocations: dict[str, float] | None = None,
) -> MetaEngineV2Input:
    return MetaEngineV2Input(
        regime=RegimeState(type=regime_type, confidence=confidence),
        portfolio=PortfolioContext(equity=100_000.0, drawdown_pct=drawdown_pct, heat_pct=0.0),
        strategies=list(strategies),
        previous_allocations=dict(previous_allocations or {}),
        evaluation_time=FIXED_NOW,
    )


def make_v3_strategy(
    name: str,
    *,
    pnl_pct: float = 0.0,
    win_rate: float = 0.5,
    drawdown_pct: float = 0.0,
    volatility_pct: float = 0.0,
    consistency: float = 0.5,
    group: str = "default",
    regime_alignment: float | None = None,
) -> dict:
    payload = {
        "name": name,
        "pnl_pct": pnl_pct,
        "win_rate": win_rate,
        "drawdown_pct": drawdown_pct,
        "volatility_pct": volatility_pct,
        "consistency": consistency,
        "group": group,
    }
    if regime_alignment is not None:
        payload["regime_alignment"] = regime_alignment
    return payload