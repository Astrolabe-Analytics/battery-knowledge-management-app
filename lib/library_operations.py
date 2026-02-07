"""
Library operations - functions for managing papers in the library.
Extracted from app_monolith.py for use in independent pages.
"""
import json
import requests
import time
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# These will be extracted from app_monolith
