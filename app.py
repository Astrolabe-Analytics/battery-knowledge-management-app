"""
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
