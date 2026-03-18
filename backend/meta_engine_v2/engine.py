from __future__ import annotations

from typing import Dict, List

from meta_engine_v2.config import DEFAULT_META_ENGINE_V2_CONFIG, MetaEngineV2Config
from meta_engine_v2.explain import build_full_explanation, build_reasoning_summary
from meta_engine_v2.rebalance import Rebalancer, normalize_weights_with_cap
from meta_engine_v2.regime_memory import RegimeMemory
from meta_engine_v2.scoring import StrategyScore, StrategyScorer
from meta_engine_v2.schemas import (
    MetaEngineV2Input,
    MetaEngineV2Output,
    RebalanceActions,
    StrategyAllocationV2,
)


class MetaEngineV2:
    def __init__(self, config: MetaEngineV2Config | None = None):
        self.config = config or DEFAULT_META_ENGINE_V2_CONFIG
        self.config.validate()
        self.scorer = StrategyScorer(self.config)
        self.regime_memory = RegimeMemory(self.config)
        self.rebalancer = Rebalancer(self.config)

    def evaluate(self, inputs: MetaEngineV2Input) -> MetaEngineV2Output:
        global_mode = self._determine_global_mode(inputs)
        regime_learning = self.regime_memory.learn_regime_scores(
            strategies=inputs.strategies,
            current_regime=inputs.regime.type,
            reference_time=inputs.evaluation_time,
        )
        scores = self.scorer.score_all(
            strategies=inputs.strategies,
            current_regime=inputs.regime.type,
            regime_learning=regime_learning,
        )

        insufficient_data = any(
            result.observations_used < self.config.min_history_points
            or result.data_quality < 0.5
            for result in regime_learning.values()
        )
        low_confidence = inputs.regime.confidence < self.config.low_confidence_regime_threshold
        deployable_cap = self.config.deployable_cap_by_mode[global_mode]
        conservative_reduction = 1.0
        if low_confidence:
            conservative_reduction *= self.config.uncertainty_global_reduction
        if insufficient_data:
            conservative_reduction *= self.config.insufficient_data_global_reduction
        deployable_cap *= conservative_reduction
        if insufficient_data and low_confidence:
            deployable_cap = min(deployable_cap, 25.0)
        deployable_cap = max(0.0, min(100.0 - self.config.min_cash_buffer_pct, deployable_cap))

        strategy_caps: Dict[str, float] = {}
        target_scores: Dict[str, float] = {}
        strategy_allocations: Dict[str, StrategyAllocationV2] = {}
        score_breakdown_lines: Dict[str, str] = {}

        for strategy in inputs.strategies:
            strategy_score = scores[strategy.strategy_name]
            status = self._status_for_score(strategy_score.score)
            cap = min(strategy.metadata.max_weight_pct, self.config.default_strategy_cap_pct)
            effective_score = strategy_score.score
            if status == "LIMITED":
                cap = min(cap, self.config.max_weight_if_limited_pct)
                effective_score *= 0.5
            elif status == "DISABLED":
                cap = 0.0
                effective_score = 0.0

            strategy_caps[strategy.strategy_name] = cap
            target_scores[strategy.strategy_name] = effective_score
            score_breakdown_lines[strategy.strategy_name] = (
                f"return={strategy_score.normalized_return:.2f}, sharpe={strategy_score.sharpe_proxy:.2f}, "
                f"alignment={strategy_score.regime_alignment:.2f}, quality={strategy_score.data_quality:.2f}"
            )
            strategy_allocations[strategy.strategy_name] = StrategyAllocationV2(
                strategy_name=strategy.strategy_name,
                weight_pct=0.0,
                status=status,
                score=strategy_score.score,
                regime_alignment=strategy_score.regime_alignment,
            )

        normalized_targets = normalize_weights_with_cap(
            strategy_scores=target_scores,
            strategy_caps=strategy_caps,
            deployable_cap_pct=deployable_cap,
        )
        rebalance_result = self.rebalancer.rebalance(
            target_weights=normalized_targets,
            previous_weights=inputs.previous_allocations,
        )

        for name, allocation in strategy_allocations.items():
            allocation.weight_pct = rebalance_result.final_weights.get(name, 0.0)

        total_allocated_pct = round(sum(item.weight_pct for item in strategy_allocations.values()), 6)
        cash_buffer_pct = round(max(0.0, 100.0 - total_allocated_pct), 6)
        reasoning_summary = build_reasoning_summary(
            regime_type=inputs.regime.type,
            regime_confidence=inputs.regime.confidence,
            global_mode=global_mode,
            total_allocated_pct=total_allocated_pct,
            cash_buffer_pct=cash_buffer_pct,
            conservative_reduction=conservative_reduction,
        )
        explanation = build_full_explanation(
            allocations=strategy_allocations,
            score_breakdown_lines=score_breakdown_lines,
        )

        return MetaEngineV2Output(
            regime=inputs.regime,
            strategy_allocations=strategy_allocations,
            global_mode=global_mode,
            rebalance_actions=RebalanceActions(
                increases=rebalance_result.increases,
                decreases=rebalance_result.decreases,
            ),
            explanation=explanation,
            reasoning_summary=reasoning_summary,
            total_allocated_pct=total_allocated_pct,
            cash_buffer_pct=cash_buffer_pct,
        )

    def _determine_global_mode(self, inputs: MetaEngineV2Input) -> str:
        mode_order = ["EXPANSION", "NORMAL", "CAUTION", "DEFENSE", "SURVIVAL"]
        mode = self.config.regime_to_mode.get(inputs.regime.type, "NORMAL")
        if inputs.regime.confidence < self.config.low_confidence_regime_threshold:
            mode = self._more_conservative(mode, mode_order)
        if inputs.portfolio.drawdown_pct >= self.config.drawdown_survival_pct:
            return "SURVIVAL"
        if inputs.portfolio.drawdown_pct >= self.config.drawdown_defense_pct:
            return "DEFENSE"
        if inputs.portfolio.drawdown_pct >= self.config.drawdown_caution_pct:
            return max(mode, "CAUTION", key=mode_order.index)
        if inputs.regime.type == "CRISIS" and mode_order.index(mode) < mode_order.index("DEFENSE"):
            return "DEFENSE"
        return mode

    @staticmethod
    def _more_conservative(mode: str, mode_order: List[str]) -> str:
        index = min(mode_order.index(mode) + 1, len(mode_order) - 1)
        return mode_order[index]

    def _status_for_score(self, score: float) -> str:
        if score < self.config.disable_score_threshold:
            return "DISABLED"
        if score < self.config.limited_score_threshold:
            return "LIMITED"
        return "ENABLED"
