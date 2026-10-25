#!/bin/bash
# AURA Backend startup script
set -euo pipefail

echo "🚀 Starting AURA Backend..."

# Ensure system-wide pip installs are on PATH
export PATH="/usr/local/bin:$PATH"

if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found."
    exit 1
fi

# Only run migrations if DATABASE_URL is set
if [ -f "alembic.ini" ] && [ -n "${DATABASE_URL:-}" ]; then
    echo "📦 Running database migrations..."
    alembic upgrade head
    echo "✅ Migrations applied."
else
    echo "⚠️  Skipping migrations (DATABASE_URL not set or no alembic.ini)"
fi

echo "✅ Starting Uvicorn server..."
# --workers 1 MANDATORY: xag_orders.py uses threading.Lock() for in-memory margin isolation
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
# Start nginx (SSL terminator)
nginx 2>/dev/null || true
