from __future__ import annotations

import pytest

from meta_engine_v3.engine import MetaEngineV3
from tests.meta_engine_test_utils import make_v3_strategy


pytestmark = pytest.mark.unit


def test_engine_regime_aware_allocation_changes_with_market_state() -> None:
    trending_engine = MetaEngineV3()
    ranging_engine = MetaEngineV3()
    strategies = [
        make_v3_strategy("momentum_alpha", pnl_pct=2.5, win_rate=0.58, drawdown_pct=2.0, volatility_pct=3.0, consistency=0.7, group="trend"),
        make_v3_strategy("mean_reversion_beta", pnl_pct=2.5, win_rate=0.58, drawdown_pct=2.0, volatility_pct=3.0, consistency=0.7, group="mean"),
    ]

    trending = trending_engine.evaluate(
        regime={"type": "TRENDING", "confidence": 0.85},
        global_mode="NORMAL",
        portfolio_context={"drawdown_pct": 2.0, "volatility_pct": 5.0},
        strategies=strategies,
        previous_allocations={"momentum_alpha": 20.0, "mean_reversion_beta": 20.0},
    )
    ranging = ranging_engine.evaluate(
        regime={"type": "RANGING", "confidence": 0.85},
        global_mode="NORMAL",
        portfolio_context={"drawdown_pct": 2.0, "volatility_pct": 5.0},
        strategies=strategies,
        previous_allocations={"momentum_alpha": 20.0, "mean_reversion_beta": 20.0},
    )

    assert trending.strategy_scores["momentum_alpha"] > trending.strategy_scores["mean_reversion_beta"]
    assert ranging.strategy_scores["mean_reversion_beta"] > ranging.strategy_scores["momentum_alpha"]
    assert trending.strategy_rankings["momentum_alpha"] < trending.strategy_rankings["mean_reversion_beta"]
    assert ranging.strategy_rankings["mean_reversion_beta"] < ranging.strategy_rankings["momentum_alpha"]


def test_engine_survival_mode_keeps_risk_low_and_cash_high() -> None:
    engine = MetaEngineV3()
    output = engine.evaluate(
        regime={"type": "CRISIS", "confidence": 0.95},
        global_mode="SURVIVAL",
        portfolio_context={"drawdown_pct": 22.0, "volatility_pct": 40.0},
        strategies=[
            make_v3_strategy("hedge_alpha", pnl_pct=1.5, win_rate=0.55, drawdown_pct=1.0, volatility_pct=2.0, consistency=0.75, group="defense"),
            make_v3_strategy("trend_beta", pnl_pct=2.0, win_rate=0.56, drawdown_pct=4.0, volatility_pct=6.0, consistency=0.6, group="trend"),
            make_v3_strategy("carry_gamma", pnl_pct=1.0, win_rate=0.52, drawdown_pct=3.0, volatility_pct=5.0, consistency=0.58, group="carry"),
        ],
        previous_allocations={"hedge_alpha": 0.0, "trend_beta": 0.0, "carry_gamma": 0.0},
    )

    assert output.total_allocated_pct <= 20.0
    assert output.cash_buffer_pct >= 80.0
    assert output.total_risk_budget_pct <= 1.8
    assert output.total_allocated_risk_pct <= output.total_risk_budget_pct


def test_engine_handles_empty_and_single_strategy_inputs() -> None:
    engine = MetaEngineV3()
    empty = engine.evaluate(
        regime={"type": "TRENDING", "confidence": 0.8},
        global_mode="NORMAL",
        portfolio_context={"drawdown_pct": 0.0, "volatility_pct": 0.0},
        strategies=[],
        previous_allocations={},
    )
    single = engine.evaluate(
        regime={"type": "TRENDING", "confidence": 0.8},
        global_mode="NORMAL",
        portfolio_context={"drawdown_pct": 0.0, "volatility_pct": 0.0},
        strategies=[make_v3_strategy("solo_trend", pnl_pct=4.0, win_rate=0.66, drawdown_pct=1.0, volatility_pct=2.0, consistency=0.82)],
        previous_allocations={"solo_trend": 0.0},
    )

    assert empty.strategy_allocations == {}
    assert empty.cash_buffer_pct == pytest.approx(100.0)
    assert set(single.strategy_allocations) == {"solo_trend"}
    assert single.total_allocated_pct <= 8.0


def test_engine_is_deterministic_for_same_inputs() -> None:
    strategies = [
        make_v3_strategy("trend_alpha", pnl_pct=5.0, win_rate=0.7, drawdown_pct=2.0, volatility_pct=3.0, consistency=0.8, group="trend"),
        make_v3_strategy("mean_beta", pnl_pct=1.5, win_rate=0.54, drawdown_pct=4.0, volatility_pct=5.0, consistency=0.55, group="mean"),
        make_v3_strategy("hedge_gamma", pnl_pct=2.0, win_rate=0.56, drawdown_pct=1.0, volatility_pct=2.0, consistency=0.72, group="defense"),
    ]
    kwargs = {
        "regime": {"type": "TRENDING", "confidence": 0.88},
        "global_mode": "NORMAL",
        "portfolio_context": {"drawdown_pct": 4.0, "volatility_pct": 8.0},
        "strategies": strategies,
        "previous_allocations": {"trend_alpha": 20.0, "mean_beta": 20.0, "hedge_gamma": 20.0},
        "enabled_strategy_names": ["trend_alpha", "mean_beta", "hedge_gamma"],
    }

    first = MetaEngineV3().evaluate(**kwargs)
    second = MetaEngineV3().evaluate(**kwargs)

    assert first.model_dump(exclude={"evaluation_time"}) == second.model_dump(exclude={"evaluation_time"})