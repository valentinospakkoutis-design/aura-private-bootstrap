"""
Autopilot Mode Configuration for AURA.
Defines SAFE / BALANCED / AGGRESSIVE presets that control
the auto-trading engine's behavior holistically.
"""

import logging
from typing import Dict

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

# Track current mode
_current_mode = "balanced"


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


def apply_mode(mode: str, auto_trader) -> Dict:
    """
    Apply an autopilot mode to the auto-trading engine.
    Updates engine config, check interval, and sizing profile.
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

    return {
        "mode": mode,
        "label": mode_def["label"],
        "config_applied": mode_def["engine_config"],
        "check_interval": mode_def["check_interval"],
        "sizing_profile": mode_def["sizing_profile"],
        "allowed_strategies": mode_def["allowed_strategies"],
    }
