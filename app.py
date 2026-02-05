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
import json
import re
import html
import time
import requests
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from pathlib import Path

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Import backend
from lib import rag, read_status, query_history, theme


def clean_html_from_text(text: str) -> str:
    """
    Remove HTML entities and tags from text.
    Converts &lt;sub&gt;4&lt;/sub&gt; to just "4"
    """
    if not text:
        return text

    # First, unescape HTML entities (&lt; -> <, &gt; -> >, etc.)
    text = html.unescape(text)

    # Then strip all HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    return text


# Page config
st.set_page_config(
    page_title="Battery Papers Library",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)


def load_theme_preference():
    """Load theme preference from settings file."""
    settings_file = Path("data/settings.json")
    if settings_file.exists():
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                return settings.get('theme', 'light')
        except:
            return 'light'
    return 'light'


def save_theme_preference(theme: str):
    """Save theme preference to settings file."""
    settings_file = Path("data/settings.json")
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing settings
    settings = {}
    if settings_file.exists():
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
        except:
            pass

    # Update theme
    settings['theme'] = theme

    # Save
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)


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


def query_crossref_for_metadata(doi: str) -> dict:
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

            # Title
            titles = message.get('title', [])
            if titles:
                metadata['title'] = titles[0]

            # Authors (format as "Last, First")
            authors = []
            for author in message.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                if family:
                    if given:
                        authors.append(f"{family}, {given}")
                    else:
                        authors.append(family)
            metadata['authors'] = authors[:10]  # Limit to 10

            # Year
            published = message.get('published-print') or message.get('published-online')
            if published and 'date-parts' in published:
                date_parts = published['date-parts'][0]
                if date_parts:
                    metadata['year'] = str(date_parts[0])

            # Journal
            container_titles = message.get('container-title', [])
            if container_titles:
                metadata['journal'] = container_titles[0]

            return metadata
        else:
            return {}
    except Exception as e:
        st.error(f"CrossRef API error: {e}")
        return {}


def update_paper_metadata(filename: str, doi: str, crossref_metadata: dict):
    """Update paper metadata in metadata.json and ChromaDB."""
    metadata_file = Path("data/metadata.json")

    # Load existing metadata
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            all_metadata = json.load(f)
    else:
        all_metadata = {}

    # Update metadata for this paper
    if filename in all_metadata:
        # Update with CrossRef data
        all_metadata[filename]['doi'] = doi
        if crossref_metadata:
            all_metadata[filename]['title'] = crossref_metadata.get('title', all_metadata[filename].get('title', ''))
            all_metadata[filename]['authors'] = crossref_metadata.get('authors', all_metadata[filename].get('authors', []))
            all_metadata[filename]['year'] = crossref_metadata.get('year', all_metadata[filename].get('year', ''))
            all_metadata[filename]['journal'] = crossref_metadata.get('journal', all_metadata[filename].get('journal', ''))

        # Save updated metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, indent=2, ensure_ascii=False)

        # Update ChromaDB
        update_chromadb_metadata(filename, all_metadata[filename])

        return True
    return False


def update_chromadb_metadata(filename: str, paper_metadata: dict):
    """Update metadata for all chunks of a paper in ChromaDB."""
    try:
        collection = rag.DatabaseClient.get_collection()

        # Get all chunks for this paper
        results = collection.get(
            where={"filename": filename},
            include=["metadatas"]
        )

        if not results['ids']:
            return

        # Update metadata for each chunk
        updated_metadatas = []
        for metadata in results['metadatas']:
            metadata['doi'] = paper_metadata.get('doi', '')
            metadata['title'] = paper_metadata.get('title', '')
            metadata['authors'] = ';'.join(paper_metadata.get('authors', []))
            metadata['year'] = paper_metadata.get('year', '')
            metadata['journal'] = paper_metadata.get('journal', '')
            updated_metadatas.append(metadata)

        # Update in ChromaDB
        collection.update(
            ids=results['ids'],
            metadatas=updated_metadatas
        )
    except Exception as e:
        st.error(f"Error updating ChromaDB: {e}")


