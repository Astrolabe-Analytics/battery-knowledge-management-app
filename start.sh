#!/usr/bin/env bash
set -euo pipefail

# Start FastAPI on localhost only
uvicorn api.main:app --host 127.0.0.1 --port 8003 --workers 2 &
UVICORN_PID=$!

cleanup() {
  kill -TERM "$UVICORN_PID" 2>/dev/null || true
  kill -TERM "$NGINX_PID" 2>/dev/null || true
  wait "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
}

trap cleanup TERM INT

# Start NGINX in foreground
nginx -g 'daemon off;' &
NGINX_PID=$!

# Exit if either process dies
wait -n "$UVICORN_PID" "$NGINX_PID"
STATUS=$?
cleanup
exit "$STATUS"
