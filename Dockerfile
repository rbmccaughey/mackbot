# Stage 1: build the React frontend
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime with Playwright + Xvfb
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99

WORKDIR /app

# Xvfb provides a virtual display so Playwright can run non-headless (needed for Cloudflare)
RUN apt-get update && apt-get install -y --no-install-recommends xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium and all its system dependencies
RUN playwright install --with-deps chromium

COPY *.py .
COPY --from=frontend /app/dist ./frontend/dist

EXPOSE 8000

# Start Xvfb on :99, then uvicorn as the main process (receives signals)
CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x720x24 -nolisten tcp & exec uvicorn server:app --host 0.0.0.0 --port 8000"]
