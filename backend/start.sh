#!/bin/bash
# Startup script for Railway deployment
# Finds Python and starts uvicorn

# Source Nix environment if available (for Nixpacks)
if [ -f ~/.nix-profile/etc/profile.d/nix.sh ]; then
    source ~/.nix-profile/etc/profile.d/nix.sh
fi

# Try to find Python - check if command exists AND is executable
PYTHON_CMD=""
if command -v python3 &> /dev/null && python3 --version &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null && python --version &> /dev/null; then
    PYTHON_CMD=python
elif [ -x /usr/bin/python3 ]; then
    PYTHON_CMD=/usr/bin/python3
elif [ -x /usr/local/bin/python3 ]; then
    PYTHON_CMD=/usr/local/bin/python3
else
    # Try to find in Nix store (Nixpacks)
    PYTHON_CMD=$(find /nix/store -name python3 -type f -executable 2>/dev/null | head -1)
    if [ -z "$PYTHON_CMD" ]; then
        PYTHON_CMD=$(find /nix/store -name python -type f -executable 2>/dev/null | head -1)
    fi
fi

# If still not found, try uvicorn directly
if [ -z "$PYTHON_CMD" ] || ! $PYTHON_CMD --version &> /dev/null; then
    if command -v uvicorn &> /dev/null; then
        echo "Python not found, trying uvicorn directly..."
        exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
    else
        echo "ERROR: Python not found and uvicorn not available"
        exit 1
    fi
fi

echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD --version

# Start uvicorn
exec $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}

