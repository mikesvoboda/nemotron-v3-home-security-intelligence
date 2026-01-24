"""Extract citations from markdown prose and frontmatter.

This module handles:
- YAML frontmatter source_refs parsing
- Inline citations in backticks: `path/file.py:123`
- Function/class name extraction from context
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import (
    INLINE_CITATION_PATTERN,
    SYMBOL_CONTEXT_PATTERN,
    Citation,
)


def _extract_frontmatter(content: str) -> tuple[str, str]:
    """Extract YAML frontmatter from markdown content.

    Args:
        content: Full markdown content

    Returns:
        Tuple of (frontmatter, body) where frontmatter may be empty
    """
    if not content.startswith("---"):
        return "", content

    # Find the closing ---
    end_match = re.search(r"\n---\n", content[3:])
    if not end_match:
        return "", content

    end_pos = end_match.end() + 3
    frontmatter = content[3 : end_pos - 4]  # Strip the --- markers
    body = content[end_pos:]

    return frontmatter, body


def _parse_frontmatter_citations(frontmatter: str, doc_file: str) -> list[Citation]:
    """Parse source_refs from YAML frontmatter.

    Handles formats like:
    - backend/services/file_watcher.py:FileWatcher:34
    - backend/services/file_watcher.py:is_image_file
    - backend/services/file_watcher.py:67

    Args:
        frontmatter: YAML frontmatter content
        doc_file: Path to the documentation file

    Returns:
        List of Citation objects
    """
    citations: list[Citation] = []

    # Find source_refs section
    source_refs_match = re.search(r"source_refs:\s*\n((?:\s+-\s+.+\n?)+)", frontmatter)
    if not source_refs_match:
        return citations

    source_refs_block = source_refs_match.group(1)

    # Parse each reference
    for line_num, raw_line in enumerate(source_refs_block.split("\n"), start=1):
        line = raw_line.strip()
        if not line or not line.startswith("-"):
            continue

        # Extract the reference (after the "- ")
        ref = line[1:].strip()
        if not ref:
            continue

        # Parse the reference: path:symbol:line or path:symbol or path:line
        parts = ref.split(":")
        if len(parts) < 1:
            continue

        file_path = parts[0]
        symbol_name: str | None = None
        line_number: int | None = None

        if len(parts) >= 2:
            # Could be symbol name or line number
            second_part = parts[1]
            if second_part.isdigit():
                line_number = int(second_part)
            else:
                symbol_name = second_part
                # Check for line number in third part
                if len(parts) >= 3 and parts[2].isdigit():
                    line_number = int(parts[2])

        # Create citation with available info
        citations.append(
            Citation(
                file_path=file_path,
                start_line=line_number or 1,  # Default to line 1 if not specified
                end_line=None,
                symbol_name=symbol_name,
                doc_file=doc_file,
                doc_line=line_num,  # Approximate line in frontmatter
                raw_text=ref,
            )
        )

    return citations


def _extract_symbol_from_context(content: str, position: int, window: int = 100) -> str | None:
    """Try to extract a symbol name from the context around a citation.

    Args:
        content: Document content
        position: Position of the citation in the content
        window: Number of characters to look before and after

    Returns:
        Symbol name if found, None otherwise
    """
    start = max(0, position - window)
    end = min(len(content), position + window)
    context = content[start:end]

    # Look for function/class/method mentions
    match = SYMBOL_CONTEXT_PATTERN.search(context)
    if match:
        return match.group(1)

    return None


def extract_markdown_citations(content: str, doc_file: str = "") -> list[Citation]:
    """Extract all citations from markdown content.

    This includes:
    - YAML frontmatter source_refs
    - Inline citations in backticks

    Args:
        content: Markdown content to parse
        doc_file: Path to the documentation file (for error messages)

    Returns:
        List of Citation objects
    """
    citations: list[Citation] = []

    # Parse frontmatter
    frontmatter, body = _extract_frontmatter(content)
    if frontmatter:
        citations.extend(_parse_frontmatter_citations(frontmatter, doc_file))

    # Calculate line number offset for body content
    frontmatter_lines = content.count("\n", 0, len(content) - len(body))

    # Extract inline citations from body
    for match in INLINE_CITATION_PATTERN.finditer(body):
        file_path = match.group(1)
        start_line = int(match.group(2))
        end_line = int(match.group(3)) if match.group(3) else None

        # Calculate line number in original document
        doc_line = body[: match.start()].count("\n") + frontmatter_lines + 1

        # Try to extract symbol name from context
        symbol_name = _extract_symbol_from_context(body, match.start())

        citations.append(
            Citation(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                symbol_name=symbol_name,
                doc_file=doc_file,
                doc_line=doc_line,
                raw_text=match.group(0),
            )
        )

    return citations


def parse_document(doc_path: str | Path) -> tuple[str, list[Citation]]:
    """Parse a documentation file and extract all citations.

    Args:
        doc_path: Path to the documentation file

    Returns:
        Tuple of (content, citations)

    Raises:
        FileNotFoundError: If the document doesn't exist
        OSError: If the document can't be read
    """
    doc_path = Path(doc_path)
    content = doc_path.read_text(encoding="utf-8")
    citations = extract_markdown_citations(content, str(doc_path))
    return content, citations
