#!/bin/bash

# Master script to start all services and frontend in separate terminal windows
# Run this from the project root directory

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo "Starting All Services and Frontend"
echo "========================================"
echo ""

# Function to start a service in a new terminal window
function start_service() {
    local service_name=$1
    local service_path=$2
    local port=$3
    
    echo "Starting $service_name on port $port..."
    
    local full_path="$PROJECT_ROOT/$service_path"
    local start_script="$full_path/start.sh"
    
    if [ -f "$start_script" ]; then
        # Make script executable
        chmod +x "$start_script"
        
        # Open new terminal window and run the service
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            osascript -e "tell application \"Terminal\" to do script \"cd '$full_path' && bash '$start_script'\""
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            # Linux
            gnome-terminal -- bash -c "cd '$full_path' && bash '$start_script'; exec bash" 2>/dev/null || \
            xterm -e "cd '$full_path' && bash '$start_script" 2>/dev/null || \
            konsole -e "cd '$full_path' && bash '$start_script" 2>/dev/null
        fi
        
        echo "  ✓ $service_name started in new terminal"
    else
        echo "  ✗ Start script not found: $start_script"
    fi
    
    sleep 0.5
}

# Start all backend services
start_service "auth-service" "services/auth-service" 8003
start_service "gmail-connector-service" "services/gmail-connector-service" 8001
start_service "application-service" "services/application-service" 8002
start_service "email-intelligence-service" "services/email-intelligence-service" 8004
start_service "notification-service" "services/notification-service" 8005
start_service "api-gateway" "services/api-gateway" 8000

# Start frontend
echo ""
echo "Starting frontend on port 5173..."
FRONTEND_PATH="$PROJECT_ROOT/frontend"

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    osascript -e "tell application \"Terminal\" to do script \"cd '$FRONTEND_PATH' && npm run dev\""
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    gnome-terminal -- bash -c "cd '$FRONTEND_PATH' && npm run dev; exec bash" 2>/dev/null || \
    xterm -e "cd '$FRONTEND_PATH' && npm run dev" 2>/dev/null || \
    konsole -e "cd '$FRONTEND_PATH' && npm run dev" 2>/dev/null
fi

echo "  ✓ Frontend started in new terminal"

echo ""
echo "========================================"
echo "All services starting..."
echo "Check the terminal windows for status"
echo "========================================"
echo ""
echo "Services should be available at:"
echo "  - Frontend: http://localhost:5173"
echo "  - API Gateway: http://localhost:8000"
echo "  - Auth Service: http://localhost:8003"
echo "  - Gmail Connector: http://localhost:8001"
echo "  - Application Service: http://localhost:8002"
echo "  - Email Intelligence: http://localhost:8004"
echo "  - Notification Service: http://localhost:8005"
echo ""
