# Multi-stage build for DocuLens: React Vite Frontend + FastAPI Backend

# Stage 1: Build the React Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend runtime
FROM python:3.11-slim
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend /app/backend

# Copy built frontend assets into frontend/dist for FastAPI to serve statically
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Expose Hugging Face default port
EXPOSE 7860

# Environment defaults
ENV PORT=7860
ENV HOST=0.0.0.0
ENV PYTHONPATH=/app/backend

# Run application with Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

