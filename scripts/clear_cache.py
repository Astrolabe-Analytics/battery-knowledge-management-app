"""
Clear Streamlit cache to force UI reload.
Run this after making database changes that aren't reflected in the UI.
"""
import streamlit as st

# This will clear all cached data
st.cache_data.clear()

print("Cache cleared successfully!")
print("Refresh your browser to see the updates.")
