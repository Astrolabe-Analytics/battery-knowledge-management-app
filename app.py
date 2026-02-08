"""
Astrolabe Paper Database - Main Entry Point
Home page with navigation to Library and other features
"""
# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from lib import styles
from lib.app_helpers import load_settings

# Page config
st.set_page_config(
    page_title="Astrolabe Research Library",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize theme
if "theme" not in st.session_state:
    settings = load_settings()
    st.session_state.theme = settings.get('theme', 'light')

# Apply CSS
current_theme = st.session_state.theme
st.markdown(styles.get_professional_css(current_theme), unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="app-header">
        <h1 class="app-title">🔭 Astrolabe Research Library</h1>
        <p class="app-subtitle">Battery research papers with AI-powered search</p>
    </div>
""", unsafe_allow_html=True)

st.divider()

# Welcome message
st.markdown("""
### Welcome to Astrolabe

Your personal research library for battery science papers.

**Quick Navigation:**
- 📚 **Library** - Browse, search, and manage your papers
- 🔬 **Research** - AI-powered semantic search across your library
- 📜 **History** - View your query history
- ⚙️ **Settings** - Configure themes, backups, and more

Use the sidebar to navigate between sections.
""")

st.info("👈 Click on **📚 Library** in the sidebar to get started!")
