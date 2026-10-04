#!/bin/bash
# AURA Backend startup script
# Aborts immediately on any error — including failed Alembic migrations.
set -euo pipefail

echo "🚀 Starting AURA Backend..."

# Check if we're in the backend directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Are we in the backend directory?"
    exit 1
fi

# Run database migrations — HARD FAIL if they don't apply cleanly.
# Never start the server on a corrupt or stale schema.
if [ -f "alembic.ini" ]; then
    echo "📦 Running database migrations..."
    alembic upgrade head
    echo "✅ Migrations applied."
fi

# Start the application
echo "✅ Starting Uvicorn server..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
