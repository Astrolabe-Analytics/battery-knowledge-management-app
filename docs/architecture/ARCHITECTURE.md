# Architecture

This project follows a clean separation of concerns between frontend (UI) and backend (business logic).

## Structure

```
astrolabe-paper-db/
├── lib/                    # Backend modules (reusable, UI-agnostic)
│   ├── __init__.py
│   └── rag.py             # RAG system business logic
├── scripts/               # Standalone scripts
│   ├── ingest.py          # PDF ingestion pipeline
│   └── query.py           # CLI query tool
├── app.py                 # Streamlit UI (thin layer over lib.rag)
└── example_backend_usage.py  # Backend usage examples
```

## Backend Module (`lib/rag.py`)

Contains all business logic with no UI dependencies:

### Database Operations
- `DatabaseClient.get_collection()` - Load ChromaDB collection
- `get_paper_library()` - Get all papers with metadata
- `get_filter_options()` - Get unique filter values
- `get_paper_details(filename)` - Get details for specific paper
- `get_collection_count()` - Get total chunk count
- `check_pdf_exists(filename)` - Check if PDF exists
- `get_pdf_path(filename)` - Get PDF file path

### Search & Retrieval
- `retrieve_relevant_chunks(question, top_k, filters)` - Semantic search for relevant passages
- `EmbeddingModelLoader.get_model()` - Load and cache sentence transformer

### LLM Integration
- `query_claude(question, chunks, api_key)` - Get answer from Claude
- `get_api_key_from_env()` - Get API key from environment

### Design Patterns
- **Singleton pattern** for model/collection loading (caching)
- **Dependency injection** for API keys
- **Exceptions for control flow** (FileNotFoundError, RuntimeError)
- **Type hints** for clear interfaces

## Frontend (`app.py`)

Pure UI layer using Streamlit:
- **No database calls** - delegates to `rag.DatabaseClient`
- **No model loading** - delegates to `rag.EmbeddingModelLoader`
- **No search logic** - calls `rag.retrieve_relevant_chunks()`
- **No LLM calls** - calls `rag.query_claude()`
- **UI-specific logic only** - session state, input widgets, display

The frontend is a thin wrapper that:
1. Collects user input
2. Calls backend functions
3. Displays results

## Benefits

1. **Frontend flexibility** - Swap Streamlit for Flask, FastAPI, CLI, etc. without changing backend
2. **Testability** - Backend can be unit tested without UI
3. **Reusability** - Backend functions can be imported anywhere
4. **Maintainability** - Clear separation of concerns
5. **API readiness** - Backend can be exposed as REST API without refactoring

## Example: Using Backend Directly

```python
from lib import rag

# Search for papers
papers = rag.get_paper_library()

# Find relevant chunks
chunks = rag.retrieve_relevant_chunks(
    question="What causes battery degradation?",
    top_k=5,
    filter_chemistry="LFP"
)

# Get answer from LLM
api_key = rag.get_api_key_from_env()
answer = rag.query_claude(question, chunks, api_key)
```

See `example_backend_usage.py` for more examples.

## Future Frontend Options

With this architecture, you can easily create:

- **REST API** (FastAPI/Flask) - Expose backend as HTTP endpoints
- **CLI tool** - Import and call backend functions (already done in scripts/query.py)
- **Discord bot** - Use backend for Discord commands
- **Jupyter notebooks** - Interactive exploration
- **Desktop GUI** - PyQt/Tkinter frontend
- **Web frontend** - React/Vue.js calling backend API

All without modifying `lib/rag.py`.
