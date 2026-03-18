from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from meta_engine_v2.config import MetaEngineV2Config
from meta_engine_v2.learning import clamp
from meta_engine_v2.schemas import RebalanceAction


@dataclass(slots=True)
class RebalanceResult:
    final_weights: Dict[str, float]
    increases: List[RebalanceAction]
    decreases: List[RebalanceAction]


def normalize_weights_with_cap(
    *,
    strategy_scores: Dict[str, float],
    strategy_caps: Dict[str, float],
    deployable_cap_pct: float,
) -> Dict[str, float]:
    positive_scores = {name: max(score, 0.0) for name, score in strategy_scores.items() if score > 0}
    if not positive_scores or deployable_cap_pct <= 0:
        return {name: 0.0 for name in strategy_scores}

    remaining = min(100.0, deployable_cap_pct)
    remaining_scores = dict(positive_scores)
    allocations = {name: 0.0 for name in strategy_scores}

    while remaining > 1e-9 and remaining_scores:
        total_score = sum(remaining_scores.values())
        if total_score <= 0:
            break
        saturated: list[str] = []
        for name, score in list(remaining_scores.items()):
            cap = max(strategy_caps.get(name, deployable_cap_pct), 0.0)
            proposed = remaining * (score / total_score)
            room = max(cap - allocations[name], 0.0)
            assigned = min(proposed, room)
            allocations[name] += assigned
            if room <= proposed + 1e-9:
                saturated.append(name)
        remaining = deployable_cap_pct - sum(allocations.values())
        for name in saturated:
            remaining_scores.pop(name, None)
        if not saturated:
            break

    return {name: round(weight, 6) for name, weight in allocations.items()}


class Rebalancer:
    def __init__(self, config: MetaEngineV2Config):
        self.config = config

    def rebalance(self, *, target_weights: Dict[str, float], previous_weights: Dict[str, float]) -> RebalanceResult:
        names = set(target_weights) | set(previous_weights)
        final_weights: Dict[str, float] = {}
        increases: List[RebalanceAction] = []
        decreases: List[RebalanceAction] = []

        for name in names:
            previous = previous_weights.get(name, 0.0)
            target = clamp(target_weights.get(name, 0.0), 0.0, 100.0)
            delta = target - previous
            if abs(delta) <= self.config.meaningful_change_threshold_pct:
                final = previous
            else:
                bounded_delta = clamp(
                    delta,
                    -self.config.max_change_per_cycle_pct,
                    self.config.max_change_per_cycle_pct,
                )
                final = clamp(previous + bounded_delta, 0.0, 100.0)

            final_weights[name] = round(final, 6)
            applied_delta = final - previous
            if abs(applied_delta) < 1e-9:
                continue
            action = RebalanceAction(
                strategy_name=name,
                from_weight_pct=previous,
                to_weight_pct=final,
                delta_pct=applied_delta,
            )
            if applied_delta > 0:
                increases.append(action)
            else:
                decreases.append(action)

        return RebalanceResult(final_weights=final_weights, increases=increases, decreases=decreases)
