#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting AURA Backend..."

# Check if we're in the backend directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Are we in the backend directory?"
    exit 1
fi

# Run database migrations (if needed)
if [ -f "alembic.ini" ]; then
    echo "📦 Running database migrations..."
    alembic upgrade head || echo "⚠️ Migration failed or not configured"
fi

# Start the application
echo "✅ Starting Uvicorn server..."
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
