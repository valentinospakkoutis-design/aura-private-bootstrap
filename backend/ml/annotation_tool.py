"""
Annotation Tool for ML Training Data
Εργαλείο για annotation/labeling training data
"""

import os
import json
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class AnnotationStatus(str, Enum):
    """Annotation status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


class AnnotationType(str, Enum):
    """Types of annotations"""
    PRICE_PREDICTION = "price_prediction"
    TRADING_SIGNAL = "trading_signal"
    SENTIMENT = "sentiment"
    NEWS_CLASSIFICATION = "news_classification"
    MARKET_REGIME = "market_regime"


class AnnotationTool:
    """
    Tool for annotating ML training data
    Supports multiple annotation types and workflows
    """
    
    def __init__(self, annotations_dir: str = "annotations"):
        """
        Initialize annotation tool
        
        Args:
            annotations_dir: Directory για αποθήκευση annotations
        """
        self.annotations_dir = annotations_dir
        os.makedirs(annotations_dir, exist_ok=True)
        
        self.annotations_file = os.path.join(annotations_dir, "annotations.json")
        self.annotations = self._load_annotations()
    
    def _load_annotations(self) -> Dict:
        """Load existing annotations"""
        if os.path.exists(self.annotations_file):
            try:
                with open(self.annotations_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[-] Error loading annotations: {e}")
                return {"annotations": [], "metadata": {}}
        return {"annotations": [], "metadata": {}}
    
    def _save_annotations(self):
        """Save annotations to file"""
        try:
            with open(self.annotations_file, 'w', encoding='utf-8') as f:
                json.dump(self.annotations, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[-] Error saving annotations: {e}")
            return False
    
    def create_annotation_task(
        self,
        annotation_type: AnnotationType,
        data_id: str,
        data: Dict[str, Any],
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create new annotation task
        
        Args:
            annotation_type: Type of annotation
            data_id: Unique identifier for data point
            data: Data to annotate
            metadata: Additional metadata
            
        Returns:
            Annotation task info
        """
        annotation = {
            "id": f"{annotation_type.value}_{data_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "annotation_type": annotation_type.value,
            "data_id": data_id,
            "data": data,
            "status": AnnotationStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "annotator": None,
            "labels": {},
            "confidence": None,
            "notes": "",
            "metadata": metadata or {}
        }
        
        self.annotations["annotations"].append(annotation)
        self._save_annotations()
        
        return annotation
    
    def get_annotation(self, annotation_id: str) -> Optional[Dict]:
        """Get annotation by ID"""
        for ann in self.annotations["annotations"]:
            if ann["id"] == annotation_id:
                return ann
        return None
    
    def update_annotation(
        self,
        annotation_id: str,
        labels: Optional[Dict] = None,
        status: Optional[AnnotationStatus] = None,
        confidence: Optional[float] = None,
        notes: Optional[str] = None,
        annotator: Optional[str] = None
    ) -> bool:
        """
        Update annotation
        
        Args:
            annotation_id: Annotation ID
            labels: Annotation labels
            status: New status
            confidence: Confidence score
            notes: Notes
            annotator: Annotator name
            
        Returns:
            True if successful
        """
        annotation = self.get_annotation(annotation_id)
        if not annotation:
            return False
        
        if labels is not None:
            annotation["labels"].update(labels)
        if status is not None:
            annotation["status"] = status.value
        if confidence is not None:
            annotation["confidence"] = confidence
        if notes is not None:
            annotation["notes"] = notes
        if annotator is not None:
            annotation["annotator"] = annotator
        
        annotation["updated_at"] = datetime.now().isoformat()
        self._save_annotations()
        
        return True
    
    def get_pending_annotations(
        self,
        annotation_type: Optional[AnnotationType] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get pending annotations
        
        Args:
            annotation_type: Filter by type
            limit: Max number to return
            
        Returns:
            List of pending annotations
        """
        pending = [
            ann for ann in self.annotations["annotations"]
            if ann["status"] == AnnotationStatus.PENDING.value
        ]
        
        if annotation_type:
            pending = [
                ann for ann in pending
                if ann["annotation_type"] == annotation_type.value
            ]
        
        return pending[:limit]
    
    def get_statistics(self) -> Dict:
        """Get annotation statistics"""
        total = len(self.annotations["annotations"])
        
        by_status = {}
        by_type = {}
        
        for ann in self.annotations["annotations"]:
            status = ann["status"]
            ann_type = ann["annotation_type"]
            
            by_status[status] = by_status.get(status, 0) + 1
            by_type[ann_type] = by_type.get(ann_type, 0) + 1
        
        return {
            "total_annotations": total,
            "by_status": by_status,
            "by_type": by_type,
            "pending_count": by_status.get(AnnotationStatus.PENDING.value, 0),
            "completed_count": by_status.get(AnnotationStatus.COMPLETED.value, 0),
            "timestamp": datetime.now().isoformat()
        }
    
    def export_annotations(
        self,
        output_path: str,
        annotation_type: Optional[AnnotationType] = None,
        status: Optional[AnnotationStatus] = None,
        format: str = "json"
    ) -> bool:
        """
        Export annotations to file
        
        Args:
            output_path: Output file path
            annotation_type: Filter by type
            status: Filter by status
            format: Export format (json, csv)
            
        Returns:
            True if successful
        """
        filtered = self.annotations["annotations"]
        
        if annotation_type:
            filtered = [
                ann for ann in filtered
                if ann["annotation_type"] == annotation_type.value
            ]
        
        if status:
            filtered = [
                ann for ann in filtered
                if ann["status"] == status.value
            ]
        
        try:
            if format == "json":
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump({"annotations": filtered}, f, indent=2, ensure_ascii=False)
            elif format == "csv":
                # Flatten annotations for CSV
                rows = []
                for ann in filtered:
                    row = {
                        "id": ann["id"],
                        "annotation_type": ann["annotation_type"],
                        "data_id": ann["data_id"],
                        "status": ann["status"],
                        "annotator": ann.get("annotator", ""),
                        "confidence": ann.get("confidence", ""),
                        "created_at": ann["created_at"],
                        "updated_at": ann["updated_at"]
                    }
                    # Add labels as columns
                    for key, value in ann.get("labels", {}).items():
                        row[f"label_{key}"] = value
                    rows.append(row)
                
                df = pd.DataFrame(rows)
                df.to_csv(output_path, index=False, encoding='utf-8')
            else:
                return False
            
            return True
        except Exception as e:
            print(f"[-] Error exporting annotations: {e}")
            return False
    
    def create_batch_annotations(
        self,
        annotation_type: AnnotationType,
        data_points: List[Dict[str, Any]],
        metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Create multiple annotation tasks at once
        
        Args:
            annotation_type: Type of annotation
            data_points: List of data points to annotate
            metadata: Additional metadata
            
        Returns:
            List of created annotations
        """
        annotations = []
        for i, data_point in enumerate(data_points):
            data_id = data_point.get("id", f"data_{i}")
            data = data_point.get("data", data_point)
            
            annotation = self.create_annotation_task(
                annotation_type=annotation_type,
                data_id=data_id,
                data=data,
                metadata=metadata
            )
            annotations.append(annotation)
        
        return annotations


# Global instance
annotation_tool = AnnotationTool()


def main():
    """Example usage"""
    tool = AnnotationTool()
    
    # Create annotation task
    task = tool.create_annotation_task(
        annotation_type=AnnotationType.PRICE_PREDICTION,
        data_id="XAUUSDT_20251211",
        data={
            "symbol": "XAUUSDT",
            "price": 2050.0,
            "features": {"sma_7": 2040, "volatility": 0.02}
        }
    )
    print(f"Created annotation: {task['id']}")
    
    # Update annotation
    tool.update_annotation(
        annotation_id=task["id"],
        labels={"predicted_price": 2100.0, "trend": "BULLISH"},
        status=AnnotationStatus.COMPLETED,
        confidence=0.92,
        annotator="admin"
    )
    
    # Get statistics
    stats = tool.get_statistics()
    print(f"Statistics: {stats}")


if __name__ == "__main__":
    main()

