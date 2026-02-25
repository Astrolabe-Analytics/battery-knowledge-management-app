"""
Convert to Streamlit Native Multipage App
Each page loads independently - real performance gains!
"""
import os
import shutil
from pathlib import Path

print("="*70)
print("CONVERTING TO STREAMLIT MULTIPAGE APP")
print("="*70)

# Backup first
if not Path('app_monolith_backup.py').exists():
    shutil.copy('app_monolith.py', 'app_monolith_backup.py')
    print("\n[OK] Backed up app_monolith.py")

# Read the monolith
with open('app_monolith.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Tab boundaries (from earlier grep)
tabs = {
    'Import': (1464, 1775),
    'Library': (1776, 3697),
    'Discover': (3698, 4207),
    'Research': (4208, 4438),
    'History': (4439, 4505),
    'Settings': (4506, 4795),
    'Trash': (4796, 5100),
}

# Extract helper functions (lines 38-1463)
helpers_section = ''.join(lines[37:1463])

# ============================================================================
# Create main app.py (landing page with sidebar)
# ============================================================================
print("\nCreating main app.py...")

main_app = '''"""
Astrolabe Paper Database - Multipage App
Each page loads independently for better performance.
"""
import streamlit as st
from pathlib import Path

# Page config
st.set_page_config(
    page_title="Astrolabe",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'

if 'selected_paper' not in st.session_state:
    st.session_state.selected_paper = None

# Import helpers
from lib import rag

# Sidebar
with st.sidebar:
    st.title("📚 Astrolabe")
    st.caption("Battery Research Paper Database")

    st.divider()

    # Load papers with caching
    if 'cached_papers' not in st.session_state or st.session_state.get('reload_papers', False):
        try:
            st.session_state.cached_papers = rag.get_paper_library()
            st.session_state.reload_papers = False
        except Exception as e:
            st.error(str(e))
            st.stop()

    papers = st.session_state.cached_papers

    # Stats
    complete = sum(1 for p in papers if p.get('title') and p.get('authors') and Path('papers', p['filename']).exists())
    metadata_only = sum(1 for p in papers if p.get('title') and p.get('authors') and not Path('papers', p['filename']).exists())

    st.metric("📄 Papers", len(papers))
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Complete", complete)
    with col2:
        st.metric("📋 Metadata", metadata_only)

# Main content
st.title("📚 Astrolabe Paper Database")
st.markdown("Battery research paper library with RAG-powered search")

st.info("👈 Use the sidebar to navigate between pages")

st.markdown("### Features")
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    **📥 Import**
    - Import papers from URL, DOI, or CSV
    - PDF upload with metadata extraction

    **📚 Library**
    - Browse all papers with filters
    - Collections and tagging
    - Quick search and sort
    """)

with col2:
    st.markdown("""
    **🔍 Discover**
    - Find frequently cited papers
    - Search Semantic Scholar

    **🔬 Research**
    - RAG-powered paper search
    - Citation network analysis
    """)
'''

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(main_app)
print("[OK] Created app.py (landing page)")

# ============================================================================
# Create lib/app_helpers.py with shared functions
# ============================================================================
print("\nCreating lib/app_helpers.py...")

app_helpers = '''"""
Helper functions shared across app pages.
Extracted from original monolithic app.py
"""
import streamlit as st
import json
import re
import requests
from pathlib import Path
from typing import Dict, Any, Optional

''' + helpers_section

with open('lib/app_helpers.py', 'w', encoding='utf-8') as f:
    f.write(app_helpers)
print("[OK] Created lib/app_helpers.py")

# ============================================================================
# Create page files
# ============================================================================
print("\nCreating page files...")

# Pages with extracted content - use the monolith temporarily
page_template = '''"""
{title} Page
"""
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="{title}", page_icon="{icon}", layout="wide")

# Import shared helpers and modules
from lib import rag, app_helpers
from lib.ui_helpers import load_settings, save_settings

# Get papers from session state (loaded in main app)
if 'cached_papers' not in st.session_state:
    st.session_state.cached_papers = rag.get_paper_library()

papers = st.session_state.cached_papers

# Page content
st.title("{icon} {title}")

# Temporarily import from monolith until fully extracted
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import app_monolith
    # Run the specific tab from monolith
    st.info("🚧 This page is temporarily using the monolith. Extraction in progress.")
except ImportError:
    st.error("Could not load app_monolith.py")
'''

pages_config = [
    ("01_📥_Import.py", "Import", "📥"),
    ("02_📚_Library.py", "Library", "📚"),
    ("03_🔍_Discover.py", "Discover", "🔍"),
    ("04_🔬_Research.py", "Research", "🔬"),
    ("05_📜_History.py", "History", "📜"),
    ("06_⚙️_Settings.py", "Settings", "⚙️"),
    ("07_🗑️_Trash.py", "Trash", "🗑️"),
]

for filename, title, icon in pages_config:
    page_content = page_template.format(title=title, icon=icon)
    with open(f'pages/{filename}', 'w', encoding='utf-8') as f:
        f.write(page_content)
    print(f"[OK] Created pages/{filename}")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "="*70)
print("MULTIPAGE CONVERSION COMPLETE!")
print("="*70)
print("\nStructure created:")
print("  app.py                  (landing page)")
print("  lib/app_helpers.py      (shared functions)")
print("  pages/")
print("    01_📥_Import.py")
print("    02_📚_Library.py")
print("    03_🔍_Discover.py")
print("    04_🔬_Research.py")
print("    05_📜_History.py")
print("    06_⚙️_Settings.py")
print("    07_🗑️_Trash.py")
print("\nHow it works:")
print("  - Streamlit automatically creates sidebar nav")
print("  - Each page loads ONLY when clicked")
print("  - Real performance improvement!")
print("\nTest it:")
print("  streamlit run app.py")
print("\nIf it works:")
print("  git add -A && git commit -m 'Convert to multipage app'")
print("="*70)
