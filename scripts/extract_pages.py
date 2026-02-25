"""
Phase 2: Extract pages from app_monolith.py
Creates actual separate page modules for real performance gains.
"""
import os
import re
from pathlib import Path

print("="*70)
print("PHASE 2: EXTRACTING PAGES FROM APP_MONOLITH")
print("="*70)

# Read app_monolith.py
with open('app_monolith.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    content = ''.join(lines)

# Find tab boundaries (already know from earlier grep)
tab_boundaries = {
    'import': (1464, 1775),
    'library': (1776, 3697),
    'discover': (3698, 4207),
    'research': (4208, 4438),
    'history': (4439, 4505),
    'settings': (4506, 4795),
    'trash': (4796, 5100),
}

def extract_section(start_line, end_line):
    """Extract lines from start to end (1-indexed like grep output)."""
    return ''.join(lines[start_line-1:end_line])

# ============================================================================
# STEP 1: Extract Library Tab
# ============================================================================
print("\nStep 1: Extracting Library Tab...")

library_code = extract_section(1776, 3697)

# Find where the tab starts and extract just the content inside the tab
library_content = re.search(r'with tab2:.*?(?=\n    # ===== TAB|\Z)', library_code, re.DOTALL)
if library_content:
    library_tab_code = library_content.group(0)
else:
    library_tab_code = library_code

library_page = '''"""
Library Tab - Main paper listing with filters and grid.
"""
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
import pandas as pd
from pathlib import Path
import json

# Import backend modules
from lib import rag, read_status, collections

def render(papers):
    """Render the library tab."""
    st.session_state.active_tab = "Library"

    # Extract and run the library tab code
''' + '\n'.join('    ' + line for line in library_tab_code.split('\n'))

with open('pages/library.py', 'w', encoding='utf-8') as f:
    f.write(library_page)
print("  [OK] pages/library.py created")

# ============================================================================
# STEP 2: Create routing app.py
# ============================================================================
print("\nStep 2: Creating routing app.py...")

new_app = '''"""
Astrolabe Paper Database - Entry Point with Page Routing
"""
import streamlit as st
from pathlib import Path

# Page config MUST be first
st.set_page_config(
    page_title="Astrolabe Paper Database",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'theme' not in st.session_state:
    from lib.ui_helpers import load_theme_preference
    st.session_state.theme = load_theme_preference()

if 'selected_paper' not in st.session_state:
    st.session_state.selected_paper = None

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "Library"

# ============================================================================
# SIDEBAR (compact version)
# ============================================================================
with st.sidebar:
    st.title("📚 Astrolabe")
    st.caption("Battery Research Paper Database")

    # Theme toggle
    from lib.ui_helpers import save_theme_preference
    new_theme = st.radio(
        "🎨 Theme",
        options=["light", "dark"],
        index=0 if st.session_state.theme == "light" else 1,
        horizontal=True,
        key="theme_radio"
    )
    if new_theme != st.session_state.theme:
        st.session_state.theme = new_theme
        save_theme_preference(new_theme)
        st.rerun()

    st.divider()

    # Load papers with caching
    if 'cached_papers' not in st.session_state or st.session_state.get('reload_papers', False):
        try:
            from lib import rag
            st.session_state.cached_papers = rag.get_paper_library()
            st.session_state.cached_filter_options = rag.get_filter_options()
            st.session_state.cached_total_chunks = rag.get_collection_count()
            st.session_state.reload_papers = False
        except (FileNotFoundError, RuntimeError) as e:
            st.error(str(e))
            st.info("Please run `python scripts/ingest.py` first")
            st.stop()

    papers = st.session_state.cached_papers

    # Stats
    complete = sum(1 for p in papers if p.get('title') and p.get('authors') and p.get('year') and p.get('journal') and Path('papers', p['filename']).exists())
    metadata_only = sum(1 for p in papers if p.get('title') and p.get('authors') and p.get('year') and p.get('journal') and not Path('papers', p['filename']).exists())
    incomplete = len(papers) - complete - metadata_only

    st.metric("📄 Total Papers", len(papers))
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Complete", complete)
    with col2:
        st.metric("📋 Metadata", metadata_only)
    if incomplete > 0:
        st.metric("⚠️ Incomplete", incomplete)

# ============================================================================
# MAIN CONTENT - Tab Routing
# ============================================================================

# Create tabs
tabs = st.tabs(["📥 Import", "📚 Library", "🔍 Discover", "🔬 Research", "📜 History", "⚙️ Settings", "🗑️ Trash"])

with tabs[0]:  # Import
    # Temporarily use monolith until extracted
    st.write("🚧 Import tab - temporarily using monolith")
    import app_monolith

with tabs[1]:  # Library
    from pages import library
    library.render(papers)

with tabs[2]:  # Discover
    st.write("🚧 Discover tab - temporarily using monolith")
    import app_monolith

with tabs[3]:  # Research
    st.write("🚧 Research tab - temporarily using monolith")
    import app_monolith

with tabs[4]:  # History
    st.write("🚧 History tab - temporarily using monolith")
    import app_monolith

with tabs[5]:  # Settings
    st.write("🚧 Settings tab - temporarily using monolith")
    import app_monolith

with tabs[6]:  # Trash
    st.write("🚧 Trash tab - temporarily using monolith")
    import app_monolith
'''

with open('app_routed.py', 'w', encoding='utf-8') as f:
    f.write(new_app)
print("  [OK] app_routed.py created")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "="*70)
print("EXTRACTION STARTED")
print("="*70)
print("\nFiles created:")
print("  - pages/library.py (Library tab extracted)")
print("  - app_routed.py (New routing entry point)")
print("\nNext: You need to:")
print("  1. Review pages/library.py to fix any import issues")
print("  2. Test: cp app_routed.py app.py && streamlit run app.py")
print("  3. If it works: git commit")
print("  4. Extract remaining tabs one by one")
print("="*70)
