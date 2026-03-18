from __future__ import annotations

import pytest

from meta_engine_v2.integration import evaluate_meta_engine_v2
from meta_engine_v3.engine import MetaEngineV3
from tests.meta_engine_test_utils import make_point, make_snapshot, make_v2_input, make_v3_strategy


pytestmark = pytest.mark.integration


def test_v2_integration_adapter_returns_valid_output_shape() -> None:
    alpha = make_snapshot("alpha", avg_return_pct=6.0, consistency=0.85, trades_count=16, history=[make_point(days_ago=1, pnl_pct=3.0, win_rate=0.68, consistency=0.85)])
    beta = make_snapshot("beta", avg_return_pct=3.0, consistency=0.55, trades_count=10, history=[make_point(days_ago=1, pnl_pct=1.0, win_rate=0.54, consistency=0.55)])

    output = evaluate_meta_engine_v2(make_v2_input([alpha, beta], previous_allocations={"alpha": 0.0, "beta": 0.0}))

    assert output.global_mode == "NORMAL"
    assert set(output.strategy_allocations) == {"alpha", "beta"}
    assert output.total_allocated_pct + output.cash_buffer_pct == pytest.approx(100.0)
    assert "alpha" in output.explanation


def test_v2_to_v3_pipeline_smoke_produces_compatible_outputs() -> None:
    v2_output = evaluate_meta_engine_v2(
        make_v2_input(
            [
                make_snapshot("trend_alpha", avg_return_pct=6.0, consistency=0.85, trades_count=18, preferred_regimes=["TRENDING"], history=[make_point(days_ago=1, pnl_pct=4.0, win_rate=0.7, consistency=0.9)]),
                make_snapshot("mean_beta", avg_return_pct=3.0, consistency=0.65, trades_count=14, preferred_regimes=["RANGING"], history=[make_point(days_ago=1, pnl_pct=1.5, win_rate=0.58, consistency=0.7)]),
                make_snapshot("hedge_gamma", avg_return_pct=4.0, consistency=0.72, trades_count=16, preferred_regimes=["CRISIS"], history=[make_point(days_ago=1, pnl_pct=2.0, win_rate=0.6, consistency=0.78)]),
            ],
            regime_type="TRENDING",
            previous_allocations={"trend_alpha": 10.0, "mean_beta": 10.0, "hedge_gamma": 10.0},
        )
    )

    v3_output = MetaEngineV3().evaluate(
        regime=v2_output.regime.model_dump(),
        global_mode=v2_output.global_mode,
        portfolio_context={"drawdown_pct": 4.0, "volatility_pct": 8.0},
        strategies=[
            make_v3_strategy("trend_alpha", pnl_pct=5.0, win_rate=0.69, drawdown_pct=2.0, volatility_pct=3.0, consistency=0.82, group="trend"),
            make_v3_strategy("mean_beta", pnl_pct=2.0, win_rate=0.56, drawdown_pct=4.0, volatility_pct=5.0, consistency=0.62, group="mean"),
            make_v3_strategy("hedge_gamma", pnl_pct=2.5, win_rate=0.58, drawdown_pct=1.0, volatility_pct=2.0, consistency=0.74, group="defense"),
        ],
        previous_allocations={name: allocation.weight_pct for name, allocation in v2_output.strategy_allocations.items()},
        enabled_strategy_names=list(v2_output.strategy_allocations.keys()),
    )

    assert set(v3_output.strategy_allocations) == set(v2_output.strategy_allocations)
    assert v3_output.total_allocated_pct + v3_output.cash_buffer_pct == pytest.approx(100.0)
    assert set(v3_output.risk_budgets) == set(v3_output.strategy_allocations)
    assert isinstance(v3_output.rotation_actions, list)


def test_pipeline_remains_conservative_under_stress() -> None:
    v2_output = evaluate_meta_engine_v2(
        make_v2_input(
            [
                make_snapshot("alpha", trades_count=2, history=[make_point(days_ago=2, pnl_pct=0.5)]),
                make_snapshot("beta", trades_count=1, history=[]),
            ],
            regime_type="CRISIS",
            confidence=0.35,
            drawdown_pct=22.0,
        )
    )
    v3_output = MetaEngineV3().evaluate(
        regime=v2_output.regime.model_dump(),
        global_mode=v2_output.global_mode,
        portfolio_context={"drawdown_pct": 22.0, "volatility_pct": 35.0},
        strategies=[
            make_v3_strategy("alpha", pnl_pct=0.8, win_rate=0.52, drawdown_pct=5.0, volatility_pct=7.0, consistency=0.55),
            make_v3_strategy("beta", pnl_pct=0.3, win_rate=0.5, drawdown_pct=6.0, volatility_pct=8.0, consistency=0.5),
        ],
        previous_allocations={"alpha": 0.0, "beta": 0.0},
    )

    assert v2_output.global_mode == "SURVIVAL"
    assert v2_output.cash_buffer_pct >= 80.0
    assert v3_output.cash_buffer_pct >= 80.0
    assert v3_output.total_risk_budget_pct <= 1.8