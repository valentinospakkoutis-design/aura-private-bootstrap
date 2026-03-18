from __future__ import annotations

import pytest

from meta_engine_v2.engine import MetaEngineV2
from tests.meta_engine_test_utils import make_point, make_snapshot, make_v2_input


pytestmark = pytest.mark.unit


def test_engine_shifts_preference_with_regime_change() -> None:
    engine = MetaEngineV2()
    trend = make_snapshot(
        "trend",
        preferred_regimes=["TRENDING"],
        avoid_regimes=["RANGING"],
        history=[make_point(days_ago=1, regime="TRENDING", pnl_pct=2.0, win_rate=0.6, consistency=0.8)],
    )
    mean_reversion = make_snapshot(
        "mean_reversion",
        preferred_regimes=["RANGING"],
        avoid_regimes=["TRENDING"],
        history=[make_point(days_ago=1, regime="RANGING", pnl_pct=2.0, win_rate=0.6, consistency=0.8)],
    )

    trending_output = engine.evaluate(
        make_v2_input(
            [trend, mean_reversion],
            regime_type="TRENDING",
            previous_allocations={"trend": 15.0, "mean_reversion": 15.0},
        )
    )
    ranging_output = engine.evaluate(
        make_v2_input(
            [trend, mean_reversion],
            regime_type="RANGING",
            previous_allocations={"trend": 15.0, "mean_reversion": 15.0},
        )
    )

    assert trending_output.strategy_allocations["trend"].score > trending_output.strategy_allocations["mean_reversion"].score
    assert ranging_output.strategy_allocations["mean_reversion"].score > ranging_output.strategy_allocations["trend"].score
    assert trending_output.strategy_allocations["trend"].regime_alignment > trending_output.strategy_allocations["mean_reversion"].regime_alignment
    assert ranging_output.strategy_allocations["mean_reversion"].regime_alignment > ranging_output.strategy_allocations["trend"].regime_alignment


def test_engine_uses_conservative_allocation_with_low_confidence_and_insufficient_data() -> None:
    engine = MetaEngineV2()
    alpha = make_snapshot("alpha", trades_count=2, history=[make_point(days_ago=1, pnl_pct=1.0)])
    beta = make_snapshot("beta", trades_count=1, history=[])

    output = engine.evaluate(
        make_v2_input(
            [alpha, beta],
            confidence=0.3,
            regime_type="TRENDING",
        )
    )

    assert output.total_allocated_pct <= 25.0
    assert output.cash_buffer_pct >= 75.0
    assert output.global_mode == "CAUTION"


def test_engine_survival_mode_triggers_on_extreme_drawdown() -> None:
    engine = MetaEngineV2()
    alpha = make_snapshot("alpha", avg_return_pct=6.0)
    beta = make_snapshot("beta", avg_return_pct=4.0)

    output = engine.evaluate(make_v2_input([alpha, beta], drawdown_pct=25.0))

    assert output.global_mode == "SURVIVAL"
    assert output.total_allocated_pct <= 20.0
    assert output.cash_buffer_pct >= 80.0


def test_engine_output_stays_bounded_for_empty_input() -> None:
    engine = MetaEngineV2()
    output = engine.evaluate(make_v2_input([]))

    assert output.strategy_allocations == {}
    assert output.rebalance_actions.increases == []
    assert output.rebalance_actions.decreases == []
    assert output.total_allocated_pct == pytest.approx(0.0)
    assert output.cash_buffer_pct == pytest.approx(100.0)


def test_engine_handles_single_strategy_without_over_allocating() -> None:
    engine = MetaEngineV2()
    solo = make_snapshot("solo", avg_return_pct=7.0, consistency=0.9, trades_count=20)

    output = engine.evaluate(make_v2_input([solo]))

    assert set(output.strategy_allocations) == {"solo"}
    assert output.strategy_allocations["solo"].weight_pct <= 30.0
    assert output.total_allocated_pct <= 30.0
    assert output.cash_buffer_pct >= 70.0