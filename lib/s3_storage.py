"""PDF storage abstraction — local filesystem (dev) or S3 (production / LocalStack).

Set PAPERS_STORAGE=s3 to enable S3 mode. Leave unset or set to 'local' for
filesystem mode (default).

S3 configuration:
  PAPERS_S3_BUCKET  — bucket name (default: astrolabe-datalake)
  AWS_ENDPOINT      — override for LocalStack e.g. http://localhost:4566
  AWS_REGION        — AWS region (default: us-west-2)
"""

import os
import time
import threading
from pathlib import Path

_LOCAL_PAPERS_DIR = Path("papers")

# Cached set of S3 PDF filenames — avoids per-request head_object for batch status checks
_pdf_set_cache: dict = {"data": None, "ts": 0.0}
_PDF_SET_TTL = 60  # seconds
_cache_lock = threading.Lock()


def is_s3_mode() -> bool:
    return os.environ.get("PAPERS_STORAGE") == "s3"


def _s3():
    import boto3
    endpoint_url = os.environ.get("AWS_ENDPOINT") or None
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=os.environ.get("AWS_REGION", "us-west-2"),
    )


def _bucket() -> str:
    return os.environ.get("PAPERS_S3_BUCKET", "astrolabe-datalake")


def _get_cached_pdf_set() -> set[str]:
    """Return a cached set of all PDF filenames in S3 (refreshed every 60s).

    Used to avoid N head_object calls when computing status for a list of papers.
    """
    now = time.time()
    if _pdf_set_cache["data"] is not None and (now - _pdf_set_cache["ts"]) < _PDF_SET_TTL:
        return _pdf_set_cache["data"]
    with _cache_lock:
        now = time.time()
        if _pdf_set_cache["data"] is not None and (now - _pdf_set_cache["ts"]) < _PDF_SET_TTL:
            return _pdf_set_cache["data"]
        pdfs = set(list_all_pdfs())
        _pdf_set_cache["data"] = pdfs
        _pdf_set_cache["ts"] = now
    return pdfs


def invalidate_pdf_cache() -> None:
    """Invalidate the PDF cache — call after uploading new files to S3."""
    with _cache_lock:
        _pdf_set_cache["data"] = None
        _pdf_set_cache["ts"] = 0.0


def pdf_exists(filename: str) -> bool:
    """Check whether a PDF file exists in local storage or S3."""
    if not is_s3_mode():
        return (_LOCAL_PAPERS_DIR / filename).exists()
    return filename in _get_cached_pdf_set()


def save_pdf(filename: str, content: bytes) -> None:
    """Save a newly imported PDF.

    Always writes to the local papers/ directory so the ingestion pipeline
    (which reads from there) can process it immediately.

    When PAPERS_STORAGE=s3, also uploads to S3 and invalidates the PDF cache.
    """
    _LOCAL_PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    (_LOCAL_PAPERS_DIR / filename).write_bytes(content)
    if is_s3_mode():
        _s3().put_object(
            Bucket=_bucket(),
            Key=f"papers/{filename}",
            Body=content,
            ContentType="application/pdf",
        )
        invalidate_pdf_cache()


def get_presigned_url(filename: str, expires_in: int = 3600) -> str:
    """Generate a presigned GET URL for a PDF stored in S3 (valid for 1 hour by default)."""
    return _s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": f"papers/{filename}"},
        ExpiresIn=expires_in,
    )


def get_pdf_bytes(filename: str) -> bytes:
    """Read PDF bytes from local storage or S3."""
    if not is_s3_mode():
        return (_LOCAL_PAPERS_DIR / filename).read_bytes()
    resp = _s3().get_object(Bucket=_bucket(), Key=f"papers/{filename}")
    return resp["Body"].read()


def list_all_pdfs() -> list[str]:
    """List all PDF filenames in local storage or S3."""
    if not is_s3_mode():
        if not _LOCAL_PAPERS_DIR.exists():
            return []
        return [p.name for p in _LOCAL_PAPERS_DIR.glob("*.pdf")]
    paginator = _s3().get_paginator("list_objects_v2")
    filenames = []
    for page in paginator.paginate(Bucket=_bucket(), Prefix="papers/"):
        for obj in page.get("Contents", []):
            fname = obj["Key"].removeprefix("papers/")
            if fname:
                filenames.append(fname)
    return filenames
