#!/usr/bin/env python3
"""
Ingest script for battery research papers RAG system.
Extracts text from PDFs, chunks it, and stores in ChromaDB.

Features:
- Robust error handling with retry logic
- Progress tracking with detailed status output
- Resume capability (saves state, skips already-processed papers)
- Graceful failure (continues with next paper if one fails)
"""

import os
import sys
import json
import re
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import pymupdf4llm
import tiktoken
import chromadb
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic
from tqdm import tqdm

# Import retry utilities
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.retry import anthropic_api_call_with_retry

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


# Configuration
PAPERS_DIR = Path(__file__).parent.parent / "papers"
DB_DIR = Path(__file__).parent.parent / "data" / "chroma_db"
RAW_TEXT_DIR = Path(__file__).parent.parent / "raw_text"
STATE_FILE = Path(__file__).parent.parent / "data" / "ingest_state.json"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TARGET_CHUNK_SIZE = 600  # Target tokens per chunk
CHUNK_OVERLAP = 100  # Overlap between chunks in tokens
COLLECTION_NAME = "battery_papers"
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "data" / "ingest.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def load_ingest_state() -> Dict[str, Any]:
    """Load ingestion state from file to support resume capability."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                logger.info(f"Loaded ingest state: {len(state.get('completed', []))} papers already processed")
                return state
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}. Starting fresh.")

    return {'completed': [], 'failed': [], 'last_updated': None}


def save_ingest_state(state: Dict[str, Any]):
    """Save ingestion state to file."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state['last_updated'] = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save state file: {e}")


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """
    Extract text from PDF using PyMuPDF4LLM, organizing by page.
    Handles two-column layouts, tables, and section headers better than pypdf.
    Returns list of dicts with 'page_num' and 'text'.
    """
    print(f"  Extracting text from {pdf_path.name}...")
    pages = []

    try:
        # Use pymupdf4llm to extract text with better formatting
        # This handles academic papers with two-column layouts, tables, etc.
        md_text = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)

        # md_text is a list of dicts with 'metadata' and 'text' keys
        for page_data in md_text:
            page_num = page_data['metadata']['page'] + 1  # Convert 0-indexed to 1-indexed
            text = page_data['text']

            if text.strip():  # Only include pages with text
                pages.append({
                    'page_num': page_num,
                    'text': text
                })
    except Exception as e:
        print(f"    ERROR: Failed to extract from {pdf_path.name}: {e}")
        return []

    print(f"    Extracted {len(pages)} pages")
    return pages


def save_raw_markdown(pages: list[dict], pdf_filename: str, output_dir: Path):
    """
    Save raw extracted markdown to a file for future re-chunking.
    Concatenates all pages into a single markdown file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create markdown filename from PDF filename
    md_filename = pdf_filename.replace('.pdf', '.md')
    output_path = output_dir / md_filename

    # Concatenate all pages with page separators
    markdown_content = []
    for page_data in pages:
        page_num = page_data['page_num']
        text = page_data['text']
        markdown_content.append(f"<!-- Page {page_num} -->\n\n{text}\n\n")

    full_markdown = '\n'.join(markdown_content)

    # Write to file
    try:
        output_path.write_text(full_markdown, encoding='utf-8')
        print(f"    Saved raw markdown to {output_path.name}")
    except Exception as e:
        print(f"    WARNING: Failed to save markdown: {e}")


@anthropic_api_call_with_retry
def _call_claude_for_metadata(text: str, filename: str, api_key: str, model: str) -> str:
    """Internal function to call Claude API with retry logic."""
    prompt = f"""Analyze this battery research paper excerpt and extract structured metadata.

Paper excerpt:
{text}

Extract the following information and respond ONLY with a valid JSON object:

{{
  "chemistries": ["list of battery chemistries discussed, e.g., LFP, NMC, NCA, LCO, LMO, LTO, graphite, silicon, etc."],
  "topics": ["list of technical topics, e.g., degradation, SOH, RUL, capacity fade, impedance, EIS, cycling, calendar aging, thermal, SEI, lithium plating, etc."],
  "application": "primary application domain: EV, grid storage, consumer electronics, aerospace, or general",
  "paper_type": "one of: experimental, simulation, review, dataset, modeling, or method"
}}

