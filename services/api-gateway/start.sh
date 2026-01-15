#!/bin/bash

# Start script for api-gateway with virtual environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found!"
    echo "Creating virtual environment..."
    
    python3 -m venv "$VENV_PATH"
    source "$VENV_PATH/bin/activate"
    pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/requirements.txt"
    deactivate
    
    echo "✅ Virtual environment created and dependencies installed"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Check if .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "⚠️  .env file not found. Creating from defaults..."
fi

# Start the service
echo "Starting api-gateway on port 8000..."
echo "Make sure auth-service (8003) and application-service (8002) are running!"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
