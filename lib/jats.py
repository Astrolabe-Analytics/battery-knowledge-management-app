"""
Strip JATS/XML markup from Crossref abstract text.

Crossref returns abstracts with JATS XML tags like <jats:p>, <jats:sub>, etc.
This module provides a single function to clean them for storage and display.
"""

import re

# Pre-compiled patterns for performance
_JATS_TITLE_LABELS = re.compile(
    r'<jats:title>\s*(Abstract|Graphic\s+abstract|Graphical\s+abstract)\s*</jats:title>',
    re.IGNORECASE,
)
_JATS_INLINE = [
    (re.compile(r'<jats:sub>(.*?)</jats:sub>', re.I | re.S), r'\1'),
    (re.compile(r'<jats:sup>(.*?)</jats:sup>', re.I | re.S), r'\1'),
    (re.compile(r'<jats:italic>(.*?)</jats:italic>', re.I | re.S), r'\1'),
    (re.compile(r'<jats:bold>(.*?)</jats:bold>', re.I | re.S), r'\1'),
    (re.compile(r'<jats:sc>(.*?)</jats:sc>', re.I | re.S), r'\1'),
    (re.compile(r'<ns4:bold>(.*?)</ns4:bold>', re.I | re.S), r'\1'),
]
_JATS_PARA_OPEN = re.compile(r'<(?:jats|ns4):p>', re.I)
_JATS_PARA_CLOSE = re.compile(r'</(?:jats|ns4):p>', re.I)
_ALL_TAGS = re.compile(r'<[^>]+>')
_MULTI_NEWLINES = re.compile(r'\n{3,}')


def strip_jats(text: str) -> str:
    """Remove JATS/XML markup from abstract text, returning clean plain text."""
    if not text:
        return text

    # Skip if no XML-like tags present (fast path for ~85% of papers)
    if '<' not in text:
        return text

    result = text
    # Remove label-only title sections
    result = _JATS_TITLE_LABELS.sub('', result)
    # Convert inline semantic tags to plain text
    for pattern, repl in _JATS_INLINE:
        result = pattern.sub(repl, result)
    # Convert paragraph tags to newlines
    result = _JATS_PARA_OPEN.sub('\n\n', result)
    result = _JATS_PARA_CLOSE.sub('', result)
    # Strip all remaining tags
    result = _ALL_TAGS.sub('', result)
    # Collapse whitespace
    result = _MULTI_NEWLINES.sub('\n\n', result).strip()
    return result
