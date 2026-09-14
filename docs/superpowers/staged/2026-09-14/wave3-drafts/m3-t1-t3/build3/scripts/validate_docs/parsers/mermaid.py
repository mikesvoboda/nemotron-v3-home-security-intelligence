"""Extract citations from mermaid diagrams.

This module handles:
- Note annotations in sequence diagrams
- Comments in flowcharts
- Node labels with file references
"""

from __future__ import annotations

import re

from ..config import INLINE_CITATION_PATTERN, MERMAID_REFERENCE_PATTERN, Citation


def _find_mermaid_blocks(content: str) -> list[tuple[str, int]]:
    """Find all mermaid code blocks in markdown content.

    Args:
        content: Markdown content to search

    Returns:
        List of (block_content, start_line) tuples
    """
    blocks: list[tuple[str, int]] = []

    # Match ```mermaid ... ```
    pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

    for match in pattern.finditer(content):
        block_content = match.group(1)
        # Calculate line number
        start_line = content[: match.start()].count("\n") + 1
        blocks.append((block_content, start_line))

    return blocks


def extract_mermaid_citations(content: str, doc_file: str = "") -> list[Citation]:
    """Extract citations from mermaid diagram blocks.

    Handles citations in:
    - Note annotations: Note right of RT: ~30-50ms `backend/services/detector_client.py:45`
    - Comments: %% See `backend/services/batch_aggregator.py:112`
    - Labels: [Detection `backend/models/detection.py:1-50`]

    Args:
        content: Markdown content containing mermaid blocks
        doc_file: Path to the documentation file

    Returns:
        List of Citation objects found in mermaid blocks
    """
    citations: list[Citation] = []
    blocks = _find_mermaid_blocks(content)

    for block_content, block_start_line in blocks:
        # Look for inline citations in backticks
        for match in INLINE_CITATION_PATTERN.finditer(block_content):
            file_path = match.group(1)
            start_line = int(match.group(2))
            end_line = int(match.group(3)) if match.group(3) else None

            # Calculate line number within block
            line_offset = block_content[: match.start()].count("\n")
            doc_line = block_start_line + line_offset

            citations.append(
                Citation(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    symbol_name=None,
                    doc_file=doc_file,
                    doc_line=doc_line,
                    raw_text=match.group(0),
                )
            )

        # Look for Note annotations with references
        for match in MERMAID_REFERENCE_PATTERN.finditer(block_content):
            file_path = match.group(1)
            start_line = int(match.group(2))
            end_line = int(match.group(3)) if match.group(3) else None

            line_offset = block_content[: match.start()].count("\n")
            doc_line = block_start_line + line_offset

            citations.append(
                Citation(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    symbol_name=None,
                    doc_file=doc_file,
                    doc_line=doc_line,
                    raw_text=match.group(0),
                )
            )

    return citations
