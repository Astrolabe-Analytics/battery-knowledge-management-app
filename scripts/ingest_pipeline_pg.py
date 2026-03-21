#!/usr/bin/env python3
"""
Modular Ingestion Pipeline — PostgreSQL version.

Stages 1 & 2 (parse, chunk) are unchanged — they produce intermediate
markdown and chunk-JSON files on disk.

Stage 3 (metadata) writes paper metadata to PostgreSQL instead of metadata.json.
Stage 4 (embed) writes chunks + embeddings to PostgreSQL/pgvector instead of ChromaDB.

Usage:
    python scripts/ingest_pipeline_pg.py --stage parse
    python scripts/ingest_pipeline_pg.py --stage chunk --force
    python scripts/ingest_pipeline_pg.py --stage metadata --new-only
    python scripts/ingest_pipeline_pg.py --stage embed
    python scripts/ingest_pipeline_pg.py --all
"""

import os
import sys
import json
import re
import time
import logging
import argparse
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
import tempfile

import opendataloader_pdf
import tiktoken
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic
from tqdm import tqdm

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.retry import anthropic_api_call_with_retry

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# ── Configuration ────────────────────────────────────────────────────────────
PAPERS_DIR = Path(__file__).parent.parent / "papers"
RAW_TEXT_DIR = Path(__file__).parent.parent / "raw_text"
CHUNKS_DIR = Path(__file__).parent.parent / "data" / "chunks"
PIPELINE_STATE_FILE = Path(__file__).parent.parent / "data" / "pipeline_state.json"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TARGET_CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "data" / "pipeline.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE STATE (shared file lightly tracks which PDFs completed each stage)
# ═══════════════════════════════════════════════════════════════════════════════