def main():
    # Initialize session state
    if "selected_paper" not in st.session_state:
        st.session_state.selected_paper = None
    if "query_result" not in st.session_state:
        st.session_state.query_result = None
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Library"

    # Initialize theme
    if "theme" not in st.session_state:
        st.session_state.theme = load_theme_preference()

    # Initialize databases
    read_status.init_db()
    query_history.init_db()

    # Apply comprehensive theme-specific CSS using centralized theme module
    current_theme = st.session_state.theme
    st.markdown(theme.get_theme_css(current_theme), unsafe_allow_html=True)

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
        # Theme toggle at the top
        st.subheader("⚙️ Settings")

        current_theme = st.session_state.theme
        theme_label = "🌙 Dark Mode" if current_theme == "light" else "☀️ Light Mode"

        if st.button(theme_label, use_container_width=True):
            # Toggle theme
            new_theme = "dark" if current_theme == "light" else "light"
            st.session_state.theme = new_theme
            save_theme_preference(new_theme)
            st.rerun()

        st.divider()

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

                            # Prepare query result
                            query_result = {
                                'question': question,
                                'answer': answer,
                                'chunks': chunks,
                                'filters': {
                                    'chemistry': filter_chemistry,
                                    'topic': filter_topic,
                                    'paper_type': filter_paper_type
                                }
                            }

                            # Save to history database
                            query_history.save_query(
                                question=question,
                                answer=answer,
                                chunks=chunks,
                                filters=query_result['filters']
                            )

                            # Save to session state
                            st.session_state.query_result = query_result
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
    tab1, tab2, tab3 = st.tabs(["📚 Library", "💬 Query Results", "🕐 History"])

    with tab1:
        st.session_state.active_tab = "Library"

        # Upload section (only show when not viewing a paper detail)
        if not st.session_state.selected_paper:
            # Upload zone with theme-aware styling
            upload_container = st.container()
            with upload_container:
                st.markdown("### 📤 Add Papers to Library")
                st.caption("Drag and drop PDF files here, or click to browse")

                uploaded_files = st.file_uploader(
                    "Upload PDFs",
                    type=['pdf'],
                    accept_multiple_files=True,
                    label_visibility="collapsed",
                    key="pdf_uploader"
                )

                if uploaded_files:

                    # Check for duplicates
                    papers_dir = Path("papers")
                    papers_dir.mkdir(parents=True, exist_ok=True)

                    duplicates = []
                    new_files = []
                    for file in uploaded_files:
                        if (papers_dir / file.name).exists():
                            duplicates.append(file)
                        else:
                            new_files.append(file)

                    # Show what was uploaded
                    st.write(f"**{len(uploaded_files)} file(s) selected:**")

                    if new_files:
                        st.success(f"✅ {len(new_files)} new file(s):")
                        for file in new_files:
                            st.write(f"- {file.name} ({file.size / 1024:.1f} KB)")

                    if duplicates:
                        st.warning(f"⚠️ {len(duplicates)} duplicate(s) found:")
                        for file in duplicates:
                            st.write(f"- {file.name} (already exists in library)")

                        duplicate_action = st.radio(
                            "How to handle duplicates?",
                            ["Skip duplicates", "Replace existing papers"],
                            key="duplicate_action"
                        )
                    else:
                        duplicate_action = "Skip duplicates"

                    col1, col2 = st.columns([1, 4])
                    with col1:
                        process_disabled = len(new_files) == 0 and duplicate_action == "Skip duplicates"
                        if st.button("🚀 Process Papers", type="primary", disabled=process_disabled):
                            # Create a container for progress updates
                            progress_container = st.container()

                            # Process the files
                            replace_mode = duplicate_action == "Replace existing papers"
                            results = process_uploaded_pdfs(uploaded_files, progress_container, replace_duplicates=replace_mode)

                            # Show results
                            total_processed = len(results['saved']) + len(results['replaced'])
                            if total_processed > 0:
                                if results['replaced']:
                                    st.success(f"✅ Successfully processed {total_processed} paper(s)!")
                                    st.info(f"📝 Replaced {len(results['replaced'])} existing paper(s)")
                                else:
                                    st.success(f"✅ Successfully added {len(results['saved'])} paper(s) to library!")
                                st.toast(f"Processed {total_processed} paper(s)", icon="✅")

                            if results['skipped']:
                                st.warning(f"⚠️ Skipped {len(results['skipped'])} duplicate(s):")
                                for filename in results['skipped']:
                                    st.caption(f"- {filename} (already exists)")

                            if results['failed']:
                                st.error(f"❌ Failed to process {len(results['failed'])} file(s):")
                                for filename, error in results['failed']:
                                    st.caption(f"- {filename}: {error}")

                            # Clear the uploader and reload
                            if total_processed > 0:
                                st.balloons()
                                time.sleep(2)
                                st.rerun()

                    with col2:
                        if st.button("Cancel"):
                            st.rerun()

            st.divider()

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
                display_title = clean_html_from_text(details.get('title', paper_filename))
                st.subheader(f"📄 {display_title}")

                st.write("**Authors:**")
                if details.get('authors') and details['authors'][0]:
                    st.write('; '.join([a.strip() for a in details['authors'] if a.strip()]))
                else:
                    st.write("Unknown")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Year:** {details.get('year', 'Unknown')}")
                with col2:
                    st.write(f"**Journal:** {details.get('journal', 'Unknown')}")
                with col3:
                    doi = details.get('doi', '')
                    if doi:
                        st.write(f"**DOI:** [{doi}](https://doi.org/{doi})")
                    else:
                        st.write("**DOI:** Not available")

                # DOI refresh/edit section
                with st.expander("🔄 Update DOI & Metadata", expanded=True):
                    st.caption("Edit the DOI or refresh metadata from CrossRef")

                    # Editable DOI input
                    current_doi = details.get('doi', '')
                    new_doi = st.text_input(
                        "DOI",
                        value=current_doi,
                        placeholder="10.xxxx/xxxxx",
                        help="Enter or update the DOI for this paper",
                        key=f"doi_edit_{paper_filename}"
                    )

                    col_btn1, col_btn2 = st.columns(2)

                    with col_btn1:
                        # Refresh button - query CrossRef with current/edited DOI
                        if st.button("🔄 Refresh from CrossRef", key=f"refresh_{paper_filename}", use_container_width=True):
                            doi_to_use = new_doi.strip() if new_doi.strip() else current_doi
                            if doi_to_use:
                                with st.spinner(f'Querying CrossRef for DOI: {doi_to_use}...'):
                                    crossref_metadata = query_crossref_for_metadata(doi_to_use)

                                if crossref_metadata:
                                    success = update_paper_metadata(paper_filename, doi_to_use, crossref_metadata)
                                    if success:
                                        st.toast('✅ Metadata updated from CrossRef!', icon='✅')
                                        updated_title = clean_html_from_text(crossref_metadata.get('title', 'N/A'))
                                        st.success(f"""
                                        **Updated:**
                                        - Title: {updated_title}
                                        - Authors: {'; '.join(crossref_metadata.get('authors', [])[:3])}
                                        - Year: {crossref_metadata.get('year', 'N/A')}
                                        - Journal: {crossref_metadata.get('journal', 'N/A')}
                                        """)
                                        st.rerun()
                                else:
                                    st.warning("No metadata found in CrossRef for this DOI")
                            else:
                                st.warning("Please enter a DOI first")

                    with col_btn2:
                        # Save DOI button (without refreshing metadata)
                        if st.button("💾 Save DOI Only", key=f"save_doi_{paper_filename}", use_container_width=True):
                            if new_doi.strip() and new_doi.strip() != current_doi:
                                metadata_file = Path("data/metadata.json")
                                if metadata_file.exists():
                                    with open(metadata_file, 'r', encoding='utf-8') as f:
                                        all_metadata = json.load(f)

                                    if paper_filename in all_metadata:
                                        all_metadata[paper_filename]['doi'] = new_doi.strip()

                                        with open(metadata_file, 'w', encoding='utf-8') as f:
                                            json.dump(all_metadata, f, indent=2, ensure_ascii=False)

                                        # Update ChromaDB
                                        update_chromadb_metadata(paper_filename, all_metadata[paper_filename])

                                        st.toast('✅ DOI saved!', icon='✅')
                                        st.rerun()
                            elif new_doi.strip() == current_doi:
                                st.info("DOI unchanged")
                            else:
                                st.warning("Please enter a DOI")

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
            st.write(f"Showing {len(papers)} papers")

            # Get read statuses
            filenames = [p['filename'] for p in papers]
            read_statuses = read_status.get_read_status(filenames)

            # Create DataFrame with new columns
            df_data = []
            for paper in papers:
                # Format authors (first 3 + "et al." if more)
                authors_list = paper.get('authors', '').split(';') if paper.get('authors') else []
                authors_display = '; '.join([a.strip() for a in authors_list[:3] if a.strip()])
                if len(authors_list) > 3:
                    authors_display += '; et al.'

                # Format DOI for display
                doi = paper.get('doi', '')
                doi_display = doi if doi else '—'

                # Clean HTML from title
                title = paper.get('title', paper['filename'].replace('.pdf', ''))
                title = clean_html_from_text(title)

                df_data.append({
                    'Title': title,
                    'Authors': authors_display,
                    'Year': paper.get('year', ''),
                    'Journal': paper.get('journal', ''),
                    'DOI': doi_display,
                    'Read': read_statuses.get(paper['filename'], False),
                    '_filename': paper['filename'],
                    '_doi_url': f"https://doi.org/{doi}" if doi else ''
                })

            df = pd.DataFrame(df_data)

            # Configure AG Grid with flex sizing for full-width layout
            gb = GridOptionsBuilder.from_dataframe(df)

            # Configure column properties with flex sizing to fill container width
            gb.configure_column("Title",
                flex=3,  # Takes 3 parts of available space
                minWidth=250,
                wrapText=True,
                autoHeight=True,
                resizable=True,
                cellStyle={
                    'whiteSpace': 'normal',
                    'lineHeight': '1.4',
                    'display': '-webkit-box',
                    '-webkit-line-clamp': '2',
                    '-webkit-box-orient': 'vertical',
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis',
                    'padding': '8px'
                },
                tooltipField="Title"
            )
            gb.configure_column("Authors",
                flex=2,  # Takes 2 parts of available space
                minWidth=180,
                wrapText=True,
                autoHeight=False,
                resizable=True,
                cellStyle={
                    'whiteSpace': 'nowrap',
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis',
                    'padding': '8px'
                },
                tooltipField="Authors"
            )
            gb.configure_column("Year",
                width=70,  # Fixed width for narrow columns
                minWidth=60,
                maxWidth=90,
                resizable=True,
                type=["numericColumn"],
                cellStyle={
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis'
                }
            )
            gb.configure_column("Journal",
                flex=2,  # Takes 2 parts of available space
                minWidth=150,
                wrapText=False,
                resizable=True,
                cellStyle={
                    'whiteSpace': 'nowrap',
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis',
                    'padding': '8px'
                },
                tooltipField="Journal"
            )

            # DOI column - clickable link with hover-only edit icon
            doi_cell_renderer = JsCode("""
                class DoiRenderer {
                    init(params) {
                        this.eGui = document.createElement('div');
                        this.eGui.style.display = 'flex';
                        this.eGui.style.alignItems = 'center';
                        this.eGui.style.gap = '8px';
                        this.eGui.style.overflow = 'hidden';
                        this.eGui.style.width = '100%';

                        if (params.value === '—' || params.value === '') {
                            // No DOI - show placeholder and edit icon (hidden until hover)
                            const placeholder = document.createElement('span');
                            placeholder.innerText = 'Add DOI';
                            placeholder.style.color = '#999';
                            placeholder.style.fontStyle = 'italic';
                            placeholder.style.fontSize = '12px';
                            placeholder.style.overflow = 'hidden';
                            placeholder.style.textOverflow = 'ellipsis';
                            placeholder.style.whiteSpace = 'nowrap';

                            const editIcon = document.createElement('span');
                            editIcon.innerText = '✏️';
                            editIcon.style.cursor = 'pointer';
                            editIcon.style.fontSize = '14px';
                            editIcon.style.opacity = '0';
                            editIcon.style.transition = 'opacity 0.2s';
                            editIcon.style.flexShrink = '0';
                            editIcon.className = 'doi-edit-icon';
                            editIcon.title = 'Click to add DOI';
                            editIcon.addEventListener('click', (e) => {
                                params.node.setSelected(true);
                            });

                            this.eGui.appendChild(placeholder);
                            this.eGui.appendChild(editIcon);
                        } else {
                            // Has DOI - show clickable link and edit icon (hidden until hover)
                            const container = document.createElement('div');
                            container.style.display = 'flex';
                            container.style.alignItems = 'center';
                            container.style.gap = '8px';
                            container.style.width = '100%';
                            container.style.overflow = 'hidden';

                            const link = document.createElement('a');
                            link.innerText = params.value;
                            link.href = params.data._doi_url;
                            link.target = '_blank';
                            link.style.color = '#1f77b4';
                            link.style.textDecoration = 'underline';
                            link.style.flex = '1';
                            link.style.minWidth = '0';
                            link.style.cursor = 'pointer';
                            link.style.overflow = 'hidden';
                            link.style.textOverflow = 'ellipsis';
                            link.style.whiteSpace = 'nowrap';
                            // Prevent link click from selecting row
                            link.addEventListener('click', (e) => {
                                e.stopPropagation();
                            });

                            const editIcon = document.createElement('span');
                            editIcon.innerText = '✏️';
                            editIcon.style.cursor = 'pointer';
                            editIcon.style.fontSize = '14px';
                            editIcon.style.opacity = '0';
                            editIcon.style.transition = 'opacity 0.2s';
                            editIcon.style.flexShrink = '0';
                            editIcon.className = 'doi-edit-icon';
                            editIcon.title = 'Edit DOI';
                            // Let edit icon click bubble up to select row
                            editIcon.addEventListener('click', (e) => {
                                params.node.setSelected(true);
                            });

                            container.appendChild(link);
                            container.appendChild(editIcon);
                            this.eGui.appendChild(container);
                        }
                    }
                    getGui() {
                        return this.eGui;
                    }
                }
            """)
            gb.configure_column("DOI",
                flex=1.5,  # Takes 1.5 parts of available space
                minWidth=140,
                resizable=True,
                cellRenderer=doi_cell_renderer,
                cellStyle={
                    'overflow': 'hidden'
                },
                tooltipField="DOI"
            )

            # Read column with checkbox
            checkbox_renderer = JsCode("""
                function(params) {
                    return params.value ? '✓' : '';
                }
            """)
            gb.configure_column("Read",
                width=70,  # Fixed width for checkbox column
                minWidth=60,
                maxWidth=80,
                resizable=False,
                cellRenderer=checkbox_renderer,
                editable=True,
                cellEditor='agCheckboxCellEditor',
                cellStyle={
                    'overflow': 'hidden',
                    'textAlign': 'center'
                }
            )

            # Hide internal columns
            gb.configure_column("_filename", hide=True)
            gb.configure_column("_doi_url", hide=True)

            # Grid options - configured for full-width with virtualization for large datasets
            gb.configure_selection(selection_mode='single', use_checkbox=False)
            gb.configure_grid_options(
                headerHeight=40,
                suppressRowHoverHighlight=False,
                enableCellTextSelection=True,
                ensureDomOrder=True,
                domLayout='normal',  # Fixed height with internal scrolling and virtualization
                rowHeight=60,  # Fixed height to accommodate 2-line titles
                suppressHorizontalScroll=True,  # Disable horizontal scrolling - table fills width
                suppressColumnVirtualisation=False,  # Enable column virtualization
                suppressRowVirtualisation=False,  # Enable row virtualization for performance with many rows
            )

            grid_options = gb.build()

            # Custom CSS for professional appearance (theme-aware)
            if st.session_state.theme == 'dark':
                custom_css = {
                    # Headers
                    ".ag-header-cell-label": {"font-weight": "600", "color": "#FFFFFF !important"},
                    ".ag-header-cell-text": {"color": "#FFFFFF !important"},
                    ".ag-header": {"background-color": "#262730 !important", "border-bottom": "1px solid #444444 !important"},
                    ".ag-header-cell": {"background-color": "#262730 !important", "color": "#FFFFFF !important"},
                    # Rows and cells - prevent overflow
                    ".ag-root-wrapper": {"background-color": "#1E1E1E !important", "width": "100% !important"},
                    ".ag-row": {"border-bottom": "1px solid #444444 !important", "background-color": "#1E1E1E !important"},
                    ".ag-cell": {
                        "padding": "8px",
                        "display": "flex",
                        "align-items": "center",
                        "color": "#E0E0E0 !important",
                        "overflow": "hidden !important",
                        "text-overflow": "ellipsis !important"
                    },
                    ".ag-row-hover": {"background-color": "#2D2D2D !important"},
                    ".ag-row-hover .doi-edit-icon": {"opacity": "1 !important"},
                    # Grid background - full width
                    ".ag-center-cols-viewport": {"background-color": "#1E1E1E !important"},
                    ".ag-body-viewport": {"background-color": "#1E1E1E !important"},
                }
            else:
                custom_css = {
                    # Headers
                    ".ag-header-cell-label": {"font-weight": "600", "color": "#2c3e50 !important"},
                    ".ag-header-cell-text": {"color": "#2c3e50 !important"},
                    ".ag-header": {"background-color": "#F0F2F6 !important", "border-bottom": "1px solid #D0D0D0 !important"},
                    ".ag-header-cell": {"background-color": "#F0F2F6 !important", "color": "#2c3e50 !important"},
                    # Rows and cells - prevent overflow
                    ".ag-root-wrapper": {"background-color": "#FFFFFF !important", "width": "100% !important"},
                    ".ag-row": {"border-bottom": "1px solid #ecf0f1 !important", "background-color": "#FFFFFF !important"},
                    ".ag-cell": {
                        "padding": "8px",
                        "display": "flex",
                        "align-items": "center",
                        "color": "#262730 !important",
                        "overflow": "hidden !important",
                        "text-overflow": "ellipsis !important"
                    },
                    ".ag-row-hover": {"background-color": "#f8f9fa !important"},
                    ".ag-row-hover .doi-edit-icon": {"opacity": "1 !important"},
                    # Grid background - full width
                    ".ag-center-cols-viewport": {"background-color": "#FFFFFF !important"},
                    ".ag-body-viewport": {"background-color": "#FFFFFF !important"},
                }

            # Choose AG Grid theme based on app theme
            ag_theme = 'alpine-dark' if st.session_state.theme == 'dark' else 'alpine'

            grid_response = AgGrid(
                df,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.MODEL_CHANGED,
                fit_columns_on_grid_load=True,  # Auto-fit columns to fill container width
                theme=ag_theme,
                custom_css=custom_css,
                allow_unsafe_jscode=True,
                enable_enterprise_modules=False,
                height=1400,  # Fixed height to show ~23 rows with internal scrolling
                reload_data=False  # Improve performance by not reloading data unnecessarily
            )

            # Handle row selection for detail view (clicking row or edit icon opens detail)
            if grid_response['selected_rows'] is not None and len(grid_response['selected_rows']) > 0:
                selected_rows_df = pd.DataFrame(grid_response['selected_rows'])
                if len(selected_rows_df) > 0:
                    selected_row = selected_rows_df.iloc[0]
                    st.session_state.selected_paper = selected_row['_filename']
                    st.rerun()

            # Handle read status changes
            if grid_response['data'] is not None:
                updated_df = pd.DataFrame(grid_response['data'])
                for idx, row in updated_df.iterrows():
                    original_status = df_data[idx]['Read']
                    new_status = row['Read']
                    if original_status != new_status:
                        filename = row['_filename']
                        if new_status:
                            read_status.mark_as_read(filename)
                        else:
                            read_status.mark_as_unread(filename)
                        st.rerun()
                        break

    with tab2:
        st.session_state.active_tab = "Query Results"

        if st.session_state.query_result:
            result = st.session_state.query_result

            # Show indicator if loaded from history
            if result.get('from_history'):
                st.info("📜 Viewing query from history")

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

    with tab3:
        st.session_state.active_tab = "History"

        st.subheader("🕐 Query History")

        # Get all queries
        all_queries = query_history.get_all_queries()

        if not all_queries:
            st.info("No query history yet. Run a query to see it saved here!")
        else:
            # Show starred queries first if any exist
            starred_queries = [q for q in all_queries if q['is_starred']]
            unstarred_queries = [q for q in all_queries if not q['is_starred']]

            # Filter options
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                show_filter = st.selectbox(
                    "Show:",
                    ["All Queries", "Starred Only", "Recent (Last 10)"],
                    key="history_filter"
                )
            with col2:
                st.metric("Total Queries", len(all_queries))
            with col3:
                st.metric("Starred", len(starred_queries))

            # Apply filter
            if show_filter == "Starred Only":
                queries_to_show = starred_queries
            elif show_filter == "Recent (Last 10)":
                queries_to_show = all_queries[:10]
            else:
                queries_to_show = all_queries

            st.divider()

            # Show starred queries section
            if starred_queries and show_filter == "All Queries":
                st.subheader("⭐ Starred Queries")
                for query in starred_queries:
                    display_query_card(query)
                    st.divider()

                if unstarred_queries:
                    st.subheader("📋 All Queries")

            # Show queries
            if not queries_to_show:
                st.info("No queries match the selected filter.")
            else:
                for query in queries_to_show:
                    if show_filter != "All Queries" or not query['is_starred']:
                        display_query_card(query)
                        st.divider()

            # Clear all history button (at the bottom, with warning)
            st.divider()
            with st.expander("⚠️ Danger Zone", expanded=False):
                st.warning("Clear all query history? This cannot be undone!")
                if st.button("🗑️ Clear All History", type="secondary"):
                    count = query_history.clear_all_history()
                    st.success(f"Deleted {count} queries from history")
                    st.rerun()


