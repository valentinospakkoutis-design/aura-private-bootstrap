from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from utils.time import utc_now


@dataclass(slots=True)
class StrategyRanking:
    strategy_name: str
    rank: int
    overall_score: float
    performance_score: float
    stability_score: float
    regime_alignment: float
    risk_efficiency: float
    consistency: float

    def is_top_performer(self, top_n: int = 5) -> bool:
        return self.rank <= top_n

    def is_underperformer(self, bottom_n: int = 3) -> bool:
        return self.rank > bottom_n


@dataclass(slots=True)
class RotationAction:
    strategy_name: str
    action: Literal["increase", "decrease", "new_entry", "exit"]
    previous_weight_pct: float
    target_weight_pct: float
    delta_pct: float
    reasoning: str


@dataclass(slots=True)
class CompetitionResult:
    strategy_rankings: Dict[str, StrategyRanking]
    competition_metrics: Dict[str, Dict[str, float]]
    top_performers: List[str]
    underperformers: List[str]


@dataclass(slots=True)
class RiskBudgetAllocation:
    strategy_name: str
    total_risk_budget_pct: float
    allocated_risk_pct: float
    cap_risk_pct: float
    unused_risk_pct: float


@dataclass(slots=True)
class RotationState:
    inflows: Dict[str, float]
    outflows: Dict[str, float]
    total_inflow_pct: float
    total_outflow_pct: float
    max_single_outflow: float
    momentum: str


class MetaEngineV3Output(BaseModel):
    regime: Dict
    global_mode: str
    strategy_allocations: Dict[str, float]
    strategy_status: Dict[str, str]
    strategy_scores: Dict[str, float]
    strategy_rankings: Dict[str, int]
    top_performers: List[str]
    underperformers: List[str]
    risk_budgets: Dict[str, float]
    total_risk_budget_pct: float
    total_allocated_risk_pct: float
    unused_risk_pct: float
    rotation_actions: List[Dict] = Field(default_factory=list)
    rotation_momentum: str = "stable"
    rotation_summary: str = ""
    cluster_exposure_summary: Dict[str, float] = Field(default_factory=dict)
    concentration_warning: bool = False
    diversification_ratio: float = 0.0
    total_allocated_pct: float = Field(ge=0.0, le=100.0)
    cash_buffer_pct: float = Field(ge=0.0, le=100.0)
    explanation: str
    reasoning_summary: str
    competition_summary: str = ""
    rotation_rationale: str = ""
    risk_budget_rationale: str = ""
    model_version: str = "3.0.0"
    evaluation_time: datetime = Field(default_factory=utc_now)


class MetaEngineV3Config(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    competition_metrics: List[Literal["performance", "stability", "regime_alignment", "risk_efficiency", "consistency"]] = [
        "performance",
        "stability",
        "regime_alignment",
        "risk_efficiency",
    ]
    metric_weights: Dict[Literal["performance", "stability", "regime_alignment", "risk_efficiency", "consistency"], float] = {
        "performance": 0.35,
        "stability": 0.2,
        "regime_alignment": 0.2,
        "risk_efficiency": 0.15,
        "consistency": 0.1,
    }
    top_performer_threshold: float = 0.55
    underperformer_threshold: float = 0.42
    max_rotation_per_cycle_pct: float = 8.0
    rotation_urgency_threshold: float = 0.25
    max_underperformer_outflow_pct: float = 5.0
    min_allocation_floor_pct: float = 1.0
    total_risk_budget_pct: float = 12.0
    risk_adjustment_by_mode: Dict[str, float] = {
        "EXPANSION": 1.5,
        "NORMAL": 1.0,
        "CAUTION": 0.67,
        "DEFENSE": 0.4,
        "SURVIVAL": 0.15,
    }
    risk_decay_per_drawdown_pct: float = 0.02
    min_active_strategies: int = 3
    max_active_strategies: int = 12
    max_single_strategy_pct: float = 30.0
    max_cluster_exposure_pct: float = 50.0
    concentration_penalty_threshold: float = 25.0
    concentration_penalty_per_point: float = 0.02
    ema_lookback_days: int = 14
    meaningful_change_threshold: float = 0.5


@dataclass(slots=True)
class MetaEngineV3State:
    previous_allocations: Dict[str, float] = field(default_factory=dict)
    previous_rankings: Dict[str, int] = field(default_factory=dict)
    rotation_history: List[RotationState] = field(default_factory=list)
    last_competition_time: Optional[datetime] = None
    last_rotation_time: Optional[datetime] = None
    strategy_momentum: Dict[str, float] = field(default_factory=dict)


def default_meta_engine_v3_config() -> MetaEngineV3Config:
    return MetaEngineV3Config()
