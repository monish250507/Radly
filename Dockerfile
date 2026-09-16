# Multi-stage Dockerfile for Radly
# Optimized for Render, Hugging Face Spaces, Koyeb, Railway, and local Docker
# 100% Stateless & Zero-DB: Ready for 1-click cloud deployment

# Stage 1: Build React Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
RUN npm run build

# Stage 2: Production Python Backend & Static Host
FROM python:3.11-slim

# Install system dependencies (git for repo cloning, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Run as non-root user for security and cloud platform compliance
RUN useradd -m -u 1000 user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /home/user/app

# Install Python dependencies (no asyncpg/compiler needed)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source, cli, and built frontend assets
COPY --chown=user:user server ./server
COPY --chown=user:user cli.py ./
COPY --chown=user:user --from=frontend-builder /app/dist ./dist

# Switch to non-root user (UID 1000)
USER user

# Default port exposure
EXPOSE 5000

# Start uvicorn dynamically bound to $PORT provided by host (Render provides $PORT)
CMD ["sh", "-c", "python -m uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-5000}"]
