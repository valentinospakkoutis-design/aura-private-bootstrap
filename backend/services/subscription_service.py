"""Subscription tiers, feature gates, and FREE quota enforcement."""

from datetime import date, datetime
from typing import Dict, Optional

from fastapi import HTTPException

from database.connection import SessionLocal
from database.models import PredictionUsage, Subscription

FREE_TIER = "free"
PRO_TIER = "pro"
ELITE_TIER = "elite"

TIERS = (FREE_TIER, PRO_TIER, ELITE_TIER)
TIER_RANK = {FREE_TIER: 0, PRO_TIER: 1, ELITE_TIER: 2}
FREE_DAILY_PREDICTIONS = 10

FEATURE_MIN_TIER = {
    "live_trading": PRO_TIER,
    "auto_trading": PRO_TIER,
    "dca_strategy": ELITE_TIER,
    "claude_validation": ELITE_TIER,
}


def normalize_tier(value: Optional[str]) -> str:
    tier = str(value or FREE_TIER).strip().lower()
    return tier if tier in TIERS else FREE_TIER


def _build_status(sub: Subscription) -> Dict:
    tier = normalize_tier(sub.tier)
    is_free = tier == FREE_TIER
    return {
        "tier": tier,
        "is_active": bool(sub.is_active),
        "started_at": sub.started_at.isoformat() if sub.started_at else None,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "daily_prediction_limit": FREE_DAILY_PREDICTIONS if is_free else None,
        "features": {
            "live_trading": has_feature_for_tier(tier, "live_trading"),
            "auto_trading": has_feature_for_tier(tier, "auto_trading"),
            "dca_strategy": has_feature_for_tier(tier, "dca_strategy"),
            "claude_validation": has_feature_for_tier(tier, "claude_validation"),
            "unlimited_predictions": not is_free,
        },
    }


def ensure_user_subscription(user_id: int, db=None) -> Subscription:
    own_session = db is None
    session = db or SessionLocal()
    try:
        sub = session.query(Subscription).filter(Subscription.user_id == int(user_id)).first()
        if sub:
            return sub

        sub = Subscription(user_id=int(user_id), tier=FREE_TIER, is_active=True, started_at=datetime.utcnow())
        session.add(sub)
        session.commit()
        session.refresh(sub)
        return sub
    finally:
        if own_session:
            session.close()


def get_subscription_status(user_id: int, db=None) -> Dict:
    sub = ensure_user_subscription(user_id, db=db)
    return _build_status(sub)


def upgrade_subscription(user_id: int, tier: str, db=None) -> Dict:
    target = normalize_tier(tier)
    if target == FREE_TIER:
        raise HTTPException(status_code=400, detail="Upgrade tier must be pro or elite")

    own_session = db is None
    session = db or SessionLocal()
    try:
        sub = ensure_user_subscription(user_id, db=session)
        sub.tier = target
        sub.is_active = True
        sub.started_at = datetime.utcnow()
        sub.updated_at = datetime.utcnow()
        sub.payment_provider = "manual"
        session.commit()
        session.refresh(sub)
        return _build_status(sub)
    finally:
        if own_session:
            session.close()


def has_feature_for_tier(tier: str, feature: str) -> bool:
    required = FEATURE_MIN_TIER.get(feature)
    if not required:
        return True
    current_rank = TIER_RANK.get(normalize_tier(tier), 0)
    required_rank = TIER_RANK.get(required, 99)
    return current_rank >= required_rank


def user_has_feature(user_id: int, feature: str, db=None) -> bool:
    status = get_subscription_status(user_id, db=db)
    return bool(status.get("features", {}).get(feature, False))


def enforce_feature(user_id: int, feature: str, db=None) -> None:
    status = get_subscription_status(user_id, db=db)
    current_tier = status.get("tier", FREE_TIER)
    if has_feature_for_tier(current_tier, feature):
        return

    required_tier = FEATURE_MIN_TIER.get(feature, PRO_TIER)
    raise HTTPException(
        status_code=403,
        detail={
            "message": "Subscription upgrade required",
            "code": "SUBSCRIPTION_REQUIRED",
            "required_tier": required_tier,
            "current_tier": current_tier,
            "feature": feature,
        },
    )


def consume_prediction_quota(user_id: int, db=None) -> Dict:
    own_session = db is None
    session = db or SessionLocal()
    try:
        sub = ensure_user_subscription(user_id, db=session)
        tier = normalize_tier(sub.tier)
        if tier != FREE_TIER:
            return {
                "tier": tier,
                "used_today": None,
                "daily_limit": None,
                "remaining_today": None,
            }

        today = date.today()
        usage = (
            session.query(PredictionUsage)
            .filter(PredictionUsage.user_id == int(user_id), PredictionUsage.usage_date == today)
            .first()
        )
        if not usage:
            usage = PredictionUsage(user_id=int(user_id), usage_date=today, predictions_requested=0)
            session.add(usage)
            session.flush()

        if int(usage.predictions_requested or 0) >= FREE_DAILY_PREDICTIONS:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "FREE daily prediction limit reached",
                    "code": "FREE_PREDICTION_LIMIT_REACHED",
                    "current_tier": FREE_TIER,
                    "required_tier": PRO_TIER,
                    "daily_limit": FREE_DAILY_PREDICTIONS,
                    "used_today": int(usage.predictions_requested or 0),
                },
            )

        usage.predictions_requested = int(usage.predictions_requested or 0) + 1
        usage.updated_at = datetime.utcnow()
        session.commit()

        return {
            "tier": tier,
            "used_today": int(usage.predictions_requested or 0),
            "daily_limit": FREE_DAILY_PREDICTIONS,
            "remaining_today": max(0, FREE_DAILY_PREDICTIONS - int(usage.predictions_requested or 0)),
        }
    finally:
        if own_session:
            session.close()
