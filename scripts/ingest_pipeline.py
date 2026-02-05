#!/usr/bin/env python3
"""
Modular Ingestion Pipeline for Battery Research Papers

Each stage can be run independently:
- Stage 1: PDF Parsing - Extract text/markdown from PDFs
- Stage 2: Chunking - Create chunks from markdown
- Stage 3: Metadata Extraction - Extract metadata (DOI + Claude)
- Stage 4: Embedding & Indexing - Embed and load into ChromaDB

Usage:
    python scripts/ingest_pipeline.py --stage parse
    python scripts/ingest_pipeline.py --stage chunk --force
    python scripts/ingest_pipeline.py --stage metadata --new-only
    python scripts/ingest_pipeline.py --stage embed
    python scripts/ingest_pipeline.py --all  # Run all stages
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
import pymupdf4llm
import tiktoken
import chromadb
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic
from tqdm import tqdm

# Import retry utilities
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.retry import anthropic_api_call_with_retry

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Configuration
PAPERS_DIR = Path(__file__).parent.parent / "papers"
RAW_TEXT_DIR = Path(__file__).parent.parent / "raw_text"
CHUNKS_DIR = Path(__file__).parent.parent / "data" / "chunks"
METADATA_FILE = Path(__file__).parent.parent / "data" / "metadata.json"
DB_DIR = Path(__file__).parent.parent / "data" / "chroma_db"
PIPELINE_STATE_FILE = Path(__file__).parent.parent / "data" / "pipeline_state.json"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TARGET_CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
COLLECTION_NAME = "battery_papers"
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


# ============================================================================
# PIPELINE STATE MANAGEMENT
# ============================================================================

def load_pipeline_state() -> Dict[str, Any]:
    """Load pipeline state tracking which papers completed each stage."""
    if PIPELINE_STATE_FILE.exists():
        try:
            with open(PIPELINE_STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load pipeline state: {e}")

    return {
        'parsed': [],      # Papers with text extracted
        'chunked': [],     # Papers with chunks created
        'metadata': [],    # Papers with metadata extracted
        'embedded': [],    # Papers with embeddings in ChromaDB
        'last_updated': None
    }


def save_pipeline_state(state: Dict[str, Any]):
    """Save pipeline state."""
    try:
        PIPELINE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state['last_updated'] = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(PIPELINE_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save pipeline state: {e}")


# ============================================================================
# STAGE 1: PDF PARSING
# ============================================================================

def extract_text_from_pdf(pdf_path: Path) -> List[dict]:
    """Extract text from PDF using PyMuPDF4LLM, organizing by page."""
    logger.info(f"Extracting text from {pdf_path.name}")
    pages = []

    try:
        md_text = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)

        for page_data in md_text:
            page_num = page_data['metadata']['page'] + 1
            text = page_data['text']

            if text.strip():
                pages.append({
                    'page_num': page_num,
                    'text': text
                })
    except Exception as e:
        logger.error(f"Failed to extract from {pdf_path.name}: {e}")
        return []

    logger.info(f"  Extracted {len(pages)} pages")
    return pages


def save_markdown(pages: List[dict], filename: str, output_dir: Path):
    """Save extracted text as markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)

    md_filename = filename.replace('.pdf', '.md')
    output_path = output_dir / md_filename

    markdown_content = []
    for page_data in pages:
        page_num = page_data['page_num']
        text = page_data['text']
        markdown_content.append(f"<!-- Page {page_num} -->\n\n{text}\n\n")

    full_markdown = '\n'.join(markdown_content)

    try:
        output_path.write_text(full_markdown, encoding='utf-8')
        logger.info(f"  Saved markdown to {md_filename}")
    except Exception as e:
        logger.error(f"Failed to save markdown: {e}")


