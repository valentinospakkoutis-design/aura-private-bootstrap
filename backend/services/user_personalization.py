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
VALID_OBJECTIVES = {"growth", "income", "preservation", "speculation"}


def get_user_profile(user_id: int) -> Dict:
    """Load user profile from DB. Returns defaults if not set."""
    try:
        from database.connection import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        row = db.execute(
            text("SELECT risk_profile, objective, confidence_threshold_override, "
                 "max_position_override, behavior_flags FROM user_profiles WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchone()
        db.close()

        if row:
            profile_name = row[0] if row[0] in VALID_PROFILES else "moderate"
            params = dict(PROFILE_PARAMS[profile_name])
            params["risk_profile"] = profile_name
            params["objective"] = row[1] or "growth"
            params["user_id"] = user_id
            # Apply per-user overrides if set
            if row[2] is not None:
                params["confidence_threshold"] = float(row[2])
            if row[3] is not None:
                params["max_positions"] = int(row[3])
            params["behavior_flags"] = row[4] or {}
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
    objective: str = "growth",
    confidence_threshold_override: Optional[float] = None,
    max_position_override: Optional[int] = None,
    behavior_flags: Optional[dict] = None,
) -> Dict:
    """Save or update user profile in DB."""
    if risk_profile not in VALID_PROFILES:
        return {"error": f"Invalid risk_profile. Must be one of: {sorted(VALID_PROFILES)}"}
    if objective not in VALID_OBJECTIVES:
        return {"error": f"Invalid objective. Must be one of: {sorted(VALID_OBJECTIVES)}"}

    try:
        from database.connection import SessionLocal
        from sqlalchemy import text
        import json

        db = SessionLocal()
        existing = db.execute(
            text("SELECT id FROM user_profiles WHERE user_id = :uid"), {"uid": user_id}
        ).fetchone()

        flags_json = json.dumps(behavior_flags or {})

        if existing:
            db.execute(text(
                "UPDATE user_profiles SET risk_profile = :rp, objective = :obj, "
                "confidence_threshold_override = :cto, max_position_override = :mpo, "
                "behavior_flags = :flags::jsonb, updated_at = NOW() "
                "WHERE user_id = :uid"
            ), {
                "rp": risk_profile, "obj": objective,
                "cto": confidence_threshold_override, "mpo": max_position_override,
                "flags": flags_json, "uid": user_id,
            })
        else:
            db.execute(text(
                "INSERT INTO user_profiles (user_id, risk_profile, objective, "
                "confidence_threshold_override, max_position_override, behavior_flags) "
                "VALUES (:uid, :rp, :obj, :cto, :mpo, :flags::jsonb)"
            ), {
                "uid": user_id, "rp": risk_profile, "obj": objective,
                "cto": confidence_threshold_override, "mpo": max_position_override,
                "flags": flags_json,
            })
        db.commit()
        db.close()

        return get_user_profile(user_id)
    except Exception as e:
        logger.error(f"[personalization] Failed to save profile: {e}")
        return {"error": str(e)}
