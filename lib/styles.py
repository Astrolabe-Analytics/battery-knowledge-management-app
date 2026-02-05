"""
Professional styling for Astrolabe Research Library
Clean, enterprise-grade design inspired by Notion and Linear
"""

def get_professional_css(theme='light'):
    """
    Return professional CSS styling for the app.

    Args:
        theme: 'light' or 'dark'

    Returns:
        CSS string to be injected via st.markdown
    """

    # Color palette
    if theme == 'light':
        colors = {
            'bg': '#ffffff',
            'bg_secondary': '#f7f8fa',
            'text': '#1f2937',
            'text_secondary': '#6b7280',
            'text_muted': '#9ca3af',
            'border': '#e5e7eb',
            'border_light': '#f3f4f6',
            'accent': '#3b82f6',  # Blue accent
            'accent_hover': '#2563eb',
            'accent_light': '#dbeafe',
            'shadow': 'rgba(0, 0, 0, 0.05)',
            'hover': '#f9fafb',
        }
    else:
        colors = {
            'bg': '#0f1419',
            'bg_secondary': '#1a1f2e',
            'text': '#e5e7eb',
            'text_secondary': '#9ca3af',
            'text_muted': '#6b7280',
            'border': '#2d3748',
            'border_light': '#1f2937',
            'accent': '#60a5fa',  # Lighter blue for dark mode
            'accent_hover': '#3b82f6',
            'accent_light': '#1e3a8a',
            'shadow': 'rgba(0, 0, 0, 0.3)',
            'hover': '#1f2937',
        }

    return f"""
    <style>
    /* Import professional Google Font */
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000&display=swap');

    /* Global typography and spacing */
    html, body, [class*="css"] {{
        font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        color: {colors['text']};
    }}

    /* Main container */
    .main {{
        padding: 2rem 3rem;
        max-width: 1400px;
        margin: 0 auto;
    }}

    /* Remove default Streamlit padding */
    .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
    }}

    /* Header styling */
    .app-header {{
        margin-bottom: 2rem;
        border-bottom: 1px solid {colors['border']};
        padding-bottom: 1.5rem;
    }}

    .app-title {{
        font-size: 1.875rem;
        font-weight: 600;
        color: {colors['text']};
        margin: 0;
        letter-spacing: -0.025em;
    }}

    .app-subtitle {{
        font-size: 0.875rem;
        color: {colors['text_secondary']};
        margin-top: 0.25rem;
        font-weight: 400;
    }}

    /* Tabs - clean professional styling */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 2rem;
        border-bottom: 1px solid {colors['border']};
        padding: 0;
    }}

    .stTabs [data-baseweb="tab"] {{
        height: 3rem;
        padding: 0 0.5rem;
        background-color: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        color: {colors['text_secondary']};
        font-weight: 500;
        font-size: 0.9375rem;
    }}

    .stTabs [aria-selected="true"] {{
        color: {colors['accent']};
        border-bottom-color: {colors['accent']};
    }}

    .stTabs [data-baseweb="tab"]:hover {{
        color: {colors['text']};
        background-color: transparent;
    }}

    /* Sidebar styling */
    [data-testid="stSidebar"] {{
        background-color: {colors['bg_secondary']};
        border-right: 1px solid {colors['border']};
        padding: 1.5rem 1rem;
    }}

    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{
        font-size: 0.875rem;
        font-weight: 600;
        color: {colors['text']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
    }}

    [data-testid="stSidebar"] .stMetric {{
        background-color: {colors['bg']};
        border: 1px solid {colors['border']};
        border-radius: 0.5rem;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
    }}

    /* Button styling */
    .stButton button {{
        background-color: {colors['accent']};
        color: white;
        border: none;
        border-radius: 0.375rem;
        padding: 0.5rem 1rem;
        font-weight: 500;
        font-size: 0.875rem;
        transition: background-color 0.15s ease;
    }}

    .stButton button:hover {{
        background-color: {colors['accent_hover']};
        border: none;
    }}

    /* Secondary buttons */
    .stButton button[kind="secondary"] {{
        background-color: transparent;
        color: {colors['text']};
        border: 1px solid {colors['border']};
    }}

    .stButton button[kind="secondary"]:hover {{
        background-color: {colors['hover']};
        border-color: {colors['text_secondary']};
    }}

    /* Input fields */
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox select {{
        border: 1px solid {colors['border']};
        border-radius: 0.375rem;
        padding: 0.5rem 0.75rem;
        font-size: 0.875rem;
        background-color: {colors['bg']};
        color: {colors['text']};
    }}

    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stSelectbox select:focus {{
        border-color: {colors['accent']};
        box-shadow: 0 0 0 3px {colors['accent_light']};
        outline: none;
    }}

    /* Search box special styling */
    .stTextInput input[placeholder*="Search"] {{
        font-size: 0.9375rem;
        padding: 0.625rem 1rem;
    }}

    /* Table styling - clean and minimal */
    .ag-theme-streamlit {{
        --ag-border-color: {colors['border_light']};
        --ag-row-hover-color: {colors['hover']};
        --ag-header-background-color: {colors['bg_secondary']};
        --ag-font-family: 'DM Sans', sans-serif;
        --ag-font-size: 0.875rem;
    }}

    .ag-header-cell {{
        font-weight: 600;
        color: {colors['text_secondary']};
        font-size: 0.8125rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    .ag-row {{
        border-bottom: 1px solid {colors['border_light']};
    }}

    .ag-cell {{
        line-height: 1.5;
    }}

    /* Expander styling */
    .streamlit-expanderHeader {{
        font-weight: 500;
        font-size: 0.9375rem;
        color: {colors['text']};
        background-color: {colors['bg_secondary']};
        border: 1px solid {colors['border']};
        border-radius: 0.375rem;
        padding: 0.75rem 1rem;
    }}

    .streamlit-expanderContent {{
        border: 1px solid {colors['border']};
        border-top: none;
        border-radius: 0 0 0.375rem 0.375rem;
        padding: 1rem;
        background-color: {colors['bg']};
    }}

    /* Card styling for detail page */
    .detail-card {{
        background-color: {colors['bg']};
        border: 1px solid {colors['border']};
        border-radius: 0.5rem;
        padding: 2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 3px {colors['shadow']};
    }}

    /* Tag pills - clean professional style */
    .tag-pill {{
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.8125rem;
        font-weight: 500;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
    }}

    .tag-chemistry {{
        background-color: {colors['accent_light']};
        color: {colors['accent']};
    }}

    .tag-topic {{
        background-color: #d1fae5;
        color: #065f46;
    }}

    .tag-application {{
        background-color: #e9d5ff;
        color: #6b21a8;
    }}

    .tag-type {{
        background-color: #fed7aa;
        color: #92400e;
    }}

    /* Divider */
    hr {{
        border: none;
        border-top: 1px solid {colors['border']};
        margin: 1.5rem 0;
    }}

    /* Info boxes */
    .stAlert {{
        border-radius: 0.375rem;
        border-left-width: 4px;
        font-size: 0.875rem;
    }}

    /* Metric styling */
    .stMetric {{
        background-color: {colors['bg']};
        border: 1px solid {colors['border']};
        border-radius: 0.5rem;
        padding: 1rem;
    }}

    .stMetric label {{
        font-size: 0.8125rem;
        font-weight: 500;
        color: {colors['text_secondary']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    .stMetric [data-testid="stMetricValue"] {{
        font-size: 1.5rem;
        font-weight: 600;
        color: {colors['text']};
    }}

    /* Progress bar */
    .stProgress > div > div {{
        background-color: {colors['accent']};
    }}

    /* Hide Streamlit branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}

    /* Tighter spacing */
    .element-container {{
        margin-bottom: 0.75rem;
    }}

    h1, h2, h3 {{
        margin-top: 0;
        margin-bottom: 0.5rem;
        font-weight: 600;
        letter-spacing: -0.025em;
    }}

    h1 {{
        font-size: 1.875rem;
    }}

    h2 {{
        font-size: 1.5rem;
    }}

    h3 {{
        font-size: 1.25rem;
    }}

    p {{
        margin-bottom: 0.75rem;
        line-height: 1.6;
    }}
    </style>
    """
