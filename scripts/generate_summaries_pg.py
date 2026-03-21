"""
Batch AI Summary Generation — PostgreSQL-native.

Generates structured AI summaries and feed blurbs for papers that have
real PDF-extracted text chunks in the database. Skips metadata-only papers.

Usage:
    python scripts/generate_summaries_pg.py --limit 5 --dry-run
    python scripts/generate_summaries_pg.py --limit 50
    python scripts/generate_summaries_pg.py --blurbs-only
    python scripts/generate_summaries_pg.py --force   # regenerate existing

Requires: ANTHROPIC_API_KEY in .env or environment
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Fix Windows console encoding (cp1252 can't handle Unicode chars in paper titles)
if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import anthropic

from sqlalchemy import select, func, or_

from lib.db import get_session
from lib.models import Paper, Chunk

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUMMARY_MODEL = "claude-sonnet-4-5-20250929"
PROGRESS_FILE = Path("data/summary_progress.json")
SAVE_INTERVAL = 10  # save progress every N papers
MIN_REAL_CHUNKS = 3  # skip papers with fewer real chunks (URL stubs, etc.)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def get_papers_needing_summaries(force: bool = False) -> list[dict]:
    """Find papers with real PDF chunks (not metadata-only stubs) that lack AI summaries.

    Requires at least MIN_REAL_CHUNKS chunks to filter out URL-only stubs
    and papers that were imported without a real PDF.
    """
    with get_session() as session:
        # Subquery: papers that have enough real content chunks
        # (metadata_only/metadata sections are import-time placeholders, not PDF text)
        papers_with_chunks = (
            select(Chunk.paper_filename, func.count(Chunk.id).label("chunk_count"))
            .where(Chunk.section_name.notin_(["metadata_only", "metadata"]))
            .group_by(Chunk.paper_filename)
            .having(func.count(Chunk.id) >= MIN_REAL_CHUNKS)
            .subquery()
        )

        query = (
            select(Paper)
            .join(papers_with_chunks, Paper.filename == papers_with_chunks.c.paper_filename)
            .where(Paper.deleted_at.is_(None))
        )

        if not force:
            # Only papers without existing summaries
            query = query.where(
                or_(Paper.ai_summary.is_(None), Paper.ai_summary == "")
            )

        query = query.order_by(Paper.date_added.desc())
        papers = session.execute(query).scalars().all()

        results = []
        for p in papers:
            results.append({
                "filename": p.filename,
                "title": p.title or "",
                "authors": p.authors or [],
                "year": p.year or "",
                "journal": p.journal or "",
                "chemistries": p.chemistries or [],
                "ai_summary": p.ai_summary or "",
                "feed_blurb": p.feed_blurb or "",
            })

    return results


def get_paper_chunks(filename: str, limit: int = 5) -> list[str]:
    """Load first N real content chunks for a paper, ordered by page/index."""
    with get_session() as session:
        chunks = (
            session.execute(
                select(Chunk)
                .where(Chunk.paper_filename == filename)
                .where(Chunk.section_name != "metadata_only")
                .where(Chunk.section_name != "metadata")
                .order_by(Chunk.page_num, Chunk.chunk_index)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [c.content for c in chunks]


def extract_abstract(chunks: list[str]) -> str:
    """Extract abstract from paper chunks using heuristic search."""
    for chunk in chunks[:10]:
        chunk_lower = chunk.lower()
        if "abstract" in chunk_lower[:200]:
            abstract_start = chunk_lower.find("abstract")
            content = chunk[abstract_start:].strip()
            if content.lower().startswith("abstract"):
                content = content[8:].strip()
            content = content.lstrip(":.-\u2014 \n\t")
            if 100 < len(content) < 2000:
                return content

    # Fallback: first chunk
    if chunks and len(chunks[0]) > 100:
        return chunks[0][:1000]
    return ""


def generate_summary(client: anthropic.Anthropic, paper: dict, abstract: str, chunks: list[str]) -> str:
    """Call Claude to generate a structured summary from paper content."""
    context_text = "\n\n".join(chunks[:5])[:10000]

    authors_str = "; ".join(paper["authors"][:5]) if isinstance(paper["authors"], list) else paper["authors"]

    prompt = f"""You are analyzing a battery research paper. Generate a structured summary with the following sections:

