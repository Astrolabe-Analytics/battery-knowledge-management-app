"""
Migration script to refactor app.py into modular structure.
Phase 1: Setup - Keep all functionality intact while creating structure.
"""
import os
import shutil
from pathlib import Path

print("="*70)
print("REFACTORING APP.PY - PHASE 1: SETUP")
print("="*70)

# Step 1: Create backup
print("\nStep 1: Creating backups...")
shutil.copy('app.py', 'app.py.backup')
print("  [OK] app.py.backup created")

# Step 2: Create app_monolith.py with full content
print("\nStep 2: Creating app_monolith.py...")
shutil.copy('app.py', 'app_monolith.py')
print("  [OK] app_monolith.py created (full 5957 lines)")

# Step 3: Create pages/ directory
print("\nStep 3: Creating directory structure...")
os.makedirs('pages', exist_ok=True)
Path('pages/__init__.py').touch()
print("  [OK] pages/ directory created")
print("  [OK] pages/__init__.py created")

# Step 4: Create new streamlined app.py
print("\nStep 4: Creating new app.py...")
new_app_content = '''"""
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
'''

with open('app_new.py', 'w', encoding='utf-8') as f:
    f.write(new_app_content)

# Step 5: Swap files
print("\nStep 5: Swapping files...")
os.rename('app.py', 'app_original.py')
os.rename('app_new.py', 'app.py')
print("  [OK] app.py -> app_original.py")
print("  [OK] app_new.py -> app.py")

# Summary
print("\n" + "="*70)
print("PHASE 1 COMPLETE!")
print("="*70)
print("\nFiles created:")
print("  - app.py (new, 16 lines - imports app_monolith)")
print("  - app_monolith.py (original code, 5957 lines)")
print("  - app_original.py (copy of original for git tracking)")
print("  - app.py.backup (safety backup)")
print("  - pages/__init__.py (empty, for future use)")
print("\nThe app should work exactly as before!")
print("\nTest it:")
print("  streamlit run app.py")
print("\nIf it works, we can commit this phase.")
print("If it breaks: git reset --hard HEAD")
print("="*70)
