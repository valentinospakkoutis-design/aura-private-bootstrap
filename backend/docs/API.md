# AURA Backend API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

### JWT Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Register

```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:** Same as register

### Refresh Token

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### Get Current User

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

### Logout

```http
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

## Assets

### Get All Assets

```http
GET /api/v1/assets
```

**Response:**
```json
[
  {
    "id": "AAPL",
    "name": "Apple Inc.",
    "symbol": "AAPL",
    "type": "stock"
  }
]
```

### Get Asset Price

```http
GET /api/v1/price/{asset_id}
```

**Response:**
```json
{
  "asset_id": "AAPL",
  "price": 278.37,
  "volume": 38360082.0,
  "change_pct": 1.5,
  "timestamp": "2025-12-13T00:00:00"
}
```

### Get Historical Prices

```http
GET /api/v1/prices/{asset_id}/historical?period=1M
```

**Parameters:**
- `period`: 1D, 1W, 1M, 3M, 1Y

## Predictions

### Get Prediction

```http
GET /api/v1/predictions/{asset_id}
```

### Get All Predictions

```http
GET /api/v1/predictions
```

## Portfolio

### Buy Asset

```http
POST /api/v1/portfolio/buy
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "asset_id": "AAPL",
  "quantity": 10,
  "price": 278.37
}
```

### Sell Asset

```http
POST /api/v1/portfolio/sell
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "asset_id": "AAPL",
  "quantity": 5,
  "price": 280.00
}
```

### Get Portfolio Positions

```http
GET /api/v1/portfolio/positions
Authorization: Bearer <access_token>
```

## Health Check

```http
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "api": {"status": "online", "version": "1.0.0"},
    "database": {"status": "not_configured"},
    "redis": {"status": "not_configured"},
    "yfinance": {"status": "available"}
  },
  "timestamp": "2025-12-13T00:00:00"
}
```

## Rate Limiting

- **Per Minute**: 60 requests
- **Per Hour**: 1000 requests

Rate limit headers are included in responses:
- `X-RateLimit-Limit-Minute`
- `X-RateLimit-Remaining-Minute`
- `X-RateLimit-Limit-Hour`
- `X-RateLimit-Remaining-Hour`

## Error Responses

All errors follow this format:

```json
{
  "error": "ERROR_CODE",
  "message": "User-friendly error message",
  "status_code": 400
}
```

Common error codes:
- `VALIDATION_ERROR` - Invalid input data
- `NOT_FOUND` - Resource not found
- `AUTH_ERROR` - Authentication failed
- `RATE_LIMIT` - Rate limit exceeded
- `INTERNAL_ERROR` - Server error

## Interactive API Documentation

Visit `http://localhost:8000/docs` for interactive Swagger documentation.

