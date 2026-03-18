from __future__ import annotations

from typing import Dict

from meta_engine_v2.schemas import StrategyAllocationV2


def build_reasoning_summary(
    *,
    regime_type: str,
    regime_confidence: float,
    global_mode: str,
    total_allocated_pct: float,
    cash_buffer_pct: float,
    conservative_reduction: float,
) -> str:
    return (
        f"Regime={regime_type} ({regime_confidence:.0%}), mode={global_mode}, "
        f"allocated={total_allocated_pct:.1f}%, cash={cash_buffer_pct:.1f}%, "
        f"conservative_factor={conservative_reduction:.2f}"
    )


def build_full_explanation(*, allocations: Dict[str, StrategyAllocationV2], score_breakdown_lines: Dict[str, str]) -> str:
    lines = []
    for name, allocation in sorted(allocations.items(), key=lambda item: item[1].weight_pct, reverse=True):
        detail = score_breakdown_lines.get(name, "")
        lines.append(
            f"{name}: weight={allocation.weight_pct:.2f}%, status={allocation.status}, "
            f"score={allocation.score:.3f}, regime_alignment={allocation.regime_alignment:.2f}"
            + (f" | {detail}" if detail else "")
        )
    return "\n".join(lines)
