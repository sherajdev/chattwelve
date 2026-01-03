#!/bin/bash

# ChatTwelve - Full Stack Development Server
# Starts both backend (FastAPI) and frontend (Next.js)

set -e

# Store PIDs for cleanup
BACKEND_PID=""
FRONTEND_PID=""

# Cleanup function to kill both servers on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null
        echo "  ✓ Backend server stopped"
    fi
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null
        echo "  ✓ Frontend server stopped"
    fi
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

echo "=========================================="
echo "  ChatTwelve Full Stack Setup"
echo "=========================================="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)

echo "[1/8] Checking Python version..."
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    echo "  ✓ Python $PYTHON_VERSION detected (3.11+ required)"
else
    echo "  ✗ Python 3.11+ required. Current version: $(python3 --version 2>&1)"
    echo "  Please install Python 3.11 or higher."
    exit 1
fi

# Check Node.js
echo "[2/8] Checking Node.js version..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "  ✓ Node.js $NODE_VERSION detected"
else
    echo "  ✗ Node.js not found. Please install Node.js 18+ for frontend."
    exit 1
fi

# Create virtual environment if it doesn't exist
echo "[3/8] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
echo "  ✓ Virtual environment activated"

# Install Python dependencies
echo "[4/8] Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo "  ✓ Python dependencies installed"
else
    echo "  ✗ requirements.txt not found"
    exit 1
fi

# Install frontend dependencies
echo "[5/8] Installing frontend dependencies..."
if [ -d "frontend" ]; then
    cd frontend
    if [ ! -d "node_modules" ]; then
        npm install --silent
        echo "  ✓ Frontend dependencies installed"
    else
        echo "  ✓ Frontend dependencies already installed"
    fi
    cd ..
else
    echo "  ✗ frontend directory not found"
    exit 1
fi

# Initialize database
echo "[6/8] Initializing database..."
if [ -f "src/database/init_db.py" ]; then
    python -c "from src.database.init_db import init_database; import asyncio; asyncio.run(init_database())" 2>/dev/null || echo "  ⚠ Database init script not ready yet"
else
    echo "  ⚠ Database initialization will run on first server start"
fi

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Check MCP server connectivity
echo "[7/8] Checking TwelveData MCP Server connectivity..."
MCP_SERVER_URL="${MCP_SERVER_URL:-http://localhost:3847}"
MCP_URL="${MCP_SERVER_URL}/health"
if curl -s --connect-timeout 5 "$MCP_URL" > /dev/null 2>&1; then
    echo "  ✓ TwelveData MCP Server reachable at ${MCP_SERVER_URL}"
else
    echo "  ⚠ TwelveData MCP Server not reachable at $MCP_URL"
    echo "    Set MCP_SERVER_URL environment variable to configure the MCP server address."
    echo "    The application will handle this gracefully, but some features may be limited."
fi

# Start the servers
echo "[8/8] Starting servers..."
echo ""
echo "=========================================="
echo "  ChatTwelve Starting"
echo "=========================================="
echo ""
echo "  Backend API:     http://localhost:8000"
echo "  API Docs:        http://localhost:8000/docs"
echo "  Health Check:    http://localhost:8000/api/health"
echo ""
echo "  Frontend:        http://localhost:3000"
echo ""
echo "  MCP Server:      ${MCP_SERVER_URL}"
echo ""
echo "  Press Ctrl+C to stop all servers"
echo ""
echo "=========================================="
echo ""

# Start backend server in background
echo "Starting backend server..."
if [ -f "src/main.py" ]; then
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    echo "  ✓ Backend server started (PID: $BACKEND_PID)"
else
    echo "  ✗ src/main.py not found. Backend not started."
    exit 1
fi

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "  ✓ Backend is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ⚠ Backend took too long to start, continuing anyway..."
    fi
    sleep 1
done

# Start frontend server in foreground
echo ""
echo "Starting frontend server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
echo "  ✓ Frontend server started (PID: $FRONTEND_PID)"
cd ..

echo ""
echo "=========================================="
echo "  All servers running!"
echo "  Open http://localhost:3000 in your browser"
echo "=========================================="
echo ""

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID
