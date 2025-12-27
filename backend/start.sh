#!/bin/bash
# Startup script for Railway deployment
# Finds Python and starts uvicorn

set -e  # Exit on error

echo "=== Finding Python ==="

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

echo "PATH: $PATH"

# Try to find Python in Nix store first (Nixpacks)
# Nixpacks installs Python in /nix/store with pattern like:
# /nix/store/...-python3-3.11.x/bin/python3
PYTHON_CMD=""

echo "Searching for Python in /nix/store..."
# Find python3 in Nix store (most specific)
PYTHON_CANDIDATES=$(find /nix/store -type f -name "python3" -executable 2>/dev/null | grep -E "python3.*bin/python3$" | head -5)
echo "Found Python candidates:"
echo "$PYTHON_CANDIDATES"

# Try each candidate
for candidate in $PYTHON_CANDIDATES; do
    if [ -n "$candidate" ] && $candidate --version &> /dev/null 2>&1; then
        PYTHON_CMD="$candidate"
        echo "✓ Found working Python: $PYTHON_CMD"
        break
    fi
done

# If not found, try broader search
if [ -z "$PYTHON_CMD" ]; then
    echo "Trying broader search..."
    PYTHON_CMD=$(find /nix/store -type f -name "python3" -executable 2>/dev/null | head -1)
    if [ -n "$PYTHON_CMD" ] && $PYTHON_CMD --version &> /dev/null 2>&1; then
        echo "✓ Found Python: $PYTHON_CMD"
    else
        PYTHON_CMD=""
    fi
fi

# Try standard locations
if [ -z "$PYTHON_CMD" ]; then
    echo "Trying standard locations..."
    if command -v python3 &> /dev/null && python3 --version &> /dev/null 2>&1; then
        PYTHON_CMD=python3
        echo "✓ Found python3 in PATH"
    elif command -v python &> /dev/null && python --version &> /dev/null 2>&1; then
        PYTHON_CMD=python
        echo "✓ Found python in PATH"
    elif [ -x /usr/bin/python3 ] && /usr/bin/python3 --version &> /dev/null 2>&1; then
        PYTHON_CMD=/usr/bin/python3
        echo "✓ Found /usr/bin/python3"
    elif [ -x /usr/local/bin/python3 ] && /usr/local/bin/python3 --version &> /dev/null 2>&1; then
        PYTHON_CMD=/usr/local/bin/python3
        echo "✓ Found /usr/local/bin/python3"
    fi
fi

# If still not found, try uvicorn directly
if [ -z "$PYTHON_CMD" ] || ! $PYTHON_CMD --version &> /dev/null 2>&1; then
    echo "Python not found, trying uvicorn directly..."
    if command -v uvicorn &> /dev/null; then
        exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
    else
        echo "=== ERROR: Python not found ==="
        echo "PATH: $PATH"
        echo ""
        echo "Searching /nix/store for Python..."
        find /nix/store -name "python*" -type f 2>/dev/null | head -10
        echo ""
        echo "Checking if /nix/store exists..."
        ls -la /nix/store 2>&1 | head -5
        exit 1
    fi
fi

echo ""
echo "=== Starting Uvicorn ==="
echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD --version
echo "Python path: $(which $PYTHON_CMD 2>/dev/null || echo $PYTHON_CMD)"
echo ""

# Check for virtual environment (Nixpacks creates /opt/venv)
if [ -d "/opt/venv" ]; then
    echo "Found virtual environment at /opt/venv"
    export PATH="/opt/venv/bin:$PATH"
    if [ -f "/opt/venv/bin/python3" ]; then
        PYTHON_CMD="/opt/venv/bin/python3"
        echo "Using Python from venv: $PYTHON_CMD"
        $PYTHON_CMD --version
    fi
fi

# Check if uvicorn is available
if ! $PYTHON_CMD -m uvicorn --help &> /dev/null 2>&1; then
    echo "ERROR: uvicorn not found in Python environment"
    echo "Checking installed packages..."
    $PYTHON_CMD -m pip list 2>&1 | grep -i uvicorn || echo "uvicorn not in pip list"
    echo ""
    echo "Trying to find uvicorn in PATH..."
    which uvicorn || echo "uvicorn not in PATH"
    echo ""
    echo "Checking /opt/venv/bin..."
    ls -la /opt/venv/bin/ 2>&1 | head -10
    exit 1
fi

# Start uvicorn
exec $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}

