"""Documentation validation script for checking code citations.

This package validates architecture documentation by checking code citations
(file:line references) against the actual codebase.

Validation Levels:
1. File Exists & Line Bounds - Basic existence checks
2. AST Verification - tree-sitter based symbol verification
3. Code Block Match - Fenced code block content matching
4. Cross-Reference Consistency - Cross-document consistency
5. Staleness Detection - Git-based staleness checking

Usage:
    python -m validate_docs docs/architecture/
    python -m validate_docs docs/architecture/ai-pipeline.md --format json
"""

__version__ = "0.1.0"
