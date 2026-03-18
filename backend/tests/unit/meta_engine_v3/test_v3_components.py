from __future__ import annotations

import pytest

from meta_engine_v3.competition import StrategyCompetitor
from meta_engine_v3.risk_budget import RiskBudgetAllocator
from meta_engine_v3.rotation import CapitalRotationEngine
from meta_engine_v3.schemas import MetaEngineV3Config
from tests.meta_engine_test_utils import make_v3_strategy


pytestmark = pytest.mark.unit


def test_competition_ranks_better_strategy_higher() -> None:
    competitor = StrategyCompetitor(MetaEngineV3Config())
    result = competitor.run_competition(
        strategies={
            "leader": make_v3_strategy("leader", pnl_pct=5.0, win_rate=0.72, drawdown_pct=1.0, volatility_pct=2.0, consistency=0.85, regime_alignment=0.9),
            "laggard": make_v3_strategy("laggard", pnl_pct=-2.0, win_rate=0.45, drawdown_pct=10.0, volatility_pct=15.0, consistency=0.2, regime_alignment=0.3),
        },
        current_regime="TRENDING",
        drawdown_pct=2.0,
    )

    assert result.strategy_rankings["leader"].rank == 1
    assert result.strategy_rankings["leader"].overall_score > result.strategy_rankings["laggard"].overall_score
    assert "leader" in result.top_performers
    assert "laggard" in result.underperformers


def test_competition_regime_shift_changes_preference() -> None:
    competitor = StrategyCompetitor(MetaEngineV3Config())
    strategies = {
        "momentum_alpha": make_v3_strategy("momentum_alpha", pnl_pct=2.5, win_rate=0.58, drawdown_pct=2.0, volatility_pct=3.0, consistency=0.7),
        "mean_reversion_beta": make_v3_strategy("mean_reversion_beta", pnl_pct=2.5, win_rate=0.58, drawdown_pct=2.0, volatility_pct=3.0, consistency=0.7),
    }

    trending = competitor.run_competition(strategies, current_regime="TRENDING", drawdown_pct=2.0)
    ranging = competitor.run_competition(strategies, current_regime="RANGING", drawdown_pct=2.0)

    assert trending.strategy_rankings["momentum_alpha"].overall_score > trending.strategy_rankings["mean_reversion_beta"].overall_score
    assert ranging.strategy_rankings["mean_reversion_beta"].overall_score > ranging.strategy_rankings["momentum_alpha"].overall_score


def test_suggest_allocation_from_ranking_preserves_order_and_total() -> None:
    competitor = StrategyCompetitor(MetaEngineV3Config())
    result = competitor.run_competition(
        strategies={
            "alpha": make_v3_strategy("alpha", pnl_pct=4.0, win_rate=0.68, drawdown_pct=2.0, volatility_pct=3.0, consistency=0.8, regime_alignment=0.85),
            "beta": make_v3_strategy("beta", pnl_pct=2.0, win_rate=0.55, drawdown_pct=3.0, volatility_pct=4.0, consistency=0.6, regime_alignment=0.6),
            "gamma": make_v3_strategy("gamma", pnl_pct=0.5, win_rate=0.5, drawdown_pct=5.0, volatility_pct=7.0, consistency=0.45, regime_alignment=0.45),
        },
        current_regime="TRENDING",
        drawdown_pct=1.0,
    )
    allocations = competitor.suggest_allocation_from_ranking(result.strategy_rankings, ["alpha", "beta", "gamma"], 75.0)

    assert sum(allocations.values()) == pytest.approx(75.0)
    assert allocations["alpha"] > allocations["beta"] > allocations["gamma"]


def test_rotation_respects_throttle_and_underperformer_outflow_cap() -> None:
    rotator = CapitalRotationEngine(MetaEngineV3Config())
    final_allocations, actions = rotator.calculate_rotation_actions(
        current_allocations={"winner": 20.0, "loser": 20.0},
        target_allocations={"winner": 40.0, "loser": 0.0},
        previous_allocations={"winner": 20.0, "loser": 20.0},
        top_performers=["winner"],
        underperformers=["loser"],
    )

    assert final_allocations["winner"] == pytest.approx(28.0)
    assert final_allocations["loser"] == pytest.approx(15.0)
    assert {action.strategy_name: action.reasoning for action in actions}["winner"] == "top performer receives incremental capital"
    assert {action.strategy_name: action.reasoning for action in actions}["loser"] == "underperformer trimmed to control risk"


def test_risk_budget_is_capped_and_survival_reduces_risk() -> None:
    allocator = RiskBudgetAllocator(MetaEngineV3Config())
    normal = allocator.allocate_risk_budgets(
        strategy_allocations={"alpha": 30.0, "beta": 20.0},
        strategy_scores={"alpha": 0.9, "beta": 0.4},
        global_mode="NORMAL",
        portfolio_drawdown_pct=2.0,
        portfolio_volatility_pct=5.0,
    )
    survival = allocator.allocate_risk_budgets(
        strategy_allocations={"alpha": 30.0, "beta": 20.0},
        strategy_scores={"alpha": 0.9, "beta": 0.4},
        global_mode="SURVIVAL",
        portfolio_drawdown_pct=18.0,
        portfolio_volatility_pct=35.0,
    )

    assert survival.total_risk_budget_pct < normal.total_risk_budget_pct
    assert survival.total_allocated <= survival.total_risk_budget_pct
    for allocation in normal.allocations.values():
        assert allocation.allocated_risk_pct <= allocation.cap_risk_pct