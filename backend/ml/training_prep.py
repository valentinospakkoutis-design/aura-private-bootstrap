"""
ML Training Preparation
Prepares data and configurations for model training
"""

from typing import Dict, List, Optional
from datetime import datetime
import json


class TrainingPrep:
    """
    Prepares data and configurations for ML model training
    """
    
    def __init__(self):
        self.training_configs: Dict[str, Dict] = {}
    
    def create_training_config(
        self,
        config_name: str,
        model_type: str,
        dataset_path: str,
        hyperparameters: Dict,
        target_metrics: Dict
    ) -> Dict:
        """
        Create training configuration
        
        Args:
            config_name: Configuration name
            model_type: Type of model to train
            dataset_path: Path to training dataset
            hyperparameters: Model hyperparameters
            target_metrics: Target performance metrics
            
        Returns:
            Training configuration
        """
        config = {
            "config_name": config_name,
            "model_type": model_type,
            "dataset_path": dataset_path,
            "hyperparameters": hyperparameters,
            "target_metrics": target_metrics,
            "created_at": datetime.now().isoformat(),
            "status": "ready",
            "training_history": []
        }
        
        self.training_configs[config_name] = config
        return config
    
    def get_training_config(self, config_name: str) -> Optional[Dict]:
        """Get training configuration"""
        return self.training_configs.get(config_name)
    
    def list_training_configs(self) -> List[Dict]:
        """List all training configurations"""
        return list(self.training_configs.values())
    
    def prepare_dataset_info(self, dataset_type: str) -> Dict:
        """
        Get dataset preparation info
        
        Args:
            dataset_type: Type of dataset (prices, sentiment, signals)
            
        Returns:
            Dataset preparation information
        """
        dataset_templates = {
            "prices": {
                "description": "Price prediction dataset",
                "required_features": [
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "symbol"
                ],
                "target": "future_price",
                "preprocessing_steps": [
                    "Normalize prices",
                    "Create time windows",
                    "Handle missing values",
                    "Feature engineering"
                ],
                "estimated_size_mb": 50
            },
            "sentiment": {
                "description": "Sentiment analysis dataset",
                "required_features": [
                    "text",
                    "source",
                    "timestamp",
                    "symbol"
                ],
                "target": "sentiment_label",
                "preprocessing_steps": [
                    "Text cleaning",
                    "Tokenization",
                    "Embedding",
                    "Label encoding"
                ],
                "estimated_size_mb": 20
            },
            "signals": {
                "description": "Trading signal dataset",
                "required_features": [
                    "price_features",
                    "technical_indicators",
                    "market_conditions"
                ],
                "target": "signal_class",
                "preprocessing_steps": [
                    "Feature scaling",
                    "Categorical encoding",
                    "Balance classes",
                    "Split train/val/test"
                ],
                "estimated_size_mb": 30
            }
        }
        
        return dataset_templates.get(dataset_type, {
            "error": f"Unknown dataset type: {dataset_type}"
        })
    
    def get_training_status(self) -> Dict:
        """Get overall training preparation status"""
        return {
            "total_configs": len(self.training_configs),
            "ready_configs": len([c for c in self.training_configs.values() if c["status"] == "ready"]),
            "supported_datasets": ["prices", "sentiment", "signals"],
            "timestamp": datetime.now().isoformat()
        }


# Global instance
training_prep = TrainingPrep()

