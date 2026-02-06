"""
Astrolabe Paper Database - Modular Entry Point
"""
import streamlit as st

# Page config must be FIRST
st.set_page_config(
    page_title="Astrolabe Paper Database",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import and run the monolithic app
# All code is in app_monolith.py - we'll refactor it gradually
import app_monolith
