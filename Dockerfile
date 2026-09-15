# Multi-stage Dockerfile for PaperBlast
# Compatible with Hugging Face Spaces, Render, Koyeb, Railway, and local Docker

# Stage 1: Build React Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Production Python Backend & Static Host
FROM python:3.11-slim

# Install system dependencies (git for repo cloning, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces runs as user 1000 by default
RUN useradd -m -u 1000 user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    RBR_DB_URL="sqlite+pysqlite:////home/user/app/rbr_local.db"

WORKDIR /home/user/app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source, migrations, cli, and built frontend assets
COPY --chown=user:user server ./server
COPY --chown=user:user infra ./infra
COPY --chown=user:user cli.py ./
COPY --chown=user:user --from=frontend-builder /app/dist ./dist

# Switch to non-root user (UID 1000) for security and Hugging Face compatibility
USER user

# Hugging Face Spaces standard HTTP port is 7860
EXPOSE 7860

# Run migrations and start uvicorn dynamically bound to $PORT (defaulting to 7860)
CMD ["sh", "-c", "python infra/migrate.py && python -m uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
