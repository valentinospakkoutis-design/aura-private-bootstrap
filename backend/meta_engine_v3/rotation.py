from __future__ import annotations

from typing import Dict, List, Optional

from meta_engine_v3.schemas import MetaEngineV3Config, RotationAction


class CapitalRotationEngine:
    def __init__(self, config: MetaEngineV3Config):
        self.config = config

    def calculate_rotation_actions(
        self,
        current_allocations: Dict[str, float],
        target_allocations: Dict[str, float],
        previous_allocations: Optional[Dict[str, float]] = None,
        top_performers: List[str] | None = None,
        underperformers: List[str] | None = None,
    ) -> tuple[Dict[str, float], List[RotationAction]]:
        previous = previous_allocations or current_allocations or {}
        names = set(current_allocations) | set(target_allocations) | set(previous)
        top = set(top_performers or [])
        bottom = set(underperformers or [])
        final_allocations: Dict[str, float] = {}
        actions: List[RotationAction] = []

        for name in names:
            current_weight = current_allocations.get(name, previous.get(name, 0.0))
            target_weight = target_allocations.get(name, 0.0)
            delta = target_weight - current_weight
            if abs(delta) <= self.config.meaningful_change_threshold:
                final_weight = current_weight
            else:
                bounded_delta = max(-self.config.max_rotation_per_cycle_pct, min(self.config.max_rotation_per_cycle_pct, delta))
                if name in bottom:
                    bounded_delta = max(bounded_delta, -self.config.max_underperformer_outflow_pct)
                final_weight = max(0.0, current_weight + bounded_delta)
            final_allocations[name] = round(final_weight, 6)

            applied_delta = final_weight - current_weight
            if abs(applied_delta) <= self.config.meaningful_change_threshold:
                continue
            if current_weight <= 0 and final_weight > 0:
                action_type = "new_entry"
            elif final_weight <= 0 and current_weight > 0:
                action_type = "exit"
            elif applied_delta > 0:
                action_type = "increase"
            else:
                action_type = "decrease"
            if name in top and applied_delta > 0:
                reasoning = "top performer receives incremental capital"
            elif name in bottom and applied_delta < 0:
                reasoning = "underperformer trimmed to control risk"
            else:
                reasoning = "rotation throttled to maintain smooth transitions"
            actions.append(
                RotationAction(
                    strategy_name=name,
                    action=action_type,
                    previous_weight_pct=current_weight,
                    target_weight_pct=final_weight,
                    delta_pct=applied_delta,
                    reasoning=reasoning,
                )
            )

        return final_allocations, actions

    @staticmethod
    def assess_rotation_momentum(current_actions: List[RotationAction], previous_actions: Optional[List[RotationAction]] = None) -> str:
        if not current_actions:
            return "stable"
        total_change = sum(abs(action.delta_pct) for action in current_actions)
        if total_change >= 15:
            return "accelerating"
        if previous_actions and total_change < sum(abs(action.delta_pct) for action in previous_actions):
            return "cooling"
        return "stable"

    @staticmethod
    def build_rotation_summary(actions: List[RotationAction], momentum: str) -> str:
        if not actions:
            return f"Rotation momentum is {momentum}; no allocation changes required."
        changed = ", ".join(f"{action.strategy_name}:{action.delta_pct:+.1f}%" for action in actions)
        return f"Rotation momentum is {momentum}; changes -> {changed}"