def stage_parse(force: bool = False, new_only: bool = False):
    """Stage 1: Parse PDFs and extract text to markdown files."""
    print("\n" + "="*60)
    print("STAGE 1: PDF PARSING")
    print("="*60)

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

    # Determine which files to process
    if force:
        files_to_process = pdf_files
        print("Force mode: Re-parsing all PDFs")
    elif new_only:
        files_to_process = [f for f in pdf_files if f.name not in parsed_files]
        print(f"New-only mode: Parsing {len(files_to_process)} new PDFs")
    else:
        # Default: parse only new files
        files_to_process = [f for f in pdf_files if f.name not in parsed_files]
        print(f"Parsing {len(files_to_process)} PDFs (skipping {len(pdf_files) - len(files_to_process)} already parsed)")

    if not files_to_process:
        print("✓ All PDFs already parsed!")
        return

    print("-"*60)

    for pdf_file in tqdm(files_to_process, desc="Parsing PDFs", unit="paper"):
        try:
            pages = extract_text_from_pdf(pdf_file)
            if not pages:
                logger.warning(f"No pages extracted from {pdf_file.name}")
                continue

            save_markdown(pages, pdf_file.name, RAW_TEXT_DIR)

            # Update state
            if pdf_file.name not in parsed_files:
                parsed_files.add(pdf_file.name)
                state['parsed'] = list(parsed_files)
                save_pipeline_state(state)

        except Exception as e:
            logger.error(f"Failed to process {pdf_file.name}: {e}")
            continue

    print(f"\n✓ Stage 1 complete: {len(parsed_files)} papers parsed")
    print(f"  Markdown files: {RAW_TEXT_DIR}")


# ============================================================================
# STAGE 2: CHUNKING
# ============================================================================

def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def chunk_text(text: str, page_num: int) -> List[dict]:
    """Chunk text into sections based on markdown headers."""
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
                sections.append({
                    'name': current_section_name or 'Content',
                    'text': '\n'.join(current_section_lines).strip()
                })
            current_section_name = header_match.group(2).strip()
            current_section_lines = []
        else:
            current_section_lines.append(line)

    if current_section_lines:
        sections.append({
            'name': current_section_name or 'Content',
            'text': '\n'.join(current_section_lines).strip()
        })

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

        section_chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = len(enc.encode(para))

            if para_tokens > TARGET_CHUNK_SIZE * 1.5:
                sentences = para.split('. ')
                for sent in sentences:
                    sent_tokens = len(enc.encode(sent))
                    if current_tokens + sent_tokens > TARGET_CHUNK_SIZE and current_chunk:
                        chunk_text = ' '.join(current_chunk)
                        section_chunks.append({
                            'text': chunk_text,
                            'token_count': current_tokens
                        })

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
                    chunk_text = ' '.join(current_chunk)
                    section_chunks.append({
                        'text': chunk_text,
                        'token_count': current_tokens
                    })

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
            chunk_text = ' '.join(current_chunk)
            section_chunks.append({
                'text': chunk_text,
                'token_count': current_tokens
            })

        for section_chunk in section_chunks:
            chunks.append({
                'text': section_chunk['text'],
                'page_num': page_num,
                'chunk_index': chunk_index,
                'section_name': section_name,
                'token_count': section_chunk['token_count']
            })
            chunk_index += 1

    return chunks


def load_markdown(md_path: Path) -> List[dict]:
    """Load markdown file and parse page markers."""
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
                pages.append({
                    'page_num': current_page,
                    'text': '\n'.join(current_text)
                })
            current_page = int(page_marker.group(1))
            current_text = []
        else:
            current_text.append(line)

    if current_text:
        pages.append({
            'page_num': current_page,
            'text': '\n'.join(current_text)
        })

    return pages


