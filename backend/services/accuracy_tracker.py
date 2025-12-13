"""
Accuracy Tracking Service
Track prediction accuracy for ML models
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json
import os


class AccuracyTracker:
    """
    Track prediction accuracy for assets
    """
    
    def __init__(self):
        self.accuracy_file = os.path.join(
            os.path.dirname(__file__), "..", "accuracy_data.json"
        )
        self.accuracy_data = self._load_accuracy_data()
    
    def _load_accuracy_data(self) -> Dict:
        """Load accuracy data from file"""
        if os.path.exists(self.accuracy_file):
            try:
                with open(self.accuracy_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading accuracy data: {e}")
                return {}
        return {}
    
    def _save_accuracy_data(self):
        """Save accuracy data to file"""
        try:
            with open(self.accuracy_file, 'w', encoding='utf-8') as f:
                json.dump(self.accuracy_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving accuracy data: {e}")
    
    def record_prediction(
        self,
        asset_id: str,
        predicted_price: float,
        predicted_date: datetime,
        confidence: float
    ):
        """
        Record a prediction for later accuracy calculation
        
        Args:
            asset_id: Asset symbol
            predicted_price: Predicted price
            predicted_date: Date of prediction
            confidence: Prediction confidence
        """
        if asset_id not in self.accuracy_data:
            self.accuracy_data[asset_id] = {
                "predictions": [],
                "accuracy_history": []
            }
        
        self.accuracy_data[asset_id]["predictions"].append({
            "predicted_price": predicted_price,
            "predicted_date": predicted_date.isoformat(),
            "confidence": confidence,
            "recorded_at": datetime.now().isoformat()
        })
        
        self._save_accuracy_data()
    
    def record_actual_price(
        self,
        asset_id: str,
        actual_price: float,
        date: datetime
    ):
        """
        Record actual price to compare with predictions
        
        Args:
            asset_id: Asset symbol
            actual_price: Actual price
            date: Date of actual price
        """
        if asset_id not in self.accuracy_data:
            return
        
        # Find matching predictions
        predictions = self.accuracy_data[asset_id]["predictions"]
        for pred in predictions:
            pred_date = datetime.fromisoformat(pred["predicted_date"])
            # Match predictions within 1 day
            if abs((date - pred_date).days) <= 1:
                if "actual_price" not in pred:
                    pred["actual_price"] = actual_price
                    pred["actual_date"] = date.isoformat()
                    
                    # Calculate accuracy
                    error = abs(pred["predicted_price"] - actual_price)
                    error_pct = (error / actual_price * 100) if actual_price > 0 else 0
                    pred["error"] = error
                    pred["error_pct"] = error_pct
                    pred["accuracy"] = max(0, 100 - error_pct)
        
        self._save_accuracy_data()
    
    def get_accuracy(self, asset_id: Optional[str] = None) -> Dict:
        """
        Get accuracy statistics
        
        Args:
            asset_id: Optional asset ID to filter
        
        Returns:
            Accuracy statistics
        """
        if asset_id:
            if asset_id not in self.accuracy_data:
                return {
                    "asset_id": asset_id,
                    "total_predictions": 0,
                    "evaluated_predictions": 0,
                    "average_accuracy": 0.0,
                    "average_error_pct": 0.0
                }
            
            asset_data = self.accuracy_data[asset_id]
            predictions = asset_data["predictions"]
            evaluated = [p for p in predictions if "actual_price" in p]
            
            if not evaluated:
                return {
                    "asset_id": asset_id,
                    "total_predictions": len(predictions),
                    "evaluated_predictions": 0,
                    "average_accuracy": 0.0,
                    "average_error_pct": 0.0
                }
            
            avg_accuracy = sum(p.get("accuracy", 0) for p in evaluated) / len(evaluated)
            avg_error_pct = sum(p.get("error_pct", 0) for p in evaluated) / len(evaluated)
            
            return {
                "asset_id": asset_id,
                "total_predictions": len(predictions),
                "evaluated_predictions": len(evaluated),
                "average_accuracy": round(avg_accuracy, 2),
                "average_error_pct": round(avg_error_pct, 2),
                "recent_predictions": evaluated[-10:]  # Last 10
            }
        
        # Overall accuracy
        all_evaluated = []
        for asset_data in self.accuracy_data.values():
            evaluated = [p for p in asset_data["predictions"] if "actual_price" in p]
            all_evaluated.extend(evaluated)
        
        if not all_evaluated:
            return {
                "total_predictions": sum(len(d["predictions"]) for d in self.accuracy_data.values()),
                "evaluated_predictions": 0,
                "average_accuracy": 0.0,
                "average_error_pct": 0.0,
                "by_asset": {}
            }
        
        avg_accuracy = sum(p.get("accuracy", 0) for p in all_evaluated) / len(all_evaluated)
        avg_error_pct = sum(p.get("error_pct", 0) for p in all_evaluated) / len(all_evaluated)
        
        # By asset
        by_asset = {}
        for asset_id, asset_data in self.accuracy_data.items():
            evaluated = [p for p in asset_data["predictions"] if "actual_price" in p]
            if evaluated:
                by_asset[asset_id] = {
                    "evaluated": len(evaluated),
                    "avg_accuracy": sum(p.get("accuracy", 0) for p in evaluated) / len(evaluated)
                }
        
        return {
            "total_predictions": sum(len(d["predictions"]) for d in self.accuracy_data.values()),
            "evaluated_predictions": len(all_evaluated),
            "average_accuracy": round(avg_accuracy, 2),
            "average_error_pct": round(avg_error_pct, 2),
            "by_asset": by_asset
        }


# Global instance
accuracy_tracker = AccuracyTracker()

