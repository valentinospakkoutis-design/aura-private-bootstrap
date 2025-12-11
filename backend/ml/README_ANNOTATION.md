# Annotation Tool Guide

## Επισκόπηση

Το Annotation Tool επιτρέπει annotation/labeling training data για ML models. Υποστηρίζει multiple annotation types και workflows.

## Αρχεία

- `annotation_tool.py` - Κύριο annotation tool class
- `annotation_api.py` - FastAPI endpoints για annotation management

## Χαρακτηριστικά

- **Multiple Annotation Types**: Price prediction, trading signals, sentiment, news classification, market regime
- **Status Tracking**: Pending, in progress, completed, reviewed, rejected
- **Batch Operations**: Create multiple annotations at once
- **Export**: Export annotations σε JSON ή CSV
- **Statistics**: Track annotation progress

## API Endpoints

### Create Annotation Task
```bash
POST /api/annotations/tasks
{
  "annotation_type": "price_prediction",
  "data_id": "XAUUSDT_20251211",
  "data": {
    "symbol": "XAUUSDT",
    "price": 2050.0,
    "features": {...}
  },
  "metadata": {...}
}
```

### Get Annotation
```bash
GET /api/annotations/tasks/{annotation_id}
```

### Update Annotation
```bash
PUT /api/annotations/tasks/{annotation_id}
{
  "labels": {
    "predicted_price": 2100.0,
    "trend": "BULLISH"
  },
  "status": "completed",
  "confidence": 0.92,
  "annotator": "admin"
}
```

### Get Pending Annotations
```bash
GET /api/annotations/tasks?annotation_type=price_prediction&limit=100
```

### Get Statistics
```bash
GET /api/annotations/statistics
```

### Export Annotations
```bash
POST /api/annotations/export
{
  "output_path": "annotations_export.json",
  "annotation_type": "price_prediction",
  "status": "completed",
  "format": "json"
}
```

### Create Batch Annotations
```bash
POST /api/annotations/batch
{
  "annotation_type": "price_prediction",
  "data_points": [
    {"id": "data_1", "data": {...}},
    {"id": "data_2", "data": {...}}
  ]
}
```

## Annotation Types

- `price_prediction` - Price prediction annotations
- `trading_signal` - Trading signal annotations
- `sentiment` - Sentiment analysis annotations
- `news_classification` - News classification annotations
- `market_regime` - Market regime annotations

## Status Values

- `pending` - Not yet annotated
- `in_progress` - Currently being annotated
- `completed` - Annotation completed
- `reviewed` - Reviewed and approved
- `rejected` - Rejected annotation

## Python Usage

```python
from ml.annotation_tool import AnnotationTool, AnnotationType, AnnotationStatus

tool = AnnotationTool()

# Create annotation
task = tool.create_annotation_task(
    annotation_type=AnnotationType.PRICE_PREDICTION,
    data_id="XAUUSDT_20251211",
    data={"symbol": "XAUUSDT", "price": 2050.0}
)

# Update annotation
tool.update_annotation(
    annotation_id=task["id"],
    labels={"predicted_price": 2100.0},
    status=AnnotationStatus.COMPLETED,
    confidence=0.92
)

# Get statistics
stats = tool.get_statistics()
print(stats)
```

## Export Formats

### JSON
```python
tool.export_annotations(
    output_path="annotations.json",
    format="json"
)
```

### CSV
```python
tool.export_annotations(
    output_path="annotations.csv",
    format="csv"
)
```

## Workflow

1. **Create Tasks**: Create annotation tasks for data points
2. **Annotate**: Update tasks with labels and status
3. **Review**: Mark as reviewed when quality checked
4. **Export**: Export completed annotations for training

## Integration with Training

Annotations can be used to:
- Validate model predictions
- Create labeled datasets
- Improve model accuracy
- Track annotation quality

## Next Steps

1. **Web UI**: Create web interface για annotation
2. **Auto-labeling**: Use model predictions as initial labels
3. **Quality Control**: Add inter-annotator agreement metrics
4. **Active Learning**: Select most informative samples for annotation

