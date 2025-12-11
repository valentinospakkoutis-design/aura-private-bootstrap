"""
Voice Briefing Service
Generates morning briefings with market news, AI predictions, and trading insights
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import random


class VoiceBriefingService:
    """
    Service for generating morning voice briefings
    Combines market data, AI predictions, and trading insights
    """
    
    def __init__(self):
        self.greetings = [
            "Καλημέρα! Είμαι το AURA.",
            "Καλημέρα! Έτοιμος για trading;",
            "Καλημέρα! Ας δούμε τι έχει το market σήμερα.",
        ]
        
        self.closings = [
            "Καλή επιτυχία στο trading σήμερα!",
            "Καλή ημέρα και καλά trades!",
            "Μέχρι το επόμενο briefing!",
        ]
    
    def generate_briefing(
        self,
        include_market_news: bool = True,
        include_ai_predictions: bool = True,
        include_portfolio: bool = True,
        max_duration_seconds: int = 90
    ) -> Dict:
        """
        Generate morning briefing content
        
        Args:
            include_market_news: Include market news (3 items)
            include_ai_predictions: Include AI predictions
            include_portfolio: Include portfolio summary
            max_duration_seconds: Maximum briefing duration
            
        Returns:
            Briefing content with text and metadata
        """
        sections = []
        total_duration = 0
        
        # Greeting
        greeting = random.choice(self.greetings)
        sections.append({
            "type": "greeting",
            "text": greeting,
            "duration_seconds": 3
        })
        total_duration += 3
        
        # Market News (3 items, ~30 seconds)
        if include_market_news and total_duration < max_duration_seconds:
            news_items = self._generate_market_news(3)
            for news in news_items:
                if total_duration + news["duration_seconds"] <= max_duration_seconds:
                    sections.append(news)
                    total_duration += news["duration_seconds"]
        
        # AI Predictions (~20 seconds)
        if include_ai_predictions and total_duration < max_duration_seconds:
            prediction = self._generate_ai_prediction()
            if total_duration + prediction["duration_seconds"] <= max_duration_seconds:
                sections.append(prediction)
                total_duration += prediction["duration_seconds"]
        
        # Portfolio Summary (~15 seconds)
        if include_portfolio and total_duration < max_duration_seconds:
            portfolio = self._generate_portfolio_summary()
            if total_duration + portfolio["duration_seconds"] <= max_duration_seconds:
                sections.append(portfolio)
                total_duration += portfolio["duration_seconds"]
        
        # Closing
        closing = random.choice(self.closings)
        sections.append({
            "type": "closing",
            "text": closing,
            "duration_seconds": 2
        })
        total_duration += 2
        
        # Combine all text
        full_text = " ".join([section["text"] for section in sections])
        
        return {
            "briefing_id": f"briefing_{int(datetime.now().timestamp())}",
            "date": datetime.now().date().isoformat(),
            "time": datetime.now().time().isoformat(),
            "sections": sections,
            "full_text": full_text,
            "duration_seconds": total_duration,
            "word_count": len(full_text.split()),
            "timestamp": datetime.now().isoformat()
        }
    
    def _generate_market_news(self, count: int = 3) -> List[Dict]:
        """Generate market news items"""
        news_templates = [
            {
                "text": "Στο χρυσό, η τιμή κινείται στα {price} δολάρια. {trend} trend σήμερα.",
                "duration_seconds": 8
            },
            {
                "text": "Το Bitcoin έχει {change}% αλλαγή τις τελευταίες 24 ώρες. {sentiment}.",
                "duration_seconds": 7
            },
            {
                "text": "Οι αγορές εμφανίζουν {volatility}. Προσοχή στα {asset}.",
                "duration_seconds": 6
            },
            {
                "text": "Νέα από το {market}: {news}.",
                "duration_seconds": 9
            },
        ]
        
        news_items = []
        for i in range(count):
            template = random.choice(news_templates)
            
            # Fill template with random data
            text = template["text"].format(
                price=random.randint(2000, 2100),
                trend=random.choice(["Bullish", "Bearish", "Sideways"]),
                change=round(random.uniform(-5, 5), 2),
                sentiment=random.choice(["Θετικό", "Αρνητικό", "Ουδέτερο"]),
                volatility=random.choice(["υψηλή", "μέτρια", "χαμηλή"]),
                asset=random.choice(["χρυσό", "Bitcoin", "άργυρο"]),
                market=random.choice(["NYSE", "NASDAQ", "Crypto"]),
                news=random.choice([
                    "Αύξηση των συναλλαγών",
                    "Νέα regulations",
                    "Institutional interest"
                ])
            )
            
            news_items.append({
                "type": "news",
                "text": text,
                "duration_seconds": template["duration_seconds"],
                "priority": "high" if i == 0 else "medium"
            })
        
        return news_items
    
    def _generate_ai_prediction(self) -> Dict:
        """Generate AI prediction summary"""
        metals = ["χρυσό", "άργυρο", "πλατίνα", "παλλάδιο"]
        metal = random.choice(metals)
        direction = random.choice(["αύξηση", "μείωση"])
        percent = round(random.uniform(1, 5), 1)
        confidence = random.randint(70, 85)
        
        text = f"Η AI πρόβλεψη για το {metal}: {direction} {percent}% την επόμενη εβδομάδα. Confidence: {confidence}%."
        
        return {
            "type": "prediction",
            "text": text,
            "duration_seconds": 12,
            "metal": metal,
            "direction": direction,
            "confidence": confidence
        }
    
    def _generate_portfolio_summary(self) -> Dict:
        """Generate portfolio summary"""
        pnl = round(random.uniform(-100, 500), 2)
        pnl_sign = "+" if pnl >= 0 else ""
        positions = random.randint(0, 5)
        
        if positions > 0:
            text = f"Το portfolio σας: {pnl_sign}{pnl} ευρώ P/L. {positions} ενεργές θέσεις."
        else:
            text = "Δεν έχετε ενεργές θέσεις αυτή τη στιγμή."
        
        return {
            "type": "portfolio",
            "text": text,
            "duration_seconds": 8,
            "pnl": pnl,
            "positions": positions
        }
    
    def get_briefing_history(self, days: int = 7) -> List[Dict]:
        """Get briefing history"""
        # In production, this would fetch from database
        # For now, return empty list
        return []
    
    def get_briefing_by_id(self, briefing_id: str) -> Optional[Dict]:
        """Get specific briefing by ID"""
        # In production, this would fetch from database
        return None


# Global instance
voice_briefing_service = VoiceBriefingService()

