"""
Real-time portfolio correlation matrix.
Prevents over-exposure to correlated assets.
"""

from typing import Optional

CORRELATION_GROUPS = {
    "crypto_large": ["BTCUSDC", "ETHUSDC", "BTC-USD", "ETH-USD"],
    "crypto_alt": ["SOLUSDC", "ADAUSDC", "AVAXUSDC", "DOTUSDC"],
    "us_tech": ["AAPL", "GOOGL", "MSFT", "NVDA"],
    "precious_metals": ["XAUUSDT", "XAGUSDT", "GC=F", "SI=F"],
    "fx": ["EURUSD", "GBPUSD", "USDJPY"],
}

MAX_GROUP_EXPOSURE = 0.40


def get_group(symbol: str) -> Optional[str]:
    """Find which correlation group a symbol belongs to."""
    symbol_u = (symbol or "").upper()
    for group, symbols in CORRELATION_GROUPS.items():
        if symbol_u in {s.upper() for s in symbols}:
            return group
    return None


def check_correlation_risk(symbol: str, proposed_size_usd: float, open_positions: list, total_portfolio_usd: float) -> dict:
    """
    Check if adding a position would create over-exposure
    to a correlated group.
    """
    try:
        proposed = float(proposed_size_usd or 0.0)
        portfolio = float(total_portfolio_usd or 0.0)

        if portfolio <= 0:
            return {"allowed": True, "reason": "no portfolio data", "max_allowed_usd": proposed}

        group = get_group(symbol)
        if not group:
            return {"allowed": True, "reason": "no correlation group", "max_allowed_usd": proposed}

        group_symbols = {s.upper() for s in CORRELATION_GROUPS[group]}
        current_group_exposure = 0.0
        for pos in open_positions or []:
            pos_symbol = str(pos.get("symbol", "")).upper()
            if pos_symbol in group_symbols:
                current_group_exposure += float(pos.get("value_usd", 0.0) or 0.0)

        max_group_usd = portfolio * MAX_GROUP_EXPOSURE
        remaining_capacity = max_group_usd - current_group_exposure

        if remaining_capacity <= 0:
            return {
                "allowed": False,
                "reason": f"Group '{group}' at max exposure ({MAX_GROUP_EXPOSURE:.0%})",
                "max_allowed_usd": 0,
                "current_exposure_pct": round(current_group_exposure / portfolio, 3),
                "group": group,
                "group_limit_pct": MAX_GROUP_EXPOSURE,
            }

        max_allowed = min(proposed, remaining_capacity)
        allowed = max_allowed >= proposed * 0.5 if proposed > 0 else True

        return {
            "allowed": bool(allowed),
            "reason": "within correlation limits" if allowed else "would exceed group limit",
            "max_allowed_usd": round(float(max_allowed), 2),
            "group": group,
            "current_group_exposure_pct": round(current_group_exposure / portfolio, 3),
            "group_limit_pct": MAX_GROUP_EXPOSURE,
        }
    except Exception as e:
        return {"allowed": True, "reason": f"correlation_check_failed: {e}", "max_allowed_usd": float(proposed_size_usd or 0.0)}