def stage_chunk(force: bool = False, new_only: bool = False):
    """Stage 2: Create chunks from markdown files."""
    print("\n" + "="*60)
    print("STAGE 2: CHUNKING")
    print("="*60)

    if not RAW_TEXT_DIR.exists():
        print(f"ERROR: Raw text directory not found: {RAW_TEXT_DIR}")
        print("Run Stage 1 (parse) first")
        return

    md_files = list(RAW_TEXT_DIR.glob("*.md"))
    if not md_files:
        print(f"ERROR: No markdown files found in {RAW_TEXT_DIR}")
        return

    print(f"Found {len(md_files)} markdown files")

    state = load_pipeline_state()
    chunked_files = set(state.get('chunked', []))

    # Determine which files to process
    if force:
        files_to_process = md_files
        print("Force mode: Re-chunking all files")
    elif new_only:
        files_to_process = [f for f in md_files if f.stem + '.pdf' not in chunked_files]
        print(f"New-only mode: Chunking {len(files_to_process)} new files")
    else:
        files_to_process = [f for f in md_files if f.stem + '.pdf' not in chunked_files]
        print(f"Chunking {len(files_to_process)} files (skipping {len(md_files) - len(files_to_process)} already chunked)")

    if not files_to_process:
        print("✓ All files already chunked!")
        return

    print("-"*60)

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    for md_file in tqdm(files_to_process, desc="Chunking", unit="file"):
        try:
            pages = load_markdown(md_file)
            if not pages:
                logger.warning(f"No pages loaded from {md_file.name}")
                continue

            all_chunks = []
            for page_data in pages:
                page_chunks = chunk_text(page_data['text'], page_data['page_num'])
                all_chunks.extend(page_chunks)

            # Save chunks to JSON
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

            # Update state
            if pdf_name not in chunked_files:
                chunked_files.add(pdf_name)
                state['chunked'] = list(chunked_files)
                save_pipeline_state(state)

        except Exception as e:
            logger.error(f"Failed to chunk {md_file.name}: {e}")
            continue

    print(f"\n✓ Stage 2 complete: {len(chunked_files)} papers chunked")
    print(f"  Chunks directory: {CHUNKS_DIR}")


# ============================================================================
# STAGE 3: METADATA EXTRACTION
# ============================================================================

def extract_doi_from_text(text: str) -> Optional[str]:
    """Extract DOI from paper text using regex patterns."""
    # DOI valid characters: alphanumeric, dash, dot, slash, parentheses
    doi_chars = r'[\w\-\.\(\)\/]+'

    doi_patterns = [
        # Match DOI in URLs (handles markdown links)
        rf'https?://doi\.org/(10\.\d{{4,}}/{doi_chars})',
        rf'https?://dx\.doi\.org/(10\.\d{{4,}}/{doi_chars})',
        # Match DOI with label
        rf'doi:\s*(10\.\d{{4,}}/{doi_chars})',
        rf'DOI:\s*(10\.\d{{4,}}/{doi_chars})',
        # Match bare DOI
        rf'\b(10\.\d{{4,}}/{doi_chars})\b',
    ]

    for pattern in doi_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            doi = match.group(1)
            # Clean up trailing punctuation
            doi = re.sub(r'[.,;:\s\)]+$', '', doi)
            return doi

    return None


def query_crossref_api(doi: str) -> Optional[dict]:
    """Query CrossRef API for canonical metadata using DOI."""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {
            'User-Agent': 'BatteryPaperLibrary/1.0 (mailto:researcher@example.com)'
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            message = data.get('message', {})

            metadata = {}

            titles = message.get('title', [])
            if titles:
                metadata['title'] = titles[0]

            authors = []
            for author in message.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                if family:
                    if given:
                        authors.append(f"{family}, {given}")
                    else:
                        authors.append(family)
            metadata['authors'] = authors[:10]

            published = message.get('published-print') or message.get('published-online')
            if published and 'date-parts' in published:
                date_parts = published['date-parts'][0]
                if date_parts:
                    metadata['year'] = str(date_parts[0])

            container_titles = message.get('container-title', [])
            if container_titles:
                metadata['journal'] = container_titles[0]

            return metadata
        else:
            return None

    except Exception as e:
        logger.debug(f"CrossRef API error: {e}")
        return None


@anthropic_api_call_with_retry
def _call_claude_for_metadata(text: str, filename: str, api_key: str, model: str) -> str:
    """Internal function to call Claude API with retry logic."""
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
  "paper_type": "one of: experimental, simulation, review, dataset, modeling, or method"
}}

