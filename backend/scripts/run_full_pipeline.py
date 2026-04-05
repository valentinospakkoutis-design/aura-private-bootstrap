"""
Full Training Pipeline Runner
Runs all 4 phases in sequence:
  Phase 1: Data Collection (OHLCV + News)
  Phase 2: Sentiment Labeling
  Phase 3: Feature Engineering
  Phase 4: Model Retraining (XGBoost + RF Ensemble)
"""

import os
import sys
import logging
import uuid
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)


def run_full_pipeline(job_id: str = None) -> dict:
    """Run all 4 phases of the training pipeline."""
    if not job_id:
        job_id = f"pipeline_{uuid.uuid4().hex[:8]}"

    from database.connection import SessionLocal, init_db
    from database.models import TrainingLog

    # Ensure tables exist
    init_db()

    db = SessionLocal()
    db.add(TrainingLog(
        job_id=job_id, phase="full_pipeline",
        status="running", message="Starting full pipeline", progress=0
    ))
    db.commit()
    db.close()

    results = {"job_id": job_id, "phases": {}}

    # Phase 1: Data Collection
    try:
        logger.info(f"[Pipeline] Phase 1: Data Collection")
        from scripts.collect_training_data import run_collection
        run_collection(job_id)
        results["phases"]["collect_data"] = "completed"
    except Exception as e:
        logger.error(f"[Pipeline] Phase 1 failed: {e}")
        results["phases"]["collect_data"] = f"failed: {e}"

    # Phase 2: Sentiment Labeling
    try:
        logger.info(f"[Pipeline] Phase 2: Sentiment Labeling")
        from ml.sentiment_labeler import label_all_news
        label_all_news(job_id)
        results["phases"]["label_sentiment"] = "completed"
    except Exception as e:
        logger.error(f"[Pipeline] Phase 2 failed: {e}")
        results["phases"]["label_sentiment"] = f"failed: {e}"

    # Phase 3: Feature Engineering
    try:
        logger.info(f"[Pipeline] Phase 3: Feature Engineering")
        from ml.feature_engineer import engineer_all_features
        engineer_all_features(job_id)
        results["phases"]["feature_engineering"] = "completed"
    except Exception as e:
        logger.error(f"[Pipeline] Phase 3 failed: {e}")
        results["phases"]["feature_engineering"] = f"failed: {e}"

    # Phase 4: Model Retraining
    try:
        logger.info(f"[Pipeline] Phase 4: Model Retraining")
        from ml.enhanced_trainer import retrain_all
        train_results = retrain_all(job_id)
        results["phases"]["retrain"] = "completed"
        results["models"] = train_results
    except Exception as e:
        logger.error(f"[Pipeline] Phase 4 failed: {e}")
        results["phases"]["retrain"] = f"failed: {e}"

    # Final log
    db = SessionLocal()
    all_ok = all(v == "completed" for v in results["phases"].values())
    db.add(TrainingLog(
        job_id=job_id, phase="full_pipeline",
        status="completed" if all_ok else "partial",
        message=f"Pipeline finished: {results['phases']}",
        progress=100, completed_at=datetime.utcnow()
    ))
    db.commit()
    db.close()

    logger.info(f"[Pipeline] Complete: {results['phases']}")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_full_pipeline()
    import json
    print(json.dumps(result, indent=2, default=str))
