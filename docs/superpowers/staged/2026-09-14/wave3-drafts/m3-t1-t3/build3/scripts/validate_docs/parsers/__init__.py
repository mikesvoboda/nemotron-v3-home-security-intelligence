"""Parsers for extracting citations from documentation.

This package provides parsers for different documentation formats:
- markdown.py: Extract citations from markdown prose and frontmatter
- mermaid.py: Extract citations from mermaid diagrams
- code_blocks.py: Extract citations from fenced code blocks
"""

from .code_blocks import extract_code_block_citations
from .markdown import extract_markdown_citations, parse_document
from .mermaid import extract_mermaid_citations

__all__ = [
    "extract_code_block_citations",
    "extract_markdown_citations",
    "extract_mermaid_citations",
    "parse_document",
]
