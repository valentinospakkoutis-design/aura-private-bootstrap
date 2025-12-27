#!/bin/bash
# Startup script for Railway deployment
# Auto-detects backend directory and finds Python

set -e  # Exit on error

echo "=== Railway Backend Startup ==="
echo "Current directory: $(pwd)"
echo "Listing files:"
ls -la
echo ""

# Auto-detect backend directory
if [ ! -f "main.py" ]; then
    if [ -d "backend" ] && [ -f "backend/main.py" ]; then
        echo "⚠ Not in backend directory, changing to backend..."
        cd backend
        echo "Now in: $(pwd)"
        echo "Listing backend files:"
        ls -la
        echo ""
    else
        echo "ERROR: main.py not found in current directory or backend/"
        echo "Current directory contents:"
        ls -la
        exit 1
    fi
fi

# Check for Nixpacks virtual environment (created during build)
if [ -d "/opt/venv" ] && [ -f "/opt/venv/bin/python3" ]; then
    echo "✓ Found Nixpacks virtual environment at /opt/venv"
    export PATH="/opt/venv/bin:$PATH"
    PYTHON_CMD="/opt/venv/bin/python3"
    echo "Using Python: $PYTHON_CMD"
    $PYTHON_CMD --version
    echo ""
    echo "=== Starting Uvicorn ==="
    exec $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
fi

# If /opt/venv not found, try to find Python in Nix store
echo "⚠ /opt/venv not found, searching for Python..."

# Source Nix environment
export PATH="/nix/var/nix/profiles/default/bin:$PATH"
if [ -f /nix/var/nix/profiles/default/etc/profile.d/nix.sh ]; then
    source /nix/var/nix/profiles/default/etc/profile.d/nix.sh
fi

# Try to find Python in Nix store
PYTHON_CMD=""
echo "Searching /nix/store for Python..."
PYTHON_CANDIDATES=$(find /nix/store -type f -name "python3" -executable 2>/dev/null | head -5)

if [ -n "$PYTHON_CANDIDATES" ]; then
    for candidate in $PYTHON_CANDIDATES; do
        if $candidate --version &> /dev/null 2>&1; then
            PYTHON_CMD="$candidate"
            echo "✓ Found Python: $PYTHON_CMD"
            $PYTHON_CMD --version
            break
        fi
    done
fi

# If still not found, try standard locations
if [ -z "$PYTHON_CMD" ]; then
    echo "Trying standard locations..."
    if command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
        echo "✓ Found python3 in PATH"
    elif command -v python &> /dev/null; then
        PYTHON_CMD=python
        echo "✓ Found python in PATH"
    fi
fi

# Final check
if [ -z "$PYTHON_CMD" ] || ! $PYTHON_CMD --version &> /dev/null 2>&1; then
    echo ""
    echo "=== ERROR: Python not found ==="
    echo "This usually means Railway's Root Directory is not set to 'backend'"
    echo ""
    echo "SOLUTION:"
    echo "1. Go to Railway Dashboard → Project → Settings"
    echo "2. Find 'Root Directory' field"
    echo "3. Enter: backend"
    echo "4. Click Save"
    echo "5. Railway will auto-redeploy"
    echo ""
    echo "Current PATH: $PATH"
    echo "Current directory: $(pwd)"
    exit 1
fi

echo ""
echo "=== Starting Uvicorn ==="
echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD --version

# Check if uvicorn is available
if ! $PYTHON_CMD -m uvicorn --help &> /dev/null 2>&1; then
    echo ""
    echo "ERROR: uvicorn not found"
    echo "This means Python dependencies were not installed"
    echo "Check that Railway's Root Directory is set to 'backend'"
    echo ""
    echo "Installed packages:"
    $PYTHON_CMD -m pip list 2>&1 | head -20
    exit 1
fi

# Start uvicorn
exec $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
