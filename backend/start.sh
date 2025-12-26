#!/bin/bash
# Startup script for Railway deployment
# Finds Python and starts uvicorn

# Try to find Python in common locations
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
elif [ -f /usr/bin/python3 ]; then
    PYTHON_CMD=/usr/bin/python3
elif [ -f /usr/local/bin/python3 ]; then
    PYTHON_CMD=/usr/local/bin/python3
else
    # Last resort: try to find python in PATH
    PYTHON_CMD=$(which python3 || which python || echo "python3")
fi

echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD --version

# Start uvicorn
exec $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}

