#!/bin/bash
# Startup script for Amazon PPC Dashboard

echo "🚀 Starting Amazon PPC Dashboard..."
echo "=================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📚 Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Check for required environment variables
if [ -z "$AMAZON_CLIENT_ID" ]; then
    echo "⚠️  Warning: AMAZON_CLIENT_ID not set"
fi

if [ -z "$AMAZON_PROFILE_ID" ]; then
    echo "⚠️  Warning: AMAZON_PROFILE_ID not set"
fi

# Launch dashboard
echo ""
echo "✅ Launching dashboard..."
echo "📊 Dashboard will open at http://localhost:8501"
echo ""

streamlit run dashboard.py
