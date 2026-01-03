#!/bin/bash

# ChatTwelve - Phase 1 Backend Foundation
# Environment Setup Script

set -e

echo "=========================================="
echo "  ChatTwelve Backend Setup"
echo "=========================================="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
REQUIRED_VERSION="3.11"

echo "[1/6] Checking Python version..."
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    echo "  ✓ Python $PYTHON_VERSION detected (3.11+ required)"
else
    echo "  ✗ Python 3.11+ required. Current version: $(python3 --version 2>&1)"
    echo "  Please install Python 3.11 or higher."
    exit 1
fi

# Create virtual environment if it doesn't exist
echo "[2/6] Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
echo "  ✓ Virtual environment activated"

# Install dependencies
echo "[3/6] Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo "  ✓ Dependencies installed"
else
    echo "  ⚠ requirements.txt not found. Creating minimal requirements..."
    cat > requirements.txt << 'EOF'
# Core Framework
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-ai>=0.0.12

# Database
aiosqlite>=0.19.0

# HTTP Client for MCP
httpx>=0.26.0
sse-starlette>=1.8.2

# Utilities
python-dotenv>=1.0.0
python-multipart>=0.0.6
EOF
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo "  ✓ Dependencies installed"
fi

# Initialize database
echo "[4/6] Initializing database..."
if [ -f "src/database/init_db.py" ]; then
    python -c "from src.database.init_db import init_database; import asyncio; asyncio.run(init_database())" 2>/dev/null || echo "  ⚠ Database init script not ready yet"
else
    echo "  ⚠ Database initialization will run on first server start"
fi

# Check MCP server connectivity
echo "[5/6] Checking TwelveData MCP Server connectivity..."
MCP_SERVER_URL="${MCP_SERVER_URL:-http://localhost:3847}"
MCP_URL="${MCP_SERVER_URL}/health"
if curl -s --connect-timeout 5 "$MCP_URL" > /dev/null 2>&1; then
    echo "  ✓ TwelveData MCP Server reachable at ${MCP_SERVER_URL}"
else
    echo "  ⚠ TwelveData MCP Server not reachable at $MCP_URL"
    echo "    Set MCP_SERVER_URL environment variable to configure the MCP server address."
    echo "    The application will handle this gracefully, but some features may be limited."
fi

# Start the server
echo "[6/6] Starting ChatTwelve API server..."
echo ""
echo "=========================================="
echo "  ChatTwelve Backend Starting"
echo "=========================================="
echo ""
echo "  API Base URL:    http://localhost:8000"
echo "  API Docs:        http://localhost:8000/docs"
echo "  Health Check:    http://localhost:8000/api/health"
echo ""
echo "  MCP Server:      ${MCP_SERVER_URL}"
echo ""
echo "  Press Ctrl+C to stop the server"
echo ""
echo "=========================================="

# Run the server
if [ -f "src/main.py" ]; then
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
else
    echo ""
    echo "  ⚠ src/main.py not found. Server not started."
    echo "    Run this script again after implementation is complete."
    echo ""
fi
