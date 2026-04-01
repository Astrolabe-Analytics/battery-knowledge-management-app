#!/usr/bin/env python3
"""Fix two orphaned Elsevier PDFs in the paper catalog.

Default mode is dry-run. Use --write to apply changes.

Operations:
1) Rename legacy metadata-only row for DOI 10.1016/j.etran.2024.100340
   from url_8e5b57cb.pdf -> 1-s2.0-S2590116824000304-main.pdf while preserving
   references and avoiding duplicate DOI rows.
2) Insert metadata-only row for DOI 10.1016/j.est.2023.107745 with filename
   1-s2.0-S2352152X23011428-main.pdf if not present.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy import func

from lib.db import get_session
from lib.models import Chunk, CollectionItem, Paper, PaperReference

EXISTING_DOI = "10.1016/j.etran.2024.100340"
MISSING_DOI = "10.1016/j.est.2023.107745"

OLD_FILENAME = "url_8e5b57cb.pdf"
EXISTING_TARGET_FILENAME = "1-s2.0-S2590116824000304-main.pdf"
MISSING_TARGET_FILENAME = "1-s2.0-S2352152X23011428-main.pdf"


def fetch_crossref_metadata(doi: str) -> dict[str, Any]:
    url = f"https://api.crossref.org/works/{doi}"
    headers = {
        "User-Agent": "AstrolabeLibrary/1.0 (mailto:research@astrolabe-analytics.com)"
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    message = response.json().get("message", {})

    authors: list[str] = []
    for a in message.get("author", []):
        given = (a.get("given") or "").strip()
        family = (a.get("family") or "").strip()
        if family:
            authors.append(f"{family}, {given}" if given else family)

    year = ""
    published = message.get("published-print") or message.get("published-online")
    if published and published.get("date-parts") and published["date-parts"][0]:
        year = str(published["date-parts"][0][0])

    return {
        "title": (message.get("title") or [""])[0],
        "authors": authors[:15],
        "year": year,
        "journal": (message.get("container-title") or [""])[0],
        "abstract": message.get("abstract") or "",
        "volume": message.get("volume") or "",
        "issue": message.get("issue") or "",
        "pages": message.get("page") or "",
    }


def print_counts(session) -> None:
    doi_rows = (
        session.query(Paper.doi, func.count(Paper.filename))
        .filter(Paper.deleted_at.is_(None))
        .filter(func.lower(Paper.doi).in_([EXISTING_DOI.lower(), MISSING_DOI.lower()]))
        .group_by(Paper.doi)
        .all()
    )
    print("DOI row counts (non-deleted):")
    if not doi_rows:
        print("  - none")
    for doi, count in doi_rows:
        print(f"  - {doi}: {count}")

    print("Filename presence (non-deleted):")
    for fn in [OLD_FILENAME, EXISTING_TARGET_FILENAME, MISSING_TARGET_FILENAME]:
        exists = (
            session.query(Paper)
            .filter(Paper.filename == fn)
            .filter(Paper.deleted_at.is_(None))
            .first()
            is not None
        )
        print(f"  - {fn}: {'present' if exists else 'missing'}")


def apply_changes(write: bool) -> int:
    metadata = fetch_crossref_metadata(MISSING_DOI)
    if not metadata.get("title"):
        raise RuntimeError(
            "CrossRef metadata precheck failed: title missing for missing DOI"
        )

    with get_session() as session:
        print("\nPre-change snapshot")
        print_counts(session)

        old_row = session.query(Paper).filter(Paper.filename == OLD_FILENAME).first()
        existing_target = (
            session.query(Paper)
            .filter(Paper.filename == EXISTING_TARGET_FILENAME)
            .first()
        )

        existing_doi_rows = (
            session.query(Paper)
            .filter(Paper.deleted_at.is_(None))
            .filter(func.lower(Paper.doi) == EXISTING_DOI.lower())
            .all()
        )
        missing_doi_rows = (
            session.query(Paper)
            .filter(Paper.deleted_at.is_(None))
            .filter(func.lower(Paper.doi) == MISSING_DOI.lower())
            .all()
        )

        if len(existing_doi_rows) > 1:
            raise RuntimeError(
                f"Aborting: existing DOI already has {len(existing_doi_rows)} rows"
            )
        if len(missing_doi_rows) > 1:
            raise RuntimeError(
                f"Aborting: missing DOI already has {len(missing_doi_rows)} rows"
            )

        refs_count = (
            session.query(func.count(PaperReference.id))
            .filter(PaperReference.paper_filename == OLD_FILENAME)
            .scalar()
            or 0
        )
        chunks_count = (
            session.query(func.count(Chunk.id))
            .filter(Chunk.paper_filename == OLD_FILENAME)
            .scalar()
            or 0
        )
        coll_count = (
            session.query(func.count(CollectionItem.id))
            .filter(CollectionItem.paper_filename == OLD_FILENAME)
            .scalar()
            or 0
        )
        print("\nDependency counts for legacy filename:")
        print(f"  - paper_references: {refs_count}")
        print(f"  - chunks: {chunks_count}")
        print(f"  - collection_items: {coll_count}")

        actions: list[str] = []

        # 1) Rename legacy row by clone+rewire+delete (FK-safe for non-cascading update constraints)
        if old_row and not existing_target:
            actions.append(
                f"rename row {OLD_FILENAME} -> {EXISTING_TARGET_FILENAME} for DOI {EXISTING_DOI}"
            )
            if write:
                old_paper_id = old_row.paper_id
                old_row.paper_id = None
                session.flush()

                new_row = Paper()
                for col in Paper.__table__.columns:
                    if col.name in {"filename", "paper_id"}:
                        continue
                    setattr(new_row, col.name, getattr(old_row, col.name))
                new_row.filename = EXISTING_TARGET_FILENAME
                new_row.paper_id = old_paper_id or f"doi:{EXISTING_DOI}"
                session.add(new_row)
                session.flush()

                session.query(PaperReference).filter(
                    PaperReference.paper_filename == OLD_FILENAME
                ).update(
                    {"paper_filename": EXISTING_TARGET_FILENAME},
                    synchronize_session=False,
                )
                session.query(Chunk).filter(
                    Chunk.paper_filename == OLD_FILENAME
                ).update(
                    {"paper_filename": EXISTING_TARGET_FILENAME},
                    synchronize_session=False,
                )
                session.query(CollectionItem).filter(
                    CollectionItem.paper_filename == OLD_FILENAME
                ).update(
                    {"paper_filename": EXISTING_TARGET_FILENAME},
                    synchronize_session=False,
                )
                # Delete with a direct query to avoid ORM delete-orphan cascade
                # from relationship bookkeeping on the old object.
                session.query(Paper).filter(Paper.filename == OLD_FILENAME).delete(
                    synchronize_session=False
                )
        elif old_row and existing_target:
            actions.append("skip rename: both old and target filenames already exist")
        else:
            actions.append("skip rename: legacy row not present")

        # 2) Insert missing DOI row if absent
        missing_filename_row = (
            session.query(Paper)
            .filter(Paper.filename == MISSING_TARGET_FILENAME)
            .filter(Paper.deleted_at.is_(None))
            .first()
        )
        missing_doi_row = (
            session.query(Paper)
            .filter(Paper.deleted_at.is_(None))
            .filter(func.lower(Paper.doi) == MISSING_DOI.lower())
            .first()
        )

        if not missing_filename_row and not missing_doi_row:
            actions.append(
                f"insert metadata-only row {MISSING_TARGET_FILENAME} for DOI {MISSING_DOI}"
            )
            if write:
                session.add(
                    Paper(
                        filename=MISSING_TARGET_FILENAME,
                        paper_id=f"doi:{MISSING_DOI}",
                        title=metadata.get("title") or "",
                        authors=metadata.get("authors") or [],
                        year=metadata.get("year") or "",
                        journal=metadata.get("journal") or "",
                        doi=MISSING_DOI,
                        abstract=metadata.get("abstract") or "",
                        volume=metadata.get("volume") or "",
                        issue=metadata.get("issue") or "",
                        pages=metadata.get("pages") or "",
                        metadata_only=True,
                        pdf_status="",
                        crossref_verified=True,
                        date_added=datetime.now(timezone.utc),
                    )
                )
        else:
            actions.append(
                "skip insert: missing DOI already present by DOI or filename"
            )

        print("\nPlanned actions:")
        for action in actions:
            print(f"  - {action}")

        if not write:
            session.rollback()
            print("\nDry run complete. No changes were written.")
            return 0

        # Ensure inserts/updates/deletes are applied before verification queries.
        session.flush()

        # Verification
        existing_after = (
            session.query(Paper)
            .filter(Paper.deleted_at.is_(None))
            .filter(func.lower(Paper.doi) == EXISTING_DOI.lower())
            .all()
        )
        missing_after = (
            session.query(Paper)
            .filter(Paper.deleted_at.is_(None))
            .filter(func.lower(Paper.doi) == MISSING_DOI.lower())
            .all()
        )

        if len(existing_after) != 1:
            raise RuntimeError(
                f"Post-check failed: expected 1 row for {EXISTING_DOI}, got {len(existing_after)}"
            )
        if len(missing_after) != 1:
            raise RuntimeError(
                f"Post-check failed: expected 1 row for {MISSING_DOI}, got {len(missing_after)}"
            )

        print("\nPost-change snapshot")
        print_counts(session)
        print("\nWrite complete.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fix orphaned Elsevier PDFs in paper catalog"
    )
    parser.add_argument(
        "--write", action="store_true", help="Apply changes (default is dry-run)"
    )
    args = parser.parse_args()
    return apply_changes(write=args.write)


if __name__ == "__main__":
    raise SystemExit(main())
