# AURA Backend API

Backend server για την εφαρμογή AURA - AI Trading Assistant

## Setup

1. **Δημιουργία Virtual Environment:**
```bash
cd backend
python -m venv venv
```

2. **Ενεργοποίηση Virtual Environment:**
- Windows:
```bash
venv\Scripts\activate
```
- macOS/Linux:
```bash
source venv/bin/activate
```

3. **Εγκατάσταση Dependencies:**
```bash
pip install -r requirements.txt
```

## Εκτέλεση

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /` - Root status
- `GET /health` - Health check
- `GET /api/quote-of-day` - Γνωμικό της ημέρας
- `GET /api/stats` - Trading statistics
- `GET /api/system-status` - Κατάσταση συστήματος

## Documentation

Μόλις τρέξει ο server:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Environment Variables

Δημιούργησε `.env` file:
```
ENVIRONMENT=development
DEBUG=True
API_KEY=your_api_key_here
```

## Deployment

### Railway (Recommended)
1. Push σε Git repository
2. Σύνδεση με Railway
3. Deploy automatically

### Render
1. Connect repository
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

