from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from meta_engine_v3.schemas import CompetitionResult, MetaEngineV3Config, StrategyRanking


@dataclass(slots=True)
class CompetitionScorecard:
    strategy_name: str
    performance_score: float = 0.5
    stability_score: float = 0.5
    regime_alignment: float = 0.5
    risk_efficiency: float = 0.5
    consistency: float = 0.5
    composite_score: float = 0.5


class StrategyCompetitor:
    def __init__(self, config: MetaEngineV3Config):
        self.config = config

    def run_competition(self, strategies: Dict[str, Dict], current_regime: str, drawdown_pct: float) -> CompetitionResult:
        scorecards: Dict[str, CompetitionScorecard] = {}
        metrics: Dict[str, Dict[str, float]] = {}

        for strategy_name, payload in strategies.items():
            name = payload.get("name", strategy_name)
            pnl_pct = float(payload.get("pnl_pct", 0.0))
            win_rate = float(payload.get("win_rate", 0.5))
            strategy_drawdown = float(payload.get("drawdown_pct", 0.0))
            volatility_pct = float(payload.get("volatility_pct", 0.0))
            consistency = float(payload.get("consistency", 0.5))
            regime_alignment = self._regime_alignment(name, payload, current_regime)

            performance_score = max(0.0, min(1.0, 0.5 + pnl_pct / 8.0 + (win_rate - 0.5) * 0.8))
            stability_score = max(0.0, min(1.0, 1.0 - strategy_drawdown / 15.0 - volatility_pct / 30.0 + consistency * 0.25))
            risk_efficiency = max(0.0, min(1.0, (pnl_pct + 2.0) / max(strategy_drawdown + volatility_pct / 2.0 + drawdown_pct + 2.0, 1.0)))

            weighted = (
                performance_score * self.config.metric_weights["performance"]
                + stability_score * self.config.metric_weights["stability"]
                + regime_alignment * self.config.metric_weights["regime_alignment"]
                + risk_efficiency * self.config.metric_weights["risk_efficiency"]
                + consistency * self.config.metric_weights["consistency"]
            )
            composite_score = max(0.0, min(1.0, weighted))
            scorecards[strategy_name] = CompetitionScorecard(
                strategy_name=strategy_name,
                performance_score=performance_score,
                stability_score=stability_score,
                regime_alignment=regime_alignment,
                risk_efficiency=risk_efficiency,
                consistency=consistency,
                composite_score=composite_score,
            )
            metrics[strategy_name] = {
                "performance": performance_score,
                "stability": stability_score,
                "regime_alignment": regime_alignment,
                "risk_efficiency": risk_efficiency,
                "consistency": consistency,
            }

        ordered = sorted(scorecards.values(), key=lambda item: item.composite_score, reverse=True)
        rankings: Dict[str, StrategyRanking] = {}
        for index, scorecard in enumerate(ordered, start=1):
            rankings[scorecard.strategy_name] = StrategyRanking(
                strategy_name=scorecard.strategy_name,
                rank=index,
                overall_score=scorecard.composite_score,
                performance_score=scorecard.performance_score,
                stability_score=scorecard.stability_score,
                regime_alignment=scorecard.regime_alignment,
                risk_efficiency=scorecard.risk_efficiency,
                consistency=scorecard.consistency,
            )

        top_performers = [name for name, rank in rankings.items() if rank.overall_score >= self.config.top_performer_threshold]
        underperformers = [name for name, rank in rankings.items() if rank.overall_score <= self.config.underperformer_threshold]
        return CompetitionResult(
            strategy_rankings=rankings,
            competition_metrics=metrics,
            top_performers=top_performers,
            underperformers=underperformers,
        )

    def suggest_allocation_from_ranking(
        self,
        rankings: Dict[str, StrategyRanking],
        enabled_strategies: List[str],
        deployable_capital_pct: float,
    ) -> Dict[str, float]:
        allocatable = [name for name in enabled_strategies if name in rankings]
        if not allocatable or deployable_capital_pct <= 0:
            return {name: 0.0 for name in enabled_strategies}

        weights: Dict[str, float] = {}
        for name in allocatable:
            ranking = rankings[name]
            weights[name] = max(0.01, ranking.overall_score * (1.0 + 0.15 / ranking.rank))

        total_weight = sum(weights.values())
        allocations = {name: 0.0 for name in enabled_strategies}
        if total_weight <= 0:
            return allocations

        for name, weight in weights.items():
            allocations[name] = round(deployable_capital_pct * weight / total_weight, 6)
        return allocations

    @staticmethod
    def _regime_alignment(strategy_name: str, payload: Dict, current_regime: str) -> float:
        if "regime_alignment" in payload:
            base_alignment = float(payload["regime_alignment"])
        else:
            lowered = strategy_name.lower()
            if current_regime == "TRENDING":
                base_alignment = 0.9 if ("momentum" in lowered or "trend" in lowered) else 0.45
            elif current_regime == "RANGING":
                base_alignment = 0.9 if ("mean" in lowered or "reversion" in lowered or "rebal" in lowered) else 0.45
            elif current_regime == "CRISIS":
                base_alignment = 0.9 if ("hedge" in lowered or "def" in lowered) else 0.3
            else:
                base_alignment = 0.55
        return max(0.0, min(1.0, base_alignment))
