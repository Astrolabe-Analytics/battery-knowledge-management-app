#!/usr/bin/env python3
"""
Ingest script for battery research papers RAG system.
Extracts text from PDFs, chunks it, and stores in ChromaDB.
"""

import os
import sys
import json
import re
import time
from pathlib import Path
import pypdf
import tiktoken
import chromadb
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic
from tqdm import tqdm

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
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TARGET_CHUNK_SIZE = 600  # Target tokens per chunk
CHUNK_OVERLAP = 100  # Overlap between chunks in tokens
COLLECTION_NAME = "battery_papers"
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """
    Extract text from PDF, organizing by page.
    Returns list of dicts with 'page_num' and 'text'.
    """
    print(f"  Extracting text from {pdf_path.name}...")
    pages = []

    try:
        with open(pdf_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
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

    prompt = f"""Analyze this battery research paper excerpt and extract structured metadata.

Paper excerpt:
{text_for_analysis}

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

    try:
        client = Anthropic(api_key=api_key)

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()

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
    Chunk text into ~TARGET_CHUNK_SIZE tokens with CHUNK_OVERLAP overlap.
    Returns list of dicts with 'text', 'page_num', 'chunk_index'.
    """
    enc = tiktoken.get_encoding("cl100k_base")

    # Split into paragraphs (double newline or single newline with significant content change)
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    chunks = []
    current_chunk = []
    current_tokens = 0
    chunk_index = 0

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
                    chunks.append({
                        'text': chunk_text,
                        'page_num': page_num,
                        'chunk_index': chunk_index,
                        'token_count': current_tokens
                    })
                    chunk_index += 1

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
                chunks.append({
                    'text': chunk_text,
                    'page_num': page_num,
                    'chunk_index': chunk_index,
                    'token_count': current_tokens
                })
                chunk_index += 1

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

    # Add remaining chunk
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        chunks.append({
            'text': chunk_text,
            'page_num': page_num,
            'chunk_index': chunk_index,
            'token_count': current_tokens
        })

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

    # Process each PDF
    print(f"\nProcessing {len(pdf_files)} PDFs...")
    print("-"*60)

    all_chunks = []

    for idx, pdf_file in enumerate(pdf_files):
        print(f"\n[{pdf_file.name}]")

        # Extract text from PDF
        pages = extract_text_from_pdf(pdf_file)
        if not pages:
            continue

        # Extract metadata using Claude
        paper_metadata = {}
        if use_metadata:
            print(f"  Extracting metadata with Claude...")
            paper_metadata = extract_paper_metadata(pages, pdf_file.name, api_key)
            print(f"    Chemistries: {', '.join(paper_metadata['chemistries']) if paper_metadata['chemistries'] else 'None detected'}")
            print(f"    Topics: {', '.join(paper_metadata['topics'][:5])}{'...' if len(paper_metadata['topics']) > 5 else ''}")
            print(f"    Application: {paper_metadata['application']}")
            print(f"    Type: {paper_metadata['paper_type']}")

            # Add delay to avoid rate limits (except after last paper)
            if idx < len(pdf_files) - 1:
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
            'token_count': chunk['token_count']
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

    print(f"\n{'='*60}")
    print("Ingestion complete!")
    print(f"  Total documents: {len(all_chunks)}")
    print(f"  Database location: {DB_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    ingest_papers()
