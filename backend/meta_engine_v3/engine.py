from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Optional

from meta_engine_v3.competition import StrategyCompetitor
from meta_engine_v3.risk_budget import RiskBudgetAllocator
from meta_engine_v3.rotation import CapitalRotationEngine
from meta_engine_v3.schemas import MetaEngineV3Config, MetaEngineV3Output, MetaEngineV3State, default_meta_engine_v3_config


class MetaEngineV3:
    def __init__(self, config: MetaEngineV3Config | None = None):
        self.config = config or default_meta_engine_v3_config()
        self.state = MetaEngineV3State()
        self.competitor = StrategyCompetitor(self.config)
        self.rotator = CapitalRotationEngine(self.config)
        self.risk_allocator = RiskBudgetAllocator(self.config)

    def evaluate(
        self,
        regime: Dict,
        global_mode: str,
        portfolio_context: Dict,
        strategies: List[Dict],
        previous_allocations: Optional[Dict[str, float]] = None,
        enabled_strategy_names: Optional[List[str]] = None,
    ) -> MetaEngineV3Output:
        previous = previous_allocations or self.state.previous_allocations or {}
        enabled_names = enabled_strategy_names or [strategy.get("name") for strategy in strategies if strategy.get("name")]
        strategy_map = {strategy.get("name", f"strategy_{index}"): strategy for index, strategy in enumerate(strategies)}
        enabled_names = [name for name in enabled_names if name in strategy_map]

        deployable_cap = self._deployable_cap_by_mode(global_mode)
        competition_result = self.competitor.run_competition(
            strategies={name: strategy_map[name] for name in enabled_names},
            current_regime=regime.get("type", "NORMAL"),
            drawdown_pct=float(portfolio_context.get("drawdown_pct", 0.0)),
        )
        target_allocations = self.competitor.suggest_allocation_from_ranking(
            rankings=competition_result.strategy_rankings,
            enabled_strategies=enabled_names,
            deployable_capital_pct=deployable_cap,
        )
        final_allocations, rotation_actions = self.rotator.calculate_rotation_actions(
            current_allocations=previous,
            target_allocations=target_allocations,
            previous_allocations=previous,
            top_performers=competition_result.top_performers,
            underperformers=competition_result.underperformers,
        )
        total_allocated_pct = round(sum(final_allocations.values()), 6)
        cash_buffer_pct = round(max(0.0, 100.0 - total_allocated_pct), 6)

        strategy_scores = {
            name: ranking.overall_score for name, ranking in competition_result.strategy_rankings.items()
        }
        risk_result = self.risk_allocator.allocate_risk_budgets(
            strategy_allocations=final_allocations,
            strategy_scores=strategy_scores,
            global_mode=global_mode,
            portfolio_drawdown_pct=float(portfolio_context.get("drawdown_pct", 0.0)),
            portfolio_volatility_pct=float(portfolio_context.get("volatility_pct", 0.0)),
        )

        momentum = self.rotator.assess_rotation_momentum(rotation_actions)
        rotation_summary = self.rotator.build_rotation_summary(rotation_actions, momentum)
        risk_rationale = self.risk_allocator.build_risk_allocation_rationale(
            adjusted_budget=risk_result.total_risk_budget_pct,
            mode=global_mode,
            drawdown_pct=float(portfolio_context.get("drawdown_pct", 0.0)),
            volatility_pct=float(portfolio_context.get("volatility_pct", 0.0)),
        )
        cluster_exposure = self._cluster_exposure(strategy_map, final_allocations)
        concentration_warning = any(value > self.config.max_cluster_exposure_pct for value in cluster_exposure.values())
        diversification_ratio = round(len([value for value in final_allocations.values() if value > 0]) / max(len(enabled_names), 1), 6)

        self.state.previous_allocations = dict(final_allocations)
        self.state.previous_rankings = {name: ranking.rank for name, ranking in competition_result.strategy_rankings.items()}

        return MetaEngineV3Output(
            regime=regime,
            global_mode=global_mode,
            strategy_allocations=final_allocations,
            strategy_status={name: ("ENABLED" if final_allocations.get(name, 0.0) > 0 else "DISABLED") for name in enabled_names},
            strategy_scores=strategy_scores,
            strategy_rankings={name: ranking.rank for name, ranking in competition_result.strategy_rankings.items()},
            top_performers=competition_result.top_performers,
            underperformers=competition_result.underperformers,
            risk_budgets={name: allocation.allocated_risk_pct for name, allocation in risk_result.allocations.items()},
            total_risk_budget_pct=risk_result.total_risk_budget_pct,
            total_allocated_risk_pct=risk_result.total_allocated,
            unused_risk_pct=risk_result.unused_buffer,
            rotation_actions=[asdict(action) for action in rotation_actions],
            rotation_momentum=momentum,
            rotation_summary=rotation_summary,
            cluster_exposure_summary=cluster_exposure,
            concentration_warning=concentration_warning,
            diversification_ratio=diversification_ratio,
            total_allocated_pct=total_allocated_pct,
            cash_buffer_pct=cash_buffer_pct,
            explanation=self._build_explanation(final_allocations, strategy_scores, global_mode, risk_result.total_risk_budget_pct),
            reasoning_summary=(
                f"mode={global_mode}, regime={regime.get('type')}, allocated={total_allocated_pct:.1f}%, "
                f"cash={cash_buffer_pct:.1f}%, risk={risk_result.total_risk_budget_pct:.2f}%"
            ),
            competition_summary=(
                f"Top performers: {', '.join(competition_result.top_performers) or 'none'}; "
                f"Underperformers: {', '.join(competition_result.underperformers) or 'none'}"
            ),
            rotation_rationale=rotation_summary,
            risk_budget_rationale=risk_rationale,
        )

    def _deployable_cap_by_mode(self, global_mode: str) -> float:
        return {
            "EXPANSION": 90.0,
            "NORMAL": 75.0,
            "CAUTION": 55.0,
            "DEFENSE": 35.0,
            "SURVIVAL": 20.0,
        }.get(global_mode, 75.0)

    @staticmethod
    def _cluster_exposure(strategy_map: Dict[str, Dict], allocations: Dict[str, float]) -> Dict[str, float]:
        exposures: Dict[str, float] = {}
        for name, allocation in allocations.items():
            payload = strategy_map.get(name, {})
            group = payload.get("group") or payload.get("cluster") or payload.get("style") or "default"
            exposures[group] = exposures.get(group, 0.0) + allocation
        return {group: round(value, 6) for group, value in exposures.items()}

    @staticmethod
    def _build_explanation(allocations: Dict[str, float], scores: Dict[str, float], mode: str, risk_budget: float) -> str:
        parts = [f"mode={mode}", f"risk_budget={risk_budget:.2f}%"]
        ordered = sorted(allocations.items(), key=lambda item: item[1], reverse=True)
        for name, weight in ordered:
            parts.append(f"{name}:{weight:.2f}%@{scores.get(name, 0.0):.3f}")
        return " | ".join(parts)
