#!/bin/bash
# Startup script for Railway deployment
# Finds Python and starts uvicorn

# Source Nix environment (Nixpacks uses Nix)
export PATH="/nix/var/nix/profiles/default/bin:$PATH"
if [ -f /nix/var/nix/profiles/default/etc/profile.d/nix.sh ]; then
    source /nix/var/nix/profiles/default/etc/profile.d/nix.sh
fi
if [ -f ~/.nix-profile/etc/profile.d/nix.sh ]; then
    source ~/.nix-profile/etc/profile.d/nix.sh
fi

# Add common Nix paths
export PATH="/usr/bin:/usr/local/bin:/bin:$PATH"

# Try to find Python in Nix store first (Nixpacks)
PYTHON_CMD=""
if [ -z "$PYTHON_CMD" ]; then
    PYTHON_CMD=$(find /nix/store -name python3 -type f -executable 2>/dev/null | grep -E "(python3|python-3)" | head -1)
fi
if [ -z "$PYTHON_CMD" ]; then
    PYTHON_CMD=$(find /nix/store -name python -type f -executable 2>/dev/null | head -1)
fi

# Try standard locations
if [ -z "$PYTHON_CMD" ] || ! $PYTHON_CMD --version &> /dev/null 2>&1; then
    if command -v python3 &> /dev/null && python3 --version &> /dev/null 2>&1; then
        PYTHON_CMD=python3
    elif command -v python &> /dev/null && python --version &> /dev/null 2>&1; then
        PYTHON_CMD=python
    elif [ -x /usr/bin/python3 ]; then
        PYTHON_CMD=/usr/bin/python3
    elif [ -x /usr/local/bin/python3 ]; then
        PYTHON_CMD=/usr/local/bin/python3
    fi
fi

# If still not found, try uvicorn directly
if [ -z "$PYTHON_CMD" ] || ! $PYTHON_CMD --version &> /dev/null 2>&1; then
    if command -v uvicorn &> /dev/null; then
        echo "Python not found, trying uvicorn directly..."
        exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
    else
        echo "ERROR: Python not found and uvicorn not available"
        echo "PATH: $PATH"
        echo "Trying to find Python in /nix/store..."
        find /nix/store -name python* -type f 2>/dev/null | head -5
        exit 1
    fi
fi

echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD --version

# Start uvicorn
exec $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}

