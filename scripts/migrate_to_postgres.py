#!/usr/bin/env python3
"""
Migrate all data stores into PostgreSQL.

Sources:
  - data/metadata.json     -> papers + paper_references
  - data/chroma_db/        -> chunks  (text + embeddings)
  - data/read_status.db    -> papers.is_read, papers.read_marked_date
  - data/collections.db    -> collections + collection_items
  - data/query_history.db  -> query_history
  - data/settings.json     -> settings

Usage:
    python scripts/migrate_to_postgres.py              # full migration
    python scripts/migrate_to_postgres.py --dry-run    # report counts, don't write
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

# ── Postgres ──────────────────────────────────────────────────────────────────
from lib.db import engine, get_session, create_all_tables, check_connection
from lib.models import (
    Base,
    Paper,
    PaperReference,
    Chunk,
    Collection,
    CollectionItem,
    QueryHistory,
    Setting,
)
from sqlalchemy import text


# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR       = PROJECT_ROOT / "data"
METADATA_FILE  = DATA_DIR / "metadata.json"
CHROMA_DIR     = DATA_DIR / "chroma_db"
READ_STATUS_DB = DATA_DIR / "read_status.db"
COLLECTIONS_DB = DATA_DIR / "collections.db"
HISTORY_DB     = DATA_DIR / "query_history.db"
SETTINGS_FILE  = DATA_DIR / "settings.json"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(val) -> datetime | None:
    """Flexible ISO-ish date parsing. Returns timezone-aware UTC datetime or None."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
    try:
        dt = datetime.fromisoformat(str(val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        pass
    # Try common date-only formats
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y"):
        try:
            dt = datetime.strptime(str(val), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _ensure_list(val) -> list:
    """Normalise a value into a list[str] suitable for JSONB."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [x.strip() for x in val.replace(";", ",").split(",") if x.strip()]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# 1. Papers + References  (metadata.json)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_papers(session, dry_run=False) -> int:
    """Migrate metadata.json -> papers + paper_references."""
    if not METADATA_FILE.exists():
        print("  ⚠ metadata.json not found - skipping papers")
        return 0

    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # Load read statuses
    read_map: dict[str, tuple[bool, str | None]] = {}
    if READ_STATUS_DB.exists():
        conn = sqlite3.connect(str(READ_STATUS_DB))
        cur = conn.cursor()
        try:
            cur.execute("SELECT filename, is_read, marked_date FROM read_status")
            for row in cur.fetchall():
                read_map[row[0]] = (bool(row[1]), row[2])
        except sqlite3.OperationalError:
            pass
        conn.close()

    count = 0
    for filename, meta in metadata.items():
        if dry_run:
            count += 1
            continue

        is_read, read_date = read_map.get(filename, (False, None))

        paper = Paper(
            filename=filename,
            title=meta.get("title", ""),
            authors=_ensure_list(meta.get("authors")),
            year=str(meta.get("year", "")),
            journal=meta.get("journal", ""),
            doi=meta.get("doi", ""),
            abstract=meta.get("abstract", ""),
            volume=meta.get("volume", ""),
            issue=meta.get("issue", ""),
            pages=meta.get("pages", ""),
            author_keywords=_ensure_list(meta.get("author_keywords")),
            chemistries=_ensure_list(meta.get("chemistries")),
            topics=_ensure_list(meta.get("topics")),
            application=meta.get("application", "general"),
            paper_type=meta.get("paper_type", "Experimental"),
            source_url=meta.get("source_url", ""),
            pdf_status=meta.get("pdf_status", ""),
            metadata_only=meta.get("metadata_only", False),
            metadata_incomplete=meta.get("metadata_incomplete", False),
            crossref_verified=meta.get("crossref_verified", False),
            needs_processing=meta.get("needs_processing", False),
            pdf_source=meta.get("pdf_source", ""),
            pdf_found_date=_parse_date(meta.get("pdf_found_date")),
            extracted_at=_parse_date(meta.get("extracted_at")),
            feed_blurb=meta.get("feed_blurb", ""),
            ai_summary=meta.get("ai_summary", ""),
            summary_generated_at=_parse_date(meta.get("summary_generated_at")),
            summary_model=meta.get("summary_model", ""),
            notes=meta.get("notes", ""),
            is_read=is_read,
            read_marked_date=_parse_date(read_date),
            date_added=_parse_date(meta.get("date_added")) or datetime.now(timezone.utc),
            deleted_at=_parse_date(meta.get("deleted_at")),
        )
        session.add(paper)

        # References
        refs = meta.get("references", [])
        if isinstance(refs, list):
            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                paper_ref = PaperReference(
                    paper_filename=filename,
                    ref_key=ref.get("key", ""),
                    doi=ref.get("DOI", ""),
                    doi_asserted_by=ref.get("doi-asserted-by", ""),
                    article_title=ref.get("article-title", ""),
                    author=ref.get("author", ""),
                    year=ref.get("year", ""),
                    journal_title=ref.get("journal-title", ""),
                    volume=ref.get("volume", ""),
                    first_page=ref.get("first-page", ""),
                )
                session.add(paper_ref)

        count += 1

        # Flush in batches of 200 to keep memory reasonable
        if count % 200 == 0:
            session.flush()
            print(f"    ... {count} papers flushed")

    if not dry_run:
        session.flush()
    print(f"  ✓ Papers: {count} (+ references)")
    return count


# ─────────────────────────────────────────────────────────────────────────────
# 2. Chunks  (ChromaDB -> chunks table)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_chunks(session, dry_run=False) -> int:
    """Migrate ChromaDB collection -> chunks table."""
    if not CHROMA_DIR.exists():
        print("  ⚠ chroma_db not found - skipping chunks")
        return 0

    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        collection = client.get_collection(name="battery_papers")
    except Exception as e:
        print(f"  ⚠ ChromaDB collection not found: {e}")
        return 0

    # Get all papers currently in the papers table (to skip orphans)
    paper_filenames_in_db = set()
    if not dry_run:
        from sqlalchemy import select
        rows = session.execute(select(Paper.filename)).all()
        paper_filenames_in_db = {r[0] for r in rows}

    total = collection.count()
    print(f"  ChromaDB has {total} chunks total")

    # Fetch in batches to avoid OOM
    BATCH = 1000
    count = 0
    skipped = 0

    for offset in range(0, total, BATCH):
        results = collection.get(
            include=["documents", "metadatas", "embeddings"],
            limit=BATCH,
            offset=offset,
        )
        for doc_id, doc_text, meta, emb in zip(
            results["ids"],
            results["documents"],
            results["metadatas"],
            results["embeddings"],
        ):
            paper_fn = meta.get("filename", "")

            # Skip chunks for papers that weren't in metadata.json
            if not dry_run and paper_fn not in paper_filenames_in_db:
                skipped += 1
                continue

            if dry_run:
                count += 1
                continue

            chunk = Chunk(
                id=doc_id,
                paper_filename=paper_fn,
                page_num=int(meta.get("page_num", 0)),
                chunk_index=int(meta.get("chunk_index", 0)),
                token_count=int(meta.get("token_count", 0)),
                section_name=meta.get("section_name", "Content"),
                content=doc_text or "",
                embedding=list(emb) if emb is not None else None,
            )
            session.add(chunk)
            count += 1

        if not dry_run:
            session.flush()
        print(f"    ... {offset + len(results['ids'])} / {total} processed ({skipped} orphans skipped)")

    print(f"  ✓ Chunks: {count} migrated, {skipped} orphans skipped")
    return count


# ─────────────────────────────────────────────────────────────────────────────
# 3. Collections  (collections.db -> collections + collection_items)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_collections(session, dry_run=False) -> int:
    """Migrate collections.db -> collections + collection_items."""
    if not COLLECTIONS_DB.exists():
        print("  ⚠ collections.db not found - skipping collections")
        return 0

    conn = sqlite3.connect(str(COLLECTIONS_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Collections
    try:
        cur.execute("SELECT id, name, color, description, created_date, modified_date FROM collections ORDER BY id")
    except sqlite3.OperationalError:
        print("  ⚠ collections table doesn't exist")
        conn.close()
        return 0

    id_map = {}  # old_id -> new Collection object
    count = 0

    for row in cur.fetchall():
        if dry_run:
            count += 1
            continue
        coll = Collection(
            name=row["name"],
            color=row["color"] or "#6c757d",
            description=row["description"] or "",
            created_date=_parse_date(row["created_date"]) or datetime.now(timezone.utc),
            modified_date=_parse_date(row["modified_date"]) or datetime.now(timezone.utc),
        )
        session.add(coll)
        session.flush()  # get the new auto-incremented id
        id_map[row["id"]] = coll
        count += 1

    # Collection items
    items_count = 0
    try:
        cur.execute("SELECT collection_id, filename, added_date FROM collection_items")
    except sqlite3.OperationalError:
        cur.close()
        conn.close()
        print(f"  ✓ Collections: {count}, Items: 0")
        return count

    for row in cur.fetchall():
        if dry_run:
            items_count += 1
            continue
        coll_obj = id_map.get(row["collection_id"])
        if coll_obj is None:
            continue
        item = CollectionItem(
            collection_id=coll_obj.id,
            paper_filename=row["filename"],
            added_date=_parse_date(row["added_date"]) or datetime.now(timezone.utc),
        )
        session.add(item)
        items_count += 1

    if not dry_run:
        session.flush()
    conn.close()

    print(f"  ✓ Collections: {count}, Items: {items_count}")
    return count


# ─────────────────────────────────────────────────────────────────────────────
# 4. Query History  (query_history.db -> query_history)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_query_history(session, dry_run=False) -> int:
    """Migrate query_history.db -> query_history."""
    if not HISTORY_DB.exists():
        print("  ⚠ query_history.db not found - skipping history")
        return 0

    conn = sqlite3.connect(str(HISTORY_DB))
    cur = conn.cursor()

    try:
        cur.execute("SELECT id, timestamp, question, answer, chunks, filters, is_starred, created_at FROM query_history ORDER BY id")
    except sqlite3.OperationalError:
        print("  ⚠ query_history table doesn't exist")
        conn.close()
        return 0

    count = 0
    for row in cur.fetchall():
        if dry_run:
            count += 1
            continue

        chunks_data = []
        try:
            chunks_data = json.loads(row[4]) if row[4] else []
        except (json.JSONDecodeError, TypeError):
            pass

        filters_data = {}
        try:
            filters_data = json.loads(row[5]) if row[5] else {}
        except (json.JSONDecodeError, TypeError):
            pass

        qh = QueryHistory(
            timestamp=_parse_date(row[1]) or datetime.now(timezone.utc),
            question=row[2] or "",
            answer=row[3] or "",
            chunks_json=chunks_data,
            filters_json=filters_data,
            is_starred=bool(row[6]),
            created_at=_parse_date(row[7]) or datetime.now(timezone.utc),
        )
        session.add(qh)
        count += 1

    if not dry_run:
        session.flush()
    conn.close()

    print(f"  ✓ Query history: {count}")
    return count


# ─────────────────────────────────────────────────────────────────────────────
# 5. Settings  (settings.json -> settings)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_settings(session, dry_run=False) -> int:
    """Migrate settings.json -> settings table."""
    if not SETTINGS_FILE.exists():
        print("  ⚠ settings.json not found - skipping settings")
        return 0

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)

    count = 0
    for key, value in settings.items():
        if dry_run:
            count += 1
            continue
        s = Setting(key=key, value=value)
        session.add(s)
        count += 1

    if not dry_run:
        session.flush()
    print(f"  ✓ Settings: {count}")
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_migration(dry_run=False):
    """Run the full migration."""
    print("=" * 60)
    print("  Astrolabe → PostgreSQL Migration")
    print("=" * 60)

    if dry_run:
        print("  MODE: DRY RUN (no data will be written)\n")
    else:
        print("  MODE: LIVE MIGRATION\n")

    # Check connection
    print("Checking PostgreSQL connection...")
    if not check_connection():
        print("  ✗ Cannot connect to PostgreSQL. Is it running?")
        sys.exit(1)
    print("  ✓ Connected\n")

    # Create / ensure tables
    print("Creating tables...")
    create_all_tables()
    print("  ✓ Tables ready\n")

    # If live, clear existing data (idempotent re-run)
    if not dry_run:
        print("Clearing existing data for clean migration...")
        with engine.connect() as conn:
            # Truncate in dependency order
            for table in [
                "collection_items",
                "paper_references",
                "chunks",
                "collections",
                "query_history",
                "settings",
                "papers",
            ]:
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            conn.commit()
        print("  ✓ Tables truncated\n")

    t0 = time.time()

    with get_session() as session:
        print("1/5  Migrating papers + references...")
        papers_count = migrate_papers(session, dry_run)

        print("\n2/5  Migrating chunks (ChromaDB → Postgres)...")
        chunks_count = migrate_chunks(session, dry_run)

        print("\n3/5  Migrating collections...")
        collections_count = migrate_collections(session, dry_run)

        print("\n4/5  Migrating query history...")
        history_count = migrate_query_history(session, dry_run)

        print("\n5/5  Migrating settings...")
        settings_count = migrate_settings(session, dry_run)

    elapsed = time.time() - t0

    print("\n" + "=" * 60)
    print(f"  Migration complete in {elapsed:.1f}s")
    print(f"  Papers:       {papers_count}")
    print(f"  Chunks:       {chunks_count}")
    print(f"  Collections:  {collections_count}")
    print(f"  History:      {history_count}")
    print(f"  Settings:     {settings_count}")
    print("=" * 60)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run_migration(dry_run=dry)
