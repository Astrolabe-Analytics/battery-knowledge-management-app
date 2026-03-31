#!/usr/bin/env bash
# Create the S3 bucket in LocalStack for local S3 development testing.
#
# Run after: docker compose --profile s3 up -d
#
# Then enable S3 mode in .env:
#   PAPERS_STORAGE=s3
#   AWS_ENDPOINT=http://localhost:4566
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
echo "Done. To enable S3 mode in .env:"
echo "  PAPERS_STORAGE=s3"
echo "  AWS_ENDPOINT=$ENDPOINT"
echo ""
echo "Then restart the API: docker compose restart api"
