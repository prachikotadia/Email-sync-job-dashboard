#!/bin/bash

# Start script for email-intelligence-service with virtual environment

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

# Start the service
echo "Starting email-intelligence-service on port 8004..."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8004
