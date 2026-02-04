#!/usr/bin/env python3
"""
Streamlit web interface: Paper Library + RAG Query System
Pure UI layer - all business logic delegated to lib.rag module
"""

import os
import sys
import streamlit as st
import pandas as pd

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Import backend
from lib import rag


# Page config
st.set_page_config(
    page_title="Battery Papers Library",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_api_key():
    """Get Anthropic API key from environment or user input (UI layer)."""
    api_key = rag.get_api_key_from_env()
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

    # Load resources using backend
    try:
        papers = rag.get_paper_library()
        filter_options = rag.get_filter_options()
        total_chunks = rag.get_collection_count()
    except (FileNotFoundError, RuntimeError) as e:
        st.error(str(e))
        st.info("Please run `python scripts/ingest.py` first to create the database")
        st.stop()

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
                        try:
                            # Use backend for search
                            chunks = rag.retrieve_relevant_chunks(
                                question=question,
                                top_k=rag.TOP_K,
                                filter_chemistry=filter_chemistry,
                                filter_topic=filter_topic,
                                filter_paper_type=filter_paper_type
                            )

                            if not chunks:
                                st.warning("No relevant passages found. Try removing filters.")
                            else:
                                # Use backend for LLM query
                                answer = rag.query_claude(question, chunks, api_key)
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
                        except RuntimeError as e:
                            st.error(f"Error: {e}")

        st.divider()

        # Library stats
        st.subheader("📊 Library Stats")
        st.metric("Total Papers", len(papers))
        st.metric("Total Chunks", total_chunks)
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

            # Get paper details from backend
            details = rag.get_paper_details(paper_filename)

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
                if rag.check_pdf_exists(paper_filename):
                    pdf_path = rag.get_pdf_path(paper_filename)
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
                section_label = f" - {chunk['section_name']}" if chunk.get('section_name') and chunk['section_name'] != 'Content' else ""
                with st.expander(f"Passage {i}: {chunk['filename']} (page {chunk['page_num']}){section_label}"):
                    st.write(chunk['text'])
                    metadata_parts = []
                    if chunk.get('section_name'):
                        metadata_parts.append(f"Section: {chunk['section_name']}")
                    if chunk['chemistries']:
                        metadata_parts.append(f"Chemistries: {', '.join(chunk['chemistries'])}")
                    if chunk['topics']:
                        metadata_parts.append(f"Topics: {', '.join(chunk['topics'][:5])}")
                    if metadata_parts:
                        st.caption(" | ".join(metadata_parts))

        else:
            st.info("👈 Ask a question in the sidebar to see results here")
            st.write("**Example questions:**")
            st.write("- What factors affect battery degradation?")
            st.write("- How does temperature impact NMC vs LFP cells?")
            st.write("- What is lithium plating and when does it occur?")
            st.write("- How to estimate state of health?")


if __name__ == "__main__":
    main()