STRICT FORMATTING RULES:
- Title: Title case, no period at the end, main title only (not subtitle)
- Authors: ALWAYS "Last, First" format, semicolon-separated (e.g., "Severson, Kristen; Attia, Peter; Jin, Norman")
- Year: 4-digit year ONLY (e.g., "2019")
- Journal: FULL NAME, never abbreviated (e.g., "Nature Energy" not "Nat. Energy", "Journal of Power Sources" not "J. Power Sources")
- Limit to first 10 authors if more than 10
- Use standard battery chemistry abbreviations (NMC, LFP, NCA, etc.)
- Include only chemistries explicitly mentioned or clearly studied
- Topics should be technical keywords (3-10 topics)
- For application, choose the most specific one that applies
- For paper_type: experimental=lab work, simulation=computational, review=literature survey, dataset=data publication, modeling=theoretical models, method=new methodology/technique
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

    # Get first 2-3 pages
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
        'title': '',
        'authors': [],
        'year': '',
        'journal': '',
        'doi': '',
        'chemistries': [],
        'topics': [],
        'application': 'general',
        'paper_type': 'experimental'
    }

    # Try DOI extraction
    doi = extract_doi_from_text(text_for_doi)
    crossref_data = None

    if doi:
        logger.info(f"  Found DOI: {doi}")
        metadata['doi'] = doi  # Always save DOI if found
        crossref_data = query_crossref_api(doi)

        if crossref_data:
            logger.info(f"  ✓ CrossRef data retrieved")
            metadata['title'] = crossref_data.get('title', '')
            metadata['authors'] = crossref_data.get('authors', [])
            metadata['year'] = crossref_data.get('year', '')
            metadata['journal'] = crossref_data.get('journal', '')
        else:
            logger.info(f"  ✗ CrossRef query failed")

    # Use Claude for battery fields or all fields
    try:
        response_text = _call_claude_for_metadata(
            text_for_analysis,
            md_path.name,
            api_key,
            CLAUDE_MODEL
        )

        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)

        claude_metadata = json.loads(response_text)

        if crossref_data:
            # Use Claude only for battery-specific fields
            metadata['chemistries'] = claude_metadata.get('chemistries', [])
            metadata['topics'] = claude_metadata.get('topics', [])
            metadata['application'] = claude_metadata.get('application', 'general')
            metadata['paper_type'] = claude_metadata.get('paper_type', 'experimental')
        else:
            # Use Claude for everything
            metadata.update(claude_metadata)

        # Normalize
        metadata['chemistries'] = [c.upper() for c in metadata.get('chemistries', [])]
        metadata['topics'] = [t.lower() for t in metadata.get('topics', [])]
        metadata['application'] = metadata.get('application', 'general').lower()
        metadata['paper_type'] = metadata.get('paper_type', 'experimental').lower()

        # Handle authors format
        if isinstance(metadata.get('authors'), str):
            metadata['authors'] = [a.strip() for a in metadata['authors'].split(';') if a.strip()]

        return metadata

    except Exception as e:
        logger.error(f"Failed to extract metadata: {e}")
        return metadata


