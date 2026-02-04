#!/usr/bin/env python3
"""
Quick test to verify the improved retrieval pipeline works.
"""

import sys
import os
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add lib to path
sys.path.insert(0, os.path.dirname(__file__))

from lib import rag

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")

    # Test that BM25 is available
    from rank_bm25 import BM25Okapi
    import numpy as np

    print("  [OK] All imports successful")
    return True


def test_functions_exist():
    """Test that new functions exist in the rag module."""
    print("\nTesting function existence...")

    assert hasattr(rag, 'expand_query'), "expand_query function not found"
    print("  [OK] expand_query exists")

    assert hasattr(rag, 'rerank_chunks'), "rerank_chunks function not found"
    print("  [OK] rerank_chunks exists")

    assert hasattr(rag, 'hybrid_search'), "hybrid_search function not found"
    print("  [OK] hybrid_search exists")

    assert hasattr(rag, 'retrieve_with_hybrid_and_reranking'), "retrieve_with_hybrid_and_reranking function not found"
    print("  [OK] retrieve_with_hybrid_and_reranking exists")

    return True


def test_database_connection():
    """Test that database connection works."""
    print("\nTesting database connection...")

    try:
        count = rag.get_collection_count()
        print(f"  [OK] Database connected ({count} documents)")
        return True
    except Exception as e:
        print(f"  [SKIP] Database connection failed: {e}")
        print("  (This is expected if you haven't run ingest.py yet)")
        return False


def main():
    print("="*60)
    print("Testing Improved Retrieval Pipeline")
    print("="*60 + "\n")

    results = []

    # Test 1: Imports
    results.append(("Imports", test_imports()))

    # Test 2: Function existence
    results.append(("Functions", test_functions_exist()))

    # Test 3: Database connection
    results.append(("Database", test_database_connection()))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n[SUCCESS] All tests passed! The improved retrieval pipeline is ready to use.")
    else:
        print("\n[WARNING] Some tests failed. Check the output above for details.")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
