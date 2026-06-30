# Trained-model persistence

## The problem this solves

Trained models live in `backend/models/` (path resolved by
`ml/model_storage.get_models_dir()`). On Railway the container filesystem is
**ephemeral** — every redeploy/restart wipes anything written at runtime, so the
daily/weekly/monthly retraining jobs lose their output and the predictor falls
back to the handful of models committed in git.

## The fix

Point `AURA_MODELS_DIR` at a **persistent volume**. On first boot,
`seed_models_dir()` copies the git-bundled baseline models into the (empty)
volume — idempotent and non-destructive, so no model is ever lost in the
migration. After that, all training writes land on the volume and survive
redeploys.

Everything reads the same env var: the 5 ML modules (`auto_trainer`,
`enhanced_trainer`, `lstm_model`, `transfer_learning`, `backtester`),
`scripts/build_rf_ensemble.py`, and `ai/asset_predictor`.

## Railway setup

1. Railway dashboard → backend service → **Variables** → add:
   ```
   AURA_MODELS_DIR=/data/models
   ```
2. Railway dashboard → backend service → **Settings → Volumes** → **New Volume**:
   - Mount path: `/data`  (or `/data/models` — must match `AURA_MODELS_DIR`)
   - Size: 1 GB is plenty (current models total a few MB).
3. Redeploy. First boot logs:
   `[model_storage] seeded N bundled model files into /data/models`

> RL agents persist in the DB (`rl_models` table) and are unaffected. Model
> metadata persists in `model_registry`; this fix makes the actual `.pkl`/`.pth`
> weights it references survive too.

## Local (docker-compose)

Already wired: the `backend` service sets `AURA_MODELS_DIR=/data/models` and
mounts the named `models` volume. Nothing to do.

## Verifying

```bash
# inside the running container
ls -la "$AURA_MODELS_DIR"        # should list seeded + freshly-trained files
# trigger a training run, redeploy, then confirm the new files are still there
```

Leaving `AURA_MODELS_DIR` unset keeps the old behavior (bundled `backend/models`)
— the change is fully backward compatible.
