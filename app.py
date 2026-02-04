#!/usr/bin/env python3
"""
Streamlit web interface: Paper Library + RAG Query System
"""

import os
import sys
from pathlib import Path
import streamlit as st
import chromadb
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic
import pandas as pd

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


# Configuration
DB_DIR = Path(__file__).parent / "data" / "chroma_db"
PAPERS_DIR = Path(__file__).parent / "papers"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "battery_papers"
TOP_K = 5
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


# Page config
st.set_page_config(
    page_title="Battery Papers Library",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def load_embedding_model():
    """Load and cache the embedding model."""
    return SentenceTransformer(EMBEDDING_MODEL)


@st.cache_resource
def load_collection():
    """Load and cache the ChromaDB collection."""
    if not DB_DIR.exists():
        st.error(f"Database not found at {DB_DIR}")
        st.info("Please run `python scripts/ingest.py` first to create the database")
        st.stop()

    try:
        client = chromadb.PersistentClient(path=str(DB_DIR))
        collection = client.get_collection(name=COLLECTION_NAME)
        return collection
    except Exception as e:
        st.error(f"Failed to load collection: {e}")
        st.info("Please run `python scripts/ingest.py` first to create the database")
        st.stop()


def get_api_key():
    """Get Anthropic API key from environment or user input."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = st.session_state.get("anthropic_api_key")
    if not api_key:
        with st.sidebar:
            st.warning("⚠️ Anthropic API key required for queries")
            api_key = st.text_input(
                "Enter your Anthropic API key:",
                type="password",
                help="Get your API key from https://console.anthropic.com/"
            )
            if api_key:
                st.session_state.anthropic_api_key = api_key
                st.rerun()
    return api_key


@st.cache_data
def get_paper_library(_collection):
    """Get all unique papers with their metadata."""
    all_results = _collection.get(include=["metadatas"])

    papers = {}
    for metadata in all_results['metadatas']:
        filename = metadata['filename']
        if filename not in papers:
            papers[filename] = {
                'filename': filename,
                'chemistries': set(),
                'topics': set(),
                'application': metadata.get('application', 'general'),
                'paper_type': metadata.get('paper_type', 'experimental'),
                'pages': set()
            }

        # Aggregate metadata
        if metadata.get('chemistries'):
            papers[filename]['chemistries'].update(metadata['chemistries'].split(','))
        if metadata.get('topics'):
            papers[filename]['topics'].update(metadata['topics'].split(','))
        papers[filename]['pages'].add(metadata['page_num'])

    # Convert sets to sorted lists/counts
    for paper in papers.values():
        paper['chemistries'] = sorted([c for c in paper['chemistries'] if c])
        paper['topics'] = sorted([t for t in paper['topics'] if t])
        paper['num_pages'] = len(paper['pages'])
        del paper['pages']

    return list(papers.values())


@st.cache_data
def get_filter_options(_collection):
    """Extract unique values for filters."""
    all_results = _collection.get(include=["metadatas"])

    chemistries = set()
    topics = set()
    paper_types = set()

    for metadata in all_results['metadatas']:
        if metadata.get('chemistries'):
            chemistries.update(metadata['chemistries'].split(','))
        if metadata.get('topics'):
            topics.update(metadata['topics'].split(','))
        if metadata.get('paper_type'):
            paper_types.add(metadata['paper_type'])

    return {
        'chemistries': sorted([c for c in chemistries if c]),
        'topics': sorted([t for t in topics if t]),
        'paper_types': sorted(paper_types)
    }


def get_paper_details(collection, filename):
    """Get detailed information for a specific paper."""
    results = collection.get(
        where={"filename": filename},
        include=["documents", "metadatas"]
    )

    if not results['documents']:
        return None

    # Get first page or first few chunks
    first_chunks = []
    for i, (doc, meta) in enumerate(zip(results['documents'][:3], results['metadatas'][:3])):
        first_chunks.append({
            'page': meta['page_num'],
            'text': doc
        })

    return {
        'filename': filename,
        'chemistries': results['metadatas'][0].get('chemistries', '').split(','),
        'topics': results['metadatas'][0].get('topics', '').split(','),
        'application': results['metadatas'][0].get('application', 'general'),
        'paper_type': results['metadatas'][0].get('paper_type', 'experimental'),
        'preview_chunks': first_chunks
    }


def retrieve_relevant_chunks(collection, question: str, model: SentenceTransformer,
                            top_k: int = TOP_K, filter_chemistry: str = None,
                            filter_topic: str = None, filter_paper_type: str = None):
    """Retrieve top-K relevant chunks for the question."""
    question_embedding = model.encode([question])[0].tolist()

    # Build where clause for filtering
    where_clause = {}
    conditions = []

    if filter_chemistry:
        conditions.append({"chemistries": {"$contains": filter_chemistry.upper()}})
    if filter_topic:
        conditions.append({"topics": {"$contains": filter_topic.lower()}})
    if filter_paper_type:
        conditions.append({"paper_type": filter_paper_type})

    if conditions:
        where_clause = {"$and": conditions} if len(conditions) > 1 else conditions[0]

    try:
        query_params = {
            "query_embeddings": [question_embedding],
            "n_results": top_k
        }
        if where_clause:
            query_params["where"] = where_clause

        results = collection.query(**query_params)
    except Exception as e:
        st.error(f"Failed to query database: {e}")
        return []

    chunks = []
    if results['documents'] and results['documents'][0]:
        for i in range(len(results['documents'][0])):
            metadata = results['metadatas'][0][i]
            chunk = {
                'text': results['documents'][0][i],
                'filename': metadata['filename'],
                'page_num': metadata['page_num'],
                'chunk_index': metadata['chunk_index'],
                'chemistries': metadata.get('chemistries', '').split(',') if metadata.get('chemistries') else [],
                'topics': metadata.get('topics', '').split(',') if metadata.get('topics') else []
            }
            chunks.append(chunk)

    return chunks


def query_claude(question: str, chunks: list[dict], api_key: str):
    """Send question + context to Claude and get answer."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[Document {i}: {chunk['filename']}, page {chunk['page_num']}]\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""You are a helpful AI assistant specializing in battery research.
Answer the following question based on the provided research paper excerpts.

Important instructions:
- Cite your sources by referring to the document number and page (e.g., "According to Document 1, page 5...")
- If the information isn't in the provided excerpts, say so clearly
- Be specific and technical when appropriate
- If multiple papers discuss the same topic, mention all relevant sources

Context from research papers:

{context}

---

Question: {question}

Please provide a detailed answer with citations:"""

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        st.error(f"Failed to query Claude API: {e}")
        return None


def main():
    # Initialize session state
    if "selected_paper" not in st.session_state:
        st.session_state.selected_paper = None
    if "query_result" not in st.session_state:
        st.session_state.query_result = None
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Library"

    # Header
    st.title("🔋 Battery Research Papers Library")

    # Load resources
    collection = load_collection()
    model = load_embedding_model()
    papers = get_paper_library(collection)
    filter_options = get_filter_options(collection)

    # Sidebar
    with st.sidebar:
        st.header("🔍 Search & Filter")

        # Query box
        st.subheader("Ask a Question")
        question = st.text_area(
            "Natural language query:",
            placeholder="What factors affect battery degradation?",
            height=100,
            label_visibility="collapsed"
        )

        # Filters
        st.subheader("Filters")

        filter_chemistry = st.selectbox(
            "Chemistry",
            options=["All"] + filter_options['chemistries']
        )
        filter_chemistry = None if filter_chemistry == "All" else filter_chemistry

        filter_topic = st.selectbox(
            "Topic",
            options=["All"] + filter_options['topics']
        )
        filter_topic = None if filter_topic == "All" else filter_topic

        filter_paper_type = st.selectbox(
            "Paper Type",
            options=["All"] + filter_options['paper_types']
        )
        filter_paper_type = None if filter_paper_type == "All" else filter_paper_type

        # Query button
        if st.button("🔍 Search", type="primary", use_container_width=True):
            if not question:
                st.warning("Please enter a question")
            else:
                api_key = get_api_key()
                if api_key:
                    with st.spinner("Searching..."):
                        chunks = retrieve_relevant_chunks(
                            collection, question, model, TOP_K,
                            filter_chemistry, filter_topic, filter_paper_type
                        )

                        if not chunks:
                            st.warning("No relevant passages found. Try removing filters.")
                        else:
                            answer = query_claude(question, chunks, api_key)
                            if answer:
                                st.session_state.query_result = {
                                    'question': question,
                                    'answer': answer,
                                    'chunks': chunks,
                                    'filters': {
                                        'chemistry': filter_chemistry,
                                        'topic': filter_topic,
                                        'paper_type': filter_paper_type
                                    }
                                }
                                st.session_state.active_tab = "Query Results"
                                st.rerun()

        st.divider()

        # Library stats
        st.subheader("📊 Library Stats")
        st.metric("Total Papers", len(papers))
        st.metric("Total Chunks", collection.count())
        st.metric("Chemistries", len(filter_options['chemistries']))
        st.metric("Topics", len(filter_options['topics']))

    # Main content - Tabs
    tab1, tab2 = st.tabs(["📚 Library", "💬 Query Results"])

    with tab1:
        st.session_state.active_tab = "Library"

        if st.session_state.selected_paper:
            # Detail view
            paper_filename = st.session_state.selected_paper

            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(f"📄 {paper_filename}")
            with col2:
                if st.button("← Back to Library"):
                    st.session_state.selected_paper = None
                    st.rerun()

            details = get_paper_details(collection, paper_filename)

            if details:
                # Metadata
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("**Chemistries:**")
                    if details['chemistries'] and details['chemistries'][0]:
                        for chem in details['chemistries']:
                            if chem:
                                st.badge(chem, icon="⚗️")
                    else:
                        st.write("None detected")

                with col2:
                    st.write("**Application:**")
                    st.write(details['application'].title())

                with col3:
                    st.write("**Paper Type:**")
                    st.write(details['paper_type'].title())

                st.write("**Topics:**")
                if details['topics'] and details['topics'][0]:
                    topic_text = ", ".join([t for t in details['topics'] if t])
                    st.write(topic_text)
                else:
                    st.write("None detected")

                st.divider()

                # Preview
                st.subheader("📖 Preview")
                for chunk in details['preview_chunks']:
                    with st.expander(f"Page {chunk['page']}", expanded=True):
                        st.write(chunk['text'][:1000] + "..." if len(chunk['text']) > 1000 else chunk['text'])

                # PDF link
                st.divider()
                pdf_path = PAPERS_DIR / paper_filename
                if pdf_path.exists():
                    st.success(f"📎 PDF available: `{pdf_path}`")
                    st.info("Open the file from the papers/ directory to view the full PDF")
                else:
                    st.warning("PDF file not found")

        else:
            # Table view
            st.subheader("📚 Paper Library")

            # Create DataFrame
            df_data = []
            for paper in papers:
                df_data.append({
                    'Title': paper['filename'].replace('.pdf', ''),
                    'Chemistries': ', '.join(paper['chemistries'][:3]) + ('...' if len(paper['chemistries']) > 3 else ''),
                    'Topics': ', '.join(paper['topics'][:3]) + ('...' if len(paper['topics']) > 3 else ''),
                    'Type': paper['paper_type'].title(),
                    'Pages': paper['num_pages'],
                    '_filename': paper['filename']
                })

            df = pd.DataFrame(df_data)

            # Display table
            st.write(f"Showing {len(df)} papers")

            # Use data editor for clickable rows
            for idx, row in df.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 1])
                    with col1:
                        if st.button(row['Title'][:50], key=f"paper_{idx}", use_container_width=True):
                            st.session_state.selected_paper = row['_filename']
                            st.rerun()
                    with col2:
                        st.write(row['Chemistries'])
                    with col3:
                        st.write(row['Topics'][:40] + "..." if len(row['Topics']) > 40 else row['Topics'])
                    with col4:
                        st.write(row['Type'])
                    with col5:
                        st.write(f"{row['Pages']} pages")

    with tab2:
        st.session_state.active_tab = "Query Results"

        if st.session_state.query_result:
            result = st.session_state.query_result

            # Show question
            st.subheader("❓ Question")
            st.info(result['question'])

            # Show active filters
            if any(result['filters'].values()):
                st.caption("**Active Filters:** " +
                          ", ".join([f"{k}: {v}" for k, v in result['filters'].items() if v]))

            st.divider()

            # Show answer
            st.subheader("💡 Answer")
            st.markdown(result['answer'])

            st.divider()

            # Show sources
            st.subheader("📚 Sources & Citations")

            # Get unique papers cited
            cited_papers = {}
            for chunk in result['chunks']:
                filename = chunk['filename']
                if filename not in cited_papers:
                    cited_papers[filename] = []
                cited_papers[filename].append(chunk['page_num'])

            st.write(f"**{len(cited_papers)} papers cited:**")
            for filename, pages in cited_papers.items():
                st.write(f"- {filename} (pages: {', '.join(map(str, sorted(set(pages))))})")

            st.divider()

            # Show chunks
            st.subheader("📝 Retrieved Passages")
            for i, chunk in enumerate(result['chunks'], 1):
                with st.expander(f"Passage {i}: {chunk['filename']} (page {chunk['page_num']})"):
                    st.write(chunk['text'])
                    if chunk['chemistries'] or chunk['topics']:
                        st.caption(f"Chemistries: {', '.join(chunk['chemistries'])} | Topics: {', '.join(chunk['topics'][:5])}")

        else:
            st.info("👈 Ask a question in the sidebar to see results here")
            st.write("**Example questions:**")
            st.write("- What factors affect battery degradation?")
            st.write("- How does temperature impact NMC vs LFP cells?")
            st.write("- What is lithium plating and when does it occur?")
            st.write("- How to estimate state of health?")


if __name__ == "__main__":
    main()
