"""Single source of truth for where trained model artifacts live.

By default models sit in the git-bundled ``backend/models`` directory. In
production (Railway) that path is on the container's EPHEMERAL filesystem, so
runtime-trained models vanish on every redeploy. Set ``AURA_MODELS_DIR`` to a
mounted persistent volume to keep them.

``seed_models_dir()`` copies the git-bundled snapshot into a freshly-mounted
(empty) volume on first boot so the migration never loses the baseline models.
"""
import os
import shutil
import logging

logger = logging.getLogger(__name__)

# The models that ship inside the repo / image.
BUNDLED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


def get_models_dir() -> str:
    """Return the active models directory (persistent volume if configured)."""
    return os.environ.get("AURA_MODELS_DIR", BUNDLED_MODELS_DIR)


def seed_models_dir() -> int:
    """Copy git-bundled model files into the active models dir if missing.

    Idempotent and non-destructive: never overwrites a file that already exists
    in the target. No-op when no separate volume is configured. Returns the
    number of files copied.
    """
    target = get_models_dir()
    if os.path.abspath(target) == os.path.abspath(BUNDLED_MODELS_DIR):
        return 0  # no separate volume — bundled dir is already the target
    if not os.path.isdir(BUNDLED_MODELS_DIR):
        return 0

    os.makedirs(target, exist_ok=True)
    copied = 0
    for name in os.listdir(BUNDLED_MODELS_DIR):
        src = os.path.join(BUNDLED_MODELS_DIR, name)
        dst = os.path.join(target, name)
        if not os.path.isfile(src) or os.path.exists(dst):
            continue
        try:
            shutil.copy2(src, dst)
            copied += 1
        except Exception as e:
            logger.warning("[model_storage] seed copy failed for %s: %s", name, e)

    if copied:
        logger.info("[model_storage] seeded %s bundled model files into %s", copied, target)
    return copied
