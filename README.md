# Battery Research Papers RAG System

A Retrieval-Augmented Generation (RAG) system for searching battery research papers using ChromaDB and Claude.

## ✨ New: Improved Retrieval Pipeline

The system now uses an advanced retrieval pipeline with three key improvements:

1. **Query Expansion**: Automatically expands your question with related technical terms using Claude
   - Example: "LFP degradation" → "LFP degradation lithium iron phosphate LiFePO4 capacity fade aging calendar life cycle life"

2. **Hybrid Search**: Combines semantic (vector) and keyword (BM25) search
   - Vector search: Understands semantic meaning and context
   - BM25: Catches exact terms like cell model numbers or author names
   - Configurable weighting (default: 50/50 split)

3. **Reranking**: Two-stage retrieval for better relevance
   - Retrieves 15 candidate chunks using hybrid search
   - Uses Claude to reorder by actual relevance to your question
   - Returns top 5 most relevant chunks for final answer

These improvements significantly enhance retrieval quality, especially for technical queries.

## Project Structure

```
astrolabe-paper-db/
├── papers/              # PDF research papers (6 PDFs included)
├── scripts/
│   ├── ingest.py        # Parses PDFs, chunks text, stores in ChromaDB
│   └── query.py         # CLI tool to ask questions and get answers
├── data/
│   └── chroma_db/       # ChromaDB persistent storage (created by ingest.py)
├── app.py              # Streamlit web interface
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Anthropic API Key

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

On Windows (PowerShell):
```powershell
$env:ANTHROPIC_API_KEY='your-api-key-here'
```

### 3. Ingest Papers

Run the ingestion script to process PDFs and create the vector database:

```bash
python scripts/ingest.py
```

This will:
- Extract text from all PDFs in the `papers/` folder
- Chunk the text into ~600 token chunks with 100 token overlap
- Generate embeddings using `sentence-transformers/all-MiniLM-L6-v2`
- Store everything in ChromaDB at `data/chroma_db/`

## Usage

### Option 1: Web Interface (Recommended)

Launch the Streamlit web interface:

```bash
streamlit run app.py
```

This will open a web browser with an interactive chat interface where you can:
- Ask questions in a chat-like interface
- View answers with automatic source citations
- See retrieved passages from the papers
- Adjust the number of chunks to retrieve
- Browse chat history

### Option 2: Command-Line Interface

**Interactive Mode:**

Run without arguments to enter interactive mode:

```bash
python scripts/query.py
```

Then type your questions:
```
Question: What are the main factors affecting battery degradation?
Question: How does temperature affect lithium-ion battery performance?
Question: quit
```

**Single Question Mode:**

Pass your question as a command-line argument:

```bash
python scripts/query.py "What are the main factors affecting battery degradation?"
```

## How It Works

1. **Ingestion (ingest.py)**:
   - Extracts text from PDFs using `pymupdf4llm`
   - Splits text into chunks (~500-800 tokens) with overlap
   - Generates embeddings using a local sentence-transformers model
   - Stores chunks with metadata (filename, page number) in ChromaDB

2. **Query (query.py, app.py)** - Improved retrieval pipeline:
   - **Step 1 - Query Expansion**: Claude expands your question with related technical terms
   - **Step 2 - Hybrid Search**: Combines vector similarity + BM25 keyword search to retrieve 15 candidates
   - **Step 3 - Reranking**: Claude reorders candidates by relevance, selects top 5
   - **Step 4 - Answer Generation**: Sends question + top 5 chunks to Claude (claude-sonnet-4-5-20250929)
   - Returns answer with citations (paper name + page number)

## Technical Details

- **PDF Processing**: pymupdf4llm (enhanced extraction with structure awareness)
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2 (runs locally, free)
- **Vector DB**: ChromaDB with persistent storage
- **Keyword Search**: BM25 (rank-bm25 library)
- **LLM**: Claude Sonnet 4.5 via Anthropic API
- **Chunking**: ~600 tokens per chunk, 100 token overlap
- **Retrieval**:
  - Query expansion using Claude API
  - Hybrid search: 50% vector similarity + 50% BM25 keyword matching
  - Reranking: Retrieve 15 candidates, return top 5 after Claude-based reordering

## Example Output

```
Question: What factors affect battery degradation?

Step 1: Expanding query with related technical terms...
Step 2: Hybrid search (retrieving 15 candidates)...
Step 3: Reranking by relevance (selecting top 5)...

Final top 5 passages:
  [1] Preger_2020_J._Electrochem._Soc._167_120532.pdf (page 3)
  [2] Severson_NatureEnergy_2019.pdf (page 2)
  [3] history-agnostic-battery-degradation-inference.pdf (page 5)
  [4] battery_degradation_review.pdf (page 12)
  [5] cycle_aging_study.pdf (page 8)

Step 4: Querying Claude for final answer...

============================================================
ANSWER:
============================================================
According to the research papers, several key factors affect battery
degradation:

1. **Temperature**: Document 1, page 3 indicates that elevated temperatures
   accelerate capacity fade...

2. **Charge/Discharge Rates**: Document 2, page 2 discusses how fast
   charging increases stress on the electrodes...

[... rest of answer with citations ...]

------------------------------------------------------------
SOURCES:
------------------------------------------------------------
  [1] Preger_2020_J._Electrochem._Soc._167_120532.pdf, page 3
  [2] Severson_NatureEnergy_2019.pdf, page 2
  [3] history-agnostic-battery-degradation-inference.pdf, page 5
  [4] battery_degradation_review.pdf, page 12
  [5] cycle_aging_study.pdf, page 8
```

## Notes

- Includes both a Streamlit web interface and command-line interface
- Local embeddings (no API costs for embeddings)
- Persistent ChromaDB storage (no need to re-ingest unless papers change)
- Query expansion and reranking use Claude API (minimal token usage)
- Hybrid search balances semantic understanding with exact keyword matching
