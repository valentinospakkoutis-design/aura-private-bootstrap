"""
Notifications Service
Manages trade alerts, price alerts, and system notifications
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import json
import os


class NotificationType(str, Enum):
    """Notification types"""
    TRADE_EXECUTED = "trade_executed"
    PRICE_ALERT = "price_alert"
    AI_SIGNAL = "ai_signal"
    PORTFOLIO_UPDATE = "portfolio_update"
    RISK_ALERT = "risk_alert"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """Notification priority"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationsService:
    """
    Service for managing notifications
    Handles trade alerts, price alerts, and system notifications
    """
    
    def __init__(self):
        self.notifications_file = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "shared", "cms", "notifications.json"
        )
        self.notifications: List[Dict] = []
        self._load_notifications()
    
    def _load_notifications(self):
        """Load notifications from file"""
        try:
            if os.path.exists(self.notifications_file):
                with open(self.notifications_file, 'r', encoding='utf-8') as f:
                    self.notifications = json.load(f)
            else:
                self.notifications = []
        except Exception as e:
            print(f"Error loading notifications: {e}")
            self.notifications = []
    
    def _save_notifications(self):
        """Save notifications to file"""
        try:
            os.makedirs(os.path.dirname(self.notifications_file), exist_ok=True)
            # Keep only last 1000 notifications
            if len(self.notifications) > 1000:
                self.notifications = self.notifications[-1000:]
            
            with open(self.notifications_file, 'w', encoding='utf-8') as f:
                json.dump(self.notifications, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving notifications: {e}")
    
    def create_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[Dict] = None,
        read: bool = False
    ) -> Dict:
        """
        Create a new notification
        
        Args:
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            priority: Notification priority
            data: Additional data
            read: Whether notification is read
            
        Returns:
            Created notification
        """
        notification_id = f"notif_{int(datetime.now().timestamp() * 1000)}"
        
        notification = {
            "id": notification_id,
            "type": notification_type.value,
            "title": title,
            "message": message,
            "priority": priority.value,
            "data": data or {},
            "read": read,
            "created_at": datetime.now().isoformat(),
            "read_at": None
        }
        
        self.notifications.insert(0, notification)  # Add to beginning
        self._save_notifications()
        
        return notification
    
    def get_notifications(
        self,
        unread_only: bool = False,
        notification_type: Optional[NotificationType] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get notifications with filters"""
        filtered = self.notifications
        
        if unread_only:
            filtered = [n for n in filtered if not n.get("read", False)]
        
        if notification_type:
            filtered = [n for n in filtered if n.get("type") == notification_type.value]
        
        return filtered[:limit]
    
    def get_notification(self, notification_id: str) -> Optional[Dict]:
        """Get notification by ID"""
        for notification in self.notifications:
            if notification.get("id") == notification_id:
                return notification
        return None
    
    def mark_as_read(self, notification_id: str) -> bool:
        """Mark notification as read"""
        notification = self.get_notification(notification_id)
        if not notification:
            return False
        
        notification["read"] = True
        notification["read_at"] = datetime.now().isoformat()
        self._save_notifications()
        return True
    
    def mark_all_as_read(self) -> int:
        """Mark all notifications as read"""
        count = 0
        for notification in self.notifications:
            if not notification.get("read", False):
                notification["read"] = True
                notification["read_at"] = datetime.now().isoformat()
                count += 1
        
        if count > 0:
            self._save_notifications()
        
        return count
    
    def delete_notification(self, notification_id: str) -> bool:
        """Delete notification"""
        original_count = len(self.notifications)
        self.notifications = [n for n in self.notifications if n.get("id") != notification_id]
        
        if len(self.notifications) < original_count:
            self._save_notifications()
            return True
        return False
    
    def delete_all_read(self) -> int:
        """Delete all read notifications"""
        original_count = len(self.notifications)
        self.notifications = [n for n in self.notifications if not n.get("read", False)]
        
        deleted = original_count - len(self.notifications)
        if deleted > 0:
            self._save_notifications()
        
        return deleted
    
    def get_unread_count(self) -> int:
        """Get count of unread notifications"""
        return len([n for n in self.notifications if not n.get("read", False)])
    
    def get_notification_stats(self) -> Dict:
        """Get notification statistics"""
        total = len(self.notifications)
        unread = self.get_unread_count()
        read = total - unread
        
        by_type = {}
        for notification in self.notifications:
            ntype = notification.get("type", "unknown")
            by_type[ntype] = by_type.get(ntype, 0) + 1
        
        by_priority = {}
        for notification in self.notifications:
            priority = notification.get("priority", "medium")
            by_priority[priority] = by_priority.get(priority, 0) + 1
        
        return {
            "total": total,
            "unread": unread,
            "read": read,
            "by_type": by_type,
            "by_priority": by_priority,
            "timestamp": datetime.now().isoformat()
        }
    
    # Convenience methods for specific notification types
    def notify_trade_executed(self, symbol: str, side: str, quantity: float, price: float) -> Dict:
        """Create trade executed notification"""
        return self.create_notification(
            notification_type=NotificationType.TRADE_EXECUTED,
            title=f"Trade Executed: {side} {symbol}",
            message=f"{side} {quantity} {symbol} @ {price}",
            priority=NotificationPriority.HIGH,
            data={
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price
            }
        )
    
    def notify_price_alert(self, symbol: str, current_price: float, target_price: float, direction: str) -> Dict:
        """Create price alert notification"""
        return self.create_notification(
            notification_type=NotificationType.PRICE_ALERT,
            title=f"Price Alert: {symbol}",
            message=f"{symbol} reached {current_price} ({direction} {target_price})",
            priority=NotificationPriority.MEDIUM,
            data={
                "symbol": symbol,
                "current_price": current_price,
                "target_price": target_price,
                "direction": direction
            }
        )
    
    def notify_ai_signal(self, symbol: str, signal: str, confidence: float) -> Dict:
        """Create AI signal notification"""
        return self.create_notification(
            notification_type=NotificationType.AI_SIGNAL,
            title=f"AI Signal: {symbol}",
            message=f"{signal} signal for {symbol} (Confidence: {confidence}%)",
            priority=NotificationPriority.HIGH,
            data={
                "symbol": symbol,
                "signal": signal,
                "confidence": confidence
            }
        )
    
    def notify_risk_alert(self, message: str, risk_level: str) -> Dict:
        """Create risk alert notification"""
        priority_map = {
            "low": NotificationPriority.LOW,
            "medium": NotificationPriority.MEDIUM,
            "high": NotificationPriority.HIGH,
            "critical": NotificationPriority.URGENT
        }
        
        return self.create_notification(
            notification_type=NotificationType.RISK_ALERT,
            title="Risk Alert",
            message=message,
            priority=priority_map.get(risk_level, NotificationPriority.MEDIUM),
            data={"risk_level": risk_level}
        )


# Global instance
notifications_service = NotificationsService()

