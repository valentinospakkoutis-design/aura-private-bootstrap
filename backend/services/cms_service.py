"""
Simple CMS Service for AURA
Content Management for Quotes, News, and other content
"""

from typing import List, Dict, Optional
from datetime import datetime
import json
import os


class CMSService:
    """Simple CMS Service for managing content"""
    
    def __init__(self):
        # Get the project root directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        
        self.quotes_path = os.path.join(project_root, "shared", "quotes.json")
        self.content_dir = os.path.join(project_root, "shared", "cms")
        
        # Ensure directories exist
        os.makedirs(self.content_dir, exist_ok=True)
        
        # Ensure quotes.json exists
        if not os.path.exists(self.quotes_path):
            # Create empty quotes file
            with open(self.quotes_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    # ========================================================================
    # QUOTES MANAGEMENT
    # ========================================================================
    
    def get_all_quotes(self) -> List[Dict]:
        """Get all quotes"""
        try:
            with open(self.quotes_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Remove comments
                content = '\n'.join(
                    line for line in content.split('\n') 
                    if not line.strip().startswith('//')
                )
                return json.loads(content)
        except Exception as e:
            print(f"Error loading quotes: {e}")
            return []
    
    def add_quote(self, quote: Dict) -> Dict:
        """Add a new quote"""
        quotes = self.get_all_quotes()
        
        # Add ID and timestamp
        new_quote = {
            "id": len(quotes) + 1,
            "el": quote.get("el", ""),
            "en": quote.get("en", ""),
            "author": quote.get("author", ""),
            "category": quote.get("category", "general"),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        quotes.append(new_quote)
        self._save_quotes(quotes)
        
        return new_quote
    
    def update_quote(self, quote_id: int, quote: Dict) -> Optional[Dict]:
        """Update a quote"""
        quotes = self.get_all_quotes()
        
        for i, q in enumerate(quotes):
            if q.get("id") == quote_id:
                quotes[i].update({
                    "el": quote.get("el", quotes[i].get("el", "")),
                    "en": quote.get("en", quotes[i].get("en", "")),
                    "author": quote.get("author", quotes[i].get("author", "")),
                    "category": quote.get("category", quotes[i].get("category", "general")),
                    "updated_at": datetime.now().isoformat()
                })
                self._save_quotes(quotes)
                return quotes[i]
        
        return None
    
    def delete_quote(self, quote_id: int) -> bool:
        """Delete a quote"""
        quotes = self.get_all_quotes()
        original_count = len(quotes)
        
        quotes = [q for q in quotes if q.get("id") != quote_id]
        
        if len(quotes) < original_count:
            self._save_quotes(quotes)
            return True
        
        return False
    
    def get_quote_by_id(self, quote_id: int) -> Optional[Dict]:
        """Get quote by ID"""
        quotes = self.get_all_quotes()
        for quote in quotes:
            if quote.get("id") == quote_id:
                return quote
        return None
    
    def _save_quotes(self, quotes: List[Dict]):
        """Save quotes to file"""
        try:
            with open(self.quotes_path, 'w', encoding='utf-8') as f:
                json.dump(quotes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving quotes: {e}")
            raise
    
    # ========================================================================
    # NEWS/CONTENT MANAGEMENT
    # ========================================================================
    
    def get_news(self) -> List[Dict]:
        """Get all news articles"""
        news_path = os.path.join(self.content_dir, "news.json")
        
        try:
            if os.path.exists(news_path):
                with open(news_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error loading news: {e}")
            return []
    
    def add_news(self, news: Dict) -> Dict:
        """Add a new news article"""
        news_list = self.get_news()
        
        new_article = {
            "id": len(news_list) + 1,
            "title": news.get("title", ""),
            "content": news.get("content", ""),
            "summary": news.get("summary", ""),
            "image_url": news.get("image_url", ""),
            "category": news.get("category", "general"),
            "published": news.get("published", False),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        news_list.append(new_article)
        self._save_news(news_list)
        
        return new_article
    
    def _save_news(self, news: List[Dict]):
        """Save news to file"""
        news_path = os.path.join(self.content_dir, "news.json")
        try:
            with open(news_path, 'w', encoding='utf-8') as f:
                json.dump(news, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving news: {e}")
            raise
    
    # ========================================================================
    # SETTINGS MANAGEMENT
    # ========================================================================
    
    def get_settings(self) -> Dict:
        """Get CMS settings"""
        settings_path = os.path.join(self.content_dir, "settings.json")
        
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # Default settings
            default_settings = {
                "app_name": "AURA",
                "app_tagline": "Το μόνο χρηματοοικονομικό ον που μαθαίνει εσένα καλύτερα από σένα.",
                "maintenance_mode": False,
                "features": {
                    "paper_trading": True,
                    "ai_predictions": True,
                    "voice_features": False
                }
            }
            
            self._save_settings(default_settings)
            return default_settings
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {}
    
    def update_settings(self, settings: Dict) -> Dict:
        """Update CMS settings"""
        current_settings = self.get_settings()
        current_settings.update(settings)
        current_settings["updated_at"] = datetime.now().isoformat()
        
        self._save_settings(current_settings)
        return current_settings
    
    def _save_settings(self, settings: Dict):
        """Save settings to file"""
        settings_path = os.path.join(self.content_dir, "settings.json")
        try:
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
            raise


# Global instance
cms_service = CMSService()

