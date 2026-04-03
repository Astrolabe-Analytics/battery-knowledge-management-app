# ── Stage 1: Frontend build ─────────────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── Stage 2: Runtime (NGINX + FastAPI) ───────────────────────────────────────
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      nginx \
      gcc \
      libpq-dev \
      curl \
      tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence-transformers model to reduce cold start
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# App code
COPY api/ ./api/
COPY lib/ ./lib/
COPY scripts/ ./scripts/

# React build served by NGINX
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html

# NGINX config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Start script for both processes
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh && \
    rm -f /etc/nginx/sites-enabled/default

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=3 \
  CMD curl -fsS http://127.0.0.1/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/start.sh"]
