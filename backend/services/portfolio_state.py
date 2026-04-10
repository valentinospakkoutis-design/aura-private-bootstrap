"""
Portfolio State & Awareness Engine for AURA.
Tracks open positions, exposure per symbol and asset class,
detects concentration risk, and recommends sizing adjustments.

Feeds into: decision validation, position sizing.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Asset class mapping (symbol prefix -> class) ────────────────
# Matches AssetType enum in ai/asset_predictor.py
ASSET_CLASS_MAP = {
    # Crypto
    "BTC": "crypto", "ETH": "crypto", "BNB": "crypto", "XRP": "crypto",
    "SOL": "crypto", "ADA": "crypto", "AVAX": "crypto", "DOT": "crypto",
    "LINK": "crypto", "SHIB": "crypto", "DOGE": "crypto", "TRX": "crypto",
    "LTC": "crypto", "ALGO": "crypto", "ATOM": "crypto", "NEAR": "crypto",
    "UNI": "crypto", "AAVE": "crypto", "FIL": "crypto", "SAND": "crypto",
    # Metals
    "XAU": "precious_metal", "XAG": "precious_metal",
    "XPT": "precious_metal", "XPD": "precious_metal",
    # Stocks
    "AAPL": "stock", "MSFT": "stock", "GOOGL": "stock", "AMZN": "stock",
    "TSLA": "stock", "NVDA": "stock", "META": "stock",
}

# ── Concentration limits ────────────────────────────────────────
CONCENTRATION_LIMITS = {
    "max_single_symbol_pct": 25.0,      # Max 25% in one symbol
    "max_asset_class_pct": 60.0,        # Max 60% in one asset class
    "max_correlated_pct": 50.0,         # Max 50% in correlated assets
    "concentration_warning_pct": 40.0,  # Warn above 40% in one class
}

# ── Correlation groups (assets that move together) ──────────────
CORRELATION_GROUPS = {
    "large_cap_crypto": {"BTC", "ETH"},
    "alt_crypto": {"SOL", "ADA", "AVAX", "DOT", "LINK", "ATOM", "NEAR"},
    "meme_crypto": {"SHIB", "DOGE"},
    "defi": {"UNI", "AAVE", "LINK"},
    "tech_stocks": {"AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"},
    "precious_metals": {"XAU", "XAG", "XPT", "XPD"},
}


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    current_value_usd: float
    asset_class: str
    side: str = "BUY"


@dataclass
class PortfolioRiskAssessment:
    portfolio_risk_score: float         # 0-100 (higher = riskier)
    total_exposure_usd: float
    position_count: int
    exposure_by_symbol: Dict[str, float]
    exposure_by_class: Dict[str, float]
    exposure_by_class_pct: Dict[str, float]
    concentration_warnings: List[str]
    correlated_exposure: Dict[str, float]
    adjustment_recommendation: str      # "ok" / "reduce" / "block"
    adjustment_details: List[str]
    size_factor: float                  # 1.0 = no adjustment, <1.0 = reduce


def _extract_base_symbol(symbol: str) -> str:
    """Extract base asset from trading pair (BTCUSDC -> BTC)."""
    for suffix in ("USDC", "USDT", "USD", "BUSD"):
        if symbol.upper().endswith(suffix):
            return symbol.upper()[:-len(suffix)]
    return symbol.upper()


def _get_asset_class(symbol: str) -> str:
    """Determine asset class from symbol."""
    base = _extract_base_symbol(symbol)
    return ASSET_CLASS_MAP.get(base, "crypto")


def _get_correlation_groups_for(symbol: str) -> List[str]:
    """Get all correlation groups this symbol belongs to."""
    base = _extract_base_symbol(symbol)
    return [name for name, members in CORRELATION_GROUPS.items() if base in members]


def assess_portfolio(
    positions: List[Dict],
    account_balance: float,
    proposed_symbol: Optional[str] = None,
    proposed_value: float = 0.0,
    user_id: Optional[int] = None,
) -> PortfolioRiskAssessment:
    """
    Analyze current portfolio state and return risk assessment.

    positions: list of dicts with {symbol, quantity, entry_price, current_value_usd}
               or {symbol, amount, value_usdc} (from Binance portfolio)
    account_balance: total account value in USD
    proposed_symbol: symbol of the proposed new trade (for pre-trade check)
    proposed_value: USD value of the proposed new trade
    """
    # Normalize positions
    parsed: List[Position] = []
    for p in positions:
        sym = p.get("symbol", "")
        val = p.get("current_value_usd") or p.get("value_usdc") or 0
        qty = p.get("quantity") or p.get("amount") or 0
        entry = p.get("entry_price") or (val / qty if qty > 0 else 0)
        if val > 0 and sym:
            parsed.append(Position(
                symbol=sym, quantity=qty, entry_price=entry,
                current_value_usd=float(val),
                asset_class=_get_asset_class(sym),
                side=p.get("side", "BUY"),
            ))

    # ── Exposure by symbol ──────────────────────────────────────
    exposure_by_symbol: Dict[str, float] = {}
    for pos in parsed:
        base = _extract_base_symbol(pos.symbol)
        exposure_by_symbol[base] = exposure_by_symbol.get(base, 0) + pos.current_value_usd

    # Include proposed trade
    if proposed_symbol and proposed_value > 0:
        base_proposed = _extract_base_symbol(proposed_symbol)
        exposure_by_symbol[base_proposed] = exposure_by_symbol.get(base_proposed, 0) + proposed_value

    total_exposure = sum(exposure_by_symbol.values())

    # ── Exposure by asset class ─────────────────────────────────
    exposure_by_class: Dict[str, float] = {}
    for sym, val in exposure_by_symbol.items():
        cls = ASSET_CLASS_MAP.get(sym, "crypto")
        exposure_by_class[cls] = exposure_by_class.get(cls, 0) + val

    exposure_by_class_pct: Dict[str, float] = {}
    if account_balance > 0:
        for cls, val in exposure_by_class.items():
            exposure_by_class_pct[cls] = round(val / account_balance * 100, 1)

    # ── Correlated exposure ─────────────────────────────────────
    correlated_exposure: Dict[str, float] = {}
    for group_name, members in CORRELATION_GROUPS.items():
        group_total = sum(exposure_by_symbol.get(m, 0) for m in members)
        if group_total > 0:
            correlated_exposure[group_name] = round(group_total, 2)

    # ── Concentration warnings ──────────────────────────────────
    warnings: List[str] = []
    risk_score = 0.0

    # Check single symbol concentration
    for sym, val in exposure_by_symbol.items():
        if account_balance > 0:
            sym_pct = val / account_balance * 100
            if sym_pct > CONCENTRATION_LIMITS["max_single_symbol_pct"]:
                warnings.append(
                    f"SYMBOL_CONCENTRATION: {sym} at {sym_pct:.1f}% "
                    f"(max {CONCENTRATION_LIMITS['max_single_symbol_pct']}%)"
                )
                risk_score += 20

    # Check asset class concentration
    for cls, pct in exposure_by_class_pct.items():
        if pct > CONCENTRATION_LIMITS["max_asset_class_pct"]:
            warnings.append(
                f"CLASS_CONCENTRATION: {cls} at {pct:.1f}% "
                f"(max {CONCENTRATION_LIMITS['max_asset_class_pct']}%)"
            )
            risk_score += 15
        elif pct > CONCENTRATION_LIMITS["concentration_warning_pct"]:
            warnings.append(
                f"CLASS_WARNING: {cls} at {pct:.1f}% approaching limit"
            )
            risk_score += 5

    # Check correlated exposure
    for group, val in correlated_exposure.items():
        if account_balance > 0:
            group_pct = val / account_balance * 100
            if group_pct > CONCENTRATION_LIMITS["max_correlated_pct"]:
                warnings.append(
                    f"CORRELATED_EXPOSURE: {group} at {group_pct:.1f}% "
                    f"(max {CONCENTRATION_LIMITS['max_correlated_pct']}%)"
                )
                risk_score += 10

    # Base risk from total exposure
    if account_balance > 0:
        total_pct = total_exposure / account_balance * 100
        risk_score += min(30, total_pct * 0.5)  # Up to 30 points from total exposure

    risk_score = min(100, max(0, risk_score))

    # ── Adjustment recommendation ───────────────────────────────
    adjustment_details: List[str] = []
    size_factor = 1.0

    if risk_score >= 70:
        adjustment = "block"
        size_factor = 0.0
        adjustment_details.append("Portfolio risk too high - new trades blocked")
    elif risk_score >= 50:
        adjustment = "reduce"
        size_factor = max(0.25, 1.0 - (risk_score - 50) / 50)
        adjustment_details.append(f"High concentration - size reduced to {size_factor:.0%}")
    elif risk_score >= 30:
        adjustment = "reduce"
        size_factor = max(0.5, 1.0 - (risk_score - 30) / 100)
        adjustment_details.append(f"Moderate concentration - size reduced to {size_factor:.0%}")
    else:
        adjustment = "ok"

    # Specific proposed-trade warnings
    if proposed_symbol and proposed_value > 0 and account_balance > 0:
        proposed_base = _extract_base_symbol(proposed_symbol)
        proposed_total = exposure_by_symbol.get(proposed_base, 0)
        proposed_pct = proposed_total / account_balance * 100
        if proposed_pct > CONCENTRATION_LIMITS["max_single_symbol_pct"]:
            adjustment = "block" if adjustment != "block" else adjustment
            size_factor = 0.0
            adjustment_details.append(
                f"Adding ${proposed_value:.0f} to {proposed_base} would reach {proposed_pct:.1f}% "
                f"(max {CONCENTRATION_LIMITS['max_single_symbol_pct']}%)"
            )

        # Check if proposed asset class would breach limit
        proposed_class = _get_asset_class(proposed_symbol)
        class_total_pct = exposure_by_class_pct.get(proposed_class, 0)
        if class_total_pct > CONCENTRATION_LIMITS["max_asset_class_pct"]:
            if adjustment != "block":
                adjustment = "reduce"
                size_factor = min(size_factor, 0.5)
            adjustment_details.append(
                f"{proposed_class} class at {class_total_pct:.1f}% - reduce new {proposed_class} exposure"
            )

    if warnings:
        for w in warnings:
            logger.info(f"[PORTFOLIO_RISK] {w}")

    # Trust layer verdict
    if warnings or adjustment != "ok":
        try:
            from ai.trust_layer import verdict_from_portfolio
            verdict_from_portfolio(
                symbol=proposed_symbol or "",
                risk_score=risk_score,
                adjustment=adjustment,
                warnings=warnings,
                size_factor=size_factor,
            )
        except Exception:
            pass

    result = PortfolioRiskAssessment(
        portfolio_risk_score=round(risk_score, 1),
        total_exposure_usd=round(total_exposure, 2),
        position_count=len(parsed),
        exposure_by_symbol={k: round(v, 2) for k, v in exposure_by_symbol.items()},
        exposure_by_class={k: round(v, 2) for k, v in exposure_by_class.items()},
        exposure_by_class_pct=exposure_by_class_pct,
        concentration_warnings=warnings,
        correlated_exposure=correlated_exposure,
        adjustment_recommendation=adjustment,
        adjustment_details=adjustment_details,
        size_factor=round(size_factor, 3),
    )

    # Persist snapshot if user_id provided
    if user_id is not None and parsed:
        try:
            from services.portfolio_persistence import save_portfolio_snapshot
            symbol_rows = []
            for pos in parsed:
                base = _extract_base_symbol(pos.symbol)
                val = pos.current_value_usd
                pct = (val / account_balance * 100) if account_balance > 0 else 0
                symbol_rows.append({
                    "symbol": base,
                    "asset_class": pos.asset_class,
                    "direction": "long" if pos.side == "BUY" else "short",
                    "quantity": pos.quantity,
                    "market_value": val,
                    "exposure_pct": round(pct, 2),
                })
            save_portfolio_snapshot(
                user_id=user_id,
                total_equity=account_balance,
                available_cash=max(0, account_balance - total_exposure),
                positions=symbol_rows,
                correlated_exposure=correlated_exposure,
                risk_score=round(risk_score, 1),
                concentration_score=round(risk_score, 1),
            )
        except Exception as e:
            logger.warning(f"[portfolio_state] Snapshot persistence failed (non-fatal): {e}")

    return result
