"""
Scheduler Service
Manages scheduled tasks like morning briefings
"""

from typing import Dict, List, Optional
from datetime import datetime, time, timedelta
from enum import Enum
import json
import os


class ScheduleStatus(str, Enum):
    """Schedule status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class SchedulerService:
    """
    Service for managing scheduled tasks
    Handles morning briefings and other scheduled events
    """
    
    def __init__(self):
        self.schedules_file = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "shared", "cms", "schedules.json"
        )
        self.schedules: List[Dict] = []
        self._load_schedules()
    
    def _load_schedules(self):
        """Load schedules from file"""
        try:
            if os.path.exists(self.schedules_file):
                with open(self.schedules_file, 'r', encoding='utf-8') as f:
                    self.schedules = json.load(f)
            else:
                self.schedules = []
        except Exception as e:
            print(f"Error loading schedules: {e}")
            self.schedules = []
    
    def _save_schedules(self):
        """Save schedules to file"""
        try:
            os.makedirs(os.path.dirname(self.schedules_file), exist_ok=True)
            with open(self.schedules_file, 'w', encoding='utf-8') as f:
                json.dump(self.schedules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving schedules: {e}")
    
    def create_schedule(
        self,
        schedule_type: str,
        time_str: str,  # "HH:MM" format
        days: List[str],  # ["monday", "tuesday", ...]
        enabled: bool = True,
        config: Optional[Dict] = None
    ) -> Dict:
        """
        Create a new schedule
        
        Args:
            schedule_type: Type of schedule (e.g., "morning_briefing")
            time_str: Time in "HH:MM" format
            days: List of days (e.g., ["monday", "tuesday"])
            enabled: Whether schedule is enabled
            config: Additional configuration
            
        Returns:
            Created schedule
        """
        schedule_id = f"schedule_{int(datetime.now().timestamp() * 1000)}"
        
        schedule = {
            "id": schedule_id,
            "type": schedule_type,
            "time": time_str,
            "days": days,
            "enabled": enabled,
            "status": ScheduleStatus.ACTIVE.value if enabled else ScheduleStatus.PAUSED.value,
            "config": config or {},
            "last_executed": None,
            "next_execution": self._calculate_next_execution(time_str, days),
            "execution_count": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.schedules.append(schedule)
        self._save_schedules()
        
        return schedule
    
    def _calculate_next_execution(self, time_str: str, days: List[str]) -> Optional[str]:
        """Calculate next execution time"""
        try:
            hour, minute = map(int, time_str.split(':'))
            schedule_time = time(hour, minute)
            now = datetime.now()
            current_time = now.time()
            
            # Get day names
            day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
            # Find next matching day
            for i in range(7):
                check_date = now + timedelta(days=i)
                day_name = day_names[check_date.weekday()].lower()
                
                if day_name in [d.lower() for d in days]:
                    # Check if time has passed today
                    if i == 0 and current_time >= schedule_time:
                        # Time passed today, check next occurrence
                        continue
                    
                    # Calculate datetime
                    execution_datetime = datetime.combine(check_date.date(), schedule_time)
                    if i == 0 and current_time < schedule_time:
                        # Today, but time hasn't passed yet
                        return execution_datetime.isoformat()
                    elif i > 0:
                        # Future day
                        return execution_datetime.isoformat()
            
            # If no match found in next 7 days, return None
            return None
        except Exception as e:
            print(f"Error calculating next execution: {e}")
            return None
    
    def get_schedules(self, schedule_type: Optional[str] = None) -> List[Dict]:
        """Get all schedules, optionally filtered by type"""
        if schedule_type:
            return [s for s in self.schedules if s.get("type") == schedule_type]
        return self.schedules
    
    def get_schedule(self, schedule_id: str) -> Optional[Dict]:
        """Get schedule by ID"""
        for schedule in self.schedules:
            if schedule.get("id") == schedule_id:
                return schedule
        return None
    
    def update_schedule(
        self,
        schedule_id: str,
        time_str: Optional[str] = None,
        days: Optional[List[str]] = None,
        enabled: Optional[bool] = None,
        config: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Update schedule"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        
        if time_str is not None:
            schedule["time"] = time_str
        if days is not None:
            schedule["days"] = days
        if enabled is not None:
            schedule["enabled"] = enabled
            schedule["status"] = ScheduleStatus.ACTIVE.value if enabled else ScheduleStatus.PAUSED.value
        if config is not None:
            schedule["config"].update(config)
        
        schedule["next_execution"] = self._calculate_next_execution(
            schedule["time"],
            schedule["days"]
        )
        schedule["updated_at"] = datetime.now().isoformat()
        
        self._save_schedules()
        return schedule
    
    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete schedule"""
        original_count = len(self.schedules)
        self.schedules = [s for s in self.schedules if s.get("id") != schedule_id]
        
        if len(self.schedules) < original_count:
            self._save_schedules()
            return True
        return False
    
    def get_upcoming_schedules(self, limit: int = 10) -> List[Dict]:
        """Get upcoming scheduled executions"""
        now = datetime.now()
        upcoming = []
        
        for schedule in self.schedules:
            if not schedule.get("enabled"):
                continue
            
            next_exec = schedule.get("next_execution")
            if next_exec:
                try:
                    exec_datetime = datetime.fromisoformat(next_exec)
                    if exec_datetime > now:
                        upcoming.append({
                            **schedule,
                            "minutes_until": int((exec_datetime - now).total_seconds() / 60)
                        })
                except:
                    pass
        
        # Sort by next execution time
        upcoming.sort(key=lambda x: x.get("next_execution", ""))
        return upcoming[:limit]
    
    def mark_executed(self, schedule_id: str) -> bool:
        """Mark schedule as executed"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return False
        
        schedule["last_executed"] = datetime.now().isoformat()
        schedule["execution_count"] = schedule.get("execution_count", 0) + 1
        schedule["next_execution"] = self._calculate_next_execution(
            schedule["time"],
            schedule["days"]
        )
        schedule["updated_at"] = datetime.now().isoformat()
        
        self._save_schedules()
        return True


# Global instance
scheduler_service = SchedulerService()

