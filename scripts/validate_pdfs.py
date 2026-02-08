"""
PDF Validation Script
Identifies and removes corrupted/invalid PDFs that are actually HTML error pages,
paywalls, bot protection challenges, etc.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
import fitz  # PyMuPDF

# Paths
BASE_DIR = Path(__file__).parent.parent
PAPERS_DIR = BASE_DIR / "papers"
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
INVALID_DIR = BASE_DIR / "papers_invalid"
MARKDOWN_DIR = BASE_DIR / "papers_markdown"

def validate_pdf(pdf_path: Path) -> Tuple[bool, str]:
    """
    Validate if a file is a real PDF.

    Returns:
        (is_valid, reason)
    """
    # Check file size
    size = pdf_path.stat().st_size
    if size < 1000:  # Less than 1KB is suspicious
        return False, f"Too small ({size} bytes)"

    # Check PDF header
    with open(pdf_path, 'rb') as f:
        header = f.read(5)
        if not header.startswith(b'%PDF-'):
            # Check if it's HTML
            f.seek(0)
            content = f.read(1000).decode('utf-8', errors='ignore')
            if '<html' in content.lower() or '<!doctype' in content.lower():
                return False, "HTML file (paywall/error page)"
            return False, "Invalid PDF header"

    # Try to open with PyMuPDF
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()

        if page_count == 0:
            return False, "0 pages"

        return True, f"Valid ({page_count} pages)"

    except Exception as e:
        return False, f"PyMuPDF error: {str(e)[:50]}"

def main():
    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Create invalid directory
    INVALID_DIR.mkdir(exist_ok=True)

    # Get all PDFs
    pdf_files = sorted(PAPERS_DIR.glob("*.pdf"))

    print(f"Validating {len(pdf_files)} PDFs...\n")

    valid_pdfs = []
    invalid_pdfs = []

    for pdf_path in pdf_files:
        is_valid, reason = validate_pdf(pdf_path)

        if is_valid:
            valid_pdfs.append((pdf_path.name, reason))
        else:
            invalid_pdfs.append((pdf_path.name, reason))

    # Report results
    print(f"Valid PDFs: {len(valid_pdfs)}")
    print(f"Invalid PDFs: {len(invalid_pdfs)}\n")

    if invalid_pdfs:
        print("Invalid PDFs (first 20):")
        for filename, reason in invalid_pdfs[:20]:
            print(f"  {filename}: {reason}")
        if len(invalid_pdfs) > 20:
            print(f"  ... and {len(invalid_pdfs) - 20} more")

        # Ask for confirmation
        print(f"\nMove {len(invalid_pdfs)} invalid PDFs to {INVALID_DIR}? (y/n): ", end="")
        response = input().strip().lower()

        if response == 'y':
            moved_count = 0
            updated_metadata = []

            invalid_filenames = {name for name, _ in invalid_pdfs}

            for filename, reason in invalid_pdfs:
                src = PAPERS_DIR / filename
                dst = INVALID_DIR / filename

                # Move PDF
                shutil.move(str(src), str(dst))

                # Remove associated markdown if exists
                md_file = MARKDOWN_DIR / f"{src.stem}.md"
                if md_file.exists():
                    md_file.unlink()

                moved_count += 1
                print(f"Moved: {filename}")

            # Update metadata.json - mark as metadata-only
            for paper in metadata:
                filename = paper.get('filename', '')
                if filename in invalid_filenames:
                    paper['pdf_status'] = 'metadata_only'
                    paper.pop('pdf_source', None)
                    paper.pop('pdf_downloaded_at', None)
                    print(f"Updated metadata: {filename} -> metadata_only")

            # Save updated metadata
            with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            print(f"\nMoved {moved_count} invalid PDFs to {INVALID_DIR}")
            print(f"Updated metadata.json ({len(invalid_filenames)} papers marked as metadata_only)")
            print(f"\nValid PDFs remaining: {len(valid_pdfs)}")
        else:
            print("Aborted.")
    else:
        print("All PDFs are valid!")

if __name__ == "__main__":
    main()
