"""
Base Broker Interface
All broker implementations should inherit from this
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime


class BaseBroker(ABC):
    """Base class for all broker integrations"""
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.connected = False
        self.name = ""
    
    @abstractmethod
    def test_connection(self) -> Dict:
        """Test connection to broker API"""
        pass
    
    @abstractmethod
    def get_account_balance(self) -> Dict:
        """Get account balance"""
        pass
    
    @abstractmethod
    def get_market_price(self, symbol: str) -> Dict:
        """Get current market price for a symbol"""
        pass
    
    @abstractmethod
    def place_paper_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET") -> Dict:
        """Place a paper trading order"""
        pass
    
    @abstractmethod
    def get_supported_symbols(self) -> List[str]:
        """Get list of supported trading symbols"""
        pass
    
    def get_status(self) -> Dict:
        """Get broker connection status"""
        return {
            "broker": self.name,
            "connected": self.connected,
            "has_api_key": bool(self.api_key),
            "timestamp": datetime.now().isoformat()
        }

