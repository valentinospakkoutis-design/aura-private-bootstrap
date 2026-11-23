"""Confidence must come from measured out-of-sample accuracy, never from move size."""

import math

from ml.calibration import (
    NO_EDGE_CONFIDENCE,
    calibrated_confidence,
    has_demonstrated_edge,
    shrunk_accuracy,
)


def _metrics(acc_pct, n):
    return {"test_direction_accuracy": acc_pct, "test_samples": n}


def test_missing_or_malformed_metrics_mean_no_edge():
    assert calibrated_confidence(None) == NO_EDGE_CONFIDENCE
    assert calibrated_confidence({}) == NO_EDGE_CONFIDENCE
    assert calibrated_confidence({"test_direction_accuracy": "n/a", "test_samples": 90}) == NO_EDGE_CONFIDENCE
    assert calibrated_confidence(_metrics(60.0, 0)) == NO_EDGE_CONFIDENCE
    assert calibrated_confidence(_metrics(float("nan"), 90)) == NO_EDGE_CONFIDENCE


def test_coin_flip_or_worse_is_never_turned_into_a_signal():
    # The models that were being traded: 47-48% out of sample.
    assert calibrated_confidence(_metrics(47.1, 190)) == NO_EDGE_CONFIDENCE
    assert calibrated_confidence(_metrics(50.0, 190)) == NO_EDGE_CONFIDENCE
    assert calibrated_confidence(_metrics(0.0, 500)) == NO_EDGE_CONFIDENCE


def test_small_samples_are_shrunk_toward_fifty():
    # 60% on 100 samples with a 100-sample prior reads as 55%.
    assert math.isclose(shrunk_accuracy(0.60, 100), 0.55)
    assert calibrated_confidence(_metrics(60.0, 100)) == 55.0
    # Same measured accuracy, far more evidence -> closer to the measurement.
    assert calibrated_confidence(_metrics(60.0, 2000)) > 59.0
    assert calibrated_confidence(_metrics(60.0, 20)) < 52.0


def test_confidence_is_bounded_and_monotonic_in_accuracy():
    values = [calibrated_confidence(_metrics(a, 150)) for a in (50, 55, 60, 70, 100)]
    assert values == sorted(values)
    assert all(NO_EDGE_CONFIDENCE <= v <= 100.0 for v in values)


def test_best_current_model_stays_far_below_the_old_fabricated_floor():
    # Best production model on 2026-10-30: 61.5% direction accuracy on ~91 test rows.
    conf = calibrated_confidence(_metrics(61.5, 91))
    assert 55.0 < conf < 56.0
    assert conf < 85.0  # the old formula started every prediction at 85


def test_has_demonstrated_edge_threshold():
    assert has_demonstrated_edge(_metrics(61.5, 91)) is True
    assert has_demonstrated_edge(_metrics(55.0, 91)) is False
    assert has_demonstrated_edge(None) is False
