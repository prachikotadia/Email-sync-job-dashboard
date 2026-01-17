#!/bin/bash

# JobPulse AI Setup Script

echo "🚀 Setting up JobPulse AI..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "⚠️  Please update .env with your Google OAuth credentials!"
    else
        echo "❌ .env.example not found. Creating basic .env file..."
        cat > .env << EOF
# JWT Configuration
JWT_SECRET=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
REDIRECT_URI=http://localhost:8001/auth/callback

# Service URLs (internal Docker network)
AUTH_SERVICE_URL=http://auth-service:8001
GMAIL_SERVICE_URL=http://gmail-connector:8002

# Frontend API URL
VITE_API_URL=http://localhost:8000
EOF
        echo "⚠️  Please update .env with your Google OAuth credentials!"
    fi
else
    echo "✅ .env file already exists"
fi

# Create volumes directory
mkdir -p volumes/gmail-sync-state

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env with your Google OAuth credentials"
echo "2. Run: docker-compose up --build"
echo "3. Access the app at http://localhost:3000"
echo ""
