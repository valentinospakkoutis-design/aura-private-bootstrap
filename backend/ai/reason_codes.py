"""
Stable machine-readable reason codes for AURA trading decisions.
Used in explanations, audit logs, analytics, and future AI feed.

Codes are string constants — deterministic, reusable, UI-mappable.
"""

# ── Positive / Directional ──────────────────────────────────────
ML_POSITIVE_FORECAST = "ML_POSITIVE_FORECAST"
ML_NEGATIVE_FORECAST = "ML_NEGATIVE_FORECAST"
TREND_BULLISH = "TREND_BULLISH"
TREND_BEARISH = "TREND_BEARISH"
SMART_SCORE_ABOVE_THRESHOLD = "SMART_SCORE_ABOVE_THRESHOLD"
SMART_SCORE_BELOW_THRESHOLD = "SMART_SCORE_BELOW_THRESHOLD"
SIGNAL_ALIGNMENT_HIGH = "SIGNAL_ALIGNMENT_HIGH"
RSI_SUPPORTS_DIRECTION = "RSI_SUPPORTS_DIRECTION"
VOLUME_CONFIRMS_MOVE = "VOLUME_CONFIRMS_MOVE"
NEWS_SENTIMENT_FAVORABLE = "NEWS_SENTIMENT_FAVORABLE"
MTF_TREND_ALIGNED = "MTF_TREND_ALIGNED"
STRONG_SIGNAL_STRENGTH = "STRONG_SIGNAL_STRENGTH"

# ── Inaction / Rejection ────────────────────────────────────────
LOW_CONFIDENCE = "LOW_CONFIDENCE"
SIGNAL_CONFLICT = "SIGNAL_CONFLICT"
NO_ML_CONFIRMATION = "NO_ML_CONFIRMATION"
TREND_TOO_WEAK = "TREND_TOO_WEAK"
MARKET_SIDEWAYS = "MARKET_SIDEWAYS"
VOLATILITY_TOO_HIGH = "VOLATILITY_TOO_HIGH"
RISK_BLOCK = "RISK_BLOCK"
PORTFOLIO_EXPOSURE_LIMIT = "PORTFOLIO_EXPOSURE_LIMIT"
SYMBOL_EXPOSURE_LIMIT = "SYMBOL_EXPOSURE_LIMIT"
GLOBAL_EXPOSURE_LIMIT = "GLOBAL_EXPOSURE_LIMIT"
WAIT_FOR_CONFIRMATION = "WAIT_FOR_CONFIRMATION"
SMART_SCORE_INSUFFICIENT = "SMART_SCORE_INSUFFICIENT"
FEAR_GREED_EXTREME = "FEAR_GREED_EXTREME"
PRICE_CHANGE_BELOW_THRESHOLD = "PRICE_CHANGE_BELOW_THRESHOLD"

# ── Sizing / Reduction ─────────────────────────────────────────
SIZE_REDUCED_BY_RISK = "SIZE_REDUCED_BY_RISK"
SIZE_REDUCED_BY_VOLATILITY = "SIZE_REDUCED_BY_VOLATILITY"
SIZE_REDUCED_BY_DRAWDOWN = "SIZE_REDUCED_BY_DRAWDOWN"
SIZE_REDUCED_BY_EXPOSURE_CAP = "SIZE_REDUCED_BY_EXPOSURE_CAP"

# ── Thresholds (from actual codebase config) ────────────────────
# These are the real thresholds used by the decision engine.
THRESHOLDS = {
    "confidence_min": 0.90,          # auto_trading_engine.py
    "smart_score_min": 75,           # auto_trading_engine.py
    "fear_greed_min": 25,            # auto_trading_engine.py
    "trend_score_directional": 0.3,  # asset_predictor.py
    "price_change_buy": 0.5,         # asset_predictor.py (%)
    "price_change_strong": 2.0,      # asset_predictor.py (%)
    "max_positions": 3,              # auto_trading_engine.py
    "stop_loss_pct": 3.0,            # auto_trading_engine.py
    "take_profit_pct": 5.0,          # auto_trading_engine.py
    "signal_agreement_high": 0.6,    # 3/5 signals
    "volatility_high": 0.7,          # trend_score magnitude
}