Rules:
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
        max_tokens=500,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def extract_paper_metadata(pages: list[dict], filename: str, api_key: str) -> dict:
    """
    Use Claude to extract metadata from paper abstract/first pages.
    Returns dict with chemistries, topics, application, and paper_type.
    """
    # Get first 2-3 pages or up to ~3000 chars (usually includes abstract + intro)
    text_for_analysis = ""
    for page in pages[:3]:
        text_for_analysis += page['text'] + "\n\n"
        if len(text_for_analysis) > 3000:
            break

    text_for_analysis = text_for_analysis[:3500]  # Limit size

    try:
        response_text = _call_claude_for_metadata(
            text_for_analysis,
            filename,
            api_key,
            CLAUDE_MODEL
        )

        # Extract JSON from response (handle cases where Claude adds explanation)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)

        metadata = json.loads(response_text)

        # Validate and set defaults
        metadata.setdefault('chemistries', [])
        metadata.setdefault('topics', [])
        metadata.setdefault('application', 'general')
        metadata.setdefault('paper_type', 'experimental')

        # Convert to lowercase for consistency
        metadata['chemistries'] = [c.upper() for c in metadata.get('chemistries', [])]
        metadata['topics'] = [t.lower() for t in metadata.get('topics', [])]
        metadata['application'] = metadata.get('application', 'general').lower()
        metadata['paper_type'] = metadata.get('paper_type', 'experimental').lower()

        return metadata

    except Exception as e:
        print(f"    WARNING: Failed to extract metadata: {e}")
        print(f"    Using default metadata")
        return {
            'chemistries': [],
            'topics': [],
            'application': 'general',
            'paper_type': 'experimental'
        }


def chunk_text(text: str, page_num: int) -> list[dict]:
    """
    Chunk text into sections based on markdown headers, then split long sections.
    Preserves section context by detecting markdown headers (# Header, ## Subheader, etc.).
    Returns list of dicts with 'text', 'page_num', 'chunk_index', 'section_name', 'token_count'.
    """
    enc = tiktoken.get_encoding("cl100k_base")

    # Parse sections from markdown headers
    lines = text.split('\n')
    sections = []
    current_section_name = None
    current_section_lines = []

    header_pattern = r'^(#{1,6})\s+(.+)$'

    for line in lines:
        # Check if this line is a markdown header
        header_match = re.match(header_pattern, line.strip())
        if header_match:
            # Save previous section
            if current_section_lines:
                sections.append({
                    'name': current_section_name or 'Content',
                    'text': '\n'.join(current_section_lines).strip()
                })
            # Start new section
            current_section_name = header_match.group(2).strip()
            current_section_lines = []
        else:
            current_section_lines.append(line)

    # Add final section
    if current_section_lines:
        sections.append({
            'name': current_section_name or 'Content',
            'text': '\n'.join(current_section_lines).strip()
        })

    # If no sections found, treat entire text as one section
    if not sections:
        sections = [{'name': 'Content', 'text': text}]

    # Now chunk each section
    chunks = []
    chunk_index = 0

    for section in sections:
        section_name = section['name']
        section_text = section['text']

        if not section_text.strip():
            continue

        # Split section into paragraphs
        paragraphs = [p.strip() for p in section_text.split('\n\n') if p.strip()]

        section_chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = len(enc.encode(para))

            # If single paragraph exceeds target, split by sentences
            if para_tokens > TARGET_CHUNK_SIZE * 1.5:
                sentences = para.split('. ')
                for sent in sentences:
                    sent_tokens = len(enc.encode(sent))
                    if current_tokens + sent_tokens > TARGET_CHUNK_SIZE and current_chunk:
                        # Save current chunk
                        chunk_text = ' '.join(current_chunk)
                        section_chunks.append({
                            'text': chunk_text,
                            'token_count': current_tokens
                        })

                        # Keep overlap
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
                # Normal paragraph processing
                if current_tokens + para_tokens > TARGET_CHUNK_SIZE and current_chunk:
                    # Save current chunk
                    chunk_text = ' '.join(current_chunk)
                    section_chunks.append({
                        'text': chunk_text,
                        'token_count': current_tokens
                    })

                    # Keep overlap (last paragraph)
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

        # Add remaining chunk from this section
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            section_chunks.append({
                'text': chunk_text,
                'token_count': current_tokens
            })

        # Add section name and indices to all chunks from this section
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


