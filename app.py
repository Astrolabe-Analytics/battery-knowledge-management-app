"""
Astrolabe Paper Database - Main Entry Point
Runs the monolith application (full page extraction deferred for performance)
"""

# Import and run the monolith
from app_monolith import main

if __name__ == "__main__":
    main()
else:
    # When imported by Streamlit, run main immediately
    main()
