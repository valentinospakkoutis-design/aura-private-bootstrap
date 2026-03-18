from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(slots=True)
class MetaEngineV2Config:
    weight_return: float = 0.2
    weight_sharpe_proxy: float = 0.16
    weight_drawdown_penalty: float = 0.16
    weight_volatility_penalty: float = 0.08
    weight_consistency_bonus: float = 0.1
    weight_trade_reliability: float = 0.08
    weight_capital_efficiency: float = 0.04
    weight_regime_alignment: float = 0.18
    disable_score_threshold: float = 0.2
    limited_score_threshold: float = 0.38
    enabled_score_threshold: float = 0.55
    min_trades_for_confidence: int = 8
    min_history_points: int = 6
    low_confidence_regime_threshold: float = 0.55
    insufficient_data_global_reduction: float = 0.75
    uncertainty_global_reduction: float = 0.8
    rolling_window_points: int = 60
    decay_lambda: float = 0.06
    max_change_per_cycle_pct: float = 5.0
    meaningful_change_threshold_pct: float = 1.0
    default_strategy_cap_pct: float = 30.0
    min_cash_buffer_pct: float = 10.0
    max_weight_if_limited_pct: float = 12.0
    deployable_cap_by_mode: Dict[str, float] = field(
        default_factory=lambda: {
            "EXPANSION": 90.0,
            "NORMAL": 75.0,
            "CAUTION": 55.0,
            "DEFENSE": 35.0,
            "SURVIVAL": 20.0,
        }
    )
    drawdown_caution_pct: float = 5.0
    drawdown_defense_pct: float = 10.0
    drawdown_survival_pct: float = 20.0
    regime_to_mode: Dict[str, str] = field(
        default_factory=lambda: {
            "TRENDING": "NORMAL",
            "RANGING": "NORMAL",
            "HIGH_VOLATILITY": "CAUTION",
            "LOW_LIQUIDITY": "CAUTION",
            "CRISIS": "DEFENSE",
        }
    )

    def validate(self) -> None:
        total_weight = (
            self.weight_return
            + self.weight_sharpe_proxy
            + self.weight_drawdown_penalty
            + self.weight_volatility_penalty
            + self.weight_consistency_bonus
            + self.weight_trade_reliability
            + self.weight_capital_efficiency
            + self.weight_regime_alignment
        )
        if total_weight <= 0:
            raise ValueError("MetaEngineV2Config weights must sum to a positive value")


DEFAULT_META_ENGINE_V2_CONFIG = MetaEngineV2Config()
