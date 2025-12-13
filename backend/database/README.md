# AURA Database Setup

## PostgreSQL Setup

### Option 1: Using Docker (Recommended)

```bash
docker run --name aura-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=aura_db \
  -p 5432:5432 \
  -d postgres:15
```

### Option 2: Local PostgreSQL Installation

1. Install PostgreSQL from https://www.postgresql.org/download/

2. Create database:
```bash
createdb aura_db
```

Or using psql:
```sql
CREATE DATABASE aura_db;
```

3. Update `.env` file:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aura_db
```

### Option 3: Using Cloud Database (Railway, Render, etc.)

1. Create PostgreSQL database on your cloud provider
2. Get connection string
3. Update `.env` file with connection string

## Initialize Database

After setting up PostgreSQL, initialize tables:

```bash
cd backend
python -c "from database.connection import init_db; init_db()"
```

Or the tables will be created automatically on server startup if `check_db_connection()` returns True.

## Database Models

- `users` - User accounts
- `user_sessions` - JWT sessions
- `portfolio_positions` - User portfolio positions
- `transactions` - Trading transactions
- `price_data` - Historical price data
- `predictions` - AI predictions
- `model_trainings` - ML model training history

## Migrations

For production, use Alembic for migrations:

```bash
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

