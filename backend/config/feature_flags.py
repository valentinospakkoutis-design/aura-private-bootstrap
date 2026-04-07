"""
AURA Feature Flags — Sentiment Rollout
All flags default to False for safe, incremental activation.
Override via environment variables (e.g. ENABLE_SENTIMENT=true).
"""

import os


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in ("true", "1", "yes")


# Phase 0 — scaffolding complete, flags exist
ENABLE_SENTIMENT = _flag("ENABLE_SENTIMENT")

# Phase 1 — data layer: fetch, score, persist, cache
# (news scheduler, DB writes, sentiment endpoints)
ENABLE_SENTIMENT_DATA = _flag("ENABLE_SENTIMENT_DATA")

# Phase 2 — read-only exposure: enrich prediction responses with sentiment context
ENABLE_SENTIMENT_EXPOSURE = _flag("ENABLE_SENTIMENT_EXPOSURE")

# Phase 3 — shadow mode: log hypothetical adjustments, no real changes
ENABLE_SENTIMENT_SHADOW = _flag("ENABLE_SENTIMENT_SHADOW")

# Phase 4 — soft activation: small confidence adjustments (±5%)
ENABLE_SENTIMENT_SOFT = _flag("ENABLE_SENTIMENT_SOFT")

# Phase 5 — hard filters: block trades below sentiment thresholds
ENABLE_SENTIMENT_HARD_FILTER = _flag("ENABLE_SENTIMENT_HARD_FILTER")

# Phase 6 — meta integration: sentiment as smart_score signal weight
ENABLE_META_SENTIMENT = _flag("ENABLE_META_SENTIMENT")

# Phase 7 — training integration: sentiment as ML training feature
ENABLE_SENTIMENT_TRAINING = _flag("ENABLE_SENTIMENT_TRAINING")
