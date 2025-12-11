"""
API Endpoints for Annotation Tool
FastAPI routes για annotation management
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from ml.annotation_tool import (
    AnnotationTool,
    AnnotationType,
    AnnotationStatus
)

router = APIRouter(prefix="/api/annotations", tags=["annotations"])

# Global annotation tool instance
annotation_tool = AnnotationTool()


class AnnotationCreate(BaseModel):
    """Request model for creating annotation"""
    annotation_type: str
    data_id: str
    data: Dict[str, Any]
    metadata: Optional[Dict] = None


class AnnotationUpdate(BaseModel):
    """Request model for updating annotation"""
    labels: Optional[Dict] = None
    status: Optional[str] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None
    annotator: Optional[str] = None


@router.post("/tasks")
def create_annotation_task(annotation: AnnotationCreate):
    """Create new annotation task"""
    try:
        ann_type = AnnotationType(annotation.annotation_type)
        task = annotation_tool.create_annotation_task(
            annotation_type=ann_type,
            data_id=annotation.data_id,
            data=annotation.data,
            metadata=annotation.metadata
        )
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid annotation type: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{annotation_id}")
def get_annotation(annotation_id: str):
    """Get annotation by ID"""
    annotation = annotation_tool.get_annotation(annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation


@router.put("/tasks/{annotation_id}")
def update_annotation(annotation_id: str, update: AnnotationUpdate):
    """Update annotation"""
    status = None
    if update.status:
        try:
            status = AnnotationStatus(update.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {update.status}")
    
    success = annotation_tool.update_annotation(
        annotation_id=annotation_id,
        labels=update.labels,
        status=status,
        confidence=update.confidence,
        notes=update.notes,
        annotator=update.annotator
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    return {"status": "updated", "annotation_id": annotation_id}


@router.get("/tasks")
def get_pending_annotations(
    annotation_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get pending annotations"""
    ann_type = None
    if annotation_type:
        try:
            ann_type = AnnotationType(annotation_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid annotation type: {annotation_type}")
    
    pending = annotation_tool.get_pending_annotations(
        annotation_type=ann_type,
        limit=limit
    )
    
    return {
        "annotations": pending,
        "count": len(pending),
        "limit": limit
    }


@router.get("/statistics")
def get_statistics():
    """Get annotation statistics"""
    return annotation_tool.get_statistics()


@router.post("/export")
def export_annotations(
    output_path: str = Body(...),
    annotation_type: Optional[str] = Body(None),
    status: Optional[str] = Body(None),
    format: str = Body("json")
):
    """Export annotations"""
    ann_type = None
    if annotation_type:
        try:
            ann_type = AnnotationType(annotation_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid annotation type: {annotation_type}")
    
    ann_status = None
    if status:
        try:
            ann_status = AnnotationStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    success = annotation_tool.export_annotations(
        output_path=output_path,
        annotation_type=ann_type,
        status=ann_status,
        format=format
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Export failed")
    
    return {"status": "exported", "output_path": output_path}


@router.post("/batch")
def create_batch_annotations(
    annotation_type: str = Body(...),
    data_points: List[Dict[str, Any]] = Body(...),
    metadata: Optional[Dict] = Body(None)
):
    """Create multiple annotation tasks"""
    try:
        ann_type = AnnotationType(annotation_type)
        annotations = annotation_tool.create_batch_annotations(
            annotation_type=ann_type,
            data_points=data_points,
            metadata=metadata
        )
        return {
            "created": len(annotations),
            "annotations": annotations
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid annotation type: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

