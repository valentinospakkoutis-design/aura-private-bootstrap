"""
Advanced Analytics Service
Tracks and analyzes trading performance, metrics, and insights
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics


class AnalyticsService:
    """
    Service for advanced trading analytics
    Tracks performance, metrics, and provides insights
    """
    
    def __init__(self):
        self.metrics_cache: Dict[str, Dict] = {}
    
    def calculate_performance_metrics(
        self,
        trades: List[Dict],
        portfolio_value: float,
        initial_balance: float
    ) -> Dict:
        """
        Calculate comprehensive performance metrics
        
        Args:
            trades: List of trade history
            portfolio_value: Current portfolio value
            initial_balance: Starting balance
            
        Returns:
            Performance metrics
        """
        if not trades:
            return self._empty_metrics()
        
        # Separate buy and sell trades
        buy_trades = [t for t in trades if t.get("side") == "BUY"]
        sell_trades = [t for t in trades if t.get("side") == "SELL"]
        
        # Calculate total P/L
        total_pnl = portfolio_value - initial_balance
        total_pnl_percent = (total_pnl / initial_balance * 100) if initial_balance > 0 else 0
        
        # Calculate win rate (simplified - would need position tracking)
        winning_trades = len([t for t in trades if t.get("pnl", 0) > 0])
        total_closed_trades = len(sell_trades)
        win_rate = (winning_trades / total_closed_trades * 100) if total_closed_trades > 0 else 0
        
        # Calculate average trade size
        trade_sizes = [t.get("quantity", 0) * t.get("price", 0) for t in trades]
        avg_trade_size = statistics.mean(trade_sizes) if trade_sizes else 0
        
        # Calculate Sharpe ratio (simplified)
        returns = [t.get("pnl", 0) / initial_balance * 100 for t in trades if t.get("pnl") is not None]
        sharpe_ratio = self._calculate_sharpe_ratio(returns) if len(returns) > 1 else 0
        
        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(trades, initial_balance)
        
        # Calculate profit factor
        profits = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0]
        losses = [abs(t.get("pnl", 0)) for t in trades if t.get("pnl", 0) < 0]
        profit_factor = (sum(profits) / sum(losses)) if sum(losses) > 0 else 0
        
        # Calculate average win/loss
        avg_win = statistics.mean(profits) if profits else 0
        avg_loss = statistics.mean(losses) if losses else 0
        
        # Calculate expectancy
        expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)
        
        return {
            "total_trades": len(trades),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_percent": round(total_pnl_percent, 2),
            "win_rate": round(win_rate, 2),
            "winning_trades": winning_trades,
            "losing_trades": total_closed_trades - winning_trades,
            "avg_trade_size": round(avg_trade_size, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_percent": round((max_drawdown / initial_balance * 100) if initial_balance > 0 else 0, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "expectancy": round(expectancy, 2),
            "roi": round(total_pnl_percent, 2),
            "timestamp": datetime.now().isoformat()
        }
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        
        mean_return = statistics.mean(returns)
        std_dev = statistics.stdev(returns) if len(returns) > 1 else 0
        
        if std_dev == 0:
            return 0.0
        
        return (mean_return - risk_free_rate) / std_dev
    
    def _calculate_max_drawdown(self, trades: List[Dict], initial_balance: float) -> float:
        """Calculate maximum drawdown"""
        if not trades:
            return 0.0
        
        # Simplified - would need full equity curve
        # For now, return 0
        return 0.0
    
    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure"""
        return {
            "total_trades": 0,
            "buy_trades": 0,
            "sell_trades": 0,
            "total_pnl": 0.0,
            "total_pnl_percent": 0.0,
            "win_rate": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_trade_size": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_percent": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "roi": 0.0,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_performance_by_period(
        self,
        trades: List[Dict],
        period: str = "daily"  # daily, weekly, monthly
    ) -> Dict:
        """
        Get performance metrics by time period
        """
        if not trades:
            return {}
        
        period_data = defaultdict(lambda: {"trades": [], "pnl": 0.0})
        
        for trade in trades:
            trade_date = datetime.fromisoformat(trade.get("executed_at", datetime.now().isoformat()))
            
            if period == "daily":
                key = trade_date.date().isoformat()
            elif period == "weekly":
                # Get week start (Monday)
                week_start = trade_date - timedelta(days=trade_date.weekday())
                key = week_start.date().isoformat()
            else:  # monthly
                key = f"{trade_date.year}-{trade_date.month:02d}"
            
            period_data[key]["trades"].append(trade)
            period_data[key]["pnl"] += trade.get("pnl", 0.0)
        
        # Convert to list
        result = []
        for key, data in sorted(period_data.items()):
            result.append({
                "period": key,
                "trades_count": len(data["trades"]),
                "total_pnl": round(data["pnl"], 2),
                "avg_pnl": round(data["pnl"] / len(data["trades"]) if data["trades"] else 0, 2)
            })
        
        return {
            "period": period,
            "data": result,
            "total_periods": len(result),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_symbol_performance(self, trades: List[Dict]) -> List[Dict]:
        """Get performance breakdown by symbol"""
        symbol_data = defaultdict(lambda: {
            "trades": [],
            "total_pnl": 0.0,
            "buy_count": 0,
            "sell_count": 0
        })
        
        for trade in trades:
            symbol = trade.get("symbol", "UNKNOWN")
            symbol_data[symbol]["trades"].append(trade)
            symbol_data[symbol]["total_pnl"] += trade.get("pnl", 0.0)
            
            if trade.get("side") == "BUY":
                symbol_data[symbol]["buy_count"] += 1
            else:
                symbol_data[symbol]["sell_count"] += 1
        
        result = []
        for symbol, data in symbol_data.items():
            result.append({
                "symbol": symbol,
                "total_trades": len(data["trades"]),
                "buy_trades": data["buy_count"],
                "sell_trades": data["sell_count"],
                "total_pnl": round(data["total_pnl"], 2),
                "avg_pnl": round(data["total_pnl"] / len(data["trades"]) if data["trades"] else 0, 2)
            })
        
        # Sort by total P/L
        result.sort(key=lambda x: x["total_pnl"], reverse=True)
        
        return result
    
    def get_trading_insights(self, metrics: Dict) -> List[str]:
        """Generate trading insights based on metrics"""
        insights = []
        
        if metrics["win_rate"] > 60:
            insights.append("✅ Excellent win rate! Your strategy is working well.")
        elif metrics["win_rate"] < 40:
            insights.append("⚠️ Low win rate. Consider reviewing your strategy.")
        
        if metrics["profit_factor"] > 2.0:
            insights.append("✅ Strong profit factor. Your wins significantly outweigh losses.")
        elif metrics["profit_factor"] < 1.0:
            insights.append("⚠️ Profit factor below 1.0. Losses exceed wins.")
        
        if metrics["sharpe_ratio"] > 1.0:
            insights.append("✅ Good risk-adjusted returns (Sharpe ratio).")
        elif metrics["sharpe_ratio"] < 0.5:
            insights.append("⚠️ Low risk-adjusted returns. Consider reducing risk.")
        
        if metrics["max_drawdown_percent"] > 20:
            insights.append("⚠️ High drawdown detected. Consider tighter risk management.")
        
        if metrics["expectancy"] > 0:
            insights.append("✅ Positive expectancy. Strategy is profitable on average.")
        else:
            insights.append("⚠️ Negative expectancy. Strategy needs improvement.")
        
        if not insights:
            insights.append("📊 Keep trading and collecting data for better insights.")
        
        return insights


# Global instance
analytics_service = AnalyticsService()

