"""
Trash Page
"""
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Trash", page_icon="🗑️", layout="wide")

# Import shared helpers and modules
from lib import rag, app_helpers
from lib.app_helpers import load_settings, save_settings

# Get papers from session state (loaded in main app)
if 'cached_papers' not in st.session_state:
    st.session_state.cached_papers = rag.get_paper_library()

papers = st.session_state.cached_papers

# Page content
st.title("🗑️ Trash")

# Temporarily import from monolith until fully extracted
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import app_monolith
    # Run the specific tab from monolith
    st.info("🚧 This page is temporarily using the monolith. Extraction in progress.")
except ImportError:
    st.error("Could not load app_monolith.py")
