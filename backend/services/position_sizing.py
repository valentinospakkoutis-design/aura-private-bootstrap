"""
Production-grade Position Sizing Engine for AURA.
Determines optimal trade size based on risk profile, confidence,
volatility, drawdown, and portfolio exposure.

Enforces strict safety caps:
- Absolute max exposure ($1000 default)
- Per-symbol cap ($500 default)
- Portfolio cap (% of balance)
- Per-trade cap (% of balance)

All multipliers and cap triggers are deterministic and auditable.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


# ── Risk profiles ───────────────────────────────────────────────
RISK_PROFILES = {
    "conservative": {"base_risk_pct": 1.0, "max_per_trade_pct": 3.0, "max_portfolio_pct": 15.0},
    "moderate":     {"base_risk_pct": 2.0, "max_per_trade_pct": 5.0, "max_portfolio_pct": 25.0},
    "aggressive":   {"base_risk_pct": 4.0, "max_per_trade_pct": 10.0, "max_portfolio_pct": 40.0},
}

# ── Safety caps (absolute, non-overridable) ─────────────────────
SAFETY_CAPS = {
    "absolute_max_exposure_usd": 1000.0,  # No single trade > $1000
    "per_symbol_max_usd": 500.0,          # Max $500 in any one symbol
    "min_trade_usd": 1.0,                 # Below this -> block (not worth fees)
}


@dataclass
class SizingInput:
    account_balance: float
    signal_confidence: float        # 0-1
    volatility: float               # 0-1
    current_drawdown: float         # 0-1
    current_portfolio_exposure: float  # 0-1
    price: float
    user_risk_profile: str = "moderate"
    symbol: str = ""
    existing_symbol_exposure_usd: float = 0.0  # Current USD in this symbol


@dataclass
class SizingResult:
    recommended_notional: float
    quantity: float
    decision: str                   # "execute" / "reduce" / "block"
    base_risk_pct: float
    confidence_multiplier: float
    volatility_multiplier: float
    drawdown_multiplier: float
    exposure_cap_applied: bool
    per_trade_cap_applied: bool
    final_risk_pct: float
    cap_adjustments: List[str] = field(default_factory=list)
    reasoning: str = ""


def calculate_position_size(inp: SizingInput) -> SizingResult:
    """
    Calculate optimal position size with risk-adjusted multipliers
    and strict safety caps.

    Pipeline:
    1. Base risk % from user profile
    2. Multiply by confidence, volatility, drawdown factors
    3. Cap by per-trade max %
    4. Cap by portfolio exposure max %
    5. Cap by absolute max exposure ($1000)
    6. Cap by per-symbol max ($500)
    7. Check min trade threshold
    8. Determine decision: execute / reduce / block
    """
    profile = RISK_PROFILES.get(inp.user_risk_profile, RISK_PROFILES["moderate"])
    base_risk = profile["base_risk_pct"]
    max_per_trade = profile["max_per_trade_pct"]
    max_portfolio = profile["max_portfolio_pct"]

    cap_adjustments: List[str] = []
    reasoning_parts = [f"Base risk: {base_risk}% ({inp.user_risk_profile})"]

    # ── Confidence multiplier ───────────────────────────────────
    conf = max(0.0, min(1.0, inp.signal_confidence))
    if conf >= 0.8:
        confidence_mult = 1.0 + (conf - 0.8) * 1.0
    elif conf >= 0.5:
        confidence_mult = 0.7 + (conf - 0.5) * 1.0
    else:
        confidence_mult = max(0.3, conf / 0.5 * 0.7)

    # ── Volatility multiplier (inverse) ─────────────────────────
    vol = max(0.0, min(1.0, inp.volatility))
    volatility_mult = max(0.3, 1.0 - vol * 0.7)

    # ── Drawdown reduction ──────────────────────────────────────
    dd = max(0.0, min(1.0, inp.current_drawdown))
    if dd > 0.15:
        drawdown_mult = 0.25
    elif dd > 0.10:
        drawdown_mult = 0.5
    elif dd > 0.05:
        drawdown_mult = 0.75
    else:
        drawdown_mult = 1.0

    if confidence_mult != 1.0:
        reasoning_parts.append(f"Confidence {conf:.0%} -> {confidence_mult:.2f}x")
    if volatility_mult != 1.0:
        reasoning_parts.append(f"Volatility {vol:.0%} -> {volatility_mult:.2f}x")
    if drawdown_mult != 1.0:
        reasoning_parts.append(f"Drawdown {dd:.0%} -> {drawdown_mult:.2f}x")

    # ── Calculate adjusted risk % ───────────────────────────────
    adjusted_risk = base_risk * confidence_mult * volatility_mult * drawdown_mult
    adjusted_risk = max(0.1, adjusted_risk)

    # ── CAP 1: Per-trade % cap ──────────────────────────────────
    per_trade_capped = False
    if adjusted_risk > max_per_trade:
        cap_adjustments.append(
            f"PER_TRADE_PCT_CAP: {adjusted_risk:.2f}% reduced to {max_per_trade}% max"
        )
        adjusted_risk = max_per_trade
        per_trade_capped = True
        reasoning_parts.append(f"Capped at {max_per_trade}% per-trade max")

    # ── Calculate raw notional ──────────────────────────────────
    notional = inp.account_balance * (adjusted_risk / 100)
    original_notional = notional

    # ── CAP 2: Portfolio exposure cap ───────────────────────────
    exposure_capped = False
    remaining_capacity = max(0, max_portfolio / 100 - inp.current_portfolio_exposure)
    max_allowed_by_portfolio = inp.account_balance * remaining_capacity
    if notional > max_allowed_by_portfolio:
        cap_adjustments.append(
            f"PORTFOLIO_CAP: ${notional:.2f} reduced to ${max_allowed_by_portfolio:.2f} "
            f"(exposure {inp.current_portfolio_exposure:.0%}/{max_portfolio}% max)"
        )
        notional = max_allowed_by_portfolio
        exposure_capped = True
        reasoning_parts.append(f"Portfolio cap: {inp.current_portfolio_exposure:.0%}/{max_portfolio}%")

    # ── CAP 3: Absolute max exposure ────────────────────────────
    abs_max = SAFETY_CAPS["absolute_max_exposure_usd"]
    if notional > abs_max:
        cap_adjustments.append(
            f"ABSOLUTE_MAX_CAP: ${notional:.2f} reduced to ${abs_max:.2f} hard limit"
        )
        notional = abs_max
        reasoning_parts.append(f"Absolute cap: ${abs_max:.0f}")

    # ── CAP 4: Per-symbol cap ───────────────────────────────────
    sym_max = SAFETY_CAPS["per_symbol_max_usd"]
    remaining_sym_capacity = max(0, sym_max - inp.existing_symbol_exposure_usd)
    if notional > remaining_sym_capacity:
        cap_adjustments.append(
            f"SYMBOL_CAP: ${notional:.2f} reduced to ${remaining_sym_capacity:.2f} "
            f"(existing ${inp.existing_symbol_exposure_usd:.2f} + new <= ${sym_max:.0f} max)"
        )
        notional = remaining_sym_capacity
        reasoning_parts.append(f"Symbol cap: ${inp.existing_symbol_exposure_usd:.0f}+new <= ${sym_max:.0f}")

    # ── Ensure non-negative ─────────────────────────────────────
    notional = max(0, notional)

    # ── Determine decision ──────────────────────────────────────
    min_trade = SAFETY_CAPS["min_trade_usd"]
    if notional < min_trade:
        decision = "block"
        if inp.account_balance <= 0:
            cap_adjustments.append("BLOCK: zero account balance")
        elif remaining_sym_capacity <= 0:
            cap_adjustments.append(f"BLOCK: symbol exposure at ${sym_max:.0f} cap")
        elif remaining_capacity <= 0:
            cap_adjustments.append(f"BLOCK: portfolio exposure at {max_portfolio}% cap")
        else:
            cap_adjustments.append(f"BLOCK: notional ${notional:.2f} below ${min_trade:.2f} minimum")
        notional = 0
    elif notional < original_notional * 0.5 and len(cap_adjustments) > 0:
        decision = "reduce"
    else:
        decision = "execute"

    # ── Calculate quantity ──────────────────────────────────────
    quantity = notional / inp.price if inp.price > 0 and notional > 0 else 0

    reasoning_parts.append(f"Final: ${notional:.2f} -> {decision.upper()}")

    # ── Log cap triggers + trust verdict ─────────────────────────
    if cap_adjustments:
        sym_label = inp.symbol or "unknown"
        for adj in cap_adjustments:
            logger.info(f"[SIZING_CAP] {sym_label}: {adj}")
        try:
            from ai.trust_layer import verdict_from_sizing
            verdict_from_sizing(sym_label, decision, cap_adjustments, notional)
        except Exception:
            pass

    return SizingResult(
        recommended_notional=round(notional, 2),
        quantity=round(quantity, 8),
        decision=decision,
        base_risk_pct=base_risk,
        confidence_multiplier=round(confidence_mult, 3),
        volatility_multiplier=round(volatility_mult, 3),
        drawdown_multiplier=round(drawdown_mult, 3),
        exposure_cap_applied=exposure_capped,
        per_trade_cap_applied=per_trade_capped,
        final_risk_pct=round(adjusted_risk, 3),
        cap_adjustments=cap_adjustments,
        reasoning=" | ".join(reasoning_parts),
    )
