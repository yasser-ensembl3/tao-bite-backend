#!/bin/bash

echo "=========================================="
echo "  Tao of Founders - Backend Launcher"
echo "=========================================="
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found!"
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
    echo ""
fi

# Activate venv
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Check if requirements are installed
if [ ! -f "venv/lib/python*/site-packages/flask/__init__.py" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
    echo ""
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "📝 Please create .env from .env.example and add your API keys"
    echo ""
    echo "Run: cp .env.example .env"
    echo "Then edit .env with your API keys"
    echo ""
    read -p "Press Enter to continue anyway or Ctrl+C to exit..."
fi

# Start the server
echo "🚀 Starting Flask server on http://localhost:8080"
echo ""
python app.py