def process_uploaded_pdfs(uploaded_files: list, progress_container, replace_duplicates: bool = False) -> Dict[str, Any]:
    """
    Process uploaded PDF files through the ingestion pipeline.

    Args:
        uploaded_files: List of uploaded file objects from st.file_uploader
        progress_container: Streamlit container for progress updates
        replace_duplicates: If True, replace existing files; if False, skip them

    Returns:
        Dictionary with processing results
    """
    import subprocess
    from pathlib import Path

    papers_dir = Path("papers")
    papers_dir.mkdir(parents=True, exist_ok=True)

    results = {
        'saved': [],
        'replaced': [],
        'skipped': [],
        'failed': [],
        'total': len(uploaded_files)
    }

    with progress_container:
        # Show immediate feedback
        st.info(f"🚀 Starting to process {len(uploaded_files)} file(s)...")
        time.sleep(0.5)  # Brief pause so user sees the message

    # Save uploaded files
    for i, uploaded_file in enumerate(uploaded_files, 1):
        filename = uploaded_file.name
        target_path = papers_dir / filename
        is_replacement = False

        with progress_container:
            st.caption(f"📄 Saving file {i}/{len(uploaded_files)}: {filename}")

        # Check for duplicates
        if target_path.exists():
            if replace_duplicates:
                # Delete the old file and mark for replacement
                try:
                    target_path.unlink()
                    is_replacement = True
                    with progress_container:
                        st.caption(f"♻️ Replacing existing file: {filename}")
                except Exception as e:
                    results['failed'].append((filename, f"Failed to replace: {str(e)}"))
                    with progress_container:
                        st.error(f"❌ Failed to replace {filename}: {str(e)}")
                    continue
            else:
                results['skipped'].append(filename)
                with progress_container:
                    st.caption(f"⏭️ Skipping duplicate: {filename}")
                continue

        try:
            # Save the file
            with open(target_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())

            if is_replacement:
                results['replaced'].append(filename)
            else:
                results['saved'].append(filename)

            with progress_container:
                st.caption(f"✓ Saved: {filename}")

        except Exception as e:
            results['failed'].append((filename, str(e)))
            with progress_container:
                st.error(f"❌ Failed to save {filename}: {str(e)}")

    # Run ingestion pipeline if we saved or replaced any files
    total_to_process = len(results['saved']) + len(results['replaced'])
    if total_to_process > 0:
        all_papers = results['saved'] + results['replaced']

        with progress_container:
            st.divider()
            if results['replaced']:
                st.info(f"📊 Processing {total_to_process} paper(s) through pipeline ({len(results['replaced'])} replacement(s))...")
            else:
                st.info(f"📊 Processing {total_to_process} new paper(s) through pipeline...")

            overall_progress = st.progress(0)
            stage_status = st.empty()
            paper_status = st.empty()

            try:
                # Stage 1: Parse (Extract text)
                stage_status.markdown("**Stage 1/4: 📄 Extracting text from PDFs**")
                for i, paper in enumerate(all_papers, 1):
                    paper_status.text(f"   Processing paper {i}/{total_to_process}: {paper}")
                    overall_progress.progress(int((i / total_to_process) * 20))
                    time.sleep(0.1)  # Brief pause for visibility

                result = subprocess.run(
                    [sys.executable, "scripts/ingest_pipeline.py", "--stage", "parse", "--new-only"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

                overall_progress.progress(25)
                paper_status.text("   ✓ Text extraction complete")
                time.sleep(0.3)

                # Stage 2: Chunk
                stage_status.markdown("**Stage 2/4: 📑 Creating chunks**")
                for i, paper in enumerate(all_papers, 1):
                    paper_status.text(f"   Chunking paper {i}/{total_to_process}: {paper}")
                    overall_progress.progress(25 + int((i / total_to_process) * 20))
                    time.sleep(0.1)

                result = subprocess.run(
                    [sys.executable, "scripts/ingest_pipeline.py", "--stage", "chunk", "--new-only"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

                overall_progress.progress(50)
                paper_status.text("   ✓ Chunking complete")
                time.sleep(0.3)

                # Stage 3: Metadata
                stage_status.markdown("**Stage 3/4: 🔍 Extracting metadata**")
                paper_status.text("   Using Claude to analyze papers and extract metadata...")
                overall_progress.progress(55)

                for i, paper in enumerate(all_papers, 1):
                    paper_status.text(f"   Analyzing paper {i}/{total_to_process}: {paper}")
                    # This stage takes longer, so update less frequently
                    overall_progress.progress(55 + int((i / total_to_process) * 20))
                    time.sleep(0.2)

                result = subprocess.run(
                    [sys.executable, "scripts/ingest_pipeline.py", "--stage", "metadata", "--new-only"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

                overall_progress.progress(75)
                paper_status.text("   ✓ Metadata extraction complete")
                time.sleep(0.3)

                # Stage 4: Embed
                stage_status.markdown("**Stage 4/4: 🧮 Generating embeddings and indexing**")
                paper_status.text("   Creating vector embeddings for semantic search...")
                overall_progress.progress(80)

                for i, paper in enumerate(all_papers, 1):
                    paper_status.text(f"   Embedding paper {i}/{total_to_process}: {paper}")
                    overall_progress.progress(80 + int((i / total_to_process) * 15))
                    time.sleep(0.1)

                result = subprocess.run(
                    [sys.executable, "scripts/ingest_pipeline.py", "--stage", "embed"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

                overall_progress.progress(100)
                paper_status.text("   ✓ Embeddings generated and indexed")
                stage_status.markdown("**✅ All stages complete!**")
                time.sleep(0.5)

            except subprocess.CalledProcessError as e:
                stage_status.markdown("**❌ Pipeline Error**")
                paper_status.text("")
                error_msg = e.stderr if e.stderr else str(e)
                st.error(f"Pipeline failed: {error_msg}")

                # Show detailed error if available
                if e.stdout:
                    with st.expander("Show pipeline output"):
                        st.code(e.stdout)

                # Mark all as failed
                all_files = results['saved'] + results['replaced']
                for filename in all_files:
                    results['failed'].append((filename, "Pipeline processing failed"))
                results['saved'] = []
                results['replaced'] = []

    return results


def display_query_card(query: Dict):
    """Display a single query card in the history view."""
    # Parse timestamp
    try:
        dt = datetime.fromisoformat(query['timestamp'])
        time_str = dt.strftime("%B %d, %Y at %I:%M %p")
    except:
        time_str = query['timestamp']

    # Create card layout
    col1, col2, col3, col4 = st.columns([6, 1, 1, 1])

    with col1:
        # Question preview (truncate if too long)
        question_preview = query['question']
        if len(question_preview) > 100:
            question_preview = question_preview[:100] + "..."

        st.markdown(f"**Q:** {question_preview}")
        st.caption(f"🕐 {time_str}")

        # Show filters if any
        if query['filters'] and any(query['filters'].values()):
            filter_text = ", ".join([
                f"{k.title()}: {v}"
                for k, v in query['filters'].items()
                if v
            ])
            st.caption(f"🔍 Filters: {filter_text}")

    with col2:
        # Star button
        star_icon = "⭐" if query['is_starred'] else "☆"
        if st.button(star_icon, key=f"star_{query['id']}", help="Star this query"):
            query_history.toggle_star(query['id'])
            st.rerun()

    with col3:
        # View button
        if st.button("👁️", key=f"view_{query['id']}", help="View this query"):
            # Load query into session state and switch to Query Results tab
            st.session_state.query_result = {
                'question': query['question'],
                'answer': query['answer'],
                'chunks': query['chunks'],
                'filters': query['filters'],
                'from_history': True
            }
            st.session_state.active_tab = "Query Results"
            st.rerun()

    with col4:
        # Delete button
        if st.button("🗑️", key=f"delete_{query['id']}", help="Delete this query"):
            query_history.delete_query(query['id'])
            st.toast("Query deleted", icon="🗑️")
            st.rerun()


if __name__ == "__main__":
    main()
