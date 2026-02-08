"""
📰 Feed - Research paper timeline with tweet-style summaries
"""
import streamlit as st
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from lib import rag
from lib import read_status

st.set_page_config(page_title="Feed - Astrolabe", page_icon="📰", layout="wide")

# Custom CSS for feed cards
st.markdown("""
<style>
.feed-meta {
    font-size: 13px;
    color: #6b7280;
    margin-bottom: 12px;
}
.feed-blurb {
    font-size: 15px;
    line-height: 1.6;
    margin-bottom: 12px;
}
.feed-tags {
    margin-top: 12px;
}
.feed-tag {
    display: inline-block;
    background-color: #e5e7eb;
    color: #374151;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    margin-right: 6px;
    margin-bottom: 6px;
}
</style>
""", unsafe_allow_html=True)

st.title("📰 Research Feed")
st.caption("Latest papers with AI-generated summaries")

# Initialize session state for expanded cards
if 'expanded_cards' not in st.session_state:
    st.session_state.expanded_cards = set()

# Load papers
@st.cache_data(ttl=60)
def load_feed_papers():
    """Load papers that have feed blurbs."""
    all_papers = rag.get_paper_library()

    # Filter to papers with feed_blurb
    feed_papers = [p for p in all_papers if p.get('feed_blurb')]

    # Sort by year (newest first), then by title
    def sort_key(paper):
        year = paper.get('year', '')
        # Convert year to int for sorting, default to 0 if empty/invalid
        try:
            year_int = int(year) if year else 0
        except (ValueError, TypeError):
            year_int = 0
        return (-year_int, paper.get('title', ''))

    feed_papers.sort(key=sort_key)

    return feed_papers

papers = load_feed_papers()

# Filters
st.markdown("---")
filter_cols = st.columns([1, 1, 1, 2])

with filter_cols[0]:
    # Get unique chemistry tags
    all_chem_tags = set()
    for p in papers:
        all_chem_tags.update(p.get('chemistries', []))
    chem_options = ["All Chemistry"] + sorted(all_chem_tags)
    chem_filter = st.selectbox("Chemistry", options=chem_options)

with filter_cols[1]:
    # Get unique topics
    all_topics = set()
    for p in papers:
        all_topics.update(p.get('topics', []))
    topic_options = ["All Topics"] + sorted(all_topics)
    topic_filter = st.selectbox("Topic", options=topic_options)

with filter_cols[2]:
    # Get unique years
    all_years = sorted(set(p.get('year') for p in papers if p.get('year')), reverse=True)
    year_options = ["All Years"] + [str(y) for y in all_years]
    year_filter = st.selectbox("Year", options=year_options)

# Apply filters
filtered_papers = papers

if chem_filter != "All Chemistry":
    filtered_papers = [p for p in filtered_papers if chem_filter in p.get('chemistries', [])]

if topic_filter != "All Topics":
    filtered_papers = [p for p in filtered_papers if topic_filter in p.get('topics', [])]

if year_filter != "All Years":
    filtered_papers = [p for p in filtered_papers if str(p.get('year')) == year_filter]

st.markdown("---")

# Show count
st.caption(f"Showing {len(filtered_papers)} papers")

# Feed cards
for paper in filtered_papers:
    filename = paper.get('filename', '')
    title = paper.get('title', 'Unknown')

    # Extract first author + et al.
    authors_raw = paper.get('authors', '')
    if authors_raw:
        # Split by comma or semicolon
        author_list = [a.strip() for a in authors_raw.replace(';', ',').split(',') if a.strip()]
        if len(author_list) > 1:
            authors = f"{author_list[0]} et al."
        else:
            authors = author_list[0] if author_list else 'Unknown'
    else:
        authors = 'Unknown'

    journal = paper.get('journal', '')
    year = paper.get('year', '')
    blurb = paper.get('feed_blurb', '')
    chemistry_tags = paper.get('chemistries', [])
    ai_summary = paper.get('ai_summary', '')

    # Create card container
    with st.container():
        # Title as bold text (larger font)
        st.markdown(f'<div style="font-size: 18px; font-weight: 600; margin-bottom: 8px; color: inherit;">{title}</div>',
                   unsafe_allow_html=True)

        # Meta line
        meta_parts = []
        if authors:
            meta_parts.append(authors)
        if journal:
            meta_parts.append(journal)
        if year:
            meta_parts.append(str(year))

        meta_text = " · ".join(meta_parts)
        st.markdown(f'<div class="feed-meta">{meta_text}</div>', unsafe_allow_html=True)

        # Blurb
        st.markdown(f'<div class="feed-blurb">{blurb}</div>', unsafe_allow_html=True)

        # Chemistry tags
        if chemistry_tags:
            tags_html = '<div class="feed-tags">'
            for tag in chemistry_tags:
                tags_html += f'<span class="feed-tag">{tag}</span>'
            tags_html += '</div>'
            st.markdown(tags_html, unsafe_allow_html=True)

        # Read Summary button (expander)
        if ai_summary:
            card_key = f"summary_{filename}"
            is_expanded = card_key in st.session_state.expanded_cards

            button_col1, button_col2, button_col3 = st.columns([2, 6, 2])
            with button_col1:
                if st.button("📖 Read Full Summary" if not is_expanded else "📕 Hide Summary",
                           key=f"btn_{filename}",
                           type="secondary"):
                    if is_expanded:
                        st.session_state.expanded_cards.remove(card_key)
                    else:
                        st.session_state.expanded_cards.add(card_key)
                    st.rerun()

            # Show full summary if expanded
            if is_expanded:
                with st.expander("Full AI Summary", expanded=True):
                    st.markdown(ai_summary)

        st.markdown("---")

# Show message if no papers
if not filtered_papers:
    st.info("No papers match the current filters.")
elif not papers:
    st.info("No papers with AI summaries yet. Papers with summaries will appear here automatically.")
