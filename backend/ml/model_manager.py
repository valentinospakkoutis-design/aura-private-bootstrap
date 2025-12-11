"""
On-Device ML Model Manager
Manages ML models for on-device inference (MLX for Apple, ONNX for Android)
"""

from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum


class ModelType(str, Enum):
    """ML Model Types"""
    PREDICTOR = "predictor"  # Price prediction models
    SENTIMENT = "sentiment"  # Sentiment analysis
    CLASSIFIER = "classifier"  # Trading signal classification
    EMBEDDING = "embedding"  # Text embeddings


class ModelFormat(str, Enum):
    """Model formats"""
    MLX = "mlx"  # Apple MLX format
    ONNX = "onnx"  # ONNX format (Android/Cross-platform)
    TORCH = "torch"  # PyTorch format (for training)


class ModelStatus(str, Enum):
    """Model status"""
    TRAINING = "training"
    READY = "ready"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"


class ModelManager:
    """
    Manages on-device ML models
    Handles model loading, versioning, and inference preparation
    """
    
    def __init__(self):
        self.models: Dict[str, Dict] = {}
        self.model_registry: Dict[str, Dict] = {}
    
    def register_model(
        self,
        model_id: str,
        model_type: ModelType,
        format: ModelFormat,
        version: str = "1.0.0",
        description: str = ""
    ) -> Dict:
        """
        Register a new model
        
        Args:
            model_id: Unique model identifier
            model_type: Type of model
            format: Model format (MLX/ONNX)
            version: Model version
            description: Model description
            
        Returns:
            Model registration info
        """
        model_info = {
            "model_id": model_id,
            "type": model_type.value,
            "format": format.value,
            "version": version,
            "description": description,
            "status": ModelStatus.READY.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metrics": {
                "accuracy": None,
                "precision": None,
                "recall": None,
                "f1_score": None
            },
            "size_mb": None,
            "inference_time_ms": None
        }
        
        self.model_registry[model_id] = model_info
        return model_info
    
    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """Get model information"""
        return self.model_registry.get(model_id)
    
    def list_models(self, model_type: Optional[ModelType] = None) -> List[Dict]:
        """List all registered models"""
        models = list(self.model_registry.values())
        
        if model_type:
            models = [m for m in models if m["type"] == model_type.value]
        
        return models
    
    def update_model_metrics(
        self,
        model_id: str,
        accuracy: Optional[float] = None,
        precision: Optional[float] = None,
        recall: Optional[float] = None,
        f1_score: Optional[float] = None,
        size_mb: Optional[float] = None,
        inference_time_ms: Optional[float] = None
    ) -> bool:
        """Update model metrics"""
        if model_id not in self.model_registry:
            return False
        
        model = self.model_registry[model_id]
        
        if accuracy is not None:
            model["metrics"]["accuracy"] = accuracy
        if precision is not None:
            model["metrics"]["precision"] = precision
        if recall is not None:
            model["metrics"]["recall"] = recall
        if f1_score is not None:
            model["metrics"]["f1_score"] = f1_score
        if size_mb is not None:
            model["size_mb"] = size_mb
        if inference_time_ms is not None:
            model["inference_time_ms"] = inference_time_ms
        
        model["updated_at"] = datetime.now().isoformat()
        return True
    
    def get_model_status(self) -> Dict:
        """Get overall model management status"""
        total_models = len(self.model_registry)
        ready_models = len([m for m in self.model_registry.values() if m["status"] == ModelStatus.READY.value])
        deployed_models = len([m for m in self.model_registry.values() if m["status"] == ModelStatus.DEPLOYED.value])
        
        return {
            "total_models": total_models,
            "ready_models": ready_models,
            "deployed_models": deployed_models,
            "mlx_models": len([m for m in self.model_registry.values() if m["format"] == ModelFormat.MLX.value]),
            "onnx_models": len([m for m in self.model_registry.values() if m["format"] == ModelFormat.ONNX.value]),
            "timestamp": datetime.now().isoformat()
        }
    
    def prepare_for_deployment(self, model_id: str, platform: str) -> Dict:
        """
        Prepare model for on-device deployment
        
        Args:
            model_id: Model identifier
            platform: Target platform (ios/android)
            
        Returns:
            Deployment preparation info
        """
        if model_id not in self.model_registry:
            return {"error": "Model not found"}
        
        model = self.model_registry[model_id]
        
        if platform.lower() == "ios":
            # Prepare for MLX (Apple)
            return {
                "model_id": model_id,
                "platform": "ios",
                "format": "mlx",
                "status": "prepared",
                "instructions": [
                    "Convert model to MLX format",
                    "Optimize for Apple Silicon",
                    "Test on-device inference",
                    "Measure performance metrics"
                ],
                "estimated_size_mb": model.get("size_mb", 0),
                "timestamp": datetime.now().isoformat()
            }
        elif platform.lower() == "android":
            # Prepare for ONNX (Android)
            return {
                "model_id": model_id,
                "platform": "android",
                "format": "onnx",
                "status": "prepared",
                "instructions": [
                    "Convert model to ONNX format",
                    "Optimize for mobile inference",
                    "Test on-device inference",
                    "Measure performance metrics"
                ],
                "estimated_size_mb": model.get("size_mb", 0),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"error": f"Unsupported platform: {platform}"}


# Global instance
model_manager = ModelManager()

# Register default models
model_manager.register_model(
    model_id="precious_metals_predictor",
    model_type=ModelType.PREDICTOR,
    format=ModelFormat.MLX,
    version="1.0.0-alpha",
    description="Precious metals price prediction model"
)

model_manager.register_model(
    model_id="trading_signal_classifier",
    model_type=ModelType.CLASSIFIER,
    format=ModelFormat.ONNX,
    version="1.0.0-alpha",
    description="Trading signal classification model"
)

