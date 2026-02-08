"""
Library Page - Fully extracted and independent
Browse, search, filter, and manage papers in your library
"""
# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import json
import time
from pathlib import Path
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# Page config
st.set_page_config(
    page_title="Library",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import from lib modules
from lib import rag, read_status, collections, styles, cached_operations
from lib.app_helpers import (
    clean_html_from_text,
    query_crossref_for_metadata,
    extract_doi_from_url,
    find_doi_via_semantic_scholar,
    enrich_library_metadata,
    load_settings,
    save_settings
)

# Import library operations from dedicated module (NOT from monolith!)
from lib.library_operations import (
    process_url_import,
    process_uploaded_pdfs,
    soft_delete_paper
)

# Initialize session state
if "selected_paper" not in st.session_state:
    st.session_state.selected_paper = None
if "query_result" not in st.session_state:
    st.session_state.query_result = None
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Library"

# Initialize theme
if "theme" not in st.session_state:
    settings = load_settings()
    st.session_state.theme = settings.get('theme', 'light')

# Initialize databases
read_status.init_db()
collections._get_connection().close()

# Apply CSS
current_theme = st.session_state.theme
st.markdown(styles.get_professional_css(current_theme), unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Astrolabe Research Library</h1>
        <p class="app-subtitle">Battery research papers with AI-powered search</p>
    </div>
""", unsafe_allow_html=True)

# Load papers (with caching)
if 'cached_papers' not in st.session_state or st.session_state.get('reload_papers', False):
    try:
        st.session_state.cached_papers = rag.get_paper_library()
        st.session_state.cached_filter_options = rag.get_filter_options()
        st.session_state.cached_total_chunks = rag.get_collection_count()
        st.session_state.reload_papers = False
    except (FileNotFoundError, RuntimeError) as e:
        st.error(str(e))
        st.info("Please run `python scripts/ingest.py` first to create the database")
        st.stop()

papers = st.session_state.cached_papers
filter_options = st.session_state.cached_filter_options
total_chunks = st.session_state.cached_total_chunks

# Build unfiltered DataFrame for stats calculation (before applying filters)
# This ensures stats match the table data since they use the same get_paper_status() function
if 'cached_stats' not in st.session_state or st.session_state.get('reload_papers', False):
    unfiltered_df = cached_operations.build_library_dataframe(
        papers=papers,
        search_query="",  # No filters for stats
        filter_chemistry="All Chemistries",
        filter_topic="All Topics",
        filter_paper_type="All Types",
        filter_collection="All Collections",
        filter_status="All Papers"
    )

    # Count stats directly from DataFrame Status column
    # This uses the exact same get_paper_status() logic as the table
    total_papers = len(unfiltered_df)
    summarized_papers = len(unfiltered_df[unfiltered_df['Status'] == '🤖 Summarized'])
    complete_papers = len(unfiltered_df[unfiltered_df['Status'] == '✅ Complete'])
    metadata_only_papers = len(unfiltered_df[unfiltered_df['Status'] == '📋 Metadata Only'])
    incomplete_papers = len(unfiltered_df[unfiltered_df['Status'] == '⚠️ Incomplete'])
    processing_pending_papers = len(unfiltered_df[unfiltered_df['Status'] == '🔄 Processing Pending'])

    st.session_state.cached_stats = {
        'total': total_papers,
        'summarized': summarized_papers,
        'complete': complete_papers,
        'metadata_only': metadata_only_papers,
        'incomplete': incomplete_papers,
        'processing_pending': processing_pending_papers
    }
else:
    total_papers = st.session_state.cached_stats['total']
    summarized_papers = st.session_state.cached_stats['summarized']
    complete_papers = st.session_state.cached_stats['complete']
    metadata_only_papers = st.session_state.cached_stats['metadata_only']
    incomplete_papers = st.session_state.cached_stats['incomplete']
    processing_pending_papers = st.session_state.cached_stats['processing_pending']

# Sidebar with stats
with st.sidebar:
    st.subheader("Library Stats")

    st.metric("Total Papers", total_papers)

    summarized_pct = (summarized_papers / total_papers * 100) if total_papers > 0 else 0
    complete_pct = (complete_papers / total_papers * 100) if total_papers > 0 else 0
    metadata_pct = (metadata_only_papers / total_papers * 100) if total_papers > 0 else 0
    incomplete_pct = (incomplete_papers / total_papers * 100) if total_papers > 0 else 0
    processing_pct = (processing_pending_papers / total_papers * 100) if total_papers > 0 else 0

    st.caption(
        f"{summarized_papers} summarized ({summarized_pct:.0f}%) | "
        f"{complete_papers} complete ({complete_pct:.0f}%) | "
        f"{metadata_only_papers} metadata only ({metadata_pct:.0f}%) | "
        f"{incomplete_papers} incomplete ({incomplete_pct:.0f}%)"
    )

    st.caption("**Data Coverage**")
    if summarized_papers > 0:
        st.progress(summarized_pct / 100, text=f"🤖 Summarized: {summarized_papers}")
    st.progress(complete_pct / 100, text=f"✅ Complete: {complete_papers}")
    st.progress(metadata_pct / 100, text=f"📋 Metadata Only: {metadata_only_papers}")
    st.progress(incomplete_pct / 100, text=f"⚠️ Incomplete: {incomplete_papers}")
    if processing_pending_papers > 0:
        st.progress(processing_pct / 100, text=f"🔄 Processing Pending: {processing_pending_papers}")

    st.divider()
    st.metric("Chunks", total_chunks)

# Set active tab
st.session_state.active_tab = "Library"

# Main content starts here - this will be the Library tab content
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

                        # Invalidate cache after adding papers
                        st.session_state.reload_papers = True
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
        # ========== HEADER AREA ==========
        # Back button on left, Open PDF button on right (normal sized, same row)
        col_back, col_pdf = st.columns([1, 5])
        with col_back:
            if st.button("← Back to Library"):
                st.session_state.selected_paper = None
                st.rerun()

        with col_pdf:
            # Only show Open PDF button if PDF exists
            if rag.check_pdf_exists(paper_filename):
                # Start PDF server (lazy initialization)
                from lib import pdf_server
                pdf_server.start_pdf_server()
                pdf_url = pdf_server.get_pdf_url(paper_filename)

                # Small button on the right
                col_spacer, col_btn = st.columns([4, 1])
                with col_btn:
                    st.markdown(f'<a href="{pdf_url}" target="_blank"><button style="width:100%; padding:0.4rem; background:#0066cc; color:white; border:none; border-radius:0.3rem; cursor:pointer; font-size:0.9rem;">📄 Open PDF</button></a>', unsafe_allow_html=True)

        st.divider()

        # ========== BIBLIOGRAPHIC BLOCK (compact, no columns) ==========
        # Title as H1
        display_title = clean_html_from_text(details.get('title', paper_filename.replace('.pdf', '')))
        st.markdown(f"# {display_title}")

        # Authors on ONE line, semicolon-separated
        if details.get('authors') and details['authors'][0]:
            authors_list = [a.strip() for a in details['authors'] if a.strip()]
            authors_str = "; ".join(authors_list)
            st.markdown(f"**{authors_str}**")

        # Journal · year · paper_type on one line, dot-separated
        info_parts = []
        if details.get('journal'):
            info_parts.append(details['journal'])
        if details.get('year'):
            info_parts.append(str(details['year']))
        if details.get('paper_type'):
            info_parts.append(details['paper_type'].title())
        if info_parts:
            st.markdown(" · ".join(info_parts))

        # DOI as clickable link on its own line
        doi = details.get('doi', '')
        if doi:
            st.markdown(f"[{doi}](https://doi.org/{doi})")

        # Tags displayed inline (colored pill badges) - no section header
        all_tags_html = []

        # Author keywords
        author_keywords = details.get('author_keywords', [])
        if author_keywords and author_keywords[0]:
            for keyword in author_keywords:
                if keyword:
                    all_tags_html.append(f'<span class="tag-pill tag-author-keyword">{keyword}</span>')

        # Chemistry tags
        if details.get('chemistries') and details['chemistries'][0]:
            for chem in details['chemistries']:
                if chem:
                    all_tags_html.append(f'<span class="tag-pill tag-chemistry">{chem}</span>')

        # Topic tags
        if details.get('topics') and details['topics'][0]:
            for topic in details['topics']:
                if topic:
                    all_tags_html.append(f'<span class="tag-pill tag-topic">{topic}</span>')

        # Display all tags inline
        if all_tags_html:
            st.markdown('<div style="margin: 12px 0 20px 0;">' + ''.join(all_tags_html) + '</div>', unsafe_allow_html=True)

        # ========== ABSTRACT (only if exists) ==========
        if details.get('abstract'):
            st.divider()
            clean_abstract = clean_html_from_text(details['abstract'])
            st.markdown(clean_abstract)

        # ========== AI SUMMARY (only if exists) ==========
        if details.get('ai_summary'):
            st.divider()
            st.subheader("🤖 AI Summary")
            st.markdown(details['ai_summary'])

        st.divider()

        # ========== COLLAPSIBLE SECTIONS (all collapsed by default) ==========

        # NOTES (collapsible)
        with st.expander("▸ Notes", expanded=False):
            # Load notes from a notes file
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
                placeholder="Add your notes, thoughts, or important findings here...",
                label_visibility="collapsed"
            )

            if st.button("💾 Save Notes"):
                with open(notes_file, 'w', encoding='utf-8') as f:
                    f.write(notes)
                st.toast("Notes saved!", icon="✅")

        # COLLECTIONS (collapsible)
        with st.expander("▸ Collections", expanded=False):
            # Get current collections for this paper
            current_collections = collections.get_paper_collections(paper_filename)
            all_collections_list = collections.get_all_collections()

            # Display current collections as color-coded tags
            if current_collections:
                cols_display = st.columns(min(len(current_collections), 4))
                for idx, coll in enumerate(current_collections):
                    with cols_display[idx % 4]:
                        color = coll.get('color') or '#6c757d'
                        st.markdown(
                            f'<span style="display: inline-block; background-color: {color}; color: white; '
                            f'padding: 4px 12px; border-radius: 12px; font-size: 13px; margin: 2px;">'
                            f'{coll["name"]}</span>',
                            unsafe_allow_html=True
                        )
            else:
                st.caption("Not in any collections")

            # Add/Remove from collection controls
            col_add, col_remove = st.columns(2)

            with col_add:
                st.markdown("**Add to Collection:**")
                # Filter out collections the paper is already in
                current_collection_ids = {c['id'] for c in current_collections}
                available_collections = [c for c in all_collections_list if c['id'] not in current_collection_ids]

                if available_collections:
                    add_col1, add_col2 = st.columns([3, 1])
                    with add_col1:
                        selected_to_add = st.selectbox(
                            "Select collection",
                            options=[c['name'] for c in available_collections],
                            key=f"add_collection_{paper_filename}",
                            label_visibility="collapsed"
                        )
                    with add_col2:
                        if st.button("➕", key=f"btn_add_{paper_filename}", use_container_width=True, help="Add to collection"):
                            collection_to_add = next((c for c in available_collections if c['name'] == selected_to_add), None)
                            if collection_to_add:
                                result = collections.add_paper_to_collection(collection_to_add['id'], paper_filename)
                                if result['success']:
                                    st.toast(f"Added to '{collection_to_add['name']}'", icon="✅")
                                    st.rerun()
                                else:
                                    st.error(result['message'])
                else:
                    st.caption("All collections added" if all_collections_list else "No collections available")

            with col_remove:
                st.markdown("**Remove from Collection:**")
                if current_collections:
                    remove_col1, remove_col2 = st.columns([3, 1])
                    with remove_col1:
                        selected_to_remove = st.selectbox(
                            "Select collection",
                            options=[c['name'] for c in current_collections],
                            key=f"remove_collection_{paper_filename}",
                            label_visibility="collapsed"
                        )
                    with remove_col2:
                        if st.button("➖", key=f"btn_remove_{paper_filename}", use_container_width=True, help="Remove from collection"):
                            collection_to_remove = next((c for c in current_collections if c['name'] == selected_to_remove), None)
                            if collection_to_remove:
                                result = collections.remove_paper_from_collection(collection_to_remove['id'], paper_filename)
                                if result['success']:
                                    st.toast(f"Removed from '{collection_to_remove['name']}'", icon="✅")
                                    st.rerun()
                                else:
                                    st.error(result['message'])
                else:
                    st.caption("Not in any collections")

            # Create new collection expander
            with st.expander("➕ Create New Collection"):
                new_coll_name = st.text_input(
                    "Collection Name",
                    placeholder="e.g., SOH Methods, Grant Proposal, EIS Papers",
                    key=f"new_coll_name_{paper_filename}"
                )
                new_coll_color = st.color_picker(
                    "Collection Color",
                    value="#6c757d",
                    key=f"new_coll_color_{paper_filename}"
                )
                new_coll_desc = st.text_area(
                    "Description (optional)",
                    placeholder="Brief description of this collection...",
                    height=80,
                    key=f"new_coll_desc_{paper_filename}"
                )

                if st.button("Create Collection", key=f"create_coll_{paper_filename}", type="primary"):
                    if new_coll_name.strip():
                        result = collections.create_collection(
                            new_coll_name.strip(),
                            new_coll_color,
                            new_coll_desc.strip()
                        )
                        if result['success']:
                            # Automatically add current paper to the new collection
                            collections.add_paper_to_collection(result['id'], paper_filename)
                            st.toast(f"Collection '{new_coll_name}' created and paper added!", icon="✅")
                            st.rerun()
                        else:
                            st.error(result['message'])
                    else:
                        st.warning("Please enter a collection name")

        # Update References expander label
        references = details.get('references', [])
        if references:
            with st.expander(f"▸ References ({len(references)})", expanded=False):
                st.caption("Papers cited by this work")

                # Get all DOIs in the library for status checking
                # Normalize DOIs by removing URL prefix if present
                def normalize_doi(doi_string):
                    """Remove https://doi.org/ prefix and lowercase"""
                    if not doi_string:
                        return ''
                    doi = doi_string.lower().strip()
                    # Remove common DOI URL prefixes
                    for prefix in ['https://doi.org/', 'http://doi.org/', 'doi.org/', 'doi:']:
                        if doi.startswith(prefix):
                            doi = doi[len(prefix):]
                    return doi

                library_dois = {normalize_doi(p.get('doi', '')) for p in papers if p.get('doi')}
                library_dois.discard('')  # Remove empty strings

                # Filter and prepare references data
                refs_data = []
                refs_full_data = {}  # Store full ref data separately (not in DataFrame)
                for i, ref in enumerate(references):
                    # Get reference fields
                    title = ref.get('article-title', '').strip()
                    authors = ref.get('author', '').strip()

                    # Mark incomplete references (missing title or author)
                    is_incomplete = not title or not authors

                    # Show what data we have, even if incomplete
                    display_title = title if title else '(No title)'
                    display_authors = authors if authors else '(No author)'

                    # Check if in library (only for complete references)
                    in_library = False
                    if not is_incomplete:
                        # Method 1: Check by normalized DOI
                        ref_doi = normalize_doi(ref.get('DOI', ''))
                        if ref_doi and ref_doi in library_dois:
                            in_library = True
                        # Method 2: If no DOI, check by title match (fuzzy)
                        elif title:
                            from difflib import SequenceMatcher
                            title_lower = title.lower()
                            for p in papers:
                                p_title = p.get('title', '').lower()
                                if p_title and SequenceMatcher(None, title_lower, p_title).ratio() > 0.9:
                                    in_library = True
                                    break

                    # Format journal with volume
                    journal = ref.get('journal-title', '')
                    if journal and ref.get('volume'):
                        journal = f"{journal}, Vol. {ref['volume']}"

                    row_idx = len(refs_data)
                    refs_data.append({
                        'Title': display_title,
                        'Authors': display_authors,
                        'Year': str(ref.get('year', '')) if ref.get('year') else '—',
                        'Journal': journal if journal else '—',
                        'DOI': ref.get('DOI', '—'),
                        'Status': '✓ In Library' if in_library else ('Incomplete' if is_incomplete else 'Not in Library'),
                        '_in_library': in_library,
                        '_incomplete': is_incomplete
                    })
                    # Store full ref data separately (dicts break AgGrid rendering)
                    refs_full_data[row_idx] = ref

                if not refs_data:
                    st.info("No valid references found (references must have both title and author)")
                else:
                    # Build DataFrame
                    refs_df = pd.DataFrame(refs_data)

                    # Configure AG Grid (EXACT copy from library table)
                    refs_gb = GridOptionsBuilder.from_dataframe(refs_df)

                    # Title column - EXACT copy from library table
                    refs_gb.configure_column("Title",
                        flex=3,
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

                    # Authors column - EXACT copy from library table
                    refs_gb.configure_column("Authors",
                        flex=2,
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

                    # Year column - EXACT copy from library table
                    refs_gb.configure_column("Year",
                        width=70,
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

                    # Journal column - EXACT copy from library table
                    refs_gb.configure_column("Journal",
                        flex=2,
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

                    # DOI column - EXACT copy from library table
                    refs_gb.configure_column("DOI",
                        flex=1.5,
                        minWidth=140,
                        resizable=True,
                        cellStyle={
                            'overflow': 'hidden'
                        },
                        tooltipField="DOI"
                    )

                    # Status column
                    refs_gb.configure_column("Status",
                        width=130,
                        minWidth=110,
                        maxWidth=150,
                        resizable=False,
                        cellStyle={'textAlign': 'center', 'overflow': 'hidden'}
                    )

                    # Hide internal columns
                    refs_gb.configure_column("_in_library", hide=True)

                    # Grid options - EXACT copy from library table
                    refs_gb.configure_selection(selection_mode='single', use_checkbox=False)
                    refs_gb.configure_grid_options(
                        headerHeight=40,
                        suppressRowHoverHighlight=False,
                        enableCellTextSelection=True,
                        ensureDomOrder=True,
                        domLayout='normal',
                        rowHeight=60,
                        suppressHorizontalScroll=True,
                        suppressColumnVirtualisation=False,
                        suppressRowVirtualisation=False
                    )

                    refs_grid_options = refs_gb.build()

                    # Custom CSS - EXACT copy from library table
                    if st.session_state.theme == 'dark':
                        refs_custom_css = {
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
                            ".ag-center-cols-viewport": {"background-color": "#1E1E1E !important"},
                            ".ag-body-viewport": {"background-color": "#1E1E1E !important"},
                        }
                    else:
                        refs_custom_css = {
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
                            ".ag-center-cols-viewport": {"background-color": "#FFFFFF !important"},
                            ".ag-body-viewport": {"background-color": "#FFFFFF !important"},
                        }

                    st.divider()

                    # Prepare data for buttons (need counts before displaying grid)
                    missing_refs = refs_df[(refs_df['_in_library'] == False) & (refs_df['_incomplete'] == False)]
                    incomplete_count = refs_df[refs_df['_incomplete'] == True].shape[0]

                    # Display references table with 1-based indexing
                    refs_display = refs_df.drop(columns=['_in_library', '_incomplete']).copy()
                    refs_display.insert(0, '#', range(1, len(refs_display) + 1))

                    # Minimal AgGrid with ONLY 2-line clamp CSS added
                    refs_minimal_gb = GridOptionsBuilder.from_dataframe(refs_display)

                    # Configure # column to be narrow and centered
                    refs_minimal_gb.configure_column("#",
                        width=60,
                        maxWidth=80,
                        pinned='left',
                        cellStyle={'textAlign': 'center', 'fontWeight': '600'}
                    )

                    # Apply conditional styling based on Status (incomplete references)
                    incomplete_style = JsCode("""
                        function(params) {
                            if (params.data.Status === 'Incomplete') {
                                return {
                                    'color': '#999999',
                                    'fontStyle': 'italic'
                                };
                            }
                            return {};
                        }
                    """)

                    # Apply greyed-out styling to all columns for incomplete rows
                    for col in ['#', 'Title', 'Authors', 'Year', 'Journal', 'DOI', 'Status']:
                        refs_minimal_gb.configure_column(col, cellStyle=incomplete_style)

                    # Enable multi-selection with checkboxes
                    refs_minimal_gb.configure_selection(selection_mode='multiple', use_checkbox=True)
                    refs_minimal_gb.configure_grid_options(domLayout='autoHeight')
                    refs_minimal_options = refs_minimal_gb.build()

                    # ONLY add the critical CSS for 2-line text wrapping (from library table)
                    refs_minimal_css = {
                        ".ag-cell .ag-cell-value": {
                            "display": "-webkit-box !important",
                            "-webkit-line-clamp": "2 !important",
                            "-webkit-box-orient": "vertical !important",
                            "overflow": "hidden !important",
                            "text-overflow": "ellipsis !important",
                            "white-space": "normal !important",
                            "line-height": "1.4 !important",
                            "max-height": "42px !important"
                        }
                    }

                    # Add to Library buttons - BEFORE grid for better UX
                    # Use container to render buttons at top but access grid response
                    buttons_placeholder = st.container()

                    refs_grid_response = AgGrid(
                        refs_display,
                        gridOptions=refs_minimal_options,
                        custom_css=refs_minimal_css,
                        fit_columns_on_grid_load=True,
                        theme='streamlit',
                        allow_unsafe_jscode=True,
                        key=f"refs_minimal_{paper_filename}"
                    )

                    # Render buttons in the placeholder at the top
                    with buttons_placeholder:
                        if len(missing_refs) > 0 or (refs_grid_response.get('selected_rows') is not None and len(refs_grid_response.get('selected_rows', [])) > 0):
                            col1, col2 = st.columns(2)

                            # "Add Selected" button - primary action
                            with col1:
                                selected_rows = refs_grid_response.get('selected_rows', [])
                                if selected_rows is not None and len(selected_rows) > 0:
                                    # Filter selected rows to only include those not in library and not incomplete
                                    selected_df = pd.DataFrame(selected_rows)
                                    addable_selected = []
                                    for _, row in selected_df.iterrows():
                                        # Find the original row index based on # column
                                        ref_num = row['#'] - 1  # Convert back to 0-based index
                                        if ref_num in refs_full_data:
                                            # Check if this ref is not in library and not incomplete
                                            orig_row = refs_df.iloc[ref_num]
                                            if not orig_row['_in_library'] and not orig_row['_incomplete']:
                                                addable_selected.append(ref_num)

                                    if len(addable_selected) > 0:
                                        if st.button(f"➕ Add Selected ({len(addable_selected)})", type="primary", use_container_width=True, key=f"add_selected_{paper_filename}"):
                                            progress_bar = st.progress(0)
                                            success_count = 0

                                            for idx, ref_idx in enumerate(addable_selected):
                                                ref_data = refs_full_data[ref_idx]
                                                result = import_reference(ref_data)
                                                if result['success']:
                                                    success_count += 1
                                                progress_bar.progress((idx + 1) / len(addable_selected))

                                            st.toast(f"✅ Added {success_count} of {len(addable_selected)} references", icon="✅")
                                            st.rerun()
                                    else:
                                        st.info("Selected references are already in library or incomplete")
                                else:
                                    st.caption("Select references using checkboxes to add them")

                            # "Add All Missing" button - secondary action
                            with col2:
                                if len(missing_refs) > 0:
                                    if incomplete_count > 0:
                                        st.caption(f"{len(missing_refs)} missing ({incomplete_count} incomplete excluded)")
                                    if st.button(f"➕ Add All Missing ({len(missing_refs)})", type="secondary", use_container_width=True, key=f"add_all_missing_{paper_filename}"):
                                        progress_bar = st.progress(0)
                                        success_count = 0

                                        for idx, (row_idx, row) in enumerate(missing_refs.iterrows()):
                                            if row_idx not in refs_full_data:
                                                continue

                                            ref_data = refs_full_data[row_idx]
                                            result = import_reference(ref_data)
                                            if result['success']:
                                                success_count += 1
                                            progress_bar.progress((idx + 1) / len(missing_refs))

                                        st.toast(f"✅ Added {success_count} of {len(missing_refs)} references", icon="✅")
                                        st.rerun()
                                else:
                                    st.caption("All references already in library")

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

                    # Ingestion pipeline trigger
                    time.sleep(1)
                    st.rerun()

        st.divider()

        # EDIT METADATA (collapsible)
        with st.expander("▸ Edit Metadata", expanded=False):
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

    # Search box and enrichment button
    col_search, col_enrich = st.columns([3, 1])
    with col_search:
        search_query = st.text_input(
            "Search papers",
            placeholder="Search by title, authors, journal...",
            label_visibility="collapsed",
            key="library_search"
        )

    # Horizontal filter bar
    col1, col2, col3, col4, col5 = st.columns(5)
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
    with col4:
        all_collections = collections.get_all_collections()
        collection_options = ["All Collections"] + [c['name'] for c in all_collections]
        filter_collection = st.selectbox(
            "📁 Collection",
            options=collection_options,
            key="library_filter_collection"
        )
    with col5:
        filter_status = st.selectbox(
            "Status",
            options=["All Papers", "🤖 Summarized", "✅ Complete", "📋 Metadata Only", "⚠️ Incomplete", "🔄 Processing Pending"],
            key="library_filter_status"
        )

    # Build library DataFrame using cached function (filters + formats data)
    df = cached_operations.build_library_dataframe(
        papers=papers,
        search_query=search_query or "",
        filter_chemistry=filter_chemistry or "All Chemistries",
        filter_topic=filter_topic or "All Topics",
        filter_paper_type=filter_paper_type or "All Types",
        filter_collection=filter_collection or "All Collections",
        filter_status=filter_status or "All Papers"
    )

    # Count filtered papers
    filtered_count = len(df)
    st.write(f"Showing {filtered_count} of {len(papers)} papers")

    # Initialize button state
    delete_button = False
    find_doi_button = False
    enrich_incomplete_button = False

    # Action buttons
    if len(df) > 0:
        st.caption("💡 **Tip:** Click a row to view details • Use checkboxes for bulk actions")
        btn_col1, btn_col2, btn_col3, spacer_col = st.columns([1, 1, 1.3, 2.7])
        with btn_col1:
            delete_button = st.button("🗑️ Delete Selected", type="secondary", use_container_width=True)
        with btn_col2:
            find_doi_button = st.button("🔍 Find DOI & Enrich", help="Find DOIs via Semantic Scholar for selected papers, then enrich with CrossRef", type="secondary", use_container_width=True)
        with btn_col3:
            enrich_incomplete_button = st.button("⚡ Enrich All Incomplete", help="Automatically find DOIs and enrich all incomplete papers", type="primary", use_container_width=True)

    # Progress bar placeholders (positioned above table)
    progress_placeholder = st.empty()
    progress_bar_placeholder = st.empty()

    # Page size selector
    col_pagesize, col_spacer = st.columns([1, 5])
    with col_pagesize:
        page_size = st.selectbox(
            "Papers per page:",
            options=[25, 50, 100, 200],
            index=1,  # Default to 50
            key="library_page_size"
        )

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

    # Configure Select (checkbox) column
    gb.configure_column("Select",
        headerName="",
        width=50,
        minWidth=50,
        maxWidth=50,
        checkboxSelection=True,
        headerCheckboxSelection=True,
        resizable=False,
        suppressMenu=True,
        lockPosition=True,
        pinned='left',
        valueFormatter=JsCode("function(params) { return ''; }"),  # Don't display value, just checkbox
        cellStyle={
            'display': 'flex',
            'alignItems': 'center',
            'justifyContent': 'center'
        }
    )

    # Custom comparator for Status column (Complete → Metadata Only → Incomplete)
    status_comparator = JsCode("""
        function(valueA, valueB) {
            const order = {
                '✅ Complete': 1,
                '📋 Metadata Only': 2,
                '⚠️ Incomplete': 3
            };
            return (order[valueA] || 999) - (order[valueB] || 999);
        }
    """)

    gb.configure_column("Status",
        width=140,
        minWidth=120,
        maxWidth=160,
        resizable=True,
        cellRenderer=status_cell_renderer,
        comparator=status_comparator,
        cellStyle={
            'textAlign': 'center',
            'padding': '4px 8px',
            'fontSize': '13px',
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
    gb.configure_column("Collections",
        headerName='📁 Collections',
        flex=1.5,  # Takes 1.5 parts of available space
        minWidth=120,
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
            'maxHeight': '45px !important',
            'fontSize': '13px !important'
        },
        tooltipField="Collections"
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

    # DOI column with clickable link and inline editing
    doi_renderer = JsCode("""
        class DoiRenderer {
            init(params) {
                this.eGui = document.createElement('div');
                this.eGui.style.display = 'flex';
                this.eGui.style.alignItems = 'center';
                this.eGui.style.gap = '8px';
                this.eGui.style.padding = '4px 8px';

                if (!params.value || params.value === '—' || params.value === '') {
                    this.eGui.innerHTML = '<span style="color: #1f77b4; cursor: pointer; text-decoration: underline;">➕ Add DOI</span>';
                } else {
                    // Value is already just the DOI (10.xxxx/...), URL is in _doi_url
                    const url = params.data._doi_url || 'https://doi.org/' + params.value;
                    this.eGui.innerHTML = '<a href="' + url + '" target="_blank" rel="noopener noreferrer" style="color: #1f77b4; text-decoration: underline; flex: 1;">' + params.value + '</a><span style="color: #999; cursor: pointer; font-size: 12px;">✏️</span>';
                }
            }

            getGui() {
                return this.eGui;
            }
        }
    """)
    gb.configure_column("DOI",
        flex=1.5,
        minWidth=140,
        resizable=True,
        editable=True,
        cellRenderer=doi_renderer,
        cellEditor='agTextCellEditor',
        cellStyle={
            'overflow': 'hidden'
        },
        tooltipField="DOI",
        valueSetter=JsCode("""
            function(params) {
                // Clean up the DOI value
                let newValue = params.newValue.trim();

                // Remove common prefixes
                newValue = newValue.replace(/^(https?:\/\/)?(dx\.)?doi\.org\//i, '');

                // Only accept valid DOI format (10.xxxx/...)
                if (newValue && !newValue.match(/^10\.\d{4,}/)) {
                    return false; // Invalid DOI format
                }

                params.data.DOI = newValue || '—';
                return true;
            }
        """)
    )

    # Read column with actual checkbox
    checkbox_renderer = JsCode("""
        class CheckboxRenderer {
            init(params) {
                this.params = params;
                this.eGui = document.createElement('div');
                this.eGui.style.textAlign = 'center';
                this.eGui.style.display = 'flex';
                this.eGui.style.alignItems = 'center';
                this.eGui.style.justifyContent = 'center';
                this.eGui.style.height = '100%';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = params.value;
                checkbox.style.cursor = 'pointer';
                checkbox.style.width = '16px';
                checkbox.style.height = '16px';

                // Handle checkbox change
                checkbox.addEventListener('change', (e) => {
                    e.stopPropagation();  // Don't trigger row navigation
                    params.setValue(e.target.checked);
                });

                this.eGui.appendChild(checkbox);
            }

            getGui() {
                return this.eGui;
            }
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
    gb.configure_column("_paper_title", hide=True)

    # Grid options - configured for full-width with virtualization for large datasets
    # Multi-select enabled via Select column (configured above with checkboxSelection=True)
    gb.configure_selection(selection_mode='multiple', suppressRowClickSelection=False)
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
        rowSelection='multiple',  # Enable multi-row selection
        rowMultiSelectWithClick=False,  # Prevent accidental multi-select on row click
        # Pagination settings
        pagination=True,  # Enable pagination
        paginationAutoPageSize=False,  # Use fixed page size
        paginationPageSize=page_size,  # Use selected page size
        paginationPageSizeSelector=False,  # Hide page size selector - use Streamlit dropdown instead
    )

    grid_options = gb.build()

    # Add cell click handler to separate different click behaviors
    grid_options['onCellClicked'] = JsCode("""
        function(event) {
            const colId = event.column ? event.column.colId : null;
            console.log('[LIBRARY] Column clicked:', colId);

            // 1. SELECT CHECKBOX: Do nothing, let default checkbox behavior handle it
            if (colId === 'Select') {
                console.log('[LIBRARY] Select column - doing nothing');
                return;
            }

            // 2. DOI COLUMN: Do nothing here, link click is handled by <a> tag
            if (colId === 'DOI') {
                console.log('[LIBRARY] DOI column - doing nothing');
                return;
            }

            // 3. READ CHECKBOX: Do nothing, let checkbox renderer handle it
            if (colId === 'Read') {
                console.log('[LIBRARY] Read column - doing nothing');
                return;
            }

            // 4. NAVIGABLE COLUMNS ONLY: Select row for navigation
            // Only Title, Authors, Year, Journal, Chemistry, Collections should navigate
            const navigableColumns = ['Title', 'Authors', 'Year', 'Journal', 'Chemistry', 'Collections', 'Status', '#'];
            if (navigableColumns.includes(colId)) {
                console.log('[LIBRARY] Navigable column - selecting row');
                event.node.setSelected(true, true);
            } else {
                console.log('[LIBRARY] Non-navigable column - doing nothing');
            }
        }
    """)

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
            # Pagination styling - dark theme
            ".ag-paging-panel": {
                "background-color": "#262730 !important",
                "color": "#E0E0E0 !important",
                "border-top": "1px solid #444444 !important",
                "padding": "8px !important",
                "font-size": "14px !important"
            },
            ".ag-paging-button": {
                "color": "#E0E0E0 !important",
                "background-color": "#1E1E1E !important",
                "border": "1px solid #444444 !important",
                "padding": "4px 8px !important",
                "margin": "0 2px !important"
            },
            ".ag-paging-button:hover": {
                "background-color": "#2D2D2D !important"
            },
            ".ag-paging-page-summary-panel": {
                "color": "#E0E0E0 !important"
            },
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
            # Pagination styling - light theme
            ".ag-paging-panel": {
                "background-color": "#F0F2F6 !important",
                "color": "#2c3e50 !important",
                "border-top": "1px solid #D0D0D0 !important",
                "padding": "8px !important",
                "font-size": "14px !important"
            },
            ".ag-paging-button": {
                "color": "#2c3e50 !important",
                "background-color": "#FFFFFF !important",
                "border": "1px solid #D0D0D0 !important",
                "padding": "4px 8px !important",
                "margin": "0 2px !important"
            },
            ".ag-paging-button:hover": {
                "background-color": "#f8f9fa !important"
            },
            ".ag-paging-page-summary-panel": {
                "color": "#2c3e50 !important"
            },
        }

    # Use streamlit theme for both modes - consistent base, colors controlled by custom CSS
    ag_theme = 'streamlit'

    # Use key to preserve grid state across reruns (include page_size to force refresh on change)
    grid_key = f"library_grid_{st.session_state.theme}_{page_size}"

    # Calculate dynamic height based on number of rows and selected page size
    # Always show all rows - no internal table scrolling, only page scrolling
    row_height = 60
    header_height = 40
    pagination_height = 60
    rows_to_show = min(page_size, len(df))

    # Full height to show all rows on current page
    table_height = (rows_to_show * row_height) + header_height + pagination_height

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED | GridUpdateMode.SELECTION_CHANGED,  # Update on both cell edits and selection
        fit_columns_on_grid_load=True,  # Auto-fit columns to fill container width
        theme=ag_theme,
        custom_css=custom_css,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        height=table_height,  # Dynamic height based on filtered row count and page size
        reload_data=False,  # Improve performance by not reloading data unnecessarily
        key=grid_key  # Preserve state across reruns
    )

    # Handle DOI cell edits - only check if we haven't just processed an update
    if grid_response['data'] is not None and not st.session_state.get('just_updated_doi', False):
        updated_df = pd.DataFrame(grid_response['data'])

        # Quick check: compare grid DOI values with original DataFrame to see if anything changed
        # This avoids expensive file I/O on every rerun when nothing was edited
        doi_changed = False
        if len(updated_df) > 0 and len(updated_df) == len(df) and 'DOI' in updated_df.columns:
            for idx in range(len(df)):
                if updated_df.iloc[idx]['DOI'] != df.iloc[idx]['DOI']:
                    doi_changed = True
                    break

        # Only load metadata from disk if DOI actually changed in grid
        if doi_changed and '_filename' in updated_df.columns:
            # Load metadata to compare with actual stored values
            metadata_file = Path("data/metadata.json")
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    all_metadata = json.load(f)

                metadata_changed = False
                changed_papers = []
                changed_files = {}  # Track filename -> new_doi for ChromaDB updates

                # Only check rows where DOI in grid differs from metadata
                for idx, updated_row in updated_df.iterrows():
                    filename = updated_row.get('_filename')
                    if filename and filename in all_metadata:
                        # Get DOI from metadata (source of truth)
                        metadata_doi = all_metadata[filename].get('doi', '')
                        metadata_doi_display = metadata_doi if metadata_doi else '—'

                        # Get DOI from grid (possibly edited)
                        grid_doi = str(updated_row.get('DOI', '—')).strip()

                        # Normalize for comparison
                        if grid_doi in ['', 'nan', 'None']:
                            grid_doi = '—'

                        # Only update if different from what's in metadata
                        if grid_doi != metadata_doi_display:
                            # Update DOI in metadata
                            new_doi = grid_doi if grid_doi != '—' else ''
                            all_metadata[filename]['doi'] = new_doi
                            changed_files[filename] = new_doi  # Track for ChromaDB update
                            metadata_changed = True
                            changed_papers.append(all_metadata[filename].get('title', filename)[:50])

                # Save metadata and show notification only if actually changed
                if metadata_changed:
                    # Save to metadata.json
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

                    # Update ChromaDB for each changed paper
                    from lib.rag import DatabaseClient
                    for filename, new_doi in changed_files.items():
                        DatabaseClient.update_paper_metadata(filename, {"doi": new_doi})

                    # Clear caches to force reload with updated DOI
                    DatabaseClient.clear_cache()
                    st.cache_data.clear()

                    # Show toast for changed papers
                    for paper_title in changed_papers:
                        st.toast(f"✅ DOI updated for {paper_title}", icon="✏️")

                    # Set flag to prevent re-checking on next rerun
                    st.session_state.just_updated_doi = True
                    st.session_state.reload_papers = True
                    st.rerun()

    # Clear the flag after one rerun
    if st.session_state.get('just_updated_doi', False):
        st.session_state.just_updated_doi = False

    # Handle delete button click
    if delete_button and grid_response['selected_rows'] is not None and len(grid_response['selected_rows']) > 0:
        selected_rows_df = pd.DataFrame(grid_response['selected_rows'])

        # Check if user has disabled confirmation dialogs
        settings = load_settings()
        skip_delete_confirmation = settings.get('skip_delete_confirmation', False)

        if skip_delete_confirmation:
            # Delete immediately without confirmation
            success_count = 0
            for _, row in selected_rows_df.iterrows():
                result = soft_delete_paper(row['_filename'])
                if result['success']:
                    success_count += 1

            st.session_state.reload_papers = True  # Invalidate cache
            st.toast(f"🗑️ Moved {success_count} paper(s) to trash", icon="✅")
            st.rerun()
        else:
            # Store papers to delete in session state and show dialog
            st.session_state.papers_to_delete = selected_rows_df
            st.session_state.show_delete_dialog = True
            st.rerun()

    # Handle confirmed deletion (outside dialog to ensure clean close)
    if st.session_state.get('delete_confirmed', False):
        papers_to_process = st.session_state.get('papers_to_delete_confirmed', None)
        if papers_to_process is not None:
            success_count = 0
            for _, row in papers_to_process.iterrows():
                result = soft_delete_paper(row['_filename'])
                if result['success']:
                    success_count += 1

            st.session_state.reload_papers = True  # Invalidate cache
            st.toast(f"🗑️ Moved {success_count} paper(s) to trash", icon="✅")

            # Clear the confirmation flags
            st.session_state.delete_confirmed = False
            if 'papers_to_delete_confirmed' in st.session_state:
                del st.session_state.papers_to_delete_confirmed
            st.rerun()

    # Show delete confirmation dialog
    if st.session_state.get('show_delete_dialog', False) and 'papers_to_delete' in st.session_state:
        @st.dialog("⚠️ Confirm Delete")
        def confirm_delete_dialog():
            papers_df = st.session_state.papers_to_delete
            paper_titles = [row['_paper_title'] for _, row in papers_df.iterrows()]
            num_papers = len(paper_titles)

            st.write(f"Are you sure you want to delete **{num_papers} paper(s)**?")
            st.write("")
            st.write("**Papers to be deleted:**")
            for title in paper_titles[:5]:  # Show first 5
                st.write(f"• {title}")
            if num_papers > 5:
                st.write(f"_... and {num_papers - 5} more_")

            st.write("")

            # Don't ask again checkbox
            dont_ask = st.checkbox("Don't ask again (skip confirmation in the future)", key="dont_ask_delete")

            st.write("")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("✓ Confirm Delete", type="primary", use_container_width=True):
                    # Save preference if checkbox is checked
                    if dont_ask:
                        settings = load_settings()
                        settings['skip_delete_confirmation'] = True
                        save_settings(settings)

                    # Store papers for deletion and set confirmation flag
                    st.session_state.papers_to_delete_confirmed = papers_df.copy()
                    st.session_state.delete_confirmed = True

                    # Close dialog
                    st.session_state.show_delete_dialog = False
                    if 'papers_to_delete' in st.session_state:
                        del st.session_state.papers_to_delete
                    st.rerun()

            with col2:
                if st.button("✗ Cancel", use_container_width=True):
                    # Clear session state and close dialog
                    st.session_state.show_delete_dialog = False
                    if 'papers_to_delete' in st.session_state:
                        del st.session_state.papers_to_delete
                    st.rerun()

        confirm_delete_dialog()

    # Handle Find DOI button click
    if find_doi_button and grid_response['selected_rows'] is not None and len(grid_response['selected_rows']) > 0:
        selected_rows_df = pd.DataFrame(grid_response['selected_rows'])

        # Filter for papers missing DOI
        papers_missing_doi = []
        for _, row in selected_rows_df.iterrows():
            doi = row.get('DOI', '—')
            if doi in ['—', '', 'nan', 'None']:
                papers_missing_doi.append({
                    'filename': row['_filename'],
                    'title': row['_paper_title']
                })

        if len(papers_missing_doi) == 0:
            st.info("ℹ️ All selected papers already have DOIs")
        else:
            # Use progress placeholders at top of page
            progress_text = progress_placeholder
            progress_bar = progress_bar_placeholder.progress(0)

            found_count = 0
            not_found_count = 0

            # Load metadata once
            metadata_file = Path("data/metadata.json")
            with open(metadata_file, 'r', encoding='utf-8') as f:
                all_metadata = json.load(f)

            from lib.app_helpers import find_doi_via_semantic_scholar, query_crossref_for_metadata
            from lib.rag import DatabaseClient

            enriched_count = 0

            for idx, paper in enumerate(papers_missing_doi):
                # Update status with running counts
                status_text = f"Finding DOIs: {idx + 1}/{len(papers_missing_doi)} complete ({found_count} found, {not_found_count} not found)"
                progress_text.text(status_text)
                progress_bar.progress((idx + 1) / len(papers_missing_doi))

                # Step 1: Find DOI via Semantic Scholar
                found_doi = find_doi_via_semantic_scholar(paper['title'])

                if found_doi:
                    # Step 2: Enrich from CrossRef using the found DOI
                    progress_text.text(f"{status_text} | Enriching metadata...")
                    crossref_data = query_crossref_for_metadata(found_doi)

                    if crossref_data and paper['filename'] in all_metadata:
                        # Update all metadata fields from CrossRef
                        all_metadata[paper['filename']]['doi'] = found_doi

                        # Extract and save additional metadata
                        if crossref_data.get('title'):
                            all_metadata[paper['filename']]['title'] = crossref_data['title']
                        if crossref_data.get('authors'):
                            all_metadata[paper['filename']]['authors'] = crossref_data['authors']
                        if crossref_data.get('year'):
                            all_metadata[paper['filename']]['year'] = crossref_data['year']
                        if crossref_data.get('journal'):
                            all_metadata[paper['filename']]['journal'] = crossref_data['journal']
                        if crossref_data.get('volume'):
                            all_metadata[paper['filename']]['volume'] = crossref_data['volume']
                        if crossref_data.get('issue'):
                            all_metadata[paper['filename']]['issue'] = crossref_data['issue']
                        if crossref_data.get('pages'):
                            all_metadata[paper['filename']]['pages'] = crossref_data['pages']

                        # Update ChromaDB with all new metadata
                        DatabaseClient.update_paper_metadata(paper['filename'], all_metadata[paper['filename']])

                        found_count += 1
                        enriched_count += 1
                    else:
                        # DOI found but enrichment failed - still save the DOI
                        all_metadata[paper['filename']]['doi'] = found_doi
                        DatabaseClient.update_paper_metadata(paper['filename'], {"doi": found_doi})
                        found_count += 1
                else:
                    not_found_count += 1

            # Save metadata.json
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(all_metadata, f, indent=2, ensure_ascii=False)

            # Clear caches and reload
            DatabaseClient.clear_cache()
            st.cache_data.clear()
            st.session_state.reload_papers = True

            # Clear progress indicators
            progress_text.empty()
            progress_bar.empty()

            # Show summary
            if found_count > 0:
                st.success(f"✅ Found and enriched {enriched_count} of {len(papers_missing_doi)} papers. {not_found_count} not found.")
            else:
                st.warning(f"⚠️ No DOIs found for any of the {len(papers_missing_doi)} selected papers.")

            time.sleep(2)
            st.rerun()

    # Handle Enrich All Incomplete button click
    if enrich_incomplete_button:
        # Get all incomplete papers from the current filtered view
        incomplete_papers = []
        for _, row in df.iterrows():
            if row['Status'] == '⚠️ Incomplete':
                doi = row.get('DOI', '—')
                if doi in ['—', '', 'nan', 'None']:
                    incomplete_papers.append({
                        'filename': row['_filename'],
                        'title': row['_paper_title']
                    })

        if len(incomplete_papers) == 0:
            st.info("ℹ️ No incomplete papers need enrichment (all have DOIs or are already complete)")
        else:
            st.info(f"🚀 Processing {len(incomplete_papers)} incomplete papers...")

            # Use progress placeholders at top of page
            progress_text = progress_placeholder
            progress_bar = progress_bar_placeholder.progress(0)

            found_count = 0
            not_found_count = 0
            enriched_count = 0

            # Load metadata once
            metadata_file = Path("data/metadata.json")
            with open(metadata_file, 'r', encoding='utf-8') as f:
                all_metadata = json.load(f)

            from lib.app_helpers import find_doi_via_semantic_scholar, query_crossref_for_metadata
            from lib.rag import DatabaseClient

            for idx, paper in enumerate(incomplete_papers):
                # Update status with running counts
                status_text = f"Processing: {idx + 1}/{len(incomplete_papers)} complete ({found_count} found, {not_found_count} not found, {enriched_count} enriched)"
                progress_text.text(status_text)
                progress_bar.progress((idx + 1) / len(incomplete_papers))

                # Step 1: Find DOI via Semantic Scholar
                found_doi = find_doi_via_semantic_scholar(paper['title'])

                if found_doi:
                    # Step 2: Enrich from CrossRef using the found DOI
                    progress_text.text(f"{status_text} | Enriching metadata...")
                    crossref_data = query_crossref_for_metadata(found_doi)

                    if crossref_data and paper['filename'] in all_metadata:
                        # Update all metadata fields from CrossRef
                        all_metadata[paper['filename']]['doi'] = found_doi

                        # Extract and save additional metadata
                        if crossref_data.get('title'):
                            all_metadata[paper['filename']]['title'] = crossref_data['title']
                        if crossref_data.get('authors'):
                            all_metadata[paper['filename']]['authors'] = crossref_data['authors']
                        if crossref_data.get('year'):
                            all_metadata[paper['filename']]['year'] = crossref_data['year']
                        if crossref_data.get('journal'):
                            all_metadata[paper['filename']]['journal'] = crossref_data['journal']
                        if crossref_data.get('volume'):
                            all_metadata[paper['filename']]['volume'] = crossref_data['volume']
                        if crossref_data.get('issue'):
                            all_metadata[paper['filename']]['issue'] = crossref_data['issue']
                        if crossref_data.get('pages'):
                            all_metadata[paper['filename']]['pages'] = crossref_data['pages']

                        # Update ChromaDB with all new metadata
                        DatabaseClient.update_paper_metadata(paper['filename'], all_metadata[paper['filename']])

                        found_count += 1
                        enriched_count += 1
                    else:
                        # DOI found but enrichment failed - still save the DOI
                        all_metadata[paper['filename']]['doi'] = found_doi
                        DatabaseClient.update_paper_metadata(paper['filename'], {"doi": found_doi})
                        found_count += 1
                else:
                    not_found_count += 1

            # Save metadata.json
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(all_metadata, f, indent=2, ensure_ascii=False)

            # Clear caches and reload
            DatabaseClient.clear_cache()
            st.cache_data.clear()
            st.session_state.reload_papers = True

            # Clear progress indicators
            progress_text.empty()
            progress_bar.empty()

            # Show summary
            if found_count > 0:
                st.success(f"✅ Found and enriched {enriched_count} of {len(incomplete_papers)} incomplete papers. {not_found_count} not found.")
            else:
                st.warning(f"⚠️ No DOIs found for any of the {len(incomplete_papers)} incomplete papers.")

            time.sleep(2)
            st.rerun()

    # Handle read status changes
    if grid_response['data'] is not None:
        updated_df = pd.DataFrame(grid_response['data'])
        for idx, row in updated_df.iterrows():
            original_status = df.iloc[idx]['Read']
            new_status = row['Read']
            if original_status != new_status:
                filename = row['_filename']
                if new_status:
                    read_status.mark_as_read(filename)
                else:
                    read_status.mark_as_unread(filename)
                st.rerun()
                break

    # Handle row selection for navigation (navigable columns select the row via JavaScript)
    # Navigate only if exactly ONE row is selected and no bulk operations are in progress
    # This allows checkboxes to work for bulk operations while single clicks navigate
    selected_rows = grid_response.get('selected_rows')
    if selected_rows is not None and len(selected_rows) > 0:
        selected_df = pd.DataFrame(selected_rows)

        if (len(selected_df) == 1 and  # Exactly one row
            not delete_button and  # No delete button clicked
            not find_doi_button and  # No find DOI button clicked
            not enrich_incomplete_button):  # No enrich button clicked

            # Navigate to paper detail view
            selected_row = selected_df.iloc[0]
            filename = selected_row.get('_filename')
            if filename:
                st.session_state.selected_paper = filename
                st.rerun()

