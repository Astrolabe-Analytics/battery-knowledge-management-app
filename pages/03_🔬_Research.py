"""
Research Page - Semantic search across papers
"""
# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="Research",
    page_icon="🔬",
    layout="wide"
)

# Temporary: Load from monolith
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set active tab before importing monolith
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Research"
else:
    st.session_state.active_tab = "Research"

from app_monolith import main
main()
