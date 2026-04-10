"""
Autopilot Mode Configuration for AURA.
Defines SAFE / BALANCED / AGGRESSIVE presets that control
the auto-trading engine's behavior holistically.

Persistence:
  - user_autopilot_settings  = mutable current state (one row per user)
  - autopilot_mode_change_log = append-only audit trail of every change
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Mode definitions ────────────────────────────────────────────
# Each mode sets: engine config, sizing profile, and allowed strategies.
AUTOPILOT_MODES = {
    "safe": {
        "label": "Safe",
        "description": "Low risk, high confidence required, fewer trades",
        "engine_config": {
            "confidence_threshold": 0.95,
            "smart_score_threshold": 85,
            "fixed_order_value_usd": 5.0,
            "max_order_value_usd": 50.0,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.03,
            "max_positions": 2,
        },
        "check_interval": 120,       # Check every 2 minutes
        "sizing_profile": "conservative",
        "allowed_strategies": ["spot_long"],  # No shorts, no futures
    },
    "balanced": {
        "label": "Balanced",
        "description": "Moderate risk and return, standard thresholds",
        "engine_config": {
            "confidence_threshold": 0.90,
            "smart_score_threshold": 75,
            "fixed_order_value_usd": 10.0,
            "max_order_value_usd": 100.0,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.05,
            "max_positions": 3,
        },
        "check_interval": 60,        # Check every minute
        "sizing_profile": "moderate",
        "allowed_strategies": ["spot_long", "spot_short"],
    },
    "aggressive": {
        "label": "Aggressive",
        "description": "Higher exposure, more frequent trades, wider stops",
        "engine_config": {
            "confidence_threshold": 0.80,
            "smart_score_threshold": 65,
            "fixed_order_value_usd": 20.0,
            "max_order_value_usd": 200.0,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.08,
            "max_positions": 5,
        },
        "check_interval": 30,        # Check every 30 seconds
        "sizing_profile": "aggressive",
        "allowed_strategies": ["spot_long", "spot_short", "futures_long"],
    },
}

VALID_MODES = set(AUTOPILOT_MODES.keys())

# In-memory fallback (used when DB is unavailable or for global default)
_current_mode = "balanced"


# ── Read helpers ───────────────────────────────────────────────

def get_current_mode() -> str:
    return _current_mode


def get_mode_config(mode: str) -> Dict:
    """Get full config for a mode."""
    if mode not in VALID_MODES:
        return {"error": f"Invalid mode. Must be one of: {sorted(VALID_MODES)}"}
    config = dict(AUTOPILOT_MODES[mode])
    config["mode"] = mode
    return config


def get_all_modes() -> Dict:
    """Get summary of all available modes."""
    return {
        name: {
            "label": m["label"],
            "description": m["description"],
            "confidence_threshold": m["engine_config"]["confidence_threshold"],
            "max_positions": m["engine_config"]["max_positions"],
            "sizing_profile": m["sizing_profile"],
            "check_interval": m["check_interval"],
        }
        for name, m in AUTOPILOT_MODES.items()
    }


# ── Persistence layer ─────────────────────────────────────────

def get_user_autopilot(user_id: int) -> Dict:
    """Load persisted autopilot settings for a user. Returns defaults if not set."""
    try:
        from database.connection import SessionLocal
        from database.models import UserAutopilotSettings
        db = SessionLocal()
        row = db.query(UserAutopilotSettings).filter(
            UserAutopilotSettings.user_id == user_id
        ).first()
        db.close()

        if row:
            mode = row.current_mode if row.current_mode in VALID_MODES else "balanced"
            mode_def = AUTOPILOT_MODES[mode]
            return {
                "user_id": user_id,
                "current_mode": mode,
                "is_enabled": row.is_enabled,
                "config_overrides": row.config_overrides_json or {},
                "label": mode_def["label"],
                "description": mode_def["description"],
                "engine_config": mode_def["engine_config"],
                "check_interval": mode_def["check_interval"],
                "sizing_profile": mode_def["sizing_profile"],
                "allowed_strategies": mode_def["allowed_strategies"],
            }
    except Exception as e:
        logger.warning(f"[autopilot] Failed to load settings for user {user_id}: {e}")

    # Default
    mode_def = AUTOPILOT_MODES["balanced"]
    return {
        "user_id": user_id,
        "current_mode": "balanced",
        "is_enabled": False,
        "config_overrides": {},
        "label": mode_def["label"],
        "description": mode_def["description"],
        "engine_config": mode_def["engine_config"],
        "check_interval": mode_def["check_interval"],
        "sizing_profile": mode_def["sizing_profile"],
        "allowed_strategies": mode_def["allowed_strategies"],
    }


def save_user_autopilot(
    user_id: int,
    mode: str,
    is_enabled: Optional[bool] = None,
    config_overrides: Optional[dict] = None,
    reason: Optional[str] = None,
    changed_by: str = "user",
    change_metadata: Optional[dict] = None,
) -> Dict:
    """
    Save or update autopilot settings for a user.
    Also logs the mode change to the append-only audit trail.
    """
    if mode not in VALID_MODES:
        return {"error": f"Invalid mode. Must be one of: {sorted(VALID_MODES)}"}

    try:
        from database.connection import SessionLocal
        from database.models import UserAutopilotSettings, AutopilotModeChangeLog

        db = SessionLocal()

        # ── Upsert settings ──
        existing = db.query(UserAutopilotSettings).filter(
            UserAutopilotSettings.user_id == user_id
        ).first()

        previous_mode = existing.current_mode if existing else None

        if existing:
            existing.current_mode = mode
            if is_enabled is not None:
                existing.is_enabled = is_enabled
            if config_overrides is not None:
                existing.config_overrides_json = config_overrides
        else:
            db.add(UserAutopilotSettings(
                user_id=user_id,
                current_mode=mode,
                is_enabled=is_enabled if is_enabled is not None else False,
                config_overrides_json=config_overrides or {},
            ))

        # ── Append change log (only if mode actually changed) ──
        if previous_mode != mode:
            db.add(AutopilotModeChangeLog(
                user_id=user_id,
                previous_mode=previous_mode,
                new_mode=mode,
                reason=reason,
                changed_by=changed_by,
                metadata_json=change_metadata or {},
            ))

        db.commit()
        db.close()

        # Unified audit trail (only if mode changed)
        if previous_mode != mode:
            try:
                from services.audit_trail import emit_audit
                emit_audit(
                    domain="autopilot",
                    event_name="AUTOPILOT_MODE_CHANGED",
                    summary=f"Mode changed from {previous_mode or 'none'} to {mode} by {changed_by}",
                    user_id=user_id,
                    entity_type="user_autopilot_settings",
                    severity="info",
                    payload={"previous_mode": previous_mode, "new_mode": mode,
                             "changed_by": changed_by, "reason": reason},
                )
            except Exception:
                pass

        return get_user_autopilot(user_id)
    except Exception as e:
        logger.error(f"[autopilot] Failed to save settings: {e}")
        return {"error": str(e)}


def get_autopilot_change_history(user_id: int, limit: int = 20) -> list:
    """Get recent mode change history for a user."""
    try:
        from database.connection import SessionLocal
        from database.models import AutopilotModeChangeLog

        db = SessionLocal()
        rows = (
            db.query(AutopilotModeChangeLog)
            .filter(AutopilotModeChangeLog.user_id == user_id)
            .order_by(AutopilotModeChangeLog.created_at.desc())
            .limit(limit)
            .all()
        )
        db.close()

        return [
            {
                "id": r.id,
                "previous_mode": r.previous_mode,
                "new_mode": r.new_mode,
                "reason": r.reason,
                "changed_by": r.changed_by,
                "metadata": r.metadata_json or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"[autopilot] Failed to load change history: {e}")
        return []


# ── Engine integration ─────────────────────────────────────────

def apply_mode(mode: str, auto_trader, user_id: int = None,
               reason: str = None, changed_by: str = "user") -> Dict:
    """
    Apply an autopilot mode to the auto-trading engine.
    Updates engine config, check interval, and sizing profile.
    Persists to DB if user_id is provided.
    Returns the applied config.
    """
    global _current_mode

    if mode not in VALID_MODES:
        return {"error": f"Invalid mode. Must be one of: {sorted(VALID_MODES)}"}

    mode_def = AUTOPILOT_MODES[mode]

    # Apply engine config
    for key, value in mode_def["engine_config"].items():
        auto_trader.config[key] = value

    # Apply check interval
    auto_trader.check_interval = mode_def["check_interval"]

    _current_mode = mode

    logger.info(f"[autopilot] Mode set to {mode}: "
                f"conf>={mode_def['engine_config']['confidence_threshold']}, "
                f"ss>={mode_def['engine_config']['smart_score_threshold']}, "
                f"max_pos={mode_def['engine_config']['max_positions']}, "
                f"interval={mode_def['check_interval']}s")

    # Persist if user_id provided
    if user_id is not None:
        save_user_autopilot(
            user_id=user_id,
            mode=mode,
            is_enabled=auto_trader.enabled if hasattr(auto_trader, "enabled") else None,
            reason=reason,
            changed_by=changed_by,
        )

    return {
        "mode": mode,
        "label": mode_def["label"],
        "config_applied": mode_def["engine_config"],
        "check_interval": mode_def["check_interval"],
        "sizing_profile": mode_def["sizing_profile"],
        "allowed_strategies": mode_def["allowed_strategies"],
    }
