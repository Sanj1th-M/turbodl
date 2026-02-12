#!/data/data/com.termux/files/usr/bin/bash

# TurboDL Startup Script for Termux
# This script starts the FastAPI server and creates a public URL with ngrok

echo "🚀 Starting TurboDL on Termux..."
echo "================================"

# Navigate to project directory
cd ~/turbodl/video_downloader || {
    echo "❌ Error: Project directory not found!"
    echo "Please clone the repository first:"
    echo "  git clone https://github.com/Sanj1th-M/turbodl.git ~/turbodl"
    exit 1
}

# Check if virtual environment exists, create if not
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install/update dependencies
echo "📥 Checking dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Kill any existing uvicorn processes
pkill -f "uvicorn main:app" 2>/dev/null

# Start FastAPI server in background
echo "🌐 Starting TurboDL server on port 8000..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ~/turbodl.log 2>&1 &
SERVER_PID=$!

echo "✅ Server started (PID: $SERVER_PID)"

# Wait for server to be ready
echo "⏳ Waiting for server to be ready..."
sleep 5

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ Server is running successfully!"
    echo ""
    echo "📱 Local access: http://localhost:8000"
    echo ""
    echo "🌍 Starting ngrok for public access..."
    echo "================================"
    echo ""
    
    # Start ngrok
    ngrok http 8000
else
    echo "❌ Server failed to start. Check logs:"
    echo "  cat ~/turbodl.log"
    exit 1
fi
