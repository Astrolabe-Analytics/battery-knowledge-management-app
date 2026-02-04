# Battery Research Papers RAG System

A simple Retrieval-Augmented Generation (RAG) system for searching battery research papers using ChromaDB and Claude.

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
   - Extracts text from PDFs using `pypdf`
   - Splits text into chunks (~500-800 tokens) with overlap
   - Generates embeddings using a local sentence-transformers model
   - Stores chunks with metadata (filename, page number) in ChromaDB

2. **Query (query.py)**:
   - Embeds your question using the same model
   - Searches ChromaDB for the top 5 most relevant chunks
   - Sends question + retrieved chunks to Claude (claude-sonnet-4-5-20250929)
   - Returns answer with citations (paper name + page number)

## Technical Details

- **PDF Processing**: pypdf (pure Python, no compilation needed)
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2 (runs locally, free)
- **Vector DB**: ChromaDB with persistent storage
- **LLM**: Claude Sonnet 4.5 via Anthropic API
- **Chunking**: ~600 tokens per chunk, 100 token overlap
- **Retrieval**: Top 5 most relevant chunks

## Example Output

```
Question: What factors affect battery degradation?

Searching for relevant passages (top 5)...
  [1] Preger_2020_J._Electrochem._Soc._167_120532.pdf (page 3)
  [2] Severson_NatureEnergy_2019.pdf (page 2)
  [3] history-agnostic-battery-degradation-inference.pdf (page 5)
  ...

Querying Claude (claude-sonnet-4-5-20250929)...

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
```

## Notes

- The system is designed as a proof-of-concept
- No web UI - command-line only
- Local embeddings (no API costs for embeddings)
- Persistent ChromaDB storage (no need to re-ingest unless papers change)