def stage_metadata(force: bool = False, new_only: bool = False):
    """Stage 3: Extract metadata for papers."""
    print("\n" + "="*60)
    print("STAGE 3: METADATA EXTRACTION")
    print("="*60)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return

    if not RAW_TEXT_DIR.exists():
        print(f"ERROR: Raw text directory not found: {RAW_TEXT_DIR}")
        print("Run Stage 1 (parse) first")
        return

    md_files = list(RAW_TEXT_DIR.glob("*.md"))
    if not md_files:
        print(f"ERROR: No markdown files found")
        return

    print(f"Found {len(md_files)} markdown files")

    # Load existing metadata
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r') as f:
            all_metadata = json.load(f)
    else:
        all_metadata = {}

    state = load_pipeline_state()
    metadata_files = set(state.get('metadata', []))

    # Determine which files to process
    if force:
        files_to_process = md_files
        print("Force mode: Re-extracting metadata for all files")
    elif new_only:
        files_to_process = [f for f in md_files if f.stem + '.pdf' not in metadata_files]
        print(f"New-only mode: Extracting metadata for {len(files_to_process)} new files")
    else:
        files_to_process = [f for f in md_files if f.stem + '.pdf' not in metadata_files]
        print(f"Extracting metadata for {len(files_to_process)} files")

    if not files_to_process:
        print("✓ All files have metadata!")
        return

    print("-"*60)

    for md_file in tqdm(files_to_process, desc="Extracting metadata", unit="paper"):
        try:
            pdf_name = md_file.stem + '.pdf'

            logger.info(f"Processing {pdf_name}")
            metadata = extract_metadata_for_paper(md_file, api_key)

            all_metadata[pdf_name] = {
                **metadata,
                'extracted_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            # Save after each paper
            METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_metadata, f, indent=2)

            # Update state
            if pdf_name not in metadata_files:
                metadata_files.add(pdf_name)
                state['metadata'] = list(metadata_files)
                save_pipeline_state(state)

            # Rate limiting
            time.sleep(30)

        except Exception as e:
            logger.error(f"Failed to extract metadata for {md_file.name}: {e}")
            continue

    print(f"\n✓ Stage 3 complete: {len(metadata_files)} papers have metadata")
    print(f"  Metadata file: {METADATA_FILE}")


# ============================================================================
# STAGE 4: EMBEDDING & INDEXING
# ============================================================================

def stage_embed(force: bool = False):
    """Stage 4: Embed chunks and load into ChromaDB."""
    print("\n" + "="*60)
    print("STAGE 4: EMBEDDING & INDEXING")
    print("="*60)

    if not CHUNKS_DIR.exists() or not list(CHUNKS_DIR.glob("*_chunks.json")):
        print(f"ERROR: No chunk files found in {CHUNKS_DIR}")
        print("Run Stage 2 (chunk) first")
        return

    if not METADATA_FILE.exists():
        print(f"ERROR: Metadata file not found: {METADATA_FILE}")
        print("Run Stage 3 (metadata) first")
        return

    # Load metadata
    with open(METADATA_FILE, 'r') as f:
        all_metadata = json.load(f)

    # Load embedding model
    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    try:
        model = SentenceTransformer(EMBEDDING_MODEL)
        print("  Model loaded successfully")
    except Exception as e:
        print(f"ERROR: Failed to load model: {e}")
        return

    # Initialize ChromaDB
    print(f"\nInitializing ChromaDB at {DB_DIR}")
    DB_DIR.mkdir(parents=True, exist_ok=True)

    try:
        client = chromadb.PersistentClient(path=str(DB_DIR))

        if force:
            try:
                client.delete_collection(name=COLLECTION_NAME)
                print("  Deleted existing collection (force mode)")
            except:
                pass

        try:
            collection = client.get_collection(name=COLLECTION_NAME)
            existing_count = collection.count()
            print(f"  Found existing collection with {existing_count} chunks")
        except:
            collection = client.create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "Battery research papers chunks"}
            )
            print("  Created new collection")
    except Exception as e:
        print(f"ERROR: Failed to initialize ChromaDB: {e}")
        return

    # Load all chunks
    chunk_files = list(CHUNKS_DIR.glob("*_chunks.json"))
    print(f"\nFound {len(chunk_files)} chunk files")

    all_chunks = []
    for chunk_file in chunk_files:
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                filename = data['filename']
                chunks = data['chunks']

                # Add filename and metadata to each chunk
                paper_metadata = all_metadata.get(filename, {})
                for chunk in chunks:
                    chunk['filename'] = filename
                    chunk['paper_metadata'] = paper_metadata

                all_chunks.extend(chunks)
        except Exception as e:
            logger.error(f"Failed to load {chunk_file.name}: {e}")
            continue

    if not all_chunks:
        print("ERROR: No chunks loaded")
        return

    print(f"Loaded {len(all_chunks)} total chunks")
    print("-"*60)

    # Prepare data for ChromaDB
    texts = [chunk['text'] for chunk in all_chunks]
    metadatas = []

    for chunk in all_chunks:
        meta = {
            'filename': chunk['filename'],
            'page_num': chunk['page_num'],
            'chunk_index': chunk['chunk_index'],
            'token_count': chunk['token_count'],
            'section_name': chunk.get('section_name', 'Content')
        }

        if chunk.get('paper_metadata'):
            pm = chunk['paper_metadata']
            meta['title'] = pm.get('title', '')
            meta['authors'] = ';'.join(pm.get('authors', []))
            meta['year'] = pm.get('year', '')
            meta['journal'] = pm.get('journal', '')
            meta['doi'] = pm.get('doi', '')
            meta['chemistries'] = ','.join(pm.get('chemistries', []))
            meta['topics'] = ','.join(pm.get('topics', []))
            meta['application'] = pm.get('application', 'general')
            meta['paper_type'] = pm.get('paper_type', 'experimental')
        else:
            meta['title'] = ''
            meta['authors'] = ''
            meta['year'] = ''
            meta['journal'] = ''
            meta['doi'] = ''
            meta['chemistries'] = ''
            meta['topics'] = ''
            meta['application'] = 'general'
            meta['paper_type'] = 'experimental'

        metadatas.append(meta)

    ids = [f"{chunk['filename']}_p{chunk['page_num']}_c{chunk['chunk_index']}"
           for chunk in all_chunks]

    # Generate embeddings
    print("\nGenerating embeddings...")
    batch_size = 32
    embeddings = []

    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
        batch_texts = texts[i:i+batch_size]
        batch_embeddings = model.encode(batch_texts, show_progress_bar=False)
        embeddings.extend(batch_embeddings.tolist())

    # Store in ChromaDB
    print("\nStoring in ChromaDB...")
    try:
        collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print("✓ Successfully stored all chunks!")
    except Exception as e:
        print(f"ERROR: Failed to store in ChromaDB: {e}")
        return

    # Update state
    state = load_pipeline_state()
    state['embedded'] = list(all_metadata.keys())
    save_pipeline_state(state)

    print(f"\n✓ Stage 4 complete: {len(all_chunks)} chunks indexed")
    print(f"  Total chunks in database: {collection.count()}")
    print(f"  Database location: {DB_DIR}")


# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Modular ingestion pipeline for battery research papers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/ingest_pipeline.py --stage parse
  python scripts/ingest_pipeline.py --stage chunk --force
  python scripts/ingest_pipeline.py --stage metadata --new-only
  python scripts/ingest_pipeline.py --stage embed
  python scripts/ingest_pipeline.py --all
        """
    )

    parser.add_argument(
        '--stage',
        choices=['parse', 'chunk', 'metadata', 'embed'],
        help='Which stage to run'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all stages sequentially'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-processing of all files (ignores pipeline state)'
    )
    parser.add_argument(
        '--new-only',
        action='store_true',
        help='Process only new files not in pipeline state'
    )

    args = parser.parse_args()

    if not args.stage and not args.all:
        parser.print_help()
        return

    if args.all:
        print("Running full pipeline (all stages)")
        stage_parse(force=args.force, new_only=args.new_only)
        stage_chunk(force=args.force, new_only=args.new_only)
        stage_metadata(force=args.force, new_only=args.new_only)
        stage_embed(force=args.force)
        print("\n" + "="*60)
        print("✓ PIPELINE COMPLETE!")
        print("="*60)
    else:
        if args.stage == 'parse':
            stage_parse(force=args.force, new_only=args.new_only)
        elif args.stage == 'chunk':
            stage_chunk(force=args.force, new_only=args.new_only)
        elif args.stage == 'metadata':
            stage_metadata(force=args.force, new_only=args.new_only)
        elif args.stage == 'embed':
            stage_embed(force=args.force)


if __name__ == "__main__":
    main()
