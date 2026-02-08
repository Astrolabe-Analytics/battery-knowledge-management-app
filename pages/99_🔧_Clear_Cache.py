"""
Cache clearing utility page.
Use this after running scripts that modify the database outside of the UI.
"""
import streamlit as st
from lib.rag import DatabaseClient

st.set_page_config(page_title="Clear Cache", page_icon="🔧")

st.title("🔧 Clear Cache")

st.markdown("""
Use this page to force the UI to reload data from the database.

**When to use this:**
- After running enrichment scripts
- After generating AI summaries
- After manual database modifications
- When the UI shows stale data
""")

st.divider()

col1, col2 = st.columns([1, 3])

with col1:
    if st.button("🗑️ Clear All Caches", type="primary", use_container_width=True):
        # Clear all caches
        DatabaseClient.clear_cache()
        st.cache_data.clear()

        # Clear session state caches
        keys_to_clear = ['cached_papers', 'cached_stats', 'cached_filter_options', 'cached_total_chunks']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]

        st.session_state.reload_papers = True

        st.success("✅ All caches cleared!")
        st.info("🔄 Navigate to the Library page to see fresh data.")
        st.balloons()

with col2:
    st.markdown("""
    **What this does:**
    1. Clears ChromaDB client cache
    2. Clears all Streamlit `@st.cache_data` caches
    3. Forces papers list to reload
    4. Forces stats to recalculate
    """)

st.divider()

st.markdown("""
### 📚 After clearing cache:
1. Go to the **Library** page
2. You should see updated stats and data
3. The "Summarized" status should now appear
""")
