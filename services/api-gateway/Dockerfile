# ============================================================================
# Base Dockerfile for api-gateway service
# ============================================================================
# Minimal setup: Python environment + dependencies
# No app logic - just the base container ready for application code
# ============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code (base structure)
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Health check endpoint (if implemented)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
