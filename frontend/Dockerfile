# ============================================================================
# Base Dockerfile for frontend service
# ============================================================================
# Multi-stage build: Node.js for build, nginx for production
# Minimal setup - just the base container ready for application code
# ============================================================================

# Build stage: Compile React application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production=false

# Copy source code
COPY . .

# Build the application
# VITE_API_URL will be set at build time via build args
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Production stage: Serve with nginx
FROM nginx:alpine

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/health || exit 1

# Run nginx
CMD ["nginx", "-g", "daemon off;"]
