# Metadata Tagging Feature

## Overview

The RAG system now automatically extracts and tags papers with metadata during ingestion using Claude AI.

## Metadata Fields

Each paper is automatically tagged with:

- **chemistries**: List of battery chemistries (NMC, LFP, NCA, LCO, LMO, LTO, etc.)
- **topics**: Technical topics (degradation, SOH, RUL, EIS, thermal, SEI, lithium plating, etc.)
- **application**: Primary domain (EV, grid storage, consumer electronics, aerospace, general)
- **paper_type**: Type of paper (experimental, simulation, review, dataset, modeling, method)

## How It Works

### During Ingestion

1. **Extract Context**: Reads first 2-3 pages (usually abstract + intro)
2. **Analyze with Claude**: Sends text to Claude with structured prompt
3. **Parse Metadata**: Extracts JSON-formatted tags
4. **Store in ChromaDB**: Metadata attached to every chunk from that paper

### During Querying

You can now filter queries by chemistry or topic to get more focused results.

## Usage

### Re-ingest Papers (Required)

Since metadata is extracted during ingestion, you need to re-run the ingest script:

```bash
# Make sure ANTHROPIC_API_KEY is set
export ANTHROPIC_API_KEY='your-key-here'

# Re-ingest papers with metadata extraction
python scripts/ingest.py
```

Output will show extracted metadata for each paper:
```
[paper.pdf]
  Extracting text from paper.pdf...
    Extracted 10 pages
  Extracting metadata with Claude...
    Chemistries: NMC, LFP
    Topics: degradation, SOH, capacity fade, cycling, thermal
    Application: ev
    Type: experimental
  Chunking text...
    Created 25 chunks
```

### Query with Filters

**Command Line:**

```bash
# Filter by chemistry
python scripts/query.py --chemistry NMC "What causes degradation?"

# Filter by topic
python scripts/query.py --topic SOH "How to estimate state of health?"

# Filter by both
python scripts/query.py --chemistry LFP --topic degradation "LFP degradation mechanisms"
```

**Web Interface:**

1. Launch Streamlit: `streamlit run app.py`
2. Use dropdown filters in sidebar:
   - Chemistry filter (NMC, LFP, NCA, etc.)
   - Topic filter (degradation, SOH, RUL, etc.)
3. Ask your question with filters applied

## Examples

### Example 1: Chemistry Filter

```bash
python scripts/query.py --chemistry NMC "What is lithium plating?"
```

Only retrieves passages from papers that discuss NMC chemistry.

### Example 2: Topic Filter

```bash
python scripts/query.py --topic EIS "How is EIS used for battery characterization?"
```

Only retrieves passages from papers tagged with the EIS topic.

### Example 3: Combined Filters

```bash
python scripts/query.py --chemistry LFP --topic "calendar aging" "How do LFP cells age during storage?"
```

Only retrieves passages from LFP papers about calendar aging.

## Benefits

1. **More Focused Results**: Filter out irrelevant papers
2. **Faster Queries**: Search only relevant subset
3. **Better Answers**: Claude gets more targeted context
4. **Exploration**: Discover papers by chemistry/topic

## Technical Details

### Metadata Storage

Metadata is stored in ChromaDB as string fields:
- `chemistries`: Comma-separated uppercase list (e.g., "NMC,LFP,NCA")
- `topics`: Comma-separated lowercase list (e.g., "degradation,soh,rul")
- `application`: Single lowercase value (e.g., "ev")
- `paper_type`: Single lowercase value (e.g., "experimental")

### Filtering Implementation

Uses ChromaDB's `$contains` operator:
```python
where = {"chemistries": {"$contains": "NMC"}}
```

Combined filters use `$and`:
```python
where = {"$and": [
    {"chemistries": {"$contains": "NMC"}},
    {"topics": {"$contains": "degradation"}}
]}
```

## Notes

- Metadata extraction requires ANTHROPIC_API_KEY
- If API key is not set, ingestion continues without metadata
- Filters only work after re-ingesting with metadata enabled
- Chemistry and topic filters are case-insensitive
