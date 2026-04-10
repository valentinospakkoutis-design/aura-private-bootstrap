"""
AURA Trust Layer — Unified explanation system.
Ensures every decision, block, and reduction across the entire app
produces standardized, machine-readable, auditable output.

This is the single integration point. All modules call through here
instead of building explanations independently.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from ai.reason_codes import (
    LOW_CONFIDENCE, SIGNAL_CONFLICT, NO_ML_CONFIRMATION,
    TREND_TOO_WEAK, MARKET_SIDEWAYS, VOLATILITY_TOO_HIGH,
    RISK_BLOCK, PORTFOLIO_EXPOSURE_LIMIT, SYMBOL_EXPOSURE_LIMIT,
    FEAR_GREED_EXTREME, SMART_SCORE_INSUFFICIENT,
    SIZE_REDUCED_BY_RISK, SIZE_REDUCED_BY_VOLATILITY,
    SIZE_REDUCED_BY_EXPOSURE_CAP,
    THRESHOLDS,
)

logger = logging.getLogger(__name__)


class TrustVerdict:
    """
    Standardized verdict produced by the trust layer.
    Attached to every decision, trade, block, and skip.
    """
    __slots__ = (
        "action", "reason_codes", "explanation", "blocked_by",
        "sizing_adjustments", "improvement_triggers",
        "source", "symbol", "timestamp",
    )

    def __init__(
        self,
        action: str,
        reason_codes: List[str],
        explanation: str,
        source: str,
        symbol: str = "",
        blocked_by: List[str] = None,
        sizing_adjustments: List[str] = None,
        improvement_triggers: List[str] = None,
    ):
        self.action = action
        self.reason_codes = reason_codes
        self.explanation = explanation
        self.source = source
        self.symbol = symbol
        self.blocked_by = blocked_by or []
        self.sizing_adjustments = sizing_adjustments or []
        self.improvement_triggers = improvement_triggers or []
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "reason_codes": self.reason_codes,
            "explanation": self.explanation,
            "blocked_by": self.blocked_by,
            "sizing_adjustments": self.sizing_adjustments,
            "improvement_triggers": self.improvement_triggers,
            "source": self.source,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
        }

    def log(self, risk_event_kwargs: dict = None):
        """Log the verdict for audit trail and persist risk events."""
        logger.info(
            f"[TRUST] {self.source} | {self.symbol} | {self.action} | "
            f"codes={','.join(self.reason_codes[:5])} | {self.explanation[:100]}"
        )
        # Persist to feed
        try:
            from services.feed_engine import emit
            severity = "info"
            if self.action in ("BLOCKED",):
                severity = "critical"
            elif self.action in ("BUY", "SELL", "REDUCE"):
                severity = "warning"

            event_type = "trade_signal"
            if self.action in ("NO-TRADE", "HOLD", "SKIP"):
                event_type = "no_trade_explanation"
            elif self.action == "BLOCKED":
                event_type = "risk_alert"

            emit(
                event_type=event_type,
                title=f"{self.action}: {self.symbol}",
                body=self.explanation[:200],
                symbol=self.symbol,
                severity=severity,
                reason_codes=self.reason_codes,
                metadata={"source": self.source},
            )
        except Exception:
            pass

        # Persist risk event if this is a meaningful intervention
        if self.action in ("BLOCKED", "BLOCK", "REDUCE", "SKIP") and self.reason_codes:
            try:
                from services.risk_event_persistence import emit_risk_event

                if self.action in ("BLOCKED", "BLOCK"):
                    r_event_type = "blocked_trade"
                    r_severity = "critical"
                elif self.action == "REDUCE":
                    r_event_type = "size_reduced"
                    r_severity = "warning"
                else:
                    r_event_type = "exposure_warning"
                    r_severity = "info"

                kwargs = {
                    "event_type": r_event_type,
                    "reason_code": self.reason_codes[0] if self.reason_codes else "UNKNOWN",
                    "summary": self.explanation[:200],
                    "symbol": self.symbol or None,
                    "severity": r_severity,
                    "details": {
                        "source": self.source,
                        "all_reason_codes": self.reason_codes,
                        "blocked_by": self.blocked_by,
                        "sizing_adjustments": self.sizing_adjustments,
                    },
                }
                if risk_event_kwargs:
                    kwargs.update(risk_event_kwargs)

                emit_risk_event(**kwargs)
            except Exception:
                pass


# ── Verdict builders for each system ────────────────────────────

def verdict_from_auto_trader_skip(
    symbol: str,
    reason: str,
    confidence: float = 0,
    smart_score: float = 0,
    fear_greed: float = 50,
) -> TrustVerdict:
    """Build a verdict when the auto-trader skips a symbol."""
    codes = []
    triggers = []

    if confidence < THRESHOLDS["confidence_min"]:
        codes.append(LOW_CONFIDENCE)
        triggers.append(f"Confidence must reach {THRESHOLDS['confidence_min']:.0%} (currently {confidence:.0%})")
    if smart_score < THRESHOLDS["smart_score_min"]:
        codes.append(SMART_SCORE_INSUFFICIENT)
        triggers.append(f"Smart Score must reach {THRESHOLDS['smart_score_min']} (currently {smart_score:.0f})")
    if fear_greed < THRESHOLDS["fear_greed_min"]:
        codes.append(FEAR_GREED_EXTREME)
        triggers.append(f"Fear & Greed must recover above {THRESHOLDS['fear_greed_min']} (currently {fear_greed:.0f})")

    if not codes:
        codes.append(SIGNAL_CONFLICT)

    v = TrustVerdict(
        action="SKIP",
        reason_codes=codes,
        explanation=reason,
        source="auto_trader",
        symbol=symbol,
        improvement_triggers=triggers,
    )
    v.log()
    return v


def verdict_from_sizing(
    symbol: str,
    decision: str,
    cap_adjustments: List[str],
    recommended_notional: float,
) -> TrustVerdict:
    """Build a verdict from position sizing engine output."""
    codes = []
    blocked_by = []
    sizing_adj = []

    for adj in cap_adjustments:
        if "ABSOLUTE_MAX_CAP" in adj:
            codes.append(SIZE_REDUCED_BY_RISK)
            sizing_adj.append(adj)
        elif "SYMBOL_CAP" in adj:
            codes.append(SYMBOL_EXPOSURE_LIMIT)
            if "BLOCK" in adj:
                blocked_by.append("Symbol exposure at cap")
            else:
                sizing_adj.append(adj)
        elif "PORTFOLIO_CAP" in adj:
            codes.append(PORTFOLIO_EXPOSURE_LIMIT)
            if "BLOCK" in adj:
                blocked_by.append("Portfolio exposure at cap")
            else:
                sizing_adj.append(adj)
        elif "BLOCK" in adj:
            codes.append(RISK_BLOCK)
            blocked_by.append(adj)
        else:
            sizing_adj.append(adj)

    action = decision.upper()  # execute / reduce / block
    if action == "EXECUTE":
        action = "SIZED"

    explanation = f"Sizing: ${recommended_notional:.2f} | {decision}"
    if cap_adjustments:
        explanation += f" | {len(cap_adjustments)} cap(s) applied"

    v = TrustVerdict(
        action=action,
        reason_codes=codes,
        explanation=explanation,
        source="position_sizing",
        symbol=symbol,
        blocked_by=blocked_by,
        sizing_adjustments=sizing_adj,
    )
    if codes:
        v.log(risk_event_kwargs={
            "adjusted_notional": recommended_notional,
        })
    return v


def verdict_from_portfolio(
    symbol: str,
    risk_score: float,
    adjustment: str,
    warnings: List[str],
    size_factor: float,
) -> TrustVerdict:
    """Build a verdict from portfolio risk assessment."""
    codes = []
    blocked_by = []
    triggers = []

    for w in warnings:
        if "SYMBOL_CONCENTRATION" in w:
            codes.append(SYMBOL_EXPOSURE_LIMIT)
        elif "CLASS_CONCENTRATION" in w:
            codes.append(PORTFOLIO_EXPOSURE_LIMIT)
        elif "CORRELATED" in w:
            codes.append(SIZE_REDUCED_BY_EXPOSURE_CAP)

    if adjustment == "block":
        codes.append(RISK_BLOCK)
        blocked_by.append(f"Portfolio risk score {risk_score:.0f}/100")
        triggers.append("Close existing positions to reduce concentration")
    elif adjustment == "reduce":
        codes.append(SIZE_REDUCED_BY_RISK)
        triggers.append(f"Diversify to reduce risk score below 30 (currently {risk_score:.0f})")

    explanation = f"Portfolio risk: {risk_score:.0f}/100 | {adjustment} | size_factor={size_factor:.0%}"

    v = TrustVerdict(
        action=adjustment.upper() if adjustment != "ok" else "OK",
        reason_codes=codes,
        explanation=explanation,
        source="portfolio_state",
        symbol=symbol,
        blocked_by=blocked_by,
        improvement_triggers=triggers,
    )
    if codes:
        v.log(risk_event_kwargs={
            "portfolio_risk_score": risk_score,
        })
    return v
