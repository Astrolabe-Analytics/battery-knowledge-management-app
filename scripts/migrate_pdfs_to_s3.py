#!/usr/bin/env python3
"""
Migrate PDFs from the local papers/ directory to S3.

Idempotent — skips files that already exist in S3. Safe to run multiple times.

Usage:
    python scripts/migrate_pdfs_to_s3.py --dry-run          # Preview (safe, default)
    python scripts/migrate_pdfs_to_s3.py --write             # Execute
    python scripts/migrate_pdfs_to_s3.py --source-dir /path  # Alternate source

Environment:
    PAPERS_S3_BUCKET  — target bucket (default: astrolabe-datalake)
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview what would be uploaded (default)",
    )
    parser.add_argument("--write", action="store_true", help="Execute the migration")
    parser.add_argument(
        "--source-dir", default="papers", help="Local PDF directory (default: papers)"
    )
    args = parser.parse_args()

    dry_run = not args.write
    source_dir = Path(args.source_dir)

    if not source_dir.exists():
        print(
            f"ERROR: Source directory '{source_dir}' does not exist.", file=sys.stderr
        )
        sys.exit(1)

    import boto3
    from botocore.exceptions import ClientError

    bucket = os.environ.get("PAPERS_S3_BUCKET", "astrolabe-datalake")
    endpoint_url = os.environ.get("AWS_ENDPOINT") or None
    region = os.environ.get("AWS_REGION", "us-west-2")
    profile = os.environ.get("AWS_PROFILE", "<default>")

    s3 = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)
    sts = boto3.client("sts", endpoint_url=endpoint_url, region_name=region)

    print("Migration preflight:")
    print(f"  Bucket: {bucket}")
    print(f"  Region: {region}")
    print(f"  AWS profile: {profile}")
    print(f"  AWS endpoint override: {endpoint_url or '<none>'}")
    print(
        f"  Target mode: {'LocalStack/custom endpoint' if endpoint_url else 'Production AWS S3'}"
    )

    try:
        ident = sts.get_caller_identity()
        print(f"  AWS account: {ident['Account']}")
        print(f"  AWS ARN: {ident['Arn']}")
    except Exception as e:
        print(f"ERROR: Unable to resolve AWS caller identity: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        location = (
            s3.get_bucket_location(Bucket=bucket).get("LocationConstraint")
            or "us-east-1"
        )
        print(f"  Bucket region: {location}")
    except Exception as e:
        print(
            f"ERROR: Unable to read bucket location for {bucket}: {e}", file=sys.stderr
        )
        sys.exit(1)

    try:
        s3.list_objects_v2(Bucket=bucket, Prefix="papers/", MaxKeys=1)
        print("  Bucket access: OK")
    except Exception as e:
        print(f"ERROR: Unable to access s3://{bucket}/papers/: {e}", file=sys.stderr)
        sys.exit(1)

    if not dry_run:
        write_test_key = "papers/.write-test"
        try:
            s3.put_object(
                Bucket=bucket,
                Key=write_test_key,
                Body=b"",
                ContentType="application/octet-stream",
            )
            s3.delete_object(Bucket=bucket, Key=write_test_key)
            print("  Write test: OK")
        except Exception as e:
            print(
                f"ERROR: Write test failed for s3://{bucket}/{write_test_key}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    print()

    pdfs = sorted(source_dir.glob("*.pdf"))
    total = len(pdfs)
    print(
        f"{'DRY RUN — ' if dry_run else ''}Migrating {total} PDFs from {source_dir}/ "
        f"→ s3://{bucket}/papers/"
    )
    print()

    uploaded = skipped = upload_failed = verify_failed = 0
    uploaded_bytes = 0
    failed_files = []
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
                upload_failed += 1
                failed_files.append((filename, f"check failed: {e}"))
                continue

        size_mb = pdf_path.stat().st_size / 1_000_000
        size_bytes = pdf_path.stat().st_size
        if dry_run:
            print(f"{prefix} WOULD UPLOAD  ({size_mb:.1f} MB)  {filename}")
            uploaded += 1
            uploaded_bytes += size_bytes
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
                uploaded_bytes += size_bytes
            except Exception as e:
                print(f"{prefix} FAILED  {filename}: {e}")
                upload_failed += 1
                failed_files.append((filename, str(e)))
                continue

        if not dry_run:
            try:
                s3.head_object(Bucket=bucket, Key=key)
            except Exception as e:
                print(f"{prefix} VERIFY FAILED  {filename}: {e}")
                verify_failed += 1
                failed_files.append((filename, f"verify failed after upload: {e}"))

    elapsed = time.time() - start
    print()
    print(f"{'DRY RUN ' if dry_run else ''}Summary ({elapsed:.1f}s):")
    print(f"  {'Would upload' if dry_run else 'Uploaded'}: {uploaded}")
    print(f"  Skipped (already in S3): {skipped}")
    print(f"  Upload failed: {upload_failed}")
    print(f"  Verify failed: {verify_failed}")
    print(
        f"  {'Would transfer' if dry_run else 'Transferred'}: {uploaded_bytes / 1_000_000_000:.2f} GB"
    )

    if failed_files:
        print()
        print("Failure details:")
        for filename, reason in failed_files[:20]:
            print(f"  {filename}: {reason}")
        if len(failed_files) > 20:
            print(f"  ... and {len(failed_files) - 20} more")

    if not dry_run and uploaded > 0:
        print(
            "  Note: if an API instance is already running with PAPERS_STORAGE=s3, restart it after migration to refresh any in-memory PDF cache."
        )

    if dry_run and (uploaded + skipped) > 0:
        print()
        cmd = f"python {__file__} --write"
        if args.source_dir != "papers":
            cmd += f" --source-dir {args.source_dir}"
        print(f"Run with --write to execute:  {cmd}")

    sys.exit(1 if (upload_failed or verify_failed) else 0)


if __name__ == "__main__":
    main()
