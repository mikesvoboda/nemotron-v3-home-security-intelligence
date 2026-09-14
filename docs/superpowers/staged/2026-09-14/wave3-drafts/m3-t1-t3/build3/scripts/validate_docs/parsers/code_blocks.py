"""Extract citations from fenced code blocks.

This module handles:
- Code blocks with # Source: path:lines comments
- Code blocks with source reference in the language tag
"""

from __future__ import annotations

import re

from ..config import CODE_BLOCK_SOURCE_PATTERN, Citation


def _find_code_blocks(content: str) -> list[tuple[str, str, int]]:
    """Find all fenced code blocks in markdown content.

    Args:
        content: Markdown content to search

    Returns:
        List of (language, block_content, start_line) tuples
    """
    blocks: list[tuple[str, str, int]] = []

    # Match ```language ... ``` (excluding mermaid which is handled separately)
    pattern = re.compile(r"```(\w*)\s*\n(.*?)```", re.DOTALL)

    for match in pattern.finditer(content):
        language = match.group(1).lower()
        # Skip mermaid blocks (handled by mermaid parser)
        if language == "mermaid":
            continue

        block_content = match.group(2)
        # Calculate line number (line after the opening ```)
        start_line = content[: match.start()].count("\n") + 2

        blocks.append((language, block_content, start_line))

    return blocks


def extract_code_block_citations(content: str, doc_file: str = "") -> list[Citation]:
    """Extract citations from fenced code blocks.

    Looks for # Source: comments within code blocks that reference
    the original source file and line numbers.

    Example:
        ```python
        # Source: backend/services/file_watcher.py:67-89
        def is_image_file(file_path: str) -> bool:
            ...
        ```

    Args:
        content: Markdown content containing code blocks
        doc_file: Path to the documentation file

    Returns:
        List of Citation objects found in code blocks
    """
    citations: list[Citation] = []
    blocks = _find_code_blocks(content)

    for _language, block_content, block_start_line in blocks:
        # Look for # Source: comments
        for match in CODE_BLOCK_SOURCE_PATTERN.finditer(block_content):
            file_path = match.group(1)
            start_line = int(match.group(2))
            end_line = int(match.group(3)) if match.group(3) else None

            # Calculate line number within block
            line_offset = block_content[: match.start()].count("\n")
            doc_line = block_start_line + line_offset

            # Extract the code content after the Source comment
            # This is used for Level 3 validation (code block matching)
            code_after_source = block_content[match.end() :].strip()

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


def extract_code_block_content(content: str, citation: Citation) -> str | None:
    """Extract the code content from a block that contains a citation.

    This is used for Level 3 validation to compare documented code
    against the actual source file.

    Args:
        content: Full markdown content
        citation: Citation to find the code block for

    Returns:
        Code content from the block (excluding the Source comment), or None
    """
    blocks = _find_code_blocks(content)

    for _language, block_content, _block_start_line in blocks:
        # Check if this block contains the citation
        match = CODE_BLOCK_SOURCE_PATTERN.search(block_content)
        if match:
            # Check if this matches our citation
            file_path = match.group(1)
            start_line = int(match.group(2))

            if file_path == citation.file_path and start_line == citation.start_line:
                # Extract code after the Source comment
                lines = block_content.split("\n")
                code_lines = []
                found_source = False

                for line in lines:
                    if CODE_BLOCK_SOURCE_PATTERN.search(line):
                        found_source = True
                        continue
                    if found_source:
                        code_lines.append(line)

                return "\n".join(code_lines).strip()

    return None
