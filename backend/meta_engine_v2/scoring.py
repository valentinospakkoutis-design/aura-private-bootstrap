from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from meta_engine_v2.config import MetaEngineV2Config
from meta_engine_v2.learning import clamp, minmax_normalize
from meta_engine_v2.regime_memory import RegimeLearningResult
from meta_engine_v2.schemas import StrategySnapshot


@dataclass(slots=True)
class StrategyScore:
    strategy_name: str
    score: float
    regime_alignment: float
    normalized_return: float
    sharpe_proxy: float
    drawdown_penalty: float
    volatility_penalty: float
    consistency_bonus: float
    trade_reliability: float
    capital_efficiency: float
    data_quality: float


class StrategyScorer:
    def __init__(self, config: MetaEngineV2Config):
        self.config = config

    def score_all(
        self,
        *,
        strategies: List[StrategySnapshot],
        current_regime: str,
        regime_learning: Dict[str, RegimeLearningResult],
    ) -> Dict[str, StrategyScore]:
        if not strategies:
            return {}

        avg_returns = [strategy.avg_return_pct for strategy in strategies]
        low_return = min(avg_returns)
        high_return = max(avg_returns)
        scores: Dict[str, StrategyScore] = {}

        for strategy in strategies:
            learning = regime_learning.get(strategy.strategy_name, RegimeLearningResult(0.5, 0.0, 0))
            metadata = strategy.metadata
            if current_regime in metadata.preferred_regimes:
                regime_alignment = 1.0
            elif current_regime in metadata.avoid_regimes:
                regime_alignment = 0.0
            elif current_regime in metadata.neutral_regimes:
                regime_alignment = 0.55
            else:
                regime_alignment = learning.regime_score

            normalized_return = minmax_normalize(strategy.avg_return_pct, low_return, high_return, default=0.5)
            sharpe_proxy = clamp(strategy.avg_return_pct / max(strategy.volatility_pct, 1.0) / 4.0 + 0.5, 0.0, 1.0)
            drawdown_penalty = clamp(strategy.drawdown_pct / 12.0, 0.0, 1.0)
            volatility_penalty = clamp(strategy.volatility_pct / 20.0, 0.0, 1.0)
            consistency_bonus = clamp(strategy.consistency, 0.0, 1.0)
            trade_reliability = clamp(strategy.trades_count / max(self.config.min_trades_for_confidence, 1), 0.0, 1.0)
            capital_efficiency = clamp(1.0 - strategy.risk_used_pct / 10.0, 0.0, 1.0)
            data_quality = clamp(max(learning.data_quality, trade_reliability), 0.0, 1.0)

            raw_score = (
                normalized_return * self.config.weight_return
                + sharpe_proxy * self.config.weight_sharpe_proxy
                + (1.0 - drawdown_penalty) * self.config.weight_drawdown_penalty
                + (1.0 - volatility_penalty) * self.config.weight_volatility_penalty
                + consistency_bonus * self.config.weight_consistency_bonus
                + trade_reliability * self.config.weight_trade_reliability
                + capital_efficiency * self.config.weight_capital_efficiency
                + regime_alignment * self.config.weight_regime_alignment
            )
            score = clamp(raw_score * (0.55 + 0.45 * data_quality), 0.0, 1.0)

            scores[strategy.strategy_name] = StrategyScore(
                strategy_name=strategy.strategy_name,
                score=score,
                regime_alignment=clamp(regime_alignment, 0.0, 1.0),
                normalized_return=normalized_return,
                sharpe_proxy=sharpe_proxy,
                drawdown_penalty=drawdown_penalty,
                volatility_penalty=volatility_penalty,
                consistency_bonus=consistency_bonus,
                trade_reliability=trade_reliability,
                capital_efficiency=capital_efficiency,
                data_quality=data_quality,
            )
        return scores
