# ── Stage 1: Frontend build ─────────────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── Stage 2: Python API (serves React frontend + API on port 8003) ───────────
FROM python:3.13-slim AS api

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first so this layer is cached independently
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformers model (~100MB).
# This layer is cached — only re-runs when requirements.txt changes.
# Eliminates the 10-30s cold-start delay on first RAG request.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code last so code changes don't bust the model cache layer
COPY api/ ./api/
COPY lib/ ./lib/
COPY scripts/ ./scripts/

# Copy built React frontend — served as static files by FastAPI
COPY --from=frontend-build /app/frontend/dist ./dist

EXPOSE 8003

HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/api/health')"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2"]
