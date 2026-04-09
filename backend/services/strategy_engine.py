"""
Modular Strategy System for AURA.
Defines a Strategy interface and a registry of pluggable strategies.
The meta engine evaluates all registered strategies and combines results.

Each strategy implements: generate_signal(), score(), explain().
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Strategy interface ──────────────────────────────────────────

class Strategy(ABC):
    """Base interface for all AURA trading strategies."""

    name: str = "base"
    description: str = ""
    version: str = "1.0"

    @abstractmethod
    def generate_signal(self, symbol: str, market_data: Dict) -> Dict:
        """
        Generate a trading signal.
        Returns: {action: BUY/SELL/HOLD, confidence: 0-1, metadata: {...}}
        """
        pass

    @abstractmethod
    def score(self, symbol: str, market_data: Dict) -> float:
        """
        Score the opportunity (0-100). Higher = more attractive.
        """
        pass

    @abstractmethod
    def explain(self, symbol: str, market_data: Dict) -> List[str]:
        """
        Explain the decision in human-readable lines.
        """
        pass


# ── Built-in strategies ─────────────────────────────────────────

class MLTrendStrategy(Strategy):
    """Follow ML model predictions when trend is strong."""

    name = "ml_trend"
    description = "Follow ML model price predictions with trend confirmation"
    version = "1.0"

    def generate_signal(self, symbol: str, market_data: Dict) -> Dict:
        trend_score = market_data.get("trend_score", 0)
        confidence = market_data.get("confidence", 0) / 100
        recommendation = market_data.get("recommendation", "HOLD")
        using_ml = market_data.get("using_ml_model", False)

        if not using_ml:
            return {"action": "HOLD", "confidence": 0.3, "metadata": {"reason": "No ML model"}}

        if abs(trend_score) < 0.3:
            return {"action": "HOLD", "confidence": confidence * 0.5, "metadata": {"reason": "Trend too weak"}}

        return {"action": recommendation, "confidence": confidence, "metadata": {"trend_score": trend_score}}

    def score(self, symbol: str, market_data: Dict) -> float:
        confidence = market_data.get("confidence", 0)
        trend = abs(market_data.get("trend_score", 0))
        using_ml = market_data.get("using_ml_model", False)
        if not using_ml:
            return 20
        return min(100, confidence * 0.6 + trend * 40)

    def explain(self, symbol: str, market_data: Dict) -> List[str]:
        reasons = []
        if market_data.get("using_ml_model"):
            pct = market_data.get("price_change_percent", 0)
            reasons.append(f"ML model predicts {pct:+.1f}% price change")
        else:
            reasons.append("No ML model available for this symbol")
        trend = market_data.get("trend_score", 0)
        if abs(trend) > 0.3:
            direction = "bullish" if trend > 0 else "bearish"
            reasons.append(f"Trend score {trend:+.2f} confirms {direction} momentum")
        else:
            reasons.append(f"Trend score {trend:+.2f} is too weak for entry")
        return reasons


class SmartScoreStrategy(Strategy):
    """Trade based on the multi-signal Smart Score composite."""

    name = "smart_score"
    description = "Multi-signal composite score combining RSI, volume, news, MTF, and ML"
    version = "1.0"

    def generate_signal(self, symbol: str, market_data: Dict) -> Dict:
        ss = market_data.get("smart_score", 50)
        recommendation = market_data.get("recommendation", "HOLD")

        if ss >= 75 and recommendation in ("BUY", "SELL"):
            return {"action": recommendation, "confidence": ss / 100, "metadata": {"smart_score": ss}}
        if ss <= 25:
            return {"action": "SELL", "confidence": (100 - ss) / 100, "metadata": {"smart_score": ss}}
        return {"action": "HOLD", "confidence": 0.5, "metadata": {"smart_score": ss}}

    def score(self, symbol: str, market_data: Dict) -> float:
        return market_data.get("smart_score", 50)

    def explain(self, symbol: str, market_data: Dict) -> List[str]:
        ss = market_data.get("smart_score", 50)
        signals = market_data.get("signals", {})
        reasons = [f"Smart Score: {ss:.0f}/100"]
        for sig_name, sig_data in signals.items():
            if isinstance(sig_data, dict) and "score" in sig_data:
                reasons.append(f"  {sig_name}: {sig_data['score']:.0f}/100")
        return reasons


class MomentumStrategy(Strategy):
    """Trade strong momentum with volume confirmation."""

    name = "momentum"
    description = "Enter on strong price momentum confirmed by volume"
    version = "1.0"

    def generate_signal(self, symbol: str, market_data: Dict) -> Dict:
        trend = market_data.get("trend_score", 0)
        volume = market_data.get("signals", {}).get("volume", {}).get("score", 50)
        confidence = market_data.get("confidence", 50) / 100

        if abs(trend) > 0.5 and volume > 60:
            action = "BUY" if trend > 0 else "SELL"
            return {"action": action, "confidence": min(1.0, confidence * 1.1), "metadata": {"trend": trend, "volume": volume}}
        return {"action": "HOLD", "confidence": 0.4, "metadata": {"trend": trend, "volume": volume}}

    def score(self, symbol: str, market_data: Dict) -> float:
        trend = abs(market_data.get("trend_score", 0))
        volume = market_data.get("signals", {}).get("volume", {}).get("score", 50)
        return min(100, trend * 60 + volume * 0.4)

    def explain(self, symbol: str, market_data: Dict) -> List[str]:
        trend = market_data.get("trend_score", 0)
        volume = market_data.get("signals", {}).get("volume", {}).get("score", 50)
        reasons = []
        if abs(trend) > 0.5:
            reasons.append(f"Strong momentum: trend_score={trend:+.2f}")
        else:
            reasons.append(f"Weak momentum: trend_score={trend:+.2f}")
        if volume > 60:
            reasons.append(f"Volume confirms move ({volume:.0f}/100)")
        else:
            reasons.append(f"Volume insufficient ({volume:.0f}/100)")
        return reasons


class MeanReversionStrategy(Strategy):
    """Counter-trend entry when RSI indicates oversold/overbought."""

    name = "mean_reversion"
    description = "Fade extremes when RSI is oversold/overbought"
    version = "1.0"

    def generate_signal(self, symbol: str, market_data: Dict) -> Dict:
        rsi = market_data.get("signals", {}).get("rsi", {}).get("score", 50)
        confidence = market_data.get("confidence", 50) / 100

        if rsi > 80:  # Overbought -> sell
            return {"action": "SELL", "confidence": min(1.0, (rsi - 70) / 30), "metadata": {"rsi": rsi}}
        if rsi < 20:  # Oversold -> buy
            return {"action": "BUY", "confidence": min(1.0, (30 - rsi) / 30), "metadata": {"rsi": rsi}}
        return {"action": "HOLD", "confidence": 0.3, "metadata": {"rsi": rsi}}

    def score(self, symbol: str, market_data: Dict) -> float:
        rsi = market_data.get("signals", {}).get("rsi", {}).get("score", 50)
        # Score peaks at extremes
        distance_from_50 = abs(rsi - 50)
        return min(100, distance_from_50 * 2.5)

    def explain(self, symbol: str, market_data: Dict) -> List[str]:
        rsi = market_data.get("signals", {}).get("rsi", {}).get("score", 50)
        if rsi > 80:
            return [f"RSI at {rsi:.0f} (overbought) - mean reversion SELL opportunity"]
        if rsi < 20:
            return [f"RSI at {rsi:.0f} (oversold) - mean reversion BUY opportunity"]
        return [f"RSI at {rsi:.0f} - no extreme for mean reversion"]


# ── Strategy Registry ───────────────────────────────────────────

class StrategyRegistry:
    """Registry of all available strategies."""

    def __init__(self):
        self._strategies: Dict[str, Strategy] = {}

    def register(self, strategy: Strategy):
        self._strategies[strategy.name] = strategy
        logger.debug(f"[strategy] Registered: {strategy.name}")

    def get(self, name: str) -> Optional[Strategy]:
        return self._strategies.get(name)

    def list_all(self) -> List[Dict]:
        return [
            {"name": s.name, "description": s.description, "version": s.version}
            for s in self._strategies.values()
        ]

    def evaluate_all(self, symbol: str, market_data: Dict) -> List[Dict]:
        """Run all strategies and return sorted results."""
        results = []
        for name, strat in self._strategies.items():
            try:
                signal = strat.generate_signal(symbol, market_data)
                score = strat.score(symbol, market_data)
                explanation = strat.explain(symbol, market_data)
                results.append({
                    "strategy": name,
                    "description": strat.description,
                    "signal": signal,
                    "score": round(score, 1),
                    "explanation": explanation,
                })
            except Exception as e:
                logger.error(f"[strategy] {name} failed for {symbol}: {e}")
                results.append({
                    "strategy": name,
                    "signal": {"action": "ERROR", "confidence": 0},
                    "score": 0,
                    "explanation": [f"Strategy error: {e}"],
                })
        results.sort(key=lambda r: r["score"], reverse=True)
        return results

    def consensus(self, symbol: str, market_data: Dict) -> Dict:
        """
        Compute consensus across all strategies.
        Returns the majority action weighted by score.
        """
        results = self.evaluate_all(symbol, market_data)
        votes: Dict[str, float] = {}

        for r in results:
            action = r["signal"].get("action", "HOLD")
            score = r["score"]
            conf = r["signal"].get("confidence", 0.5)
            weight = score * conf
            votes[action] = votes.get(action, 0) + weight

        if not votes:
            return {"action": "HOLD", "confidence": 0.5, "agreement": 0, "votes": {}}

        best_action = max(votes, key=votes.get)
        total_weight = sum(votes.values())
        agreement = votes[best_action] / total_weight if total_weight > 0 else 0

        return {
            "action": best_action,
            "confidence": round(agreement, 3),
            "agreement": round(agreement, 3),
            "votes": {k: round(v, 1) for k, v in votes.items()},
            "strategy_count": len(results),
        }


# ── Global registry (pre-populated) ────────────────────────────

strategy_registry = StrategyRegistry()
strategy_registry.register(MLTrendStrategy())
strategy_registry.register(SmartScoreStrategy())
strategy_registry.register(MomentumStrategy())
strategy_registry.register(MeanReversionStrategy())