def load_pipeline_state() -> Dict[str, Any]:
    if PIPELINE_STATE_FILE.exists():
        try:
            with open(PIPELINE_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load pipeline state: {e}")
    return {
        'parsed': [], 'chunked': [], 'metadata': [],
        'embedded': [], 'last_updated': None,
    }


def save_pipeline_state(state: Dict[str, Any]):
    try:
        PIPELINE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state['last_updated'] = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(PIPELINE_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save pipeline state: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 1: PDF PARSING  (identical to original — produces markdown files)
# ═══════════════════════════════════════════════════════════════════════════════

# Page separator used by opendataloader-pdf to split markdown output by page
_PAGE_SEP = '<!-- PAGE_BREAK %%page-number%% -->'
_PAGE_SEP_PATTERN = re.compile(r'<!-- PAGE_BREAK %(\d+)% -->')


def extract_text_from_pdf(pdf_path: Path) -> List[dict]:
    logger.info(f"Extracting text from {pdf_path.name}")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            opendataloader_pdf.convert(
                input_path=[str(pdf_path)],
                output_dir=tmpdir,
                format='markdown',
                quiet=True,
                image_output='off',
                markdown_page_separator=_PAGE_SEP,
            )
            md_file = Path(tmpdir) / pdf_path.name.replace('.pdf', '.md')
            if not md_file.exists():
                # Fallback: find any .md file in the output dir
                md_files = list(Path(tmpdir).glob('*.md'))
                if not md_files:
                    logger.error(f"No markdown output for {pdf_path.name}")
                    return []
                md_file = md_files[0]
            content = md_file.read_text(encoding='utf-8')

        # Split by page separators
        pages = []
        parts = _PAGE_SEP_PATTERN.split(content)
        # parts alternates: [text_before_first_sep, page_num, text, page_num, text, ...]
        # First element is text before any separator (usually empty)
        if len(parts) >= 3:
            for i in range(1, len(parts), 2):
                page_num = int(parts[i])
                text = parts[i + 1] if i + 1 < len(parts) else ''
                if text.strip():
                    pages.append({'page_num': page_num, 'text': text.strip()})
        elif content.strip():
            # No page separators found — treat as single page
            pages.append({'page_num': 1, 'text': content.strip()})

        logger.info(f"  Extracted {len(pages)} pages")
        return pages
    except Exception as e:
        logger.error(f"Failed to extract from {pdf_path.name}: {e}")
        return []


def save_markdown(pages: List[dict], filename: str, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    md_filename = filename.replace('.pdf', '.md')
    output_path = output_dir / md_filename
    markdown_content = []
    for page_data in pages:
        markdown_content.append(f"<!-- Page {page_data['page_num']} -->\n\n{page_data['text']}\n\n")
    try:
        output_path.write_text('\n'.join(markdown_content), encoding='utf-8')
        logger.info(f"  Saved markdown to {md_filename}")
    except Exception as e:
        logger.error(f"Failed to save markdown: {e}")


def stage_parse(force: bool = False, new_only: bool = False):
    print("\n" + "=" * 60)
    print("STAGE 1: PDF PARSING")
    print("=" * 60)

    if not PAPERS_DIR.exists():
        print(f"ERROR: Papers directory not found: {PAPERS_DIR}")
        return

    pdf_files = list(PAPERS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"ERROR: No PDF files found in {PAPERS_DIR}")
        return

    print(f"Found {len(pdf_files)} PDF files")

    state = load_pipeline_state()
    parsed_files = set(state.get('parsed', []))

    if force:
        files_to_process = pdf_files
        print("Force mode: Re-parsing all PDFs")
    elif new_only:
        files_to_process = [f for f in pdf_files if f.name not in parsed_files]
        print(f"New-only mode: Parsing {len(files_to_process)} new PDFs")
    else:
        files_to_process = [f for f in pdf_files if f.name not in parsed_files]
        print(f"Parsing {len(files_to_process)} PDFs (skipping {len(pdf_files) - len(files_to_process)} already parsed)")

    if not files_to_process:
        print("✓ All PDFs already parsed!")
        return

    print("-" * 60)
    for pdf_file in tqdm(files_to_process, desc="Parsing PDFs", unit="paper"):
        try:
            pages = extract_text_from_pdf(pdf_file)
            if not pages:
                continue
            save_markdown(pages, pdf_file.name, RAW_TEXT_DIR)
            parsed_files.add(pdf_file.name)
            state['parsed'] = list(parsed_files)
            save_pipeline_state(state)
        except Exception as e:
            logger.error(f"Failed to process {pdf_file.name}: {e}")
    print(f"\n✓ Stage 1 complete: {len(parsed_files)} papers parsed")


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 2: CHUNKING  (identical to original — produces chunk JSON files)
# ═══════════════════════════════════════════════════════════════════════════════

def count_tokens(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def chunk_text(text: str, page_num: int) -> List[dict]:
    enc = tiktoken.get_encoding("cl100k_base")
    lines = text.split('\n')
    sections = []
    current_section_name = None
    current_section_lines = []
    header_pattern = r'^(#{1,6})\s+(.+)$'

    for line in lines:
        header_match = re.match(header_pattern, line.strip())
        if header_match:
            if current_section_lines:
                sections.append({'name': current_section_name or 'Content', 'text': '\n'.join(current_section_lines).strip()})
            current_section_name = header_match.group(2).strip()
            current_section_lines = []
        else:
            current_section_lines.append(line)

    if current_section_lines:
        sections.append({'name': current_section_name or 'Content', 'text': '\n'.join(current_section_lines).strip()})

    if not sections:
        sections = [{'name': 'Content', 'text': text}]

    chunks = []
    chunk_index = 0

    for section in sections:
        section_name = section['name']
        section_text = section['text']
        if not section_text.strip():
            continue

        paragraphs = [p.strip() for p in section_text.split('\n\n') if p.strip()]
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = len(enc.encode(para))

            if para_tokens > TARGET_CHUNK_SIZE * 1.5:
                sentences = para.split('. ')
                for sent in sentences:
                    sent_tokens = len(enc.encode(sent))
                    if current_tokens + sent_tokens > TARGET_CHUNK_SIZE and current_chunk:
                        chunks.append({'text': ' '.join(current_chunk), 'page_num': page_num, 'chunk_index': chunk_index, 'section_name': section_name, 'token_count': current_tokens})
                        chunk_index += 1
                        overlap_text = ' '.join(current_chunk[-2:]) if len(current_chunk) >= 2 else ''
                        overlap_tokens = len(enc.encode(overlap_text))
                        if overlap_tokens > 0:
                            current_chunk = current_chunk[-2:]
                            current_tokens = overlap_tokens
                        else:
                            current_chunk = []
                            current_tokens = 0
                    current_chunk.append(sent)
                    current_tokens += sent_tokens
            else:
                if current_tokens + para_tokens > TARGET_CHUNK_SIZE and current_chunk:
                    chunks.append({'text': ' '.join(current_chunk), 'page_num': page_num, 'chunk_index': chunk_index, 'section_name': section_name, 'token_count': current_tokens})
                    chunk_index += 1
                    if current_chunk:
                        overlap_text = current_chunk[-1]
                        overlap_tokens = len(enc.encode(overlap_text))
                        if overlap_tokens <= CHUNK_OVERLAP:
                            current_chunk = [current_chunk[-1]]
                            current_tokens = overlap_tokens
                        else:
                            current_chunk = []
                            current_tokens = 0
                current_chunk.append(para)
                current_tokens += para_tokens

        if current_chunk:
            chunks.append({'text': ' '.join(current_chunk), 'page_num': page_num, 'chunk_index': chunk_index, 'section_name': section_name, 'token_count': current_tokens})
            chunk_index += 1

    return chunks


def load_markdown(md_path: Path) -> List[dict]:
    try:
        content = md_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Failed to read {md_path.name}: {e}")
        return []

    pages = []
    current_page = 1
    current_text = []

    for line in content.split('\n'):
        page_marker = re.match(r'<!-- Page (\d+) -->', line.strip())
        if page_marker:
            if current_text:
                pages.append({'page_num': current_page, 'text': '\n'.join(current_text)})
            current_page = int(page_marker.group(1))
            current_text = []
        else:
            current_text.append(line)

    if current_text:
        pages.append({'page_num': current_page, 'text': '\n'.join(current_text)})
    return pages


def stage_chunk(force: bool = False, new_only: bool = False):
    print("\n" + "=" * 60)
    print("STAGE 2: CHUNKING")
    print("=" * 60)

    if not RAW_TEXT_DIR.exists():
        print(f"ERROR: Raw text directory not found: {RAW_TEXT_DIR}")
        return

    md_files = list(RAW_TEXT_DIR.glob("*.md"))
    if not md_files:
        print(f"ERROR: No markdown files found")
        return

    print(f"Found {len(md_files)} markdown files")

    state = load_pipeline_state()
    chunked_files = set(state.get('chunked', []))

    if force:
        files_to_process = md_files
    elif new_only:
        files_to_process = [f for f in md_files if f.stem + '.pdf' not in chunked_files]
    else:
        files_to_process = [f for f in md_files if f.stem + '.pdf' not in chunked_files]

    print(f"Chunking {len(files_to_process)} files")

    if not files_to_process:
        print("✓ All files already chunked!")
        return

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    for md_file in tqdm(files_to_process, desc="Chunking", unit="file"):
        try:
            pages = load_markdown(md_file)
            if not pages:
                continue

            all_chunks = []
            for page_data in pages:
                page_chunks = chunk_text(page_data['text'], page_data['page_num'])
                all_chunks.extend(page_chunks)

            pdf_name = md_file.stem + '.pdf'
            chunks_file = CHUNKS_DIR / f"{md_file.stem}_chunks.json"

            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'filename': pdf_name,
                    'chunks': all_chunks,
                    'total_chunks': len(all_chunks),
                    'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }, f, indent=2)

            logger.info(f"Created {len(all_chunks)} chunks for {pdf_name}")
            chunked_files.add(pdf_name)
            state['chunked'] = list(chunked_files)
            save_pipeline_state(state)

        except Exception as e:
            logger.error(f"Failed to chunk {md_file.name}: {e}")

    print(f"\n✓ Stage 2 complete: {len(chunked_files)} papers chunked")


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 3: METADATA EXTRACTION → PostgreSQL  (replaces metadata.json writes)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_doi_from_text(text: str) -> Optional[str]:
    doi_chars = r'[\w\-\.\(\)\/]+'
    doi_patterns = [
        rf'https?://doi\.org/(10\.\d{{4,}}/{doi_chars})',
        rf'https?://dx\.doi\.org/(10\.\d{{4,}}/{doi_chars})',
        rf'doi:\s*(10\.\d{{4,}}/{doi_chars})',
        rf'DOI:\s*(10\.\d{{4,}}/{doi_chars})',
        rf'\b(10\.\d{{4,}}/{doi_chars})\b',
    ]
    for pattern in doi_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            doi = match.group(1)
            doi = re.sub(r'[.,;:\s\)]+$', '', doi)
            return doi
    return None


def query_crossref_api(doi: str) -> Optional[dict]:
    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {'User-Agent': 'BatteryPaperLibrary/1.0 (mailto:researcher@example.com)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        message = response.json().get('message', {})
        metadata = {}

        titles = message.get('title', [])
        if titles:
            metadata['title'] = titles[0]

        authors = []
        for author in message.get('author', []):
            given = author.get('given', '')
            family = author.get('family', '')
            if family:
                authors.append(f"{family}, {given}" if given else family)
        metadata['authors'] = authors[:10]

        published = message.get('published-print') or message.get('published-online')
        if published and 'date-parts' in published:
            date_parts = published['date-parts'][0]
            if date_parts:
                metadata['year'] = str(date_parts[0])

        from lib.journal_normalizer import normalize_journal_name
        container_titles = message.get('container-title', [])
        if container_titles:
            metadata['journal'] = normalize_journal_name(container_titles[0])

        # References (raw dicts for save_paper_references)
        metadata['_raw_references'] = message.get('reference', [])[:100]

        return metadata
    except Exception as e:
        logger.debug(f"CrossRef API error: {e}")
        return None


_PAPER_TYPE_MAP = {
    'experimental': 'Experimental',
    'modeling': 'Modeling & Simulation',
    'modeling & simulation': 'Modeling & Simulation',
    'simulation': 'Modeling & Simulation',
    'method': 'Modeling & Simulation',
    'review': 'Review',
    'reference': 'Review',
    'dataset': 'Dataset',
}


def _normalize_paper_type(raw: str) -> str:
    return _PAPER_TYPE_MAP.get(raw.lower().strip(), 'Experimental') if raw else 'Experimental'


@anthropic_api_call_with_retry
def _call_claude_for_metadata(text: str, filename: str, api_key: str, model: str) -> str:
    prompt = f"""Analyze this battery research paper excerpt and extract structured metadata.

Paper excerpt:
{text}

Extract the following information and respond ONLY with a valid JSON object:

{{
  "title": "Exact paper title from the document",
  "authors": ["Last, First; Last, First; Last, First"],
  "year": "2023",
  "journal": "Journal of Power Sources",
  "chemistries": ["list of battery chemistries discussed, e.g., LFP, NMC, NCA, LCO, LMO, LTO, graphite, silicon, etc."],
  "topics": ["list of technical topics, e.g., degradation, SOH, RUL, capacity fade, impedance, EIS, cycling, calendar aging, thermal, SEI, lithium plating, etc."],
  "application": "primary application domain: EV, grid storage, consumer electronics, aerospace, or general",
  "paper_type": "one of: Experimental, Modeling & Simulation, Review, or Dataset"
}}

STRICT FORMATTING RULES:
- Title: Title case, no period at the end, main title only (not subtitle)
- Authors: ALWAYS "Last, First" format, semicolon-separated
- Year: 4-digit year ONLY
- Journal: FULL NAME, never abbreviated
- Limit to first 10 authors if more than 10
- Use standard battery chemistry abbreviations (NMC, LFP, NCA, etc.)
- Topics should be technical keywords (3-10 topics)
- For paper_type: Experimental=lab/physical testing, Modeling & Simulation=computational models/algorithms/ML methods, Review=literature surveys/overviews, Dataset=published data collections
- Return ONLY the JSON object, no other text

JSON:"""

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=600,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def extract_metadata_for_paper(md_path: Path, api_key: str) -> dict:
    """Extract metadata for a single paper using DOI-first approach."""
    pages = load_markdown(md_path)
    if not pages:
        return {}

    text_for_analysis = ""
    text_for_doi = ""
    for i, page in enumerate(pages[:3]):
        text_for_analysis += page['text'] + "\n\n"
        if i < 2:
            text_for_doi += page['text'] + "\n\n"
        if len(text_for_analysis) > 3000:
            break
    text_for_analysis = text_for_analysis[:3500]

    metadata = {
        'title': '', 'authors': [], 'year': '', 'journal': '',
        'doi': '', 'chemistries': [], 'topics': [],
        'application': 'general', 'paper_type': 'Experimental',
        '_raw_references': [],
    }

    doi = extract_doi_from_text(text_for_doi)
    crossref_data = None

    if doi:
        logger.info(f"  Found DOI: {doi}")
        metadata['doi'] = doi
        crossref_data = query_crossref_api(doi)
        if crossref_data:
            logger.info("  ✓ CrossRef data retrieved")
            metadata['title'] = crossref_data.get('title', '')
            metadata['authors'] = crossref_data.get('authors', [])
            metadata['year'] = crossref_data.get('year', '')
            metadata['journal'] = crossref_data.get('journal', '')
            metadata['_raw_references'] = crossref_data.get('_raw_references', [])

    # Use Claude for battery fields (or all fields if no CrossRef)
    try:
        response_text = _call_claude_for_metadata(
            text_for_analysis, md_path.name, api_key, CLAUDE_MODEL
        )
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)

        claude_metadata = json.loads(response_text)

        if crossref_data:
            metadata['chemistries'] = claude_metadata.get('chemistries', [])
            metadata['topics'] = claude_metadata.get('topics', [])
            metadata['application'] = claude_metadata.get('application', 'general')
            metadata['paper_type'] = claude_metadata.get('paper_type', 'Experimental')
        else:
            metadata.update(claude_metadata)

        metadata['chemistries'] = [c.upper() for c in metadata.get('chemistries', [])]
        metadata['topics'] = [t.lower() for t in metadata.get('topics', [])]
        metadata['application'] = metadata.get('application', 'general').lower()
        metadata['paper_type'] = _normalize_paper_type(metadata.get('paper_type', 'Experimental'))

        if isinstance(metadata.get('authors'), str):
            metadata['authors'] = [a.strip() for a in metadata['authors'].split(';') if a.strip()]

    except Exception as e:
        logger.error(f"Failed to extract metadata: {e}")

    return metadata


def stage_metadata(force: bool = False, new_only: bool = False):
    """Stage 3: Extract metadata and write to PostgreSQL."""
    print("\n" + "=" * 60)
    print("STAGE 3: METADATA EXTRACTION → PostgreSQL")
    print("=" * 60)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return

    if not RAW_TEXT_DIR.exists():
        print(f"ERROR: Raw text directory not found")
        return

    md_files = list(RAW_TEXT_DIR.glob("*.md"))
    if not md_files:
        print("ERROR: No markdown files found")
        return

    print(f"Found {len(md_files)} markdown files")

    state = load_pipeline_state()
    metadata_files = set(state.get('metadata', []))

    if force:
        files_to_process = md_files
    elif new_only:
        files_to_process = [f for f in md_files if f.stem + '.pdf' not in metadata_files]
    else:
        files_to_process = [f for f in md_files if f.stem + '.pdf' not in metadata_files]

    print(f"Extracting metadata for {len(files_to_process)} files")

    if not files_to_process:
        print("✓ All files have metadata!")
        return

    from lib.db_operations import upsert_paper, save_paper_references
    from datetime import datetime, timezone

    print("-" * 60)
    for md_file in tqdm(files_to_process, desc="Extracting metadata", unit="paper"):
        try:
            pdf_name = md_file.stem + '.pdf'
            logger.info(f"Processing {pdf_name}")

            metadata = extract_metadata_for_paper(md_file, api_key)

            # Pop internal field before saving
            raw_refs = metadata.pop('_raw_references', [])

            # Write to PostgreSQL
            upsert_paper(pdf_name, {
                **metadata,
                'extracted_at': datetime.now(timezone.utc),
            })

            # Save references
            if raw_refs:
                save_paper_references(pdf_name, raw_refs)

            logger.info(f"  ✓ Saved to PostgreSQL: {metadata.get('title', '')[:60]}")

            metadata_files.add(pdf_name)
            state['metadata'] = list(metadata_files)
            save_pipeline_state(state)

            # Rate limiting for Claude
            time.sleep(30)

        except Exception as e:
            logger.error(f"Failed to extract metadata for {md_file.name}: {e}")

    print(f"\n✓ Stage 3 complete: {len(metadata_files)} papers have metadata in PostgreSQL")


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 4: EMBEDDING & INDEXING → PostgreSQL/pgvector  (replaces ChromaDB)
# ═══════════════════════════════════════════════════════════════════════════════

def stage_embed(force: bool = False):
    """Stage 4: Embed chunks and load into PostgreSQL with pgvector."""
    print("\n" + "=" * 60)
    print("STAGE 4: EMBEDDING & INDEXING → PostgreSQL/pgvector")
    print("=" * 60)

    if not CHUNKS_DIR.exists() or not list(CHUNKS_DIR.glob("*_chunks.json")):
        print(f"ERROR: No chunk files found in {CHUNKS_DIR}")
        return

    # Load embedding model
    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    try:
        model = SentenceTransformer(EMBEDDING_MODEL)
        print("  Model loaded successfully")
    except Exception as e:
        print(f"ERROR: Failed to load model: {e}")
        return

    from lib.db_operations import add_chunks, delete_chunks_for_paper, get_paper_by_filename

    # Determine which chunk files to process
    state = load_pipeline_state()
    embedded_files = set(state.get('embedded', []))

    chunk_files = list(CHUNKS_DIR.glob("*_chunks.json"))
    print(f"Found {len(chunk_files)} chunk files")

    if force:
        files_to_process = chunk_files
        print("Force mode: Re-embedding all chunk files")
    else:
        files_to_process = []
        for cf in chunk_files:
            # Derive PDF filename from chunk filename
            pdf_name = cf.stem.replace('_chunks', '') + '.pdf'
            if pdf_name not in embedded_files:
                files_to_process.append(cf)
        print(f"Embedding {len(files_to_process)} new files (skipping {len(chunk_files) - len(files_to_process)} already done)")

    if not files_to_process:
        print("✓ All chunks already embedded!")
        return

    print("-" * 60)

    total_new_chunks = 0

    for chunk_file in tqdm(files_to_process, desc="Embedding & inserting", unit="file"):
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            filename = data['filename']
            chunks = data['chunks']
            if not chunks:
                continue

            # If force mode, delete existing chunks for this paper first
            if force:
                deleted = delete_chunks_for_paper(filename)
                if deleted:
                    logger.info(f"  Deleted {deleted} existing chunks for {filename}")

            # Generate embeddings for this paper's chunks
            texts = [c['text'] for c in chunks]
            batch_size = 32
            embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embs = model.encode(batch, show_progress_bar=False)
                embeddings.extend(batch_embs.tolist())

            # Build chunk records for db_operations.add_chunks()
            chunk_records = []
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{filename}_p{chunk['page_num']}_c{chunk['chunk_index']}"
                chunk_records.append({
                    'id': chunk_id,
                    'paper_filename': filename,
                    'page_num': chunk['page_num'],
                    'chunk_index': chunk['chunk_index'],
                    'token_count': chunk.get('token_count', 0),
                    'section_name': chunk.get('section_name', 'Content'),
                    'content': chunk['text'],
                    'embedding': embeddings[idx],
                })

            add_chunks(chunk_records)
            total_new_chunks += len(chunk_records)
            logger.info(f"  ✓ {filename}: {len(chunk_records)} chunks embedded & stored in PostgreSQL")

            # Update state
            embedded_files.add(filename)
            state['embedded'] = list(embedded_files)
            save_pipeline_state(state)

        except Exception as e:
            logger.error(f"Failed to embed {chunk_file.name}: {e}")

    print(f"\n✓ Stage 4 complete: {total_new_chunks} new chunks embedded in PostgreSQL/pgvector")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Ingestion pipeline (PostgreSQL version)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/ingest_pipeline_pg.py --stage parse
  python scripts/ingest_pipeline_pg.py --stage chunk --force
  python scripts/ingest_pipeline_pg.py --stage metadata --new-only
  python scripts/ingest_pipeline_pg.py --stage embed
  python scripts/ingest_pipeline_pg.py --all
        """
    )

    parser.add_argument('--stage', choices=['parse', 'chunk', 'metadata', 'embed'])
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--new-only', action='store_true')

    args = parser.parse_args()

    if not args.stage and not args.all:
        parser.print_help()
        return

    if args.all:
        print("Running full pipeline (PostgreSQL target)")
        stage_parse(force=args.force, new_only=args.new_only)
        stage_chunk(force=args.force, new_only=args.new_only)
        stage_metadata(force=args.force, new_only=args.new_only)
        stage_embed(force=args.force)

        print(f"\nCreating automatic backup...")
        try:
            from lib import backup as backup_module
            result = backup_module.create_backup(include_logs=True)
            if result['success']:
                print(f"  ✓ Backup created: {result['size_mb']} MB")
        except Exception as e:
            print(f"  ⚠ Backup failed: {e}")

        print("\n" + "=" * 60)
        print("✓ PIPELINE COMPLETE (PostgreSQL)")
        print("=" * 60)
    else:
        stage_map = {
            'parse': lambda: stage_parse(force=args.force, new_only=args.new_only),
            'chunk': lambda: stage_chunk(force=args.force, new_only=args.new_only),
            'metadata': lambda: stage_metadata(force=args.force, new_only=args.new_only),
            'embed': lambda: stage_embed(force=args.force),
        }
        stage_map[args.stage]()


if __name__ == "__main__":
    main()