def ingest_papers():
    """Main ingestion function."""
    print("\n" + "="*60)
    print("Battery Research Papers RAG - Ingestion Script")
    print("="*60)

    # Check papers directory
    if not PAPERS_DIR.exists():
        print(f"\nERROR: Papers directory not found: {PAPERS_DIR}")
        sys.exit(1)

    pdf_files = list(PAPERS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"\nERROR: No PDF files found in {PAPERS_DIR}")
        sys.exit(1)

    print(f"\nFound {len(pdf_files)} PDF files")

    # Get Anthropic API key for metadata extraction
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\nWARNING: ANTHROPIC_API_KEY not set")
        print("  Metadata tagging will be skipped")
        print("  Set API key to enable automatic paper tagging")
        use_metadata = False
    else:
        use_metadata = True
        print("\n✓ API key found - will extract metadata from papers")

    # Load embedding model
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    try:
        model = SentenceTransformer(EMBEDDING_MODEL)
        print("  Model loaded successfully")
    except Exception as e:
        print(f"  ERROR: Failed to load model: {e}")
        sys.exit(1)

    # Initialize ChromaDB
    print(f"\nInitializing ChromaDB at {DB_DIR}")
    DB_DIR.mkdir(parents=True, exist_ok=True)

    try:
        client = chromadb.PersistentClient(path=str(DB_DIR))

        # Delete existing collection if it exists
        try:
            client.delete_collection(name=COLLECTION_NAME)
            print("  Deleted existing collection")
        except:
            pass

        collection = client.create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Battery research papers chunks"}
        )
        print("  Collection created successfully")
    except Exception as e:
        print(f"  ERROR: Failed to initialize ChromaDB: {e}")
        sys.exit(1)

    # Load ingestion state for resume capability
    state = load_ingest_state()
    completed_files = set(state.get('completed', []))
    failed_files = set(state.get('failed', []))

    # Filter out already-processed files
    pdf_files_to_process = [
        f for f in pdf_files
        if f.name not in completed_files
    ]

    if len(pdf_files_to_process) < len(pdf_files):
        skipped = len(pdf_files) - len(pdf_files_to_process)
        print(f"\nResuming from previous run:")
        print(f"  ✓ {len(completed_files)} papers already processed")
        print(f"  ✗ {len(failed_files)} papers previously failed")
        print(f"  ⟳ {len(pdf_files_to_process)} papers remaining")
    else:
        print(f"\nProcessing {len(pdf_files)} PDFs...")

    if not pdf_files_to_process:
        print("\n✓ All papers already processed!")
        print(f"Total chunks in database: {collection.count()}")
        return

    print("-"*60)

    all_chunks = []
    successful_count = 0
    failed_count = 0

    # Process each PDF with progress bar
    for pdf_file in tqdm(pdf_files_to_process, desc="Processing PDFs", unit="paper"):
        logger.info(f"Processing: {pdf_file.name}")
        print(f"\n[{pdf_file.name}]")

        try:
            # Extract text from PDF
            pages = extract_text_from_pdf(pdf_file)
            if not pages:
                logger.warning(f"No pages extracted from {pdf_file.name}, skipping")
                state['failed'].append(pdf_file.name)
                failed_count += 1
                save_ingest_state(state)
                continue

            # Save raw markdown for future re-chunking
            save_raw_markdown(pages, pdf_file.name, RAW_TEXT_DIR)

            # Extract metadata using Claude
            paper_metadata = {}
            if use_metadata:
                print(f"  Extracting metadata with Claude...")
                paper_metadata = extract_paper_metadata(pages, pdf_file.name, api_key)
                print(f"    Chemistries: {', '.join(paper_metadata['chemistries']) if paper_metadata['chemistries'] else 'None detected'}")
                print(f"    Topics: {', '.join(paper_metadata['topics'][:5])}{'...' if len(paper_metadata['topics']) > 5 else ''}")
                print(f"    Application: {paper_metadata['application']}")
                print(f"    Type: {paper_metadata['paper_type']}")

                # Add delay to avoid rate limits
                print(f"    Waiting 30 seconds to avoid rate limits...")
                time.sleep(30)

            # Chunk each page
            print(f"  Chunking text...")
            file_chunks = []
            for page_data in pages:
                page_chunks = chunk_text(page_data['text'], page_data['page_num'])
                for chunk in page_chunks:
                    chunk['filename'] = pdf_file.name
                    # Add paper-level metadata to each chunk
                    chunk['paper_metadata'] = paper_metadata
                    file_chunks.append(chunk)

            print(f"    Created {len(file_chunks)} chunks")
            all_chunks.extend(file_chunks)

            # Mark as successfully processed
            state['completed'].append(pdf_file.name)
            successful_count += 1
            save_ingest_state(state)
            logger.info(f"✓ Successfully processed {pdf_file.name}")

        except Exception as e:
            # Log error but continue with next paper
            error_msg = f"Failed to process {pdf_file.name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(f"  ✗ ERROR: {e}")
            print(f"  Continuing with next paper...")

            state['failed'].append(pdf_file.name)
            failed_count += 1
            save_ingest_state(state)
            continue

    if not all_chunks:
        print("\nERROR: No chunks created from PDFs")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Total chunks created: {len(all_chunks)}")
    print(f"{'='*60}")

    # Generate embeddings and store in ChromaDB
    print("\nGenerating embeddings and storing in ChromaDB...")

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
        # Add paper-level metadata
        if chunk.get('paper_metadata'):
            pm = chunk['paper_metadata']
            meta['chemistries'] = ','.join(pm.get('chemistries', []))
            meta['topics'] = ','.join(pm.get('topics', []))
            meta['application'] = pm.get('application', 'general')
            meta['paper_type'] = pm.get('paper_type', 'experimental')
        else:
            meta['chemistries'] = ''
            meta['topics'] = ''
            meta['application'] = 'general'
            meta['paper_type'] = 'experimental'

        metadatas.append(meta)

    ids = [f"{chunk['filename']}_p{chunk['page_num']}_c{chunk['chunk_index']}"
           for chunk in all_chunks]

    # Generate embeddings in batches
    print("  Generating embeddings...")
    batch_size = 32
    embeddings = []

    for i in tqdm(range(0, len(texts), batch_size), desc="  Embedding batches"):
        batch_texts = texts[i:i+batch_size]
        batch_embeddings = model.encode(batch_texts, show_progress_bar=False)
        embeddings.extend(batch_embeddings.tolist())

    print("  Storing in ChromaDB...")
    try:
        collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print("  Successfully stored all chunks!")
    except Exception as e:
        print(f"  ERROR: Failed to store in ChromaDB: {e}")
        sys.exit(1)

    # Final summary
    print(f"\n{'='*60}")
    print("Ingestion Complete!")
    print(f"{'='*60}")
    print(f"  ✓ Successfully processed: {successful_count} papers")
    if failed_count > 0:
        print(f"  ✗ Failed: {failed_count} papers")
        print(f"    (see data/ingest.log for details)")
    print(f"  Total chunks created: {len(all_chunks)}")
    print(f"  Total chunks in database: {collection.count()}")
    print(f"  Database location: {DB_DIR}")
    print(f"  State file: {STATE_FILE}")
    print(f"{'='*60}\n")

    if failed_count > 0:
        logger.warning(f"Ingestion completed with {failed_count} failures")
        logger.warning(f"Failed papers: {state['failed']}")
    else:
        logger.info("Ingestion completed successfully!")


if __name__ == "__main__":
    ingest_papers()
