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
from lib import rag, read_status, query_history, theme, styles


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
    page_title="Astrolabe Research Library",
    page_icon="⚛️",
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

            # Abstract
            metadata['abstract'] = message.get('abstract', '')

            # Author keywords
            metadata['author_keywords'] = message.get('keywords', [])

            # Volume, Issue, Pages
            metadata['volume'] = message.get('volume', '')
            metadata['issue'] = message.get('issue', '')
            metadata['pages'] = message.get('page', '')

            # References
            metadata['references'] = message.get('reference', [])

            return metadata
        else:
            return {}
    except Exception as e:
        st.error(f"CrossRef API error: {e}")
        return {}


def save_metadata_only_paper(doi: str, crossref_metadata: dict) -> str:
    """Save metadata-only paper to ChromaDB and metadata.json"""
    import chromadb

    safe_doi = doi.replace('/', '_').replace('.', '_')
    filename = f"doi_{safe_doi}.pdf"

    # Save to metadata.json
    metadata_file = Path("data/metadata.json")
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    all_metadata = {}
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            all_metadata = json.load(f)

    all_metadata[filename] = {
        'filename': filename,
        'title': crossref_metadata.get('title', 'Unknown Title'),
        'authors': crossref_metadata.get('authors', []),
        'year': crossref_metadata.get('year', ''),
        'journal': crossref_metadata.get('journal', ''),
        'doi': doi,
        'chemistries': [],
        'topics': [],
        'application': 'general',
        'paper_type': 'experimental',
        'metadata_only': True,
        'date_added': datetime.now().isoformat(),
        'abstract': crossref_metadata.get('abstract', ''),
        'author_keywords': crossref_metadata.get('author_keywords', []),
        'volume': crossref_metadata.get('volume', ''),
        'issue': crossref_metadata.get('issue', ''),
        'pages': crossref_metadata.get('pages', ''),
        'source_url': '',
        'notes': '',
        'references': crossref_metadata.get('references', [])
    }

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    # Add to ChromaDB using the DatabaseClient to ensure consistency
    from lib.rag import DatabaseClient

    # First clear any cached collection to force a fresh connection
    DatabaseClient.clear_cache()

    # Now get a fresh collection reference
    collection = DatabaseClient.get_collection()

    doc_id = f"{filename}_metadata_only"
    try:
        collection.delete(ids=[doc_id])
    except:
        pass

    collection.add(
        documents=[f"Metadata-only: {crossref_metadata.get('title', '')}. DOI: {doi}"],
        metadatas=[{
            'filename': filename,
            'page_num': 0,
            'section_name': 'metadata_only',
            'title': crossref_metadata.get('title', ''),
            'authors': ';'.join(crossref_metadata.get('authors', [])) if crossref_metadata.get('authors') else '',
            'year': crossref_metadata.get('year', ''),
            'journal': crossref_metadata.get('journal', ''),
            'doi': doi,
            'chemistries': '',
            'topics': '',
            'application': 'general',
            'paper_type': 'experimental',
            'abstract': crossref_metadata.get('abstract', ''),
            'author_keywords': ';'.join(crossref_metadata.get('author_keywords', [])),
            'volume': crossref_metadata.get('volume', ''),
            'issue': crossref_metadata.get('issue', ''),
            'pages': crossref_metadata.get('pages', ''),
            'date_added': datetime.now().isoformat(),
            'source_url': ''
        }],
        ids=[doc_id]
    )

    # Clear cache again so next get_paper_library() call sees the new paper
    DatabaseClient.clear_cache()

    return filename


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

    # Apply professional CSS styling
    current_theme = st.session_state.theme
    st.markdown(styles.get_professional_css(current_theme), unsafe_allow_html=True)

    # Header - Clean and professional
    st.markdown("""
        <div class="app-header">
            <h1 class="app-title">Astrolabe Research Library</h1>
            <p class="app-subtitle">Battery research papers with AI-powered search</p>
        </div>
    """, unsafe_allow_html=True)

    # Load resources using backend
    try:
        papers = rag.get_paper_library()
        filter_options = rag.get_filter_options()
        total_chunks = rag.get_collection_count()
    except (FileNotFoundError, RuntimeError) as e:
        st.error(str(e))
        st.info("Please run `python scripts/ingest.py` first to create the database")
        st.stop()

    # Sidebar - Simplified and professional
    with st.sidebar:
        # Quick stats
        st.subheader("Library Stats")
        st.metric("Papers", len(papers))
        st.metric("Chunks", total_chunks)

    # Main content - Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Library", "Research", "History", "Settings"])

    with tab1:
        st.session_state.active_tab = "Library"

        # Upload section (only show when not viewing a paper detail)
        if not st.session_state.selected_paper:
            st.markdown("### Add Papers to Library")

            # Side-by-side layout for import options
            col_left, col_right = st.columns(2)

            with col_left:
                # URL import section
                with st.expander("Import from URL or DOI", expanded=False):
                    # Hide the "Press Enter to submit" message
                    st.markdown("""
                        <style>
                        /* Hide form submission instructions */
                        .stForm [data-testid="stMarkdownContainer"] p:contains("Press Enter") {
                            display: none !important;
                        }
                        .stForm small {
                            display: none !important;
                        }
                        [data-testid="InputInstructions"] {
                            display: none !important;
                        }
                        </style>
                    """, unsafe_allow_html=True)

                    with st.form("url_import_form", clear_on_submit=False):
                        st.caption("**Import from URL**")
                        url_input = st.text_input(
                            "Paste URL here",
                            placeholder="https://arxiv.org/abs/... or https://ieeexplore.ieee.org/...",
                            label_visibility="collapsed",
                            key="url_import_input"
                        )

                        st.caption("**Or enter DOI directly**")
                        doi_input = st.text_input(
                            "Enter DOI",
                            placeholder="10.1016/j.jpowsour.2024.235555",
                            label_visibility="collapsed",
                            key="doi_import_input"
                        )

                        st.caption("**Supported formats:**")
                        st.caption("• arXiv: `arxiv.org/abs/...` or `arxiv.org/pdf/...`")
                        st.caption("• DOI: `doi.org/10.xxxx/...` or `10.xxxx/...`")
                        st.caption("• Publisher pages: IEEE, ScienceDirect, Wiley, Springer, Nature, MDPI, ACS, RSC, IOP, etc.")
                        st.caption("• Direct PDF: Any URL ending in `.pdf`")

                        st.warning("⚠️ **Publisher Blocking:** Many publishers (especially ScienceDirect, Wiley, Springer) block automated access to their article pages. If you get a \"403 Forbidden\" error, use the **DOI field** instead, which bypasses the publisher page entirely.")

                        # Determine what to import
                        import_input = None
                        if url_input and doi_input:
                            st.warning("⚠️ Please use either URL or DOI, not both")
                        elif doi_input:
                            # Treat DOI as a doi.org URL
                            doi_clean = doi_input.strip()
                            if not doi_clean.startswith('http'):
                                import_input = f"https://doi.org/{doi_clean}"
                            else:
                                import_input = doi_clean
                        elif url_input:
                            import_input = url_input

                        submit_button = st.form_submit_button("Import", type="primary", use_container_width=True)

                    # Process result outside the form
                    if submit_button:
                        if not import_input:
                            st.warning("⚠️ Please enter a URL or DOI")

                    if submit_button and import_input:
                        # Create a container for progress updates
                        progress_container = st.container()

                        # Process the URL or DOI
                        result = process_url_import(import_input, progress_container)

                        # Show results
                        if result['success']:
                            if result['metadata_only']:
                                st.success(f"✅ Metadata saved for: **{result['title']}**")
                                st.info(f"📄 Filename: {result['filename']}")
                                st.info("📌 No open access PDF available. You can manually upload the PDF later.")
                                time.sleep(3)
                                st.rerun()
                            else:
                                st.success(f"✅ Successfully imported: **{result['title'] or result['filename']}**")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                        else:
                            st.error(f"❌ Import failed: {result['error']}")

            with col_right:
                # Drag-and-drop PDF upload
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
            # Detail view - Clean layout
            paper_filename = st.session_state.selected_paper

            # Get paper details from backend
            details = rag.get_paper_details(paper_filename)

            if details:
                from pathlib import Path  # Ensure Path is available in this scope

                # TOP BAR: Back button + Open PDF button
                col_back, col_pdf = st.columns([1, 2])
                with col_back:
                    if st.button("← Back to Library", use_container_width=True):
                        st.session_state.selected_paper = None
                        st.rerun()

                with col_pdf:
                    if rag.check_pdf_exists(paper_filename):
                        # Start PDF server (lazy initialization)
                        from lib import pdf_server
                        pdf_server.start_pdf_server()

                        # Get URL for the PDF
                        pdf_url = pdf_server.get_pdf_url(paper_filename)

                        # Create button that opens PDF in new tab
                        st.markdown(f"""
                        <style>
                        .pdf-open-button {{
                            display: inline-block;
                            width: 100%;
                            padding: 0.5rem 0.75rem;
                            background-color: #ff4b4b;
                            color: white;
                            text-align: center;
                            text-decoration: none;
                            border-radius: 0.5rem;
                            font-weight: 600;
                            font-size: 1rem;
                            transition: background-color 0.2s;
                        }}
                        .pdf-open-button:hover {{
                            background-color: #ff6b6b;
                            text-decoration: none;
                        }}
                        </style>
                        <a href="{pdf_url}" target="_blank" class="pdf-open-button">📄 Open PDF</a>
                        """, unsafe_allow_html=True)
                    else:
                        st.button("📄 No PDF Available", use_container_width=True, disabled=True)

                st.divider()

                # TITLE
                display_title = clean_html_from_text(details.get('title', paper_filename.replace('.pdf', '')))
                st.markdown(f"## {display_title}")

                # BIBLIOGRAPHIC INFO SECTION
                st.markdown("### 📚 Bibliographic Information")

                col1, col2 = st.columns(2)

                with col1:
                    # Authors
                    if details.get('authors') and details['authors'][0]:
                        authors_list = [a.strip() for a in details['authors'] if a.strip()]
                        st.markdown("**Authors:**")
                        for author in authors_list[:10]:  # Show up to 10 authors
                            st.markdown(f"- {author}")
                        if len(authors_list) > 10:
                            st.caption(f"... and {len(authors_list) - 10} more")
                    else:
                        st.markdown("**Authors:** _Not available_")

                    # Year
                    if details.get('year'):
                        st.markdown(f"**Year:** {details['year']}")

                    # Paper Type
                    if details.get('paper_type'):
                        st.markdown(f"**Type:** {details['paper_type'].title()}")

                    # Date Added
                    if details.get('date_added'):
                        try:
                            from datetime import datetime
                            date_str = details['date_added']
                            formatted_date = ''
                            # Try multiple formats
                            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                                try:
                                    dt = datetime.strptime(date_str.split('.')[0] if '.' in date_str else date_str, fmt)
                                    formatted_date = dt.strftime("%b %d, %Y")
                                    break
                                except:
                                    continue
                            st.markdown(f"**Added:** {formatted_date if formatted_date else date_str}")
                        except:
                            st.markdown(f"**Added:** {details['date_added']}")

                with col2:
                    # Journal
                    if details.get('journal'):
                        st.markdown(f"**Journal:** {details['journal']}")
                    else:
                        st.markdown("**Journal:** _Not available_")

                    # DOI
                    doi = details.get('doi', '')
                    if doi:
                        st.markdown(f"**DOI:** [{doi}](https://doi.org/{doi})")
                    else:
                        st.markdown("**DOI:** _Not available_")

                    # Application
                    if details.get('application'):
                        st.markdown(f"**Application:** {details['application'].title()}")

                    # Reference Count
                    ref_count = len(details.get('references', []))
                    if ref_count > 0:
                        st.markdown(f"**References:** {ref_count}")

                st.divider()

                # TAGS SECTION
                st.markdown("### 🏷️ Tags")

                # Author keywords
                author_keywords = details.get('author_keywords', [])
                if author_keywords and author_keywords[0]:
                    st.markdown("**Author Keywords:**")
                    author_tags_html = []
                    for keyword in author_keywords:
                        if keyword:
                            author_tags_html.append(f'<span class="tag-pill tag-author-keyword">{keyword}</span>')
                    if author_tags_html:
                        st.markdown('<div style="margin: 8px 0;">' + ''.join(author_tags_html) + '</div>', unsafe_allow_html=True)

                # AI-generated tags
                ai_tags_exist = False
                ai_tags_html = []

                # Chemistry tags
                if details.get('chemistries') and details['chemistries'][0]:
                    ai_tags_exist = True
                    for chem in details['chemistries']:
                        if chem:
                            ai_tags_html.append(f'<span class="tag-pill tag-chemistry">{chem}</span>')

                # Topic tags
                if details.get('topics') and details['topics'][0]:
                    ai_tags_exist = True
                    for topic in details['topics']:
                        if topic:
                            ai_tags_html.append(f'<span class="tag-pill tag-topic">{topic}</span>')

                if ai_tags_exist:
                    st.markdown("**AI-Generated Tags:**")
                    st.markdown('<div style="margin: 8px 0;">' + ''.join(ai_tags_html) + '</div>', unsafe_allow_html=True)

                if not author_keywords and not ai_tags_exist:
                    st.caption("_No tags available_")

                st.divider()

                # ABSTRACT SECTION (placeholder for now)
                st.markdown("### 📄 Abstract")
                if details.get('abstract'):
                    st.markdown(details['abstract'])
                else:
                    st.caption("_Abstract not yet extracted. This will be added in a future update._")

                st.divider()

                # NOTES SECTION (editable)
                st.markdown("### 📝 Notes")

                # Load notes from a notes file (or session state)
                notes_file = Path(f"data/notes/{paper_filename}.txt")
                notes_file.parent.mkdir(parents=True, exist_ok=True)

                current_notes = ""
                if notes_file.exists():
                    with open(notes_file, 'r', encoding='utf-8') as f:
                        current_notes = f.read()

                notes = st.text_area(
                    "Your notes about this paper:",
                    value=current_notes,
                    height=200,
                    key=f"notes_{paper_filename}",
                    placeholder="Add your notes, thoughts, or important findings here..."
                )

                col_save, col_clear = st.columns([1, 4])
                with col_save:
                    if st.button("💾 Save Notes", use_container_width=True):
                        with open(notes_file, 'w', encoding='utf-8') as f:
                            f.write(notes)
                        st.toast("Notes saved!", icon="✅")

                st.divider()

                # REFERENCES SECTION
                references = details.get('references', [])
                if references:
                    with st.expander(f"📚 References ({len(references)})", expanded=False):
                        st.caption("Papers cited by this work")

                        # Get all DOIs in the library for highlighting
                        library_dois = {p.get('doi', '').lower() for p in papers if p.get('doi')}

                        for i, ref in enumerate(references, 1):
                            # Format reference
                            ref_parts = []

                            # Authors
                            if ref.get('author'):
                                ref_parts.append(ref['author'])

                            # Year
                            if ref.get('year'):
                                ref_parts.append(f"({ref['year']})")

                            # Title
                            title = ref.get('article-title', '')
                            if title:
                                ref_parts.append(f'"{title}"')

                            # Journal
                            journal = ref.get('journal-title', '')
                            if journal:
                                journal_str = journal
                                if ref.get('volume'):
                                    journal_str += f", {ref['volume']}"
                                ref_parts.append(journal_str)

                            # Format the citation
                            citation = '. '.join(ref_parts) if ref_parts else f"Reference {i}"
                            if not citation.endswith('.'):
                                citation += '.'

                            # Check if this paper is in library
                            ref_doi = ref.get('DOI', '').lower()
                            in_library = ref_doi and ref_doi in library_dois

                            # Display with optional DOI link and library indicator
                            if in_library:
                                citation = f"**{citation}** 📚"  # Bold + library icon

                            if ref.get('DOI'):
                                doi_url = f"https://doi.org/{ref['DOI']}"
                                st.markdown(f"{i}. {citation} [DOI]({doi_url})")
                            else:
                                st.markdown(f"{i}. {citation}")

                        st.divider()
                        st.caption("**📚** = Paper is in your library")
                else:
                    with st.expander("📚 References", expanded=False):
                        st.caption("_No references found for this paper._")

                st.divider()

                # PDF UPLOAD (if no PDF exists)
                if not rag.check_pdf_exists(paper_filename):
                    with st.expander("📤 Upload PDF", expanded=True):
                        st.info("No PDF file found for this paper. Upload one to enable PDF viewing.")

                        uploaded_pdf = st.file_uploader(
                            "Upload PDF",
                            type=['pdf'],
                            key=f"upload_pdf_{paper_filename}"
                        )

                        if uploaded_pdf:
                            # Save uploaded PDF
                            papers_dir = Path("papers")
                            papers_dir.mkdir(parents=True, exist_ok=True)
                            pdf_path = papers_dir / paper_filename

                            with open(pdf_path, 'wb') as f:
                                f.write(uploaded_pdf.read())

                            st.success("✅ PDF uploaded successfully!")
                            st.info("Processing PDF... This may take a moment.")

                            # TODO: Run ingestion pipeline on the uploaded PDF
                            time.sleep(1)
                            st.rerun()

                st.divider()

                # EDIT METADATA SECTION (at the bottom)
                with st.expander("Edit Metadata", expanded=False):
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
                        if st.button("🔄 Refresh from CrossRef", key=f"refresh_{paper_filename}", use_container_width=True):
                            doi_to_use = new_doi.strip() if new_doi.strip() else current_doi
                            if doi_to_use:
                                with st.spinner(f'Querying CrossRef for DOI: {doi_to_use}...'):
                                    crossref_metadata = query_crossref_for_metadata(doi_to_use)

                                if crossref_metadata:
                                    success = update_paper_metadata(paper_filename, doi_to_use, crossref_metadata)
                                    if success:
                                        st.toast('✅ Metadata updated from CrossRef!', icon='✅')
                                        st.rerun()
                                else:
                                    st.warning("No metadata found in CrossRef for this DOI")
                            else:
                                st.warning("Please enter a DOI first")

                    with col_btn2:
                        if st.button("💾 Save", key=f"save_doi_{paper_filename}", use_container_width=True):
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

        else:
            # Table view
            st.subheader("Paper Library")

            # Search box
            search_query = st.text_input(
                "Search papers",
                placeholder="Search by title, authors, journal...",
                label_visibility="collapsed",
                key="library_search"
            )

            # Horizontal filter bar
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_chemistry = st.selectbox(
                    "Chemistry",
                    options=["All Chemistries"] + filter_options['chemistries'],
                    key="library_filter_chemistry"
                )
            with col2:
                filter_topic = st.selectbox(
                    "Topic",
                    options=["All Topics"] + filter_options['topics'],
                    key="library_filter_topic"
                )
            with col3:
                filter_paper_type = st.selectbox(
                    "Paper Type",
                    options=["All Types"] + filter_options['paper_types'],
                    key="library_filter_paper_type"
                )

            # Apply filters
            filtered_papers = papers

            # Text search filter - searches across title, authors, journal, DOI, keywords, and tags
            if search_query:
                search_lower = search_query.lower()
                filtered_papers = [
                    p for p in filtered_papers
                    if (search_lower in p.get('title', '').lower() or
                        search_lower in p.get('authors', '').lower() or
                        search_lower in p.get('journal', '').lower() or
                        search_lower in p.get('doi', '').lower() or
                        # Search in author keywords
                        any(search_lower in kw.lower() for kw in p.get('author_keywords', [])) or
                        # Search in AI-generated chemistries and topics
                        any(search_lower in chem.lower() for chem in p.get('chemistries', [])) or
                        any(search_lower in topic.lower() for topic in p.get('topics', [])))
                ]

            # Chemistry filter
            if filter_chemistry and filter_chemistry != "All Chemistries":
                filtered_papers = [
                    p for p in filtered_papers
                    if filter_chemistry in p.get('chemistries', [])
                ]

            # Topic filter
            if filter_topic and filter_topic != "All Topics":
                filtered_papers = [
                    p for p in filtered_papers
                    if filter_topic in p.get('topics', [])
                ]

            # Paper type filter
            if filter_paper_type and filter_paper_type != "All Types":
                filtered_papers = [
                    p for p in filtered_papers
                    if p.get('paper_type') == filter_paper_type.lower()
                ]

            st.write(f"Showing {len(filtered_papers)} of {len(papers)} papers")

            # Get read statuses
            filenames = [p['filename'] for p in filtered_papers]
            read_statuses = read_status.get_read_status(filenames)

            # Create DataFrame with new columns
            df_data = []
            for paper in filtered_papers:
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

                # Format date_added (like "Feb 4, 2026")
                date_added_str = ''
                if paper.get('date_added'):
                    try:
                        from datetime import datetime
                        date_str = paper['date_added']
                        # Try multiple formats
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                            try:
                                dt = datetime.strptime(date_str.split('.')[0] if '.' in date_str else date_str, fmt)
                                date_added_str = dt.strftime("%b %d, %Y")
                                break
                            except:
                                continue
                        if not date_added_str:
                            # If all parsing fails, try to extract just the date
                            date_added_str = date_str.split()[0] if date_str else ''
                    except:
                        date_added_str = ''

                # Determine status: check if PDF exists
                from pathlib import Path
                pdf_path = Path("papers") / paper['filename']
                if pdf_path.exists():
                    status = "✅ PDF"  # Checkmark - has PDF
                elif paper.get('title') or paper.get('doi'):
                    status = "⚠️ Metadata"  # Warning - has metadata but no PDF
                else:
                    status = "❌ Missing"  # X - no data

                df_data.append({
                    'Status': status,
                    'Title': title,
                    'Authors': authors_display,
                    'Year': paper.get('year', ''),
                    'Journal': paper.get('journal', ''),
                    'Added': date_added_str,
                    'DOI': doi_display,
                    'Read': read_statuses.get(paper['filename'], False),
                    '_filename': paper['filename'],
                    '_doi_url': f"https://doi.org/{doi}" if doi else ''
                })

            df = pd.DataFrame(df_data)

            # Configure AG Grid with flex sizing for full-width layout
            gb = GridOptionsBuilder.from_dataframe(df)

            # Configure column properties with flex sizing to fill container width
            # Status column with emoji indicators (colorblind-friendly)
            status_cell_renderer = JsCode("""
                class StatusCellRenderer {
                    init(params) {
                        this.eGui = document.createElement('div');
                        this.eGui.style.textAlign = 'center';
                        this.eGui.style.padding = '8px';
                        this.eGui.style.fontSize = '14px';
                        this.eGui.textContent = params.value;
                    }

                    getGui() {
                        return this.eGui;
                    }
                }
            """)

            gb.configure_column("Status",
                width=110,
                minWidth=110,
                maxWidth=120,
                resizable=True,
                cellRenderer=status_cell_renderer,
                cellStyle={
                    'textAlign': 'center',
                    'padding': '4px 8px',
                    'fontSize': '14px',
                    'whiteSpace': 'nowrap',
                    'overflow': 'visible',
                    'display': 'flex',
                    'alignItems': 'center',
                    'justifyContent': 'center'
                }
            )

            gb.configure_column("Title",
                flex=3,  # Takes 3 parts of available space
                minWidth=250,
                wrapText=True,
                autoHeight=False,
                resizable=True,
                cellStyle={
                    'whiteSpace': 'normal !important',
                    'lineHeight': '1.4 !important',
                    'display': '-webkit-box !important',
                    '-webkit-line-clamp': '2 !important',
                    '-webkit-box-orient': 'vertical !important',
                    'overflow': 'hidden !important',
                    'textOverflow': 'ellipsis !important',
                    'padding': '8px !important',
                    'maxHeight': '45px !important'
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
                    'whiteSpace': 'normal !important',
                    'lineHeight': '1.4 !important',
                    'display': '-webkit-box !important',
                    '-webkit-line-clamp': '2 !important',
                    '-webkit-box-orient': 'vertical !important',
                    'overflow': 'hidden !important',
                    'textOverflow': 'ellipsis !important',
                    'padding': '8px !important',
                    'maxHeight': '45px !important'
                },
                tooltipField="Authors"
            )
            gb.configure_column("Year",
                width=70,  # Fixed width for narrow columns
                minWidth=60,
                maxWidth=90,
                resizable=True,
                cellStyle={
                    'whiteSpace': 'nowrap !important',
                    'overflow': 'hidden !important',
                    'textOverflow': 'ellipsis !important',
                    'display': 'flex !important',
                    'justifyContent': 'flex-start !important',
                    'alignItems': 'center !important',
                    'textAlign': 'left !important',
                    'paddingLeft': '8px !important'
                }
            )
            gb.configure_column("Journal",
                flex=2,  # Takes 2 parts of available space
                minWidth=150,
                wrapText=True,
                resizable=True,
                cellStyle={
                    'whiteSpace': 'normal !important',
                    'lineHeight': '1.4 !important',
                    'display': '-webkit-box !important',
                    '-webkit-line-clamp': '2 !important',
                    '-webkit-box-orient': 'vertical !important',
                    'overflow': 'hidden !important',
                    'textOverflow': 'ellipsis !important',
                    'padding': '8px !important',
                    'maxHeight': '45px !important'
                },
                tooltipField="Journal"
            )
            gb.configure_column("Added",
                width=110,
                minWidth=100,
                maxWidth=130,
                resizable=True,
                cellStyle={
                    'whiteSpace': 'nowrap !important',
                    'overflow': 'hidden !important',
                    'textOverflow': 'ellipsis !important',
                    'display': 'flex !important',
                    'justifyContent': 'flex-start !important',
                    'alignItems': 'center !important',
                    'textAlign': 'left !important',
                    'paddingLeft': '8px !important',
                    'fontSize': '13px !important'
                }
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
            # Structural properties are identical in both themes, only colors differ
            if st.session_state.theme == 'dark':
                custom_css = {
                    # Headers - consistent structure, dark colors
                    ".ag-header-cell-label": {
                        "font-weight": "600",
                        "font-size": "14px",
                        "font-family": "inherit",
                        "color": "#FFFFFF !important"
                    },
                    ".ag-header-cell-text": {
                        "color": "#FFFFFF !important",
                        "font-size": "14px"
                    },
                    ".ag-header": {
                        "background-color": "#262730 !important",
                        "border-bottom": "1px solid #444444 !important",
                        "height": "40px !important"
                    },
                    ".ag-header-cell": {
                        "background-color": "#262730 !important",
                        "color": "#FFFFFF !important",
                        "padding": "0 8px !important"
                    },
                    # Rows and cells - consistent structure, dark colors
                    ".ag-root-wrapper": {
                        "background-color": "#1E1E1E !important",
                        "width": "100% !important",
                        "font-family": "inherit",
                        "font-size": "14px"
                    },
                    ".ag-row": {
                        "border-bottom": "1px solid #444444 !important",
                        "background-color": "#1E1E1E !important",
                        "height": "60px !important"
                    },
                    ".ag-cell": {
                        "padding": "8px !important",
                        "display": "flex !important",
                        "align-items": "center !important",
                        "color": "#E0E0E0 !important",
                        "overflow": "hidden !important",
                        "text-overflow": "ellipsis !important",
                        "font-size": "14px !important",
                        "font-family": "inherit !important",
                        "line-height": "1.5 !important"
                    },
                    # Multi-line text cells with line-clamp
                    ".ag-cell .ag-cell-value": {
                        "display": "-webkit-box !important",
                        "-webkit-line-clamp": "2 !important",
                        "-webkit-box-orient": "vertical !important",
                        "overflow": "hidden !important",
                        "text-overflow": "ellipsis !important",
                        "white-space": "normal !important",
                        "line-height": "1.4 !important",
                        "max-height": "42px !important",
                        "width": "100% !important"
                    },
                    ".ag-row-hover": {"background-color": "#2D2D2D !important"},
                    ".ag-row-hover .doi-edit-icon": {"opacity": "1 !important"},
                    # Grid background - full width
                    ".ag-center-cols-viewport": {"background-color": "#1E1E1E !important"},
                    ".ag-body-viewport": {"background-color": "#1E1E1E !important"},
                }
            else:
                custom_css = {
                    # Headers - consistent structure, light colors
                    ".ag-header-cell-label": {
                        "font-weight": "600",
                        "font-size": "14px",
                        "font-family": "inherit",
                        "color": "#2c3e50 !important"
                    },
                    ".ag-header-cell-text": {
                        "color": "#2c3e50 !important",
                        "font-size": "14px"
                    },
                    ".ag-header": {
                        "background-color": "#F0F2F6 !important",
                        "border-bottom": "1px solid #D0D0D0 !important",
                        "height": "40px !important"
                    },
                    ".ag-header-cell": {
                        "background-color": "#F0F2F6 !important",
                        "color": "#2c3e50 !important",
                        "padding": "0 8px !important"
                    },
                    # Rows and cells - consistent structure, light colors
                    ".ag-root-wrapper": {
                        "background-color": "#FFFFFF !important",
                        "width": "100% !important",
                        "font-family": "inherit",
                        "font-size": "14px"
                    },
                    ".ag-row": {
                        "border-bottom": "1px solid #ecf0f1 !important",
                        "background-color": "#FFFFFF !important",
                        "height": "60px !important"
                    },
                    ".ag-cell": {
                        "padding": "8px !important",
                        "display": "flex !important",
                        "align-items": "center !important",
                        "color": "#262730 !important",
                        "overflow": "hidden !important",
                        "text-overflow": "ellipsis !important",
                        "font-size": "14px !important",
                        "font-family": "inherit !important",
                        "line-height": "1.5 !important"
                    },
                    # Multi-line text cells with line-clamp
                    ".ag-cell .ag-cell-value": {
                        "display": "-webkit-box !important",
                        "-webkit-line-clamp": "2 !important",
                        "-webkit-box-orient": "vertical !important",
                        "overflow": "hidden !important",
                        "text-overflow": "ellipsis !important",
                        "white-space": "normal !important",
                        "line-height": "1.4 !important",
                        "max-height": "42px !important",
                        "width": "100% !important"
                    },
                    ".ag-row-hover": {"background-color": "#f8f9fa !important"},
                    ".ag-row-hover .doi-edit-icon": {"opacity": "1 !important"},
                    # Grid background - full width
                    ".ag-center-cols-viewport": {"background-color": "#FFFFFF !important"},
                    ".ag-body-viewport": {"background-color": "#FFFFFF !important"},
                }

            # Use streamlit theme for both modes - consistent base, colors controlled by custom CSS
            ag_theme = 'streamlit'

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
        st.session_state.active_tab = "Research"

        # Prominent "Ask a Question" section at the top
        st.subheader("Ask a Research Question")
        st.caption("Ask questions about your battery research papers using AI-powered search")

        question = st.text_area(
            "Your question:",
            placeholder="What factors affect battery degradation?",
            height=100,
            label_visibility="collapsed",
            key="research_question"
        )

        # Filters in horizontal layout
        st.caption("**Optional Filters:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_chemistry = st.selectbox(
                "Chemistry",
                options=["All"] + filter_options['chemistries'],
                key="research_filter_chemistry"
            )
            filter_chemistry = None if filter_chemistry == "All" else filter_chemistry
        with col2:
            filter_topic = st.selectbox(
                "Topic",
                options=["All"] + filter_options['topics'],
                key="research_filter_topic"
            )
            filter_topic = None if filter_topic == "All" else filter_topic
        with col3:
            filter_paper_type = st.selectbox(
                "Paper Type",
                options=["All"] + filter_options['paper_types'],
                key="research_filter_paper_type"
            )
            filter_paper_type = None if filter_paper_type == "All" else filter_paper_type

        # Search button
        if st.button("Search", type="primary", use_container_width=True, key="research_search_button"):
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
                            st.rerun()
                    except RuntimeError as e:
                        progress_text.empty()
                        progress_bar.empty()
                        st.error(f"Error: {e}")

        st.divider()

        # Show results if available
        if st.session_state.query_result:
            result = st.session_state.query_result

            # Show indicator if loaded from history
            if result.get('from_history'):
                st.info("Viewing query from history")

            # Show question
            st.subheader("Question")
            st.info(result['question'])

            # Show active filters
            if any(result['filters'].values()):
                st.caption("**Active Filters:** " +
                          ", ".join([f"{k}: {v}" for k, v in result['filters'].items() if v]))

            st.divider()

            # Show answer
            st.subheader("Answer")
            st.markdown(result['answer'])

            st.divider()

            # Show sources
            st.subheader("Sources & Citations")

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
            st.subheader("Retrieved Passages")
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
            st.info("💡 **Tip:** Ask questions about your battery research papers and get AI-powered answers")
            st.write("**Example questions:**")
            st.write("- What factors affect battery degradation?")
            st.write("- How does temperature impact NMC vs LFP cells?")
            st.write("- What is lithium plating and when does it occur?")
            st.write("- How to estimate state of health?")

    with tab3:
        st.session_state.active_tab = "History"

        st.subheader("Query History")

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

    with tab4:
        st.session_state.active_tab = "Settings"

        st.markdown("### ⚙️ Application Settings")

        # Theme Settings
        st.markdown("#### Appearance")

        current_theme = st.session_state.theme
        theme_label = "🌙 Switch to Dark Mode" if current_theme == "light" else "☀️ Switch to Light Mode"

        if st.button(theme_label, use_container_width=True, type="primary"):
            # Toggle theme
            new_theme = "dark" if current_theme == "light" else "light"
            st.session_state.theme = new_theme
            save_theme_preference(new_theme)
            st.rerun()

        st.caption(f"Current theme: **{current_theme.title()}**")

        st.divider()

        # Backup & Restore
        st.markdown("#### Backup & Restore")
        st.caption("Create backups of your database and restore from previous backups.")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Create Backup**")
            if st.button("📦 Create Backup", use_container_width=True):
                with st.spinner("Creating backup..."):
                    from lib import backup as backup_module
                    result = backup_module.create_backup(include_logs=False)

                    if result['success']:
                        st.success(f"✓ Backup created!")
                        st.caption(f"Size: {result['size_mb']} MB")
                        st.caption(f"Files: {result['file_count']}")

                        # Offer download
                        with open(result['backup_path'], 'rb') as f:
                            st.download_button(
                                label="💾 Download Backup",
                                data=f,
                                file_name=Path(result['backup_path']).name,
                                mime="application/zip",
                                use_container_width=True
                            )
                    else:
                        st.error(f"Backup failed: {result.get('error', 'Unknown error')}")

        with col2:
            st.markdown("**Restore from Backup**")
            # Show existing backups
            from lib import backup as backup_module
            backups = backup_module.list_backups()

            if backups:
                backup_options = {f"{b['name']} ({b['size_mb']} MB)": b['path']
                                  for b in backups}

                selected = st.selectbox(
                    "Select backup to restore:",
                    options=list(backup_options.keys()),
                    key="restore_backup_select",
                    label_visibility="collapsed"
                )

                if st.button("♻️ Restore", type="secondary", use_container_width=True):
                    backup_path = Path(backup_options[selected])

                    # Confirmation
                    if st.session_state.get('restore_confirmed', False):
                        with st.spinner("Restoring backup..."):
                            result = backup_module.restore_backup(backup_path)

                            if result['success']:
                                st.success(result['message'])
                                st.info("Please refresh the page to see restored data.")
                                st.session_state['restore_confirmed'] = False
                            else:
                                st.error(f"Restore failed: {result.get('error')}")
                    else:
                        st.warning("⚠️ This will replace current data. Click again to confirm.")
                        st.session_state['restore_confirmed'] = True
            else:
                st.info("No backups available yet")

        st.divider()

        # About section
        st.markdown("#### About")
        st.markdown("""
        **Astrolabe Paper Database**

        A comprehensive research paper management system with:
        - PDF ingestion and text extraction
        - Semantic search powered by ChromaDB
        - Metadata extraction and management
        - Reading history tracking
        - Automatic backups

        For more information, see the documentation files in the project directory.
        """)


def process_url_import(url: str, progress_container) -> Dict[str, Any]:
    """
    Import a paper from URL (arXiv, DOI, or direct PDF link).

    Args:
        url: URL to import from
        progress_container: Streamlit container for progress updates

    Returns:
        Dictionary with import results
    """
    import subprocess
    import urllib.parse
    from pathlib import Path

    papers_dir = Path("papers")
    papers_dir.mkdir(parents=True, exist_ok=True)

    result = {
        'success': False,
        'title': None,
        'filename': None,
        'error': None,
        'metadata_only': False
    }

    url = url.strip()

    with progress_container:
        st.info(f"🔗 Processing URL: {url}")

        try:
            # Detect URL type
            if 'arxiv.org' in url:
                # arXiv link
                st.caption("📄 Detected: arXiv paper")

                # Extract arXiv ID
                import re
                arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
                if not arxiv_match:
                    result['error'] = "Invalid arXiv URL format"
                    return result

                arxiv_id = arxiv_match.group(1)
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                filename = f"arxiv_{arxiv_id.replace('.', '_')}.pdf"

                st.caption(f"📥 Downloading from arXiv (ID: {arxiv_id})...")

                # Download PDF
                response = requests.get(pdf_url, timeout=30)
                if response.status_code == 200:
                    filepath = papers_dir / filename
                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    result['filename'] = filename
                    result['success'] = True
                    st.caption(f"✓ Downloaded: {filename}")
                else:
                    result['error'] = f"Failed to download from arXiv (HTTP {response.status_code})"
                    return result

            elif any(publisher in url.lower() for publisher in [
                'sciencedirect.com', 'ieeexplore.ieee.org', 'onlinelibrary.wiley.com',
                'link.springer.com', 'nature.com/articles', 'mdpi.com', 'cell.com',
                'thelancet.com', 'pubs.acs.org', 'pubs.rsc.org', 'iopscience.iop.org'
            ]):
                # Publisher article page
                st.caption("📰 Detected: Publisher article page")
                st.caption(f"🔍 Extracting DOI from page...")

                doi = None

                # Try to extract DOI from URL pattern first
                if 'doi.org' in url or '/doi/' in url:
                    # DOI is in the URL
                    doi_match = re.search(r'(?:doi\.org/|/doi/(?:abs/|full/)?)(10\.\d+/[^\s?&#]+)', url)
                    if doi_match:
                        doi = doi_match.group(1)

                # If not in URL, scrape from page
                if not doi:
                    try:
                        st.caption("🌐 Fetching page to extract DOI...")
                        # Use more complete browser headers to avoid blocking
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'DNT': '1',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                            'Sec-Fetch-Dest': 'document',
                            'Sec-Fetch-Mode': 'navigate',
                            'Sec-Fetch-Site': 'none',
                            'Cache-Control': 'max-age=0'
                        }

                        page_response = requests.get(url, timeout=15, headers=headers)

                        if page_response.status_code == 403:
                            st.warning("⚠️ Publisher blocked automated access (403 Forbidden)")
                            st.info("💡 Workaround: Manually enter the DOI instead, or download the PDF and upload it.")
                            result['error'] = "Publisher blocked automated access. Try entering DOI directly or upload PDF."
                            return result
                        elif page_response.status_code != 200:
                            st.warning(f"⚠️ Could not fetch page (HTTP {page_response.status_code})")
                            result['error'] = f"HTTP {page_response.status_code} when fetching page"
                            return result

                        if page_response.status_code == 200:
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(page_response.text, 'html.parser')

                            # Try all common meta tag patterns
                            meta_tags_to_try = [
                                ('name', 'citation_doi'),
                                ('name', 'DC.Identifier'),
                                ('property', 'citation_doi'),
                                ('name', 'DOI'),
                                ('name', 'dc.identifier'),
                                ('property', 'og:identifier'),
                                ('name', 'prism.doi'),  # Common in ScienceDirect
                            ]

                            for attr, value in meta_tags_to_try:
                                doi_meta = soup.find('meta', {attr: value})
                                if doi_meta and doi_meta.get('content'):
                                    doi_content = doi_meta['content'].strip()
                                    # Extract just the DOI part
                                    if 'doi.org/' in doi_content:
                                        doi = doi_content.split('doi.org/')[-1]
                                    elif doi_content.startswith('10.'):
                                        doi = doi_content

                                    if doi:
                                        st.caption(f"✓ Found DOI in meta tag: {attr}={value}")
                                        break

                            # If still no DOI, search page HTML for DOI pattern
                            if not doi:
                                # Look for DOI in script tags (ScienceDirect often has it in JSON-LD)
                                script_tags = soup.find_all('script', {'type': 'application/ld+json'})
                                for script in script_tags:
                                    doi_match = re.search(r'"doi"\s*:\s*"(10\.\d+/[^"]+)"', script.string or '')
                                    if doi_match:
                                        doi = doi_match.group(1)
                                        st.caption("✓ Found DOI in JSON-LD schema")
                                        break

                            # Last resort: search entire page text for DOI pattern
                            if not doi:
                                doi_pattern = re.search(r'\b(10\.\d{4,}/[^\s<>"\']+)\b', page_response.text)
                                if doi_pattern:
                                    candidate = doi_pattern.group(1)
                                    # Clean up common trailing characters
                                    candidate = re.sub(r'[,;.\)]+$', '', candidate)
                                    if candidate:
                                        doi = candidate
                                        st.caption("✓ Found DOI in page content")

                    except Exception as e:
                        st.warning(f"⚠️ Could not fetch page: {str(e)}")

                if not doi:
                    result['error'] = "Could not extract DOI from publisher page"
                    return result

                st.caption(f"✓ Found DOI: {doi}")

                # Now proceed with DOI-based lookup
                st.caption(f"📖 Looking up metadata for DOI: {doi}")

                # Get metadata from CrossRef
                metadata = query_crossref_for_metadata(doi)
                if not metadata:
                    result['error'] = "Could not retrieve metadata from CrossRef"
                    return result

                result['title'] = metadata.get('title', 'Unknown')
                st.caption(f"✓ Found: {result['title']}")

                # Try to find open access PDF via Unpaywall
                st.caption("🔓 Checking for open access PDF via Unpaywall...")

                unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email=researcher@example.com"
                unpaywall_response = requests.get(unpaywall_url, timeout=10)

                pdf_url = None
                if unpaywall_response.status_code == 200:
                    unpaywall_data = unpaywall_response.json()
                    if unpaywall_data.get('is_oa') and unpaywall_data.get('best_oa_location'):
                        pdf_url = unpaywall_data['best_oa_location'].get('url_for_pdf')

                if pdf_url:
                    st.caption(f"✓ Found open access PDF!")
                    st.caption(f"📥 Downloading from {urllib.parse.urlparse(pdf_url).netloc}...")

                    # Download PDF
                    try:
                        pdf_response = requests.get(pdf_url, timeout=30, allow_redirects=True)
                        if pdf_response.status_code == 200 and pdf_response.headers.get('content-type', '').startswith('application/pdf'):
                            # Create safe filename from DOI
                            safe_doi = doi.replace('/', '_').replace('.', '_')
                            filename = f"doi_{safe_doi}.pdf"
                            filepath = papers_dir / filename

                            with open(filepath, 'wb') as f:
                                f.write(pdf_response.content)

                            result['filename'] = filename
                            result['success'] = True
                            st.caption(f"✓ Downloaded: {filename}")
                        else:
                            st.warning("⚠️ Could not download PDF (may be paywalled)")
                            result['metadata_only'] = True
                            result['filename'] = save_metadata_only_paper(doi, metadata)
                            result['success'] = True
                    except Exception as e:
                        st.warning(f"⚠️ PDF download failed: {str(e)}")
                        result['metadata_only'] = True
                        result['filename'] = save_metadata_only_paper(doi, metadata)
                        result['success'] = True
                else:
                    st.warning("⚠️ No open access PDF found - this paper may be paywalled")
                    result['metadata_only'] = True
                    result['filename'] = save_metadata_only_paper(doi, metadata)
                    result['success'] = True

            elif 'doi.org' in url or url.startswith('10.'):
                # DOI link or DOI string
                st.caption("🔍 Detected: DOI")

                # Extract DOI
                if url.startswith('10.'):
                    doi = url
                else:
                    doi = url.split('doi.org/')[-1]

                st.caption(f"📖 Looking up metadata for DOI: {doi}")

                # Get metadata from CrossRef
                metadata = query_crossref_for_metadata(doi)
                if not metadata:
                    result['error'] = "Could not retrieve metadata from CrossRef"
                    return result

                result['title'] = metadata.get('title', 'Unknown')
                st.caption(f"✓ Found: {result['title']}")

                # Try to find open access PDF via Unpaywall
                st.caption("🔓 Checking for open access PDF via Unpaywall...")

                unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email=researcher@example.com"
                unpaywall_response = requests.get(unpaywall_url, timeout=10)

                pdf_url = None
                if unpaywall_response.status_code == 200:
                    unpaywall_data = unpaywall_response.json()
                    if unpaywall_data.get('is_oa') and unpaywall_data.get('best_oa_location'):
                        pdf_url = unpaywall_data['best_oa_location'].get('url_for_pdf')

                if pdf_url:
                    st.caption(f"✓ Found open access PDF!")
                    st.caption(f"📥 Downloading from {urllib.parse.urlparse(pdf_url).netloc}...")

                    # Download PDF
                    try:
                        pdf_response = requests.get(pdf_url, timeout=30, allow_redirects=True)
                        if pdf_response.status_code == 200 and pdf_response.headers.get('content-type', '').startswith('application/pdf'):
                            # Create safe filename from DOI
                            safe_doi = doi.replace('/', '_').replace('.', '_')
                            filename = f"doi_{safe_doi}.pdf"
                            filepath = papers_dir / filename

                            with open(filepath, 'wb') as f:
                                f.write(pdf_response.content)

                            result['filename'] = filename
                            result['success'] = True
                            st.caption(f"✓ Downloaded: {filename}")
                        else:
                            st.warning("⚠️ Could not download PDF (may be paywalled)")
                            result['metadata_only'] = True
                            result['filename'] = save_metadata_only_paper(doi, metadata)
                            result['success'] = True
                    except Exception as e:
                        st.warning(f"⚠️ PDF download failed: {str(e)}")
                        result['metadata_only'] = True
                        result['filename'] = save_metadata_only_paper(doi, metadata)
                        result['success'] = True
                else:
                    st.warning("⚠️ No open access PDF found - this paper may be paywalled")
                    result['metadata_only'] = True
                    result['filename'] = save_metadata_only_paper(doi, metadata)
                    result['success'] = True

            elif url.endswith('.pdf') or 'pdf' in url.lower():
                # Direct PDF link
                st.caption("📄 Detected: Direct PDF link")
                st.caption(f"📥 Downloading PDF...")

                # Download PDF
                response = requests.get(url, timeout=30, allow_redirects=True)
                if response.status_code == 200:
                    # Try to get filename from URL or Content-Disposition header
                    filename = None
                    if 'content-disposition' in response.headers:
                        import re
                        cd = response.headers['content-disposition']
                        filename_match = re.findall('filename="?([^"]+)"?', cd)
                        if filename_match:
                            filename = filename_match[0]

                    if not filename:
                        # Extract from URL
                        filename = url.split('/')[-1].split('?')[0]
                        if not filename.endswith('.pdf'):
                            filename = f"downloaded_{int(time.time())}.pdf"

                    filepath = papers_dir / filename
                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    result['filename'] = filename
                    result['success'] = True
                    st.caption(f"✓ Downloaded: {filename}")
                else:
                    result['error'] = f"Failed to download PDF (HTTP {response.status_code})"
                    return result
            else:
                result['error'] = "Unrecognized URL format. Supported: arXiv, DOI (doi.org/...), or direct PDF links"
                return result

            # Run ingestion pipeline if we have a PDF
            if result['filename'] and not result['metadata_only']:
                st.divider()
                st.info(f"📊 Processing paper through pipeline...")

                progress_bar = st.progress(0)
                status_text = st.empty()

                try:
                    # Stage 1: Parse
                    status_text.text("Stage 1/4: Extracting text from PDF...")
                    progress_bar.progress(25)
                    subprocess.run(
                        [sys.executable, "scripts/ingest_pipeline.py", "--stage", "parse", "--new-only"],
                        check=True,
                        capture_output=True,
                        text=True
                    )

                    # Stage 2: Chunk
                    status_text.text("Stage 2/4: Creating chunks...")
                    progress_bar.progress(50)
                    subprocess.run(
                        [sys.executable, "scripts/ingest_pipeline.py", "--stage", "chunk", "--new-only"],
                        check=True,
                        capture_output=True,
                        text=True
                    )

                    # Stage 3: Metadata
                    status_text.text("Stage 3/4: Extracting metadata...")
                    progress_bar.progress(75)
                    subprocess.run(
                        [sys.executable, "scripts/ingest_pipeline.py", "--stage", "metadata", "--new-only"],
                        check=True,
                        capture_output=True,
                        text=True
                    )

                    # Stage 4: Embed
                    status_text.text("Stage 4/4: Creating embeddings...")
                    progress_bar.progress(90)
                    subprocess.run(
                        [sys.executable, "scripts/ingest_pipeline.py", "--stage", "embed"],
                        check=True,
                        capture_output=True,
                        text=True
                    )

                    progress_bar.progress(100)
                    status_text.text("✅ Processing complete!")

                except subprocess.CalledProcessError as e:
                    result['error'] = f"Pipeline processing failed: {str(e)}"
                    return result

        except requests.exceptions.Timeout:
            result['error'] = "Request timed out - server not responding"
        except requests.exceptions.ConnectionError:
            result['error'] = "Connection error - check your internet connection"
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"

    return result


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
            # Load query into session state and switch to Research tab
            st.session_state.query_result = {
                'question': query['question'],
                'answer': query['answer'],
                'chunks': query['chunks'],
                'filters': query['filters'],
                'from_history': True
            }
            st.session_state.active_tab = "Research"
            st.rerun()

    with col4:
        # Delete button
        if st.button("🗑️", key=f"delete_{query['id']}", help="Delete this query"):
            query_history.delete_query(query['id'])
            st.toast("Query deleted", icon="🗑️")
            st.rerun()


if __name__ == "__main__":
    main()
