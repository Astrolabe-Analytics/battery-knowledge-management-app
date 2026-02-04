#!/usr/bin/env python3
"""
Streamlit web interface: Paper Library + RAG Query System
Pure UI layer - all business logic delegated to lib.rag module

Now uses improved retrieval pipeline with:
- Query expansion (Claude expands queries with related terms)
- Hybrid search (combines vector similarity + BM25 keyword search)
- Reranking (retrieves 15 candidates, reorders by relevance, returns top 5)
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
from lib import rag, read_status


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

    # Initialize read status database
    read_status.init_db()

    # Header
    st.title("🔋 Battery Research Papers Library")
    st.caption("✨ Now with improved retrieval: Query expansion + Hybrid search (Vector + BM25) + Reranking")

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
        if st.button("🔍 Search", type="primary", width='stretch'):
            if not question:
                st.warning("Please enter a question")
            else:
                api_key = get_api_key()
                if api_key:
                    # Show progress with improved retrieval steps
                    progress_text = st.empty()
                    progress_bar = st.progress(0)

                    try:
                        # Step 1: Query expansion
                        progress_text.text("Step 1/4: Expanding query...")
                        progress_bar.progress(25)

                        # Step 2: Hybrid search
                        progress_text.text("Step 2/4: Hybrid search (vector + BM25)...")
                        progress_bar.progress(50)

                        # Step 3: Reranking
                        progress_text.text("Step 3/4: Reranking by relevance...")
                        progress_bar.progress(75)

                        # Use improved retrieval pipeline
                        chunks = rag.retrieve_with_hybrid_and_reranking(
                            question=question,
                            api_key=api_key,
                            top_k=5,
                            n_candidates=15,
                            alpha=0.5,
                            filter_chemistry=filter_chemistry,
                            filter_topic=filter_topic,
                            filter_paper_type=filter_paper_type,
                            enable_query_expansion=True,
                            enable_reranking=True
                        )

                        if not chunks:
                            progress_text.empty()
                            progress_bar.empty()
                            st.warning("No relevant passages found. Try removing filters.")
                        else:
                            # Step 4: Query Claude
                            progress_text.text("Step 4/4: Generating answer with Claude...")
                            progress_bar.progress(90)

                            # Use backend for LLM query
                            answer = rag.query_claude(question, chunks, api_key)

                            progress_bar.progress(100)
                            progress_text.empty()
                            progress_bar.empty()

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
                        progress_text.empty()
                        progress_bar.empty()
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
                # Title and bibliographic info
                st.subheader(f"📄 {details.get('title', paper_filename)}")

                st.write("**Authors:**")
                if details.get('authors') and details['authors'][0]:
                    st.write('; '.join([a.strip() for a in details['authors'] if a.strip()]))
                else:
                    st.write("Unknown")

                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Year:** {details.get('year', 'Unknown')}")
                with col2:
                    st.write(f"**Journal:** {details.get('journal', 'Unknown')}")

                st.divider()

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

                # PDF viewing
                if rag.check_pdf_exists(paper_filename):
                    pdf_path = rag.get_pdf_path(paper_filename)

                    # Create a download button that opens PDF in new tab
                    with open(pdf_path, 'rb') as pdf_file:
                        pdf_bytes = pdf_file.read()
                        st.download_button(
                            label="📄 Open PDF in Browser",
                            data=pdf_bytes,
                            file_name=paper_filename,
                            mime="application/pdf",
                            width='stretch'
                        )

                    st.info(f"PDF location: `{pdf_path}`")
                else:
                    st.warning("PDF file not found")

                st.divider()

                # Preview
                st.subheader("📖 Preview")
                for chunk in details['preview_chunks']:
                    with st.expander(f"Page {chunk['page']}", expanded=True):
                        st.write(chunk['text'][:1000] + "..." if len(chunk['text']) > 1000 else chunk['text'])

        else:
            # Table view
            st.subheader("📚 Paper Library")

            # Get read statuses
            filenames = [p['filename'] for p in papers]
            read_statuses = read_status.get_read_status(filenames)

            # Create DataFrame with new columns
            df_data = []
            for paper in papers:
                # Format authors (first 3 + "et al." if more)
                # Authors are now semicolon-separated in "Last, First" format
                authors_list = paper.get('authors', '').split(';') if paper.get('authors') else []
                authors_display = '; '.join([a.strip() for a in authors_list[:3] if a.strip()])
                if len(authors_list) > 3:
                    authors_display += '; et al.'

                df_data.append({
                    'Title': paper.get('title', paper['filename'].replace('.pdf', '')),
                    'Authors': authors_display,
                    'Year': paper.get('year', ''),
                    'Journal': paper.get('journal', ''),
                    'Read': '✓' if read_statuses.get(paper['filename'], False) else '',
                    '_filename': paper['filename'],
                    '_is_read': read_statuses.get(paper['filename'], False)
                })

            # Display table header
            st.write(f"Showing {len(papers)} papers")

            # Create table header
            header_cols = st.columns([3, 2, 1, 2, 0.5])
            with header_cols[0]:
                st.markdown("**Title**")
            with header_cols[1]:
                st.markdown("**Authors**")
            with header_cols[2]:
                st.markdown("**Year**")
            with header_cols[3]:
                st.markdown("**Journal**")
            with header_cols[4]:
                st.markdown("**Read**")

            st.divider()

            # Display each paper as a row
            for i, paper_data in enumerate(df_data):
                col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 2, 0.5])

                with col1:
                    # Clickable title button
                    if st.button(
                        paper_data['Title'][:60] + ('...' if len(paper_data['Title']) > 60 else ''),
                        key=f"title_{i}",
                        width='stretch'
                    ):
                        st.session_state.selected_paper = paper_data['_filename']
                        st.rerun()

                with col2:
                    st.write(paper_data['Authors'][:40] + ('...' if len(paper_data['Authors']) > 40 else ''))

                with col3:
                    st.write(paper_data['Year'])

                with col4:
                    st.write(paper_data['Journal'][:30] + ('...' if len(paper_data['Journal']) > 30 else ''))

                with col5:
                    # Interactive checkbox for read status
                    is_read = st.checkbox(
                        label="",
                        value=paper_data['_is_read'],
                        key=f"read_{i}",
                        label_visibility="collapsed"
                    )
                    # Update read status if changed
                    if is_read != paper_data['_is_read']:
                        if is_read:
                            read_status.mark_as_read(paper_data['_filename'])
                        else:
                            read_status.mark_as_unread(paper_data['_filename'])
                        st.rerun()

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
