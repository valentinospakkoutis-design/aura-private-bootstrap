from __future__ import annotations

import pytest

from meta_engine_v2.config import MetaEngineV2Config
from meta_engine_v2.rebalance import Rebalancer, normalize_weights_with_cap
from meta_engine_v2.regime_memory import RegimeMemory
from meta_engine_v2.scoring import StrategyScorer
from tests.meta_engine_test_utils import FIXED_NOW, make_point, make_snapshot


pytestmark = pytest.mark.unit


def test_scoring_prefers_higher_return_and_consistency() -> None:
    scorer = StrategyScorer(MetaEngineV2Config())
    strong = make_snapshot("strong", avg_return_pct=6.0, consistency=0.9, volatility_pct=3.0)
    weak = make_snapshot("weak", avg_return_pct=2.0, consistency=0.35, volatility_pct=3.0)

    scores = scorer.score_all(
        strategies=[strong, weak],
        current_regime="TRENDING",
        regime_learning={},
    )

    assert scores["strong"].score > scores["weak"].score
    assert scores["strong"].normalized_return > scores["weak"].normalized_return
    assert scores["strong"].consistency_bonus > scores["weak"].consistency_bonus


def test_scoring_penalizes_drawdown() -> None:
    scorer = StrategyScorer(MetaEngineV2Config())
    lower_drawdown = make_snapshot("lower_drawdown", drawdown_pct=2.0)
    higher_drawdown = make_snapshot("higher_drawdown", drawdown_pct=10.0)

    scores = scorer.score_all(
        strategies=[lower_drawdown, higher_drawdown],
        current_regime="TRENDING",
        regime_learning={},
    )

    assert scores["lower_drawdown"].score > scores["higher_drawdown"].score
    assert scores["lower_drawdown"].drawdown_penalty < scores["higher_drawdown"].drawdown_penalty


def test_regime_memory_gives_more_weight_to_recent_data() -> None:
    memory = RegimeMemory(MetaEngineV2Config())
    recent_good = make_snapshot(
        "recent_good",
        history=[
            make_point(days_ago=1, pnl_pct=4.0, win_rate=0.72, drawdown_pct=1.0, volatility_pct=2.0, consistency=0.92),
            make_point(days_ago=45, pnl_pct=-3.0, win_rate=0.35, drawdown_pct=8.0, volatility_pct=10.0, consistency=0.2),
        ],
    )
    recent_bad = make_snapshot(
        "recent_bad",
        history=[
            make_point(days_ago=1, pnl_pct=-3.0, win_rate=0.35, drawdown_pct=8.0, volatility_pct=10.0, consistency=0.2),
            make_point(days_ago=45, pnl_pct=4.0, win_rate=0.72, drawdown_pct=1.0, volatility_pct=2.0, consistency=0.92),
        ],
    )

    results = memory.learn_regime_scores(
        strategies=[recent_good, recent_bad],
        current_regime="TRENDING",
        reference_time=FIXED_NOW,
    )

    assert results["recent_good"].regime_score > results["recent_bad"].regime_score
    assert results["recent_good"].observations_used == 2
    assert results["recent_good"].data_quality == pytest.approx(2 / 6)


def test_regime_memory_fallback_uses_preferred_and_avoid_regimes() -> None:
    memory = RegimeMemory(MetaEngineV2Config())
    preferred = make_snapshot("preferred", preferred_regimes=["TRENDING"])
    unmatched = make_snapshot("unmatched", preferred_regimes=["TRENDING"])
    avoid = make_snapshot("avoid", preferred_regimes=["TRENDING"], avoid_regimes=["CRISIS"])

    trending = memory.learn_regime_scores(
        strategies=[preferred],
        current_regime="TRENDING",
        reference_time=FIXED_NOW,
    )
    ranging = memory.learn_regime_scores(
        strategies=[unmatched],
        current_regime="RANGING",
        reference_time=FIXED_NOW,
    )
    crisis = memory.learn_regime_scores(
        strategies=[avoid],
        current_regime="CRISIS",
        reference_time=FIXED_NOW,
    )

    assert trending["preferred"].regime_score == pytest.approx(1.0)
    assert ranging["unmatched"].regime_score == pytest.approx(0.35)
    assert crisis["avoid"].regime_score == pytest.approx(0.05)


def test_normalize_weights_with_cap_respects_total_and_strategy_caps() -> None:
    allocations = normalize_weights_with_cap(
        strategy_scores={"alpha": 0.9, "beta": 0.6, "gamma": 0.3},
        strategy_caps={"alpha": 25.0, "beta": 15.0, "gamma": 40.0},
        deployable_cap_pct=50.0,
    )

    assert sum(allocations.values()) == pytest.approx(50.0)
    assert allocations["alpha"] <= 25.0
    assert allocations["beta"] <= 15.0
    assert allocations["alpha"] > allocations["gamma"]


def test_rebalancer_throttles_changes_and_filters_small_deltas() -> None:
    rebalancer = Rebalancer(MetaEngineV2Config())
    result = rebalancer.rebalance(
        target_weights={"alpha": 20.0, "beta": 11.4, "gamma": 0.6},
        previous_weights={"alpha": 10.0, "beta": 11.0, "gamma": 0.0},
    )

    assert result.final_weights["alpha"] == pytest.approx(15.0)
    assert result.final_weights["beta"] == pytest.approx(11.0)
    assert result.final_weights["gamma"] == pytest.approx(0.0)
    assert [action.strategy_name for action in result.increases] == ["alpha"]
    assert result.decreases == []