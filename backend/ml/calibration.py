"""
Honest confidence for model predictions.

A prediction's confidence must reflect how often the model has actually been
right on data it did not train on — not the size of the predicted move.

`calibrated_confidence` turns the out-of-sample direction accuracy stored with
each trained model into a 0-100 confidence:

  * the measured accuracy is shrunk toward 50% (coin flip) according to how
    few test samples it was measured on, so a lucky 60% on 90 samples does
    not read as a real 60%;
  * a model that is at or below 50% out of sample has no demonstrated edge,
    so its confidence is exactly 50 — it is never inverted into a signal;
  * a model with no stored metrics gets 50.

The result is deliberately unspectacular: with today's models it lands in the
50-58 range. That is the point — downstream gates should only open when a
model has earned it.
"""

from typing import Any, Dict, Optional

# Neutral value: "no better than a coin flip".
NO_EDGE_CONFIDENCE = 50.0

# Strength of the 50% prior, in pseudo-observations. With PRIOR_N = 100 a model
# measured at 60% on 100 test samples is reported as 55%.
PRIOR_N = 100.0


def shrunk_accuracy(accuracy: float, n_samples: float, prior_n: float = PRIOR_N) -> float:
    """Shrink a measured accuracy (0-1) toward 0.5 by sample size. Returns 0-1."""
    n = max(0.0, float(n_samples))
    acc = min(1.0, max(0.0, float(accuracy)))
    return (acc * n + 0.5 * prior_n) / (n + prior_n)


def calibrated_confidence(metrics: Optional[Dict[str, Any]], prior_n: float = PRIOR_N) -> float:
    """Confidence (0-100) from a model's stored out-of-sample metrics.

    Expects the `metrics` dict written by ml.auto_trainer.train_symbol:
    `test_direction_accuracy` in percent and `test_samples` as a count.
    """
    if not isinstance(metrics, dict):
        return NO_EDGE_CONFIDENCE
    try:
        acc_pct = float(metrics.get("test_direction_accuracy"))
        n = float(metrics.get("test_samples"))
    except (TypeError, ValueError):
        return NO_EDGE_CONFIDENCE
    if n <= 0 or acc_pct != acc_pct:  # no samples or NaN
        return NO_EDGE_CONFIDENCE

    shrunk = shrunk_accuracy(acc_pct / 100.0, n, prior_n)
    return round(max(NO_EDGE_CONFIDENCE, shrunk * 100.0), 2)


def has_demonstrated_edge(metrics: Optional[Dict[str, Any]], min_confidence: float = 55.0) -> bool:
    """True when the shrunk out-of-sample accuracy clears `min_confidence`."""
    return calibrated_confidence(metrics) >= min_confidence
