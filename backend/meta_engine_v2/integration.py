from __future__ import annotations

from meta_engine_v2.engine import MetaEngineV2
from meta_engine_v2.schemas import MetaEngineV2Input, MetaEngineV2Output


def evaluate_meta_engine_v2(inputs: MetaEngineV2Input) -> MetaEngineV2Output:
    return MetaEngineV2().evaluate(inputs)