PAPER METADATA:
Title: {paper.get('title', 'Unknown')}
Authors: {authors_str}
Journal: {paper.get('journal', 'Unknown')}
Year: {paper.get('year', 'Unknown')}
Chemistries: {', '.join(paper.get('chemistries', []))}

ABSTRACT:
{abstract}

PAPER TEXT (first sections):
{context_text}

Generate a structured summary in the following format:

## Overview
[2-3 sentences summarizing the paper's main focus and contribution]

## Key Findings
- [Finding 1]
- [Finding 2]
- [Finding 3]
[Add up to 5 bullet points of the most important findings]

## Methods
- [Method 1]
- [Method 2]
[2-3 bullet points describing the experimental or computational methods]

## Novel Contributions
[1-2 sentences on what makes this work novel or significant]

Be concise, technical, and focus on the most important aspects. Use battery domain terminology."""

    response = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=1500,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def generate_blurb(client: anthropic.Anthropic, title: str, summary: str) -> str:
    """Generate a 280-char feed blurb from an AI summary."""
    prompt = f"""Convert this research paper summary into a punchy, tweet-style blurb (max 280 characters).

Paper title: {title}

Full summary:
{summary}

Requirements:
- Exactly 1-2 sentences, maximum 280 characters
- Lead with the key finding or result, not the method
- Informative but punchy, like a science journalist
- Use specific numbers/metrics when available
- No hashtags, no emojis

Example style: "Hybrid physics-informed neural net predicts battery discharge across 5 load levels with <3% EOD error -- and a GP layer forecasts fleet-wide degradation without per-battery calibration."

Generate the blurb:"""

    response = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    blurb = response.content[0].text.strip()
    if len(blurb) > 280:
        blurb = blurb[:277] + "..."
    return blurb


def save_summary_to_db(filename: str, summary: str, blurb: str):
    """Write AI summary, blurb, and metadata to the papers table."""
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper:
            paper.ai_summary = summary
            paper.feed_blurb = blurb
            paper.summary_generated_at = datetime.now(timezone.utc)
            paper.summary_model = SUMMARY_MODEL


def save_blurb_to_db(filename: str, blurb: str):
    """Write just the feed blurb (for --blurbs-only mode)."""
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper:
            paper.feed_blurb = blurb


def load_progress() -> dict:
    """Load progress file for resume support."""
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "failed": []}


def save_progress(progress: dict):
    """Save progress file."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Blurbs-only mode
# ---------------------------------------------------------------------------

def run_blurbs_only(client: anthropic.Anthropic, limit: int, dry_run: bool, delay: float):
    """Generate blurbs for papers that have summaries but no blurbs."""
    with get_session() as session:
        papers = session.execute(
            select(Paper)
            .where(Paper.deleted_at.is_(None))
            .where(Paper.ai_summary.isnot(None))
            .where(Paper.ai_summary != "")
            .where(or_(Paper.feed_blurb.is_(None), Paper.feed_blurb == ""))
        ).scalars().all()

        candidates = [
            {"filename": p.filename, "title": p.title or "", "ai_summary": p.ai_summary}
            for p in papers
        ]

    if limit:
        candidates = candidates[:limit]

    print(f"Found {len(candidates)} papers needing blurbs")

    generated = 0
    for idx, paper in enumerate(candidates):
        title_short = paper["title"][:50]
        print(f"[{idx+1}/{len(candidates)}] {title_short}...")

        if dry_run:
            print(f"  [DRY RUN] Would generate blurb from {len(paper['ai_summary'])} char summary")
            continue

        try:
            blurb = generate_blurb(client, paper["title"], paper["ai_summary"])
            save_blurb_to_db(paper["filename"], blurb)
            generated += 1
            print(f"  OK ({len(blurb)} chars): {blurb[:80]}...")
            time.sleep(delay)
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nGenerated {generated} blurbs")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch generate AI summaries for papers with PDFs")
    parser.add_argument("--limit", type=int, default=0, help="Max papers to process (0 = all)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between API calls (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without calling API")
    parser.add_argument("--blurbs-only", action="store_true", help="Only generate blurbs for papers with summaries")
    parser.add_argument("--force", action="store_true", help="Regenerate even if summary exists")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        print("ERROR: ANTHROPIC_API_KEY not set. Use --dry-run to preview.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key) if api_key else None

    print("=" * 70)
    print("ASTROLABE — Batch AI Summary Generation (PostgreSQL)")
    print("=" * 70)

    if args.blurbs_only:
        run_blurbs_only(client, args.limit, args.dry_run, args.delay)
        return

    # Find papers needing summaries
    papers = get_papers_needing_summaries(force=args.force)
    print(f"\nFound {len(papers)} papers with real chunks needing summaries")

    if args.limit:
        papers = papers[:args.limit]
        print(f"Processing first {args.limit} papers")

    if not papers:
        print("Nothing to do!")
        return

    # Load progress for resume support
    progress = load_progress()
    completed_set = set(progress["completed"])

    # Filter out already-completed papers (for resume)
    remaining = [p for p in papers if p["filename"] not in completed_set]
    if len(remaining) < len(papers):
        print(f"Resuming: {len(papers) - len(remaining)} already done, {len(remaining)} remaining")
    papers = remaining

    if not papers:
        print("All papers already processed (check data/summary_progress.json)")
        return

    # Process
    generated = 0
    failed = 0
    start_time = time.time()

    for idx, paper in enumerate(papers):
        title_short = paper["title"][:60] if paper["title"] else paper["filename"]
        print(f"\n[{idx+1}/{len(papers)}] {title_short}")

        # Load chunks
        chunks = get_paper_chunks(paper["filename"], limit=5)
        if not chunks:
            print("  SKIP: No content chunks found")
            progress["failed"].append(paper["filename"])
            failed += 1
            continue

        total_chars = sum(len(c) for c in chunks)
        print(f"  Chunks: {len(chunks)}, Total chars: {total_chars}")

        # Extract abstract
        abstract = extract_abstract(chunks)
        if abstract:
            print(f"  Abstract: {len(abstract)} chars")

        if args.dry_run:
            print(f"  [DRY RUN] Would generate summary from {total_chars} chars of text")
            print(f"  [DRY RUN] Prompt would include: title, {len(chunks)} chunks, abstract")
            continue

        try:
            # Generate summary
            summary = generate_summary(client, paper, abstract, chunks)
            print(f"  Summary: {len(summary)} chars")

            # Generate blurb
            blurb = generate_blurb(client, paper["title"], summary)
            print(f"  Blurb ({len(blurb)} chars): {blurb[:80]}...")

            # Save to database
            save_summary_to_db(paper["filename"], summary, blurb)
            generated += 1
            progress["completed"].append(paper["filename"])
            print("  SAVED")

            # Save progress periodically
            if generated % SAVE_INTERVAL == 0:
                save_progress(progress)
                print(f"  [Progress saved: {generated} done]")

            # Rate limit
            time.sleep(args.delay)

        except anthropic.RateLimitError as e:
            print(f"  RATE LIMITED: {e}")
            print("  Waiting 30s before retry...")
            time.sleep(30)
            # Retry once
            try:
                summary = generate_summary(client, paper, abstract, chunks)
                blurb = generate_blurb(client, paper["title"], summary)
                save_summary_to_db(paper["filename"], summary, blurb)
                generated += 1
                progress["completed"].append(paper["filename"])
                print("  SAVED (after retry)")
            except Exception as e2:
                print(f"  FAILED after retry: {e2}")
                progress["failed"].append(paper["filename"])
                failed += 1

        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            progress["failed"].append(paper["filename"])
            failed += 1

    # Final save
    save_progress(progress)

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Generated: {generated}")
    print(f"  Failed:    {failed}")
    print(f"  Skipped:   {len(papers) - generated - failed}")
    print(f"  Time:      {elapsed:.1f}s ({elapsed/max(generated,1):.1f}s per paper)")
    print(f"  Progress:  {PROGRESS_FILE}")
    if args.dry_run:
        print("  (DRY RUN — no API calls made)")


if __name__ == "__main__":
    main()
