#!/usr/bin/env python3
"""
Centralized Theme Management
Provides theme-aware CSS for all Streamlit components
"""

def get_theme_css(theme: str) -> str:
    """
    Get comprehensive CSS for the current theme.

    Args:
        theme: Either 'dark' or 'light'

    Returns:
        CSS string to inject into Streamlit
    """

    if theme == "dark":
        return """
        <style>
            /* ===== DARK MODE ===== */

            /* Main app background */
            .stApp {
                background-color: #0E1117 !important;
            }

            /* Main content area */
            .main .block-container {
                background-color: #0E1117 !important;
            }

            /* Sidebar - multiple selectors for full coverage */
            [data-testid="stSidebar"] {
                background-color: #1E1E1E !important;
            }

            [data-testid="stSidebar"] > div:first-child {
                background-color: #1E1E1E !important;
            }

            section[data-testid="stSidebar"] {
                background-color: #1E1E1E !important;
            }

            section[data-testid="stSidebar"] > div {
                background-color: #1E1E1E !important;
            }

            /* All text elements */
            .stApp, .stApp p, .stApp span, .stApp label, .stApp li {
                color: #E0E0E0 !important;
            }

            /* Headers */
            .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
                color: #FFFFFF !important;
            }

            /* Markdown and captions */
            .stMarkdown, [data-testid="stMarkdownContainer"] {
                color: #E0E0E0 !important;
            }

            /* Buttons - more aggressive targeting */
            .stButton > button,
            button[kind="secondary"],
            button[kind="primary"] {
                background-color: #3D3D46 !important;
                color: #FFFFFF !important;
                border: 1px solid #5A5A5A !important;
                font-weight: 500 !important;
            }

            .stButton > button:hover {
                background-color: #4A4A56 !important;
                border-color: #6A6A6A !important;
            }

            /* Primary buttons */
            .stButton > button[kind="primary"],
            button[kind="primary"] {
                background-color: #0068C9 !important;
                color: #FFFFFF !important;
            }

            /* Text inputs - aggressive targeting */
            .stTextInput > div > div > input,
            .stTextArea > div > div > textarea,
            input[type="text"],
            input[type="password"],
            textarea {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #4A4A4A !important;
            }

            .stTextInput > div > div > input::placeholder,
            .stTextArea > div > div > textarea::placeholder {
                color: #8A8A8A !important;
            }

            /* Input labels in sidebar */
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] .stMarkdown,
            [data-testid="stSidebar"] p,
            [data-testid="stSidebar"] span {
                color: #E0E0E0 !important;
            }

            /* Select boxes - more aggressive */
            .stSelectbox > div > div > div,
            .stSelectbox [data-baseweb="select"],
            .stSelectbox [data-baseweb="select"] > div,
            [data-baseweb="select"] {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border-color: #4A4A4A !important;
            }

            /* Select box text */
            .stSelectbox [data-baseweb="select"] span,
            .stSelectbox [data-baseweb="select"] div {
                color: #FAFAFA !important;
            }

            /* Dropdown menu */
            [data-baseweb="popover"] {
                background-color: #262730 !important;
            }

            [role="listbox"] {
                background-color: #262730 !important;
            }

            [role="option"] {
                background-color: #262730 !important;
                color: #FAFAFA !important;
            }

            [role="option"]:hover {
                background-color: #3D3D46 !important;
            }

            /* File uploader */
            [data-testid="stFileUploader"] {
                background-color: #262730 !important;
                border: 2px dashed #4A4A4A !important;
                border-radius: 8px !important;
            }

            [data-testid="stFileUploader"]:hover {
                border-color: #0068C9 !important;
                background-color: #2D2D38 !important;
            }

            [data-testid="stFileUploader"] section {
                background-color: transparent !important;
            }

            [data-testid="stFileUploader"] label {
                color: #E0E0E0 !important;
            }

            /* Upload drop zone styling */
            .upload-zone {
                background-color: rgba(0, 104, 201, 0.1) !important;
                border: 2px dashed #0068C9 !important;
                border-radius: 8px !important;
                padding: 20px !important;
            }

            .upload-zone:hover {
                background-color: rgba(0, 104, 201, 0.15) !important;
                border-color: #1E88E5 !important;
            }

            /* Radio buttons */
            .stRadio > div {
                background-color: transparent !important;
            }

            .stRadio label {
                color: #E0E0E0 !important;
            }

            /* Expanders */
            .streamlit-expanderHeader,
            [data-testid="stExpander"] summary {
                background-color: #262730 !important;
                color: #FAFAFA !important;
            }

            .streamlit-expanderContent,
            [data-testid="stExpander"] > div {
                background-color: #1E1E1E !important;
                border-color: #4A4A4A !important;
            }

            /* Metrics */
            [data-testid="stMetricValue"] {
                color: #FAFAFA !important;
            }

            [data-testid="stMetricLabel"] {
                color: #B0B0B0 !important;
            }

            /* Alerts/Info boxes */
            .stAlert, [data-baseweb="notification"] {
                background-color: #262730 !important;
                color: #FAFAFA !important;
            }

            /* Success messages */
            .stSuccess {
                background-color: #1B4332 !important;
                color: #A7F3D0 !important;
            }

            /* Warning messages */
            .stWarning {
                background-color: #78350F !important;
                color: #FDE68A !important;
            }

            /* Error messages */
            .stError {
                background-color: #7F1D1D !important;
                color: #FCA5A5 !important;
            }

            /* Info messages */
            .stInfo {
                background-color: #1E3A8A !important;
                color: #93C5FD !important;
            }

            /* Dividers */
            hr {
                border-color: #4A4A4A !important;
            }

            /* Tabs */
            .stTabs [data-baseweb="tab-list"] {
                background-color: #1E1E1E !important;
            }

            .stTabs [data-baseweb="tab"] {
                color: #B0B0B0 !important;
            }

            .stTabs [aria-selected="true"] {
                color: #FAFAFA !important;
            }

            /* Code blocks */
            .stCodeBlock, code {
                background-color: #1E1E1E !important;
                color: #E0E0E0 !important;
            }

            /* Dataframe/Table */
            .stDataFrame, .stTable {
                color: #E0E0E0 !important;
            }

            /* Links */
            a {
                color: #58A6FF !important;
            }

            a:hover {
                color: #79C0FF !important;
            }

            /* Progress bar */
            .stProgress > div > div > div > div {
                background-color: #0068C9 !important;
            }

            /* Containers */
            [data-testid="stVerticalBlock"] > div {
                background-color: transparent !important;
            }
        </style>
        """
    else:  # light mode
        return """
        <style>
            /* ===== LIGHT MODE ===== */

            /* Main app background */
            .stApp {
                background-color: #FFFFFF !important;
            }

            /* Main content area */
            .main .block-container {
                background-color: #FFFFFF !important;
            }

            /* Sidebar */
            [data-testid="stSidebar"],
            section[data-testid="stSidebar"] {
                background-color: #F0F2F6 !important;
            }

            [data-testid="stSidebar"] > div:first-child,
            section[data-testid="stSidebar"] > div {
                background-color: #F0F2F6 !important;
            }

            /* All text elements */
            .stApp, .stApp p, .stApp span, .stApp label, .stApp li {
                color: #262730 !important;
            }

            /* Headers */
            .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
                color: #262730 !important;
            }

            /* Buttons */
            .stButton > button,
            button[kind="secondary"],
            button[kind="primary"] {
                background-color: #FFFFFF !important;
                color: #262730 !important;
                border: 1px solid #D0D0D0 !important;
                font-weight: 500 !important;
            }

            .stButton > button:hover {
                background-color: #F8F9FA !important;
                border-color: #B0B0B0 !important;
            }

            /* Primary buttons */
            .stButton > button[kind="primary"],
            button[kind="primary"] {
                background-color: #FF4B4B !important;
                color: #FFFFFF !important;
            }

            /* Text inputs */
            .stTextInput > div > div > input,
            .stTextArea > div > div > textarea,
            input[type="text"],
            input[type="password"],
            textarea {
                background-color: #FFFFFF !important;
                color: #262730 !important;
                border: 1px solid #D0D0D0 !important;
            }

            /* Select boxes */
            .stSelectbox > div > div > div,
            .stSelectbox [data-baseweb="select"],
            .stSelectbox [data-baseweb="select"] > div,
            [data-baseweb="select"] {
                background-color: #FFFFFF !important;
                color: #262730 !important;
                border-color: #D0D0D0 !important;
            }

            /* Select box text */
            .stSelectbox [data-baseweb="select"] span,
            .stSelectbox [data-baseweb="select"] div {
                color: #262730 !important;
            }

            /* Dropdown menu */
            [data-baseweb="popover"] {
                background-color: #FFFFFF !important;
            }

            [role="listbox"] {
                background-color: #FFFFFF !important;
            }

            [role="option"] {
                background-color: #FFFFFF !important;
                color: #262730 !important;
            }

            [role="option"]:hover {
                background-color: #F0F2F6 !important;
            }

            /* File uploader */
            [data-testid="stFileUploader"] {
                background-color: #F8F9FA !important;
                border: 2px dashed #D0D0D0 !important;
                border-radius: 8px !important;
            }

            [data-testid="stFileUploader"]:hover {
                border-color: #0068C9 !important;
                background-color: #E8F4FD !important;
            }

            [data-testid="stFileUploader"] section {
                background-color: transparent !important;
            }

            [data-testid="stFileUploader"] label {
                color: #262730 !important;
            }

            /* Upload drop zone styling */
            .upload-zone {
                background-color: rgba(0, 104, 201, 0.05) !important;
                border: 2px dashed #0068C9 !important;
                border-radius: 8px !important;
                padding: 20px !important;
            }

            .upload-zone:hover {
                background-color: rgba(0, 104, 201, 0.1) !important;
                border-color: #1E88E5 !important;
            }

            /* Radio buttons */
            .stRadio label {
                color: #262730 !important;
            }

            /* Expanders */
            .streamlit-expanderHeader,
            [data-testid="stExpander"] summary {
                background-color: #F0F2F6 !important;
                color: #262730 !important;
            }

            /* Containers */
            [data-testid="stVerticalBlock"] > div {
                background-color: transparent !important;
            }
        </style>
        """
