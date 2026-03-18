from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from meta_engine_v3.schemas import MetaEngineV3Config, RiskBudgetAllocation


@dataclass(slots=True)
class RiskAllocationResult:
    total_risk_budget_pct: float
    allocations: Dict[str, RiskBudgetAllocation]
    total_allocated: float
    unused_buffer: float


class RiskBudgetAllocator:
    def __init__(self, config: MetaEngineV3Config):
        self.config = config

    def allocate_risk_budgets(
        self,
        strategy_allocations: Dict[str, float],
        strategy_scores: Dict[str, float],
        global_mode: str,
        portfolio_drawdown_pct: float,
        portfolio_volatility_pct: float,
    ) -> RiskAllocationResult:
        mode_multiplier = self.config.risk_adjustment_by_mode.get(global_mode, 1.0)
        drawdown_multiplier = max(0.2, 1.0 - portfolio_drawdown_pct * self.config.risk_decay_per_drawdown_pct)
        volatility_multiplier = max(0.35, 1.0 - portfolio_volatility_pct / 100.0)
        adjusted_budget = self.config.total_risk_budget_pct * mode_multiplier * drawdown_multiplier * volatility_multiplier

        weighted: Dict[str, float] = {}
        for name, allocation in strategy_allocations.items():
            score = max(strategy_scores.get(name, 0.0), 0.0)
            weighted[name] = max(allocation, 0.0) * max(score, 0.05)
        total_weight = sum(weighted.values())

        allocations: Dict[str, RiskBudgetAllocation] = {}
        total_allocated = 0.0
        for name, allocation in strategy_allocations.items():
            if total_weight <= 0 or allocation <= 0:
                allocated_risk = 0.0
            else:
                allocated_risk = adjusted_budget * weighted[name] / total_weight
            cap_risk_pct = adjusted_budget * max(allocation, 0.0) / 100.0
            allocated_risk = min(allocated_risk, cap_risk_pct)
            unused_risk = max(cap_risk_pct - allocated_risk, 0.0)
            allocations[name] = RiskBudgetAllocation(
                strategy_name=name,
                total_risk_budget_pct=adjusted_budget,
                allocated_risk_pct=round(allocated_risk, 6),
                cap_risk_pct=round(cap_risk_pct, 6),
                unused_risk_pct=round(unused_risk, 6),
            )
            total_allocated += allocated_risk

        return RiskAllocationResult(
            total_risk_budget_pct=round(adjusted_budget, 6),
            allocations=allocations,
            total_allocated=round(total_allocated, 6),
            unused_buffer=round(max(adjusted_budget - total_allocated, 0.0), 6),
        )

    def build_risk_allocation_rationale(self, adjusted_budget: float, mode: str, drawdown_pct: float, volatility_pct: float) -> str:
        return (
            f"Risk budget {adjusted_budget:.2f}% after mode={mode}, "
            f"drawdown={drawdown_pct:.1f}%, volatility={volatility_pct:.1f}%"
        )

    @staticmethod
    def calculate_position_size_from_risk_budget(risk_budget_pct: float, account_equity: float, stop_loss_pct: float) -> float:
        if account_equity <= 0 or stop_loss_pct <= 0:
            return 0.0
        risk_capital = account_equity * risk_budget_pct / 100.0
        return risk_capital / (stop_loss_pct / 100.0)
