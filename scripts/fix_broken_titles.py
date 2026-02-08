"""
Fix broken titles in metadata.json that have HTML entities and newlines.
"""
import json
import html
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def clean_title(title: str) -> str:
    """Clean title by removing HTML tags, entities, and excess whitespace."""
    if not title:
        return title

    # Unescape HTML entities (&lt; -> <, &gt; -> >, etc.)
    title = html.unescape(title)

    # Remove HTML tags (including <sub>, <sup>, etc.)
    title = re.sub(r'<[^>]+>', '', title)

    # Remove newlines and excess whitespace
    title = title.replace('\n', ' ')
    title = re.sub(r'\s+', ' ', title)

    return title.strip()

def main():
    print("Fixing broken titles in metadata.json...")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    fixed_count = 0

    for filename, data in metadata.items():
        original_title = data.get('title', '')

        # Check if title has issues (HTML entities, newlines, or tags)
        if ('&lt;' in original_title or '&gt;' in original_title or
            '\n' in original_title or '<' in original_title):

            clean = clean_title(original_title)

            if clean != original_title:
                print(f"\n{filename}:")
                print(f"  OLD: {original_title[:100].encode('ascii', 'replace').decode('ascii')}...")
                print(f"  NEW: {clean.encode('ascii', 'replace').decode('ascii')}")

                data['title'] = clean
                fixed_count += 1

    if fixed_count > 0:
        # Save updated metadata
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"\n" + "=" * 70)
        print(f"Fixed {fixed_count} titles")
        print("Updated metadata.json")
    else:
        print("No titles needed fixing")

if __name__ == "__main__":
    main()
