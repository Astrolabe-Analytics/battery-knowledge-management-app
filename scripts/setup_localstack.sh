#!/usr/bin/env bash
# Create the S3 bucket in LocalStack for local S3 development testing.
#
# Run after: docker compose --profile s3 up -d
#
# Then enable S3 mode in .env (LOCAL DEV ONLY):
#   PAPERS_STORAGE=s3
#   AWS_ENDPOINT=http://host.docker.internal:4566  # if API runs in Docker Compose
#   AWS_ENDPOINT=http://localhost:4566              # if API runs on host
#   AWS_ACCESS_KEY_ID=test
#   AWS_SECRET_ACCESS_KEY=test
# In staging/production ECS: DO NOT set AWS_ENDPOINT/AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY.
# And restart: docker compose restart api

set -e

BUCKET="${PAPERS_S3_BUCKET:-astrolabe-knowledge-pdfs}"
ENDPOINT="${AWS_ENDPOINT:-http://localhost:4566}"

echo "Creating S3 bucket '$BUCKET' at $ENDPOINT ..."

aws --endpoint-url="$ENDPOINT" --region us-east-1 \
    s3 mb "s3://$BUCKET" 2>/dev/null \
  && echo "Bucket created." \
  || echo "Bucket already exists — skipping."

echo ""
echo "Done. To enable S3 mode in .env (LOCAL DEV ONLY):"
echo "  PAPERS_STORAGE=s3"
echo "  AWS_ENDPOINT=http://host.docker.internal:4566   # API in Docker Compose"
echo "  AWS_ENDPOINT=http://localhost:4566               # API on host"
echo "  AWS_ACCESS_KEY_ID=test"
echo "  AWS_SECRET_ACCESS_KEY=test"
echo ""
echo "Do NOT set AWS_ENDPOINT/AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY in staging/production ECS."
echo "Then restart the API: docker compose restart api"
