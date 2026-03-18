from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal

from pydantic import BaseModel, Field

from utils.time import utc_now

RegimeType = Literal["TRENDING", "RANGING", "HIGH_VOLATILITY", "LOW_LIQUIDITY", "CRISIS"]
GlobalMode = Literal["EXPANSION", "NORMAL", "CAUTION", "DEFENSE", "SURVIVAL"]
StrategyStatus = Literal["ENABLED", "LIMITED", "DISABLED"]


class RegimeState(BaseModel):
    type: RegimeType
    confidence: float = Field(ge=0.0, le=1.0)


class PortfolioContext(BaseModel):
    equity: float = Field(gt=0)
    drawdown_pct: float = Field(default=0.0, ge=0)
    heat_pct: float = Field(default=0.0, ge=0)


class PerformancePoint(BaseModel):
    timestamp: datetime
    regime: RegimeType
    pnl_pct: float = 0.0
    win_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    drawdown_pct: float = Field(default=0.0, ge=0)
    volatility_pct: float = Field(default=0.0, ge=0)
    consistency: float = Field(default=0.5, ge=0.0, le=1.0)
    trades: int = Field(default=0, ge=0)
    risk_used_pct: float = Field(default=0.0, ge=0)


class StrategyMetadata(BaseModel):
    strategy_name: str
    tags: List[str] = Field(default_factory=list)
    group: str | None = None
    preferred_regimes: List[RegimeType] = Field(default_factory=list)
    neutral_regimes: List[RegimeType] = Field(default_factory=list)
    avoid_regimes: List[RegimeType] = Field(default_factory=list)
    max_weight_pct: float = Field(default=30.0, ge=0.0, le=100.0)
    min_weight_pct: float = Field(default=0.0, ge=0.0, le=100.0)


class StrategySnapshot(BaseModel):
    strategy_name: str
    pnl_pct: float = 0.0
    win_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    drawdown_pct: float = Field(default=0.0, ge=0)
    volatility_pct: float = Field(default=0.0, ge=0)
    consistency: float = Field(default=0.5, ge=0.0, le=1.0)
    trades_count: int = Field(default=0, ge=0)
    avg_return_pct: float = 0.0
    risk_used_pct: float = Field(default=0.0, ge=0)
    metadata: StrategyMetadata
    history: List[PerformancePoint] = Field(default_factory=list)


class RebalanceAction(BaseModel):
    strategy_name: str
    from_weight_pct: float = Field(ge=0.0, le=100.0)
    to_weight_pct: float = Field(ge=0.0, le=100.0)
    delta_pct: float


class StrategyAllocationV2(BaseModel):
    strategy_name: str
    weight_pct: float = Field(ge=0.0, le=100.0)
    status: StrategyStatus
    score: float = Field(ge=0.0, le=1.0)
    regime_alignment: float = Field(ge=0.0, le=1.0)


class RebalanceActions(BaseModel):
    increases: List[RebalanceAction] = Field(default_factory=list)
    decreases: List[RebalanceAction] = Field(default_factory=list)


class MetaEngineV2Input(BaseModel):
    regime: RegimeState
    portfolio: PortfolioContext
    strategies: List[StrategySnapshot]
    previous_allocations: Dict[str, float] = Field(default_factory=dict)
    evaluation_time: datetime = Field(default_factory=utc_now)


class MetaEngineV2Output(BaseModel):
    regime: RegimeState
    strategy_allocations: Dict[str, StrategyAllocationV2]
    global_mode: GlobalMode
    rebalance_actions: RebalanceActions
    explanation: str
    reasoning_summary: str
    total_allocated_pct: float = Field(ge=0.0, le=100.0)
    cash_buffer_pct: float = Field(ge=0.0, le=100.0)
    model_version: str = "2.0.0"
