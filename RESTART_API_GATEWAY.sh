#!/bin/bash
echo "🔄 Force restarting API Gateway..."

# Kill all processes
pkill -9 -f "uvicorn.*8000" 2>/dev/null
pkill -9 -f "python.*api-gateway" 2>/dev/null

# Clear Python cache
find services/api-gateway -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find services/api-gateway -name "*.pyc" -delete 2>/dev/null

echo "✅ Cleared caches"
echo "⏳ Waiting 3 seconds..."
sleep 3

# Restart
cd services/api-gateway
source venv/bin/activate
echo "🚀 Starting API Gateway..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

