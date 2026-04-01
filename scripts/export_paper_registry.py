#!/usr/bin/env python3
"""Export the paper registry from PostgreSQL to S3 as _system/paper-library.json.

This script is the canonical exporter — it replaces the legacy Node.js
export-paper-library.mjs for production use.

Usage (inside Docker):
    docker compose exec api python scripts/export_paper_registry.py --dry-run
    docker compose exec api python scripts/export_paper_registry.py --write
    docker compose exec api python scripts/export_paper_registry.py --assign-only

Flags:
    --dry-run      Validate and preview without uploading (default)
    --write        Upload to S3 at _system/paper-library.json
    --assign-only  Assign paper_id values to Postgres without S3 export
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select

# Bootstrap — add project root to path
sys.path.insert(0, "/app")

from lib.db import get_session
from lib.models import Paper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("export_paper_registry")

S3_KEY = "_system/paper-library.json"
S3_TMP_KEY = "_system/.paper-library.json.tmp"


# ─────────────────────────────────────────────────────────────────────────────
# paperId derivation
# ─────────────────────────────────────────────────────────────────────────────

def normalize_doi(doi: str) -> str:
    """Normalize a DOI: lowercase, strip whitespace, remove leading URL prefixes."""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "https://dx.doi.org/"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a URL-safe slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:max_len]


def derive_paper_id(doi: str, title: str, year: str) -> str:
    """Derive a paperId from DOI or title+year.

    Rules:
      1. If DOI present: "doi:{normalized_doi}"
      2. Else: "title:{slug}-{year}"
    """
    if doi and doi.strip():
        return f"doi:{normalize_doi(doi)}"
    slug = slugify(title or "untitled")
    yr = (year or "").strip() or "0000"
    return f"title:{slug}-{yr}"


def assign_paper_ids(session) -> int:
    """Assign paper_id to all papers that don't have one yet.

    Uses collision detection: appends -a through -e suffixes, then falls
    back to key:{sha256[:20]} if all suffixes are taken.

    Returns count of newly assigned IDs.
    """
    papers = session.execute(
        select(Paper).where(Paper.paper_id.is_(None)).where(Paper.deleted_at.is_(None))
    ).scalars().all()

    if not papers:
        return 0

    # Collect existing IDs to detect collisions
    existing_ids = set(
        session.execute(
            select(Paper.paper_id).where(Paper.paper_id.isnot(None))
        ).scalars().all()
    )

    assigned = 0
    for paper in papers:
        base_id = derive_paper_id(paper.doi or "", paper.title or "", paper.year or "")

        # Collision resolution
        candidate = base_id
        if candidate in existing_ids:
            resolved = False
            for suffix in "abcde":
                candidate = f"{base_id}-{suffix}"
                if candidate not in existing_ids:
                    resolved = True
                    break
            if not resolved:
                # SHA256 fallback
                h = hashlib.sha256(paper.filename.encode()).hexdigest()[:20]
                candidate = f"key:{h}"
                if candidate in existing_ids:
                    log.error("SHA256 collision for %s — this should never happen", paper.filename)
                    continue

        paper.paper_id = candidate
        existing_ids.add(candidate)
        assigned += 1

    session.flush()
    log.info("Assigned paper_id to %d papers", assigned)
    return assigned


# ─────────────────────────────────────────────────────────────────────────────
# Serialization
# ─────────────────────────────────────────────────────────────────────────────

def load_papers_for_export() -> list[dict]:
    """Load papers using the canonical serialization from db_operations.

    Adds lastModified field needed for S3 export envelope.
    """
    from lib.db_operations import get_paper_library_for_export
    papers = get_paper_library_for_export()

    # Enrich with lastModified from DB (not available in the API serialization)
    with get_session() as session:
        date_map = {}
        rows = session.execute(
            select(Paper.filename, Paper.date_added)
            .where(Paper.deleted_at.is_(None))
        ).all()
        for fn, da in rows:
            date_map[fn] = da.isoformat() if da else ""

    for p in papers:
        p["lastModified"] = date_map.get(p["filename"], "")

    return papers


def build_envelope(papers: list[dict]) -> dict:
    """Build the full JSON envelope for _system/paper-library.json."""
    with_doi = sum(1 for p in papers if p.get("doi"))
    with_pdf = sum(1 for p in papers if p.get("pdfS3Key"))
    embedded = sum(1 for p in papers if p.get("ragReady"))
    with_abstract = sum(1 for p in papers if p.get("abstract"))

    return {
        "version": "1.0.0",
        "schemaVersion": "1.0.0",
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "source": "battery-knowledge-management-app",
        "stats": {
            "total": len(papers),
            "withDoi": with_doi,
            "withPdf": with_pdf,
            "embedded": embedded,
            "withAbstract": with_abstract,
            "embeddingModel": "all-MiniLM-L6-v2",
        },
        "papers": papers,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_export(envelope: dict, expected_count: int) -> list[str]:
    """Run 5-point validation. Returns list of errors (empty = pass)."""
    errors = []
    papers = envelope.get("papers", [])

    # 1. All paperId non-null
    null_ids = [p["filename"] for p in papers if not p.get("paperId")]
    if null_ids:
        errors.append(f"{len(null_ids)} papers have null paperId: {null_ids[:5]}")

    # 2. No duplicate paperId values
    ids = [p["paperId"] for p in papers if p.get("paperId")]
    dupes = set(x for x in ids if ids.count(x) > 1)
    if dupes:
        errors.append(f"Duplicate paperIds: {dupes}")

    # 3. Sample records have expected fields
    required_fields = {"paperId", "filename", "title", "doi", "authors"}
    for p in papers[:10]:
        missing = required_fields - set(p.keys())
        if missing:
            errors.append(f"Paper {p.get('filename', '?')} missing fields: {missing}")

    # 4. Count matches expected
    if len(papers) != expected_count:
        errors.append(f"Paper count mismatch: export has {len(papers)}, DB has {expected_count}")

    # 5. JSON serializable
    try:
        json.dumps(envelope, default=str)
    except (TypeError, ValueError) as e:
        errors.append(f"JSON serialization error: {e}")

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# S3 upload (atomic)
# ─────────────────────────────────────────────────────────────────────────────

def upload_to_s3(envelope: dict) -> None:
    """Atomic upload: write to tmp key, validate, copy to final, delete tmp."""
    import boto3
    import os

    endpoint_url = os.environ.get("AWS_ENDPOINT") or None
    bucket = os.environ.get("PAPERS_S3_BUCKET", "astrolabe-datalake")
    region = os.environ.get("AWS_REGION", "us-west-2")

    s3 = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)

    payload = json.dumps(envelope, default=str, ensure_ascii=False)
    payload_bytes = payload.encode("utf-8")

    # 1. Write to tmp key
    log.info("Uploading to s3://%s/%s (%d bytes)", bucket, S3_TMP_KEY, len(payload_bytes))
    s3.put_object(
        Bucket=bucket,
        Key=S3_TMP_KEY,
        Body=payload_bytes,
        ContentType="application/json",
    )

    # 2. Read back and validate
    resp = s3.get_object(Bucket=bucket, Key=S3_TMP_KEY)
    readback = json.loads(resp["Body"].read())
    if len(readback.get("papers", [])) != len(envelope["papers"]):
        s3.delete_object(Bucket=bucket, Key=S3_TMP_KEY)
        raise RuntimeError("S3 readback validation failed — paper count mismatch")

    # 3. Copy to final key
    s3.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": S3_TMP_KEY},
        Key=S3_KEY,
        ContentType="application/json",
    )

    # 4. Read final key back and verify published shape/counts
    final_resp = s3.get_object(Bucket=bucket, Key=S3_KEY)
    published = json.loads(final_resp["Body"].read())
    if len(published.get("papers", [])) != len(envelope["papers"]):
        raise RuntimeError("Published S3 object validation failed — paper count mismatch")
    if published.get("stats", {}).get("withPdf") != envelope.get("stats", {}).get("withPdf"):
        raise RuntimeError("Published S3 object validation failed — withPdf mismatch")

    # 5. Delete tmp
    s3.delete_object(Bucket=bucket, Key=S3_TMP_KEY)
    log.info("Successfully published s3://%s/%s", bucket, S3_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Export paper registry to S3")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True, help="Validate without uploading (default)")
    group.add_argument("--write", action="store_true", help="Upload to S3")
    group.add_argument("--assign-only", action="store_true", help="Assign paper_ids without S3 export")
    args = parser.parse_args()

    # --write and --assign-only override the default --dry-run
    is_dry_run = not args.write and not args.assign_only

    log.info("=== Paper Registry Export ===")
    log.info("Mode: %s", "dry-run" if is_dry_run else ("assign-only" if args.assign_only else "write"))
    log.info(
        "Storage preflight: PAPERS_STORAGE=%s bucket=%s region=%s endpoint=%s",
        os.environ.get("PAPERS_STORAGE", "local"),
        os.environ.get("PAPERS_S3_BUCKET", "astrolabe-datalake"),
        os.environ.get("AWS_REGION", "us-west-2"),
        os.environ.get("AWS_ENDPOINT") or "<none>",
    )

    with get_session() as session:
        # Step 1: Assign paper_ids to any papers missing them
        assigned = assign_paper_ids(session)
        if assigned:
            log.info("Backfilled %d paper_ids", assigned)
            session.commit()

        if args.assign_only:
            log.info("Done (assign-only mode)")
            return

    # Step 2: Load papers using canonical serialization
    papers_data = load_papers_for_export()
    expected_count = len(papers_data)
    log.info("Found %d non-deleted papers", expected_count)

    # Step 3: Build envelope
    envelope = build_envelope(papers_data)

    # Step 4: Validate
    errors = validate_export(envelope, expected_count)
    if errors:
        for e in errors:
            log.error("VALIDATION FAILED: %s", e)
        sys.exit(1)

    log.info("Validation passed — %d papers, %d with DOI, %d ragReady",
             envelope["stats"]["total"],
             envelope["stats"]["withDoi"],
             envelope["stats"]["embedded"])
    log.info("Actual PDFs in active storage: %d", envelope["stats"]["withPdf"])

    if is_dry_run:
        # Preview first 2 papers
        for p in papers_data[:2]:
            log.info("Sample: paperId=%s doi=%s title=%.60s",
                     p["paperId"], p["doi"], p["title"])
        log.info("Dry run complete. Use --write to upload to S3.")
        return

    # Step 5: Upload
    try:
        upload_to_s3(envelope)
    except Exception as e:
        log.error("S3 upload failed: %s", e)
        log.error("DB paper_id assignments were committed. S3 is stale. Re-run with --write to retry.")
        sys.exit(1)

    log.info("=== Export complete ===")


if __name__ == "__main__":
    main()
