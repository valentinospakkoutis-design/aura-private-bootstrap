"""
User Personalization Service for AURA.
Maps user risk profile and preferences into concrete engine parameters.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Profile parameter mappings ──────────────────────────────────
# These adjust how the decision engine and position sizing behave
# per user, within the existing safety cap framework.
PROFILE_PARAMS = {
    "conservative": {
        "sizing_profile": "conservative",
        "confidence_threshold": 0.80,   # Higher bar to trade
        "smart_score_min": 80,          # Stricter smart score
        "max_positions": 2,
        "description": "Lower risk, higher confidence required, smaller positions",
    },
    "moderate": {
        "sizing_profile": "moderate",
        "confidence_threshold": 0.70,
        "smart_score_min": 75,
        "max_positions": 3,
        "description": "Balanced risk and return",
    },
    "aggressive": {
        "sizing_profile": "aggressive",
        "confidence_threshold": 0.55,   # Lower bar to trade
        "smart_score_min": 65,          # More lenient
        "max_positions": 5,
        "description": "Higher risk tolerance, more frequent trades, larger positions",
    },
}

VALID_PROFILES = set(PROFILE_PARAMS.keys())
VALID_OBJECTIVES = {"capital_preservation", "balanced_growth", "aggressive_growth",
                     "growth", "income", "preservation", "speculation"}
VALID_MODES = {"manual_assist", "guided", "autopilot"}


def get_user_profile(user_id: int) -> Dict:
    """Load user profile from DB. Returns defaults if not set."""
    try:
        from database.connection import SessionLocal
        from database.models import UserProfile
        db = SessionLocal()
        row = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        db.close()

        if row:
            profile_name = row.risk_profile if row.risk_profile in VALID_PROFILES else "moderate"
            params = dict(PROFILE_PARAMS[profile_name])
            params["risk_profile"] = profile_name
            params["objective"] = row.investment_objective or "balanced_growth"
            params["preferred_mode"] = row.preferred_mode or "manual_assist"
            params["user_id"] = user_id
            if row.confidence_threshold_override is not None:
                params["confidence_threshold"] = float(row.confidence_threshold_override)
            if row.max_position_size_override is not None:
                params["max_positions"] = int(row.max_position_size_override)
            if row.max_portfolio_exposure_override is not None:
                params["max_portfolio_exposure"] = float(row.max_portfolio_exposure_override)
            params["behavior_flags"] = row.behavior_flags_json or {}
            params["notes"] = row.notes_json or {}
            return params
    except Exception as e:
        logger.warning(f"[personalization] Failed to load profile for user {user_id}: {e}")

    # Default
    params = dict(PROFILE_PARAMS["moderate"])
    params["risk_profile"] = "moderate"
    params["objective"] = "growth"
    params["user_id"] = user_id
    params["behavior_flags"] = {}
    return params


def save_user_profile(
    user_id: int,
    risk_profile: str,
    objective: str = "balanced_growth",
    preferred_mode: str = "manual_assist",
    confidence_threshold_override: Optional[float] = None,
    max_position_override: Optional[int] = None,
    max_portfolio_exposure_override: Optional[float] = None,
    behavior_flags: Optional[dict] = None,
    notes: Optional[dict] = None,
) -> Dict:
    """Save or update user profile in DB using ORM."""
    if risk_profile not in VALID_PROFILES:
        return {"error": f"Invalid risk_profile. Must be one of: {sorted(VALID_PROFILES)}"}
    if objective not in VALID_OBJECTIVES:
        return {"error": f"Invalid objective. Must be one of: {sorted(VALID_OBJECTIVES)}"}
    if preferred_mode not in VALID_MODES:
        return {"error": f"Invalid preferred_mode. Must be one of: {sorted(VALID_MODES)}"}

    try:
        from database.connection import SessionLocal
        from database.models import UserProfile

        db = SessionLocal()
        existing = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

        if existing:
            existing.risk_profile = risk_profile
            existing.investment_objective = objective
            existing.preferred_mode = preferred_mode
            existing.confidence_threshold_override = confidence_threshold_override
            existing.max_position_size_override = max_position_override
            existing.max_portfolio_exposure_override = max_portfolio_exposure_override
            existing.behavior_flags_json = behavior_flags or {}
            existing.notes_json = notes or {}
        else:
            db.add(UserProfile(
                user_id=user_id,
                risk_profile=risk_profile,
                investment_objective=objective,
                preferred_mode=preferred_mode,
                confidence_threshold_override=confidence_threshold_override,
                max_position_size_override=max_position_override,
                max_portfolio_exposure_override=max_portfolio_exposure_override,
                behavior_flags_json=behavior_flags or {},
                notes_json=notes or {},
            ))
        db.commit()
        db.close()

        return get_user_profile(user_id)
    except Exception as e:
        logger.error(f"[personalization] Failed to save profile: {e}")
        return {"error": str(e)}
