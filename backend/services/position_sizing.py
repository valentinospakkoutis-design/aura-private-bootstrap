"""
Production-grade Position Sizing Engine for AURA.
Determines optimal trade size based on risk profile, confidence,
volatility, drawdown, and portfolio exposure.

All multipliers are deterministic and auditable.
"""

from dataclasses import dataclass
from typing import Optional


# ── Risk profiles ───────────────────────────────────────────────
RISK_PROFILES = {
    "conservative": {"base_risk_pct": 1.0, "max_per_trade_pct": 3.0, "max_portfolio_pct": 15.0},
    "moderate":     {"base_risk_pct": 2.0, "max_per_trade_pct": 5.0, "max_portfolio_pct": 25.0},
    "aggressive":   {"base_risk_pct": 4.0, "max_per_trade_pct": 10.0, "max_portfolio_pct": 40.0},
}


@dataclass
class SizingInput:
    account_balance: float          # Total account value in USD
    signal_confidence: float        # 0-1 (from explanation layer)
    volatility: float               # 0-1 (abs trend_score or ATR-based)
    current_drawdown: float         # 0-1 (0 = no drawdown, 0.1 = 10% down)
    current_portfolio_exposure: float  # 0-1 (fraction of balance in open positions)
    price: float                    # Current asset price
    user_risk_profile: str = "moderate"  # conservative / moderate / aggressive


@dataclass
class SizingResult:
    recommended_notional: float     # USD value of the position
    quantity: float                 # Units to buy/sell
    base_risk_pct: float
    confidence_multiplier: float
    volatility_multiplier: float
    drawdown_multiplier: float
    exposure_cap_applied: bool
    per_trade_cap_applied: bool
    final_risk_pct: float
    reasoning: str


def calculate_position_size(inp: SizingInput) -> SizingResult:
    """
    Calculate optimal position size with risk-adjusted multipliers.

    1. Start with base risk % from user profile
    2. Scale by confidence (higher confidence -> larger size)
    3. Scale by inverse volatility (higher vol -> smaller size)
    4. Reduce for drawdown (in drawdown -> smaller size)
    5. Cap by per-trade max and portfolio exposure max
    """
    profile = RISK_PROFILES.get(inp.user_risk_profile, RISK_PROFILES["moderate"])
    base_risk = profile["base_risk_pct"]
    max_per_trade = profile["max_per_trade_pct"]
    max_portfolio = profile["max_portfolio_pct"]

    # ── Confidence multiplier ───────────────────────────────────
    # Low confidence (< 0.4) -> 0.5x, high (> 0.8) -> 1.2x
    conf = max(0.0, min(1.0, inp.signal_confidence))
    if conf >= 0.8:
        confidence_mult = 1.0 + (conf - 0.8) * 1.0  # 1.0 - 1.2
    elif conf >= 0.5:
        confidence_mult = 0.7 + (conf - 0.5) * 1.0  # 0.7 - 1.0
    else:
        confidence_mult = max(0.3, conf / 0.5 * 0.7)  # 0.0 - 0.7

    # ── Volatility multiplier (inverse) ─────────────────────────
    # High volatility -> smaller size
    vol = max(0.0, min(1.0, inp.volatility))
    volatility_mult = max(0.3, 1.0 - vol * 0.7)  # 0.3 - 1.0

    # ── Drawdown reduction ──────────────────────────────────────
    # In drawdown -> reduce size to protect remaining capital
    dd = max(0.0, min(1.0, inp.current_drawdown))
    if dd > 0.15:
        drawdown_mult = 0.25  # Severe drawdown: cut to 25%
    elif dd > 0.10:
        drawdown_mult = 0.5   # Moderate drawdown: cut to 50%
    elif dd > 0.05:
        drawdown_mult = 0.75  # Light drawdown: cut to 75%
    else:
        drawdown_mult = 1.0   # No significant drawdown

    # ── Calculate adjusted risk % ───────────────────────────────
    adjusted_risk = base_risk * confidence_mult * volatility_mult * drawdown_mult
    adjusted_risk = max(0.1, adjusted_risk)  # Floor: always at least 0.1%

    # ── Apply per-trade cap ─────────────────────────────────────
    per_trade_capped = False
    if adjusted_risk > max_per_trade:
        adjusted_risk = max_per_trade
        per_trade_capped = True

    # ── Calculate notional ──────────────────────────────────────
    notional = inp.account_balance * (adjusted_risk / 100)

    # ── Apply portfolio exposure cap ────────────────────────────
    exposure_capped = False
    remaining_capacity = max(0, max_portfolio / 100 - inp.current_portfolio_exposure)
    max_allowed_notional = inp.account_balance * remaining_capacity
    if notional > max_allowed_notional:
        notional = max_allowed_notional
        exposure_capped = True

    # ── Ensure non-negative ─────────────────────────────────────
    notional = max(0, notional)

    # ── Calculate quantity ──────────────────────────────────────
    quantity = notional / inp.price if inp.price > 0 else 0

    # ── Build reasoning ─────────────────────────────────────────
    parts = [f"Base risk: {base_risk}% ({inp.user_risk_profile})"]
    if confidence_mult != 1.0:
        parts.append(f"Confidence {conf:.0%} -> {confidence_mult:.2f}x")
    if volatility_mult != 1.0:
        parts.append(f"Volatility {vol:.0%} -> {volatility_mult:.2f}x")
    if drawdown_mult != 1.0:
        parts.append(f"Drawdown {dd:.0%} -> {drawdown_mult:.2f}x")
    if per_trade_capped:
        parts.append(f"Capped at {max_per_trade}% per-trade max")
    if exposure_capped:
        parts.append(f"Capped by portfolio exposure ({inp.current_portfolio_exposure:.0%}/{max_portfolio}% max)")
    parts.append(f"Final: ${notional:.2f} ({adjusted_risk:.2f}% of ${inp.account_balance:.0f})")

    return SizingResult(
        recommended_notional=round(notional, 2),
        quantity=round(quantity, 8),
        base_risk_pct=base_risk,
        confidence_multiplier=round(confidence_mult, 3),
        volatility_multiplier=round(volatility_mult, 3),
        drawdown_multiplier=round(drawdown_mult, 3),
        exposure_cap_applied=exposure_capped,
        per_trade_cap_applied=per_trade_capped,
        final_risk_pct=round(adjusted_risk, 3),
        reasoning=" | ".join(parts),
    )
