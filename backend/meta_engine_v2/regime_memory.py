from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from meta_engine_v2.config import MetaEngineV2Config
from meta_engine_v2.learning import age_days, decay_weight, recent_window, weighted_average
from meta_engine_v2.schemas import StrategySnapshot


@dataclass(slots=True)
class RegimeLearningResult:
    regime_score: float
    data_quality: float
    observations_used: int


class RegimeMemory:
    def __init__(self, config: MetaEngineV2Config):
        self.config = config

    def learn_regime_scores(
        self,
        *,
        strategies: List[StrategySnapshot],
        current_regime: str,
        reference_time: datetime,
    ) -> Dict[str, RegimeLearningResult]:
        results: Dict[str, RegimeLearningResult] = {}
        for strategy in strategies:
            points = recent_window(strategy.history, self.config.rolling_window_points)
            matching = [point for point in points if point.regime == current_regime]
            weighted_points = []
            for point in matching:
                weight = decay_weight(age_days(reference_time, point.timestamp), self.config.decay_lambda)
                signal = (
                    point.pnl_pct * 0.45
                    + point.win_rate * 4.0
                    + point.consistency * 3.0
                    - point.drawdown_pct * 0.35
                    - point.volatility_pct * 0.15
                )
                weighted_points.append((signal, weight))

            raw_score = weighted_average(weighted_points, default=0.0)
            regime_score = 1.0 / (1.0 + pow(2.718281828, -raw_score / 4.0))
            observations_used = len(matching)
            data_quality = min(1.0, observations_used / max(self.config.min_history_points, 1))
            if not matching and strategy.metadata.preferred_regimes:
                regime_score = 1.0 if current_regime in strategy.metadata.preferred_regimes else 0.35
                if current_regime in strategy.metadata.avoid_regimes:
                    regime_score = 0.05
            results[strategy.strategy_name] = RegimeLearningResult(
                regime_score=regime_score,
                data_quality=data_quality,
                observations_used=observations_used,
            )
        return results
