#!/usr/bin/env python3
"""
Migrate PDFs from the local papers/ directory to S3.

Idempotent — skips files that already exist in S3. Safe to run multiple times.

Usage:
    python scripts/migrate_pdfs_to_s3.py --dry-run          # Preview (safe, default)
    python scripts/migrate_pdfs_to_s3.py --write             # Execute
    python scripts/migrate_pdfs_to_s3.py --source-dir /path  # Alternate source

Environment:
    PAPERS_S3_BUCKET  — target bucket (default: astrolabe-knowledge-pdfs)
    AWS_ENDPOINT      — override for LocalStack e.g. http://localhost:4566
    AWS_REGION        — AWS region (default: us-west-2)
    AWS_PROFILE       — AWS profile (e.g. astrolabe-ro for production reads)
"""

import argparse
import os
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Migrate PDFs to S3")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview what would be uploaded (default)")
    parser.add_argument("--write", action="store_true",
                        help="Execute the migration")
    parser.add_argument("--source-dir", default="papers",
                        help="Local PDF directory (default: papers)")
    args = parser.parse_args()

    dry_run = not args.write
    source_dir = Path(args.source_dir)

    if not source_dir.exists():
        print(f"ERROR: Source directory '{source_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    import boto3
    from botocore.exceptions import ClientError

    bucket = os.environ.get("PAPERS_S3_BUCKET", "astrolabe-knowledge-pdfs")
    endpoint_url = os.environ.get("AWS_ENDPOINT") or None
    region = os.environ.get("AWS_REGION", "us-west-2")

    s3 = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)

    pdfs = sorted(source_dir.glob("*.pdf"))
    total = len(pdfs)
    print(f"{'DRY RUN — ' if dry_run else ''}Migrating {total} PDFs from {source_dir}/ "
          f"→ s3://{bucket}/papers/")
    print()

    uploaded = skipped = failed = 0
    start = time.time()

    for i, pdf_path in enumerate(pdfs, 1):
        filename = pdf_path.name
        key = f"papers/{filename}"
        prefix = f"[{i:4}/{total}]"

        # Skip if already in S3
        try:
            s3.head_object(Bucket=bucket, Key=key)
            print(f"{prefix} SKIP  {filename}")
            skipped += 1
            continue
        except ClientError as e:
            if e.response["Error"]["Code"] != "404":
                print(f"{prefix} ERROR checking {filename}: {e}")
                failed += 1
                continue

        size_mb = pdf_path.stat().st_size / 1_000_000
        if dry_run:
            print(f"{prefix} WOULD UPLOAD  ({size_mb:.1f} MB)  {filename}")
            uploaded += 1
        else:
            try:
                content = pdf_path.read_bytes()
                s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    ContentType="application/pdf",
                )
                print(f"{prefix} UPLOADED  ({size_mb:.1f} MB)  {filename}")
                uploaded += 1
            except Exception as e:
                print(f"{prefix} FAILED  {filename}: {e}")
                failed += 1

    elapsed = time.time() - start
    print()
    print(f"{'DRY RUN ' if dry_run else ''}Summary ({elapsed:.1f}s):")
    print(f"  {'Would upload' if dry_run else 'Uploaded'}: {uploaded}")
    print(f"  Skipped (already in S3): {skipped}")
    print(f"  Failed: {failed}")

    if dry_run and (uploaded + skipped) > 0:
        print()
        cmd = f"python {__file__} --write"
        if args.source_dir != "papers":
            cmd += f" --source-dir {args.source_dir}"
        print(f"Run with --write to execute:  {cmd}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
