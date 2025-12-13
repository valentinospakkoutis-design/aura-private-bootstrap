# AURA Backend Setup Guide

## Prerequisites

- Python 3.10+ (3.14 tested)
- PostgreSQL (optional, for production)
- Redis (optional, for caching)

## Installation

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

Create `.env` file in `backend/` directory:

```env
# Database (optional)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aura_db

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# JWT Secret (change in production!)
JWT_SECRET_KEY=your-secret-key-here

# Database Echo (for debugging)
DB_ECHO=false
```

### 5. Setup Database (Optional)

**Using Docker:**
```bash
docker run --name aura-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=aura_db \
  -p 5432:5432 \
  -d postgres:15
```

**Initialize tables:**
```bash
python scripts/setup_database.py
```

### 6. Run Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at: `http://localhost:8000`

## Features

- ✅ JWT Authentication
- ✅ Rate Limiting (60/min, 1000/hour)
- ✅ Error Handling (Greek messages)
- ✅ Security (encryption, hashing)
- ✅ yfinance Integration (real market data)
- ✅ PostgreSQL Support
- ✅ Redis Caching
- ✅ API Documentation (Swagger)

## Testing

### Test Endpoints

```bash
python tests/test_endpoints.py
```

### Test Security

```bash
python tests/test_security.py
```

## API Documentation

- Interactive: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Troubleshooting

### Database Connection Failed

- Ensure PostgreSQL is running
- Check `DATABASE_URL` in `.env`
- Verify database exists: `createdb aura_db`

### Redis Connection Failed

- Server will continue without Redis (caching disabled)
- To enable: Install and start Redis server

### Import Errors

- Ensure virtual environment is activated
- Run: `pip install -r requirements.txt`

## Production Deployment

1. Set strong `JWT_SECRET_KEY` in environment
2. Configure PostgreSQL database
3. Setup Redis for caching
4. Use production WSGI server (Gunicorn)
5. Enable HTTPS
6. Configure CORS properly

