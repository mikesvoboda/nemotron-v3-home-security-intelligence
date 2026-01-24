"""Validators for checking documentation citations.

This package provides validators for different validation levels:
- file_exists.py: Level 1 - File existence checks
- line_bounds.py: Level 1 - Line number validation
- ast_python.py: Level 2 - Python AST verification with tree-sitter
- ast_typescript.py: Level 2 - TypeScript AST verification
- code_match.py: Level 3 - Code block content matching
- cross_reference.py: Level 4 - Cross-document consistency
- staleness.py: Level 5 - Git-based staleness detection
"""

from .code_match import validate_code_match
from .cross_reference import validate_cross_references
from .file_exists import validate_file_exists
from .line_bounds import validate_line_bounds
from .staleness import validate_staleness

# AST validators are optional (require tree-sitter)
try:
    from .ast_python import validate_python_ast
except ImportError:
    validate_python_ast = None  # type: ignore[assignment, misc]

try:
    from .ast_typescript import validate_typescript_ast
except ImportError:
    validate_typescript_ast = None  # type: ignore[assignment, misc]

__all__ = [
    "validate_code_match",
    "validate_cross_references",
    "validate_file_exists",
    "validate_line_bounds",
    "validate_python_ast",
    "validate_staleness",
    "validate_typescript_ast",
]
