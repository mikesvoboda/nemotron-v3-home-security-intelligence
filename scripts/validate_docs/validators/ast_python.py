"""Level 2 Validator: Python AST verification using tree-sitter.

This module validates that cited symbols (functions, classes) exist
at the specified lines in Python files.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..config import Citation, CitationStatus, ValidationLevel, ValidationResult

# Try to import tree-sitter
_TREE_SITTER_AVAILABLE = False
_ts_python = None
_PY_LANGUAGE = None

try:
    import tree_sitter_python as ts_python

    _ts_python = ts_python
    _TREE_SITTER_AVAILABLE = True
except ImportError:
    pass


@lru_cache(maxsize=1)
def _get_python_parser() -> object | None:
    """Get a cached Python tree-sitter parser.

    Returns:
        Parser instance or None if tree-sitter is not available
    """
    if not _TREE_SITTER_AVAILABLE or _ts_python is None:
        return None

    try:
        from tree_sitter import Language, Parser

        language = Language(_ts_python.language())
        parser: object = Parser(language)
    except Exception:
        return None
    else:
        return parser


def _find_symbols_at_line(
    tree: object,
    source_bytes: bytes,
    target_line: int,
) -> list[dict[str, str | int]]:
    """Find all symbol definitions at or containing a target line.

    Args:
        tree: Parsed tree-sitter tree
        source_bytes: Source code as bytes
        target_line: Target line number (0-indexed)

    Returns:
        List of symbol info dicts with keys: name, type, start_line, end_line
    """
    symbols: list[dict[str, str | int]] = []

    def visit_node(node: object) -> None:
        """Visit a node and check for symbol definitions."""
        # Get node attributes safely
        node_type = getattr(node, "type", "")
        start_point = getattr(node, "start_point", (0, 0))
        end_point = getattr(node, "end_point", (0, 0))

        # Check if this is a symbol definition
        if node_type in ("function_definition", "class_definition", "decorated_definition"):
            start_line = start_point[0]  # 0-indexed
            end_line = end_point[0]

            # Check if target line is within this definition
            if start_line <= target_line <= end_line:
                # Extract symbol name
                name = _extract_symbol_name(node, source_bytes)
                if name:
                    symbols.append(
                        {
                            "name": name,
                            "type": node_type.replace("_definition", ""),
                            "start_line": start_line + 1,  # Convert to 1-indexed
                            "end_line": end_line + 1,
                        }
                    )

        # Visit children
        children = getattr(node, "children", [])
        for child in children:
            visit_node(child)

    root_node = getattr(tree, "root_node", None)
    if root_node:
        visit_node(root_node)

    return symbols


def _extract_symbol_name(node: object, source_bytes: bytes) -> str | None:
    """Extract the name of a symbol from its AST node.

    Args:
        node: tree-sitter node for a definition
        source_bytes: Source code as bytes

    Returns:
        Symbol name or None if not found
    """
    node_type = getattr(node, "type", "")

    # Handle decorated definitions
    if node_type == "decorated_definition":
        children = getattr(node, "children", [])
        for child in children:
            child_type = getattr(child, "type", "")
            if child_type in ("function_definition", "class_definition"):
                return _extract_symbol_name(child, source_bytes)
        return None

    # Look for identifier child that represents the name
    children = getattr(node, "children", [])
    for child in children:
        child_type = getattr(child, "type", "")
        if child_type == "identifier":
            start_byte = getattr(child, "start_byte", 0)
            end_byte = getattr(child, "end_byte", 0)
            return source_bytes[start_byte:end_byte].decode("utf-8")

    return None


def _find_all_symbols(tree: object, source_bytes: bytes) -> list[dict[str, str | int]]:
    """Find all symbol definitions in a file.

    Args:
        tree: Parsed tree-sitter tree
        source_bytes: Source code as bytes

    Returns:
        List of all symbol info dicts
    """
    symbols: list[dict[str, str | int]] = []

    def visit_node(node: object) -> None:
        """Visit a node and collect symbol definitions."""
        node_type = getattr(node, "type", "")
        start_point = getattr(node, "start_point", (0, 0))
        end_point = getattr(node, "end_point", (0, 0))

        if node_type in ("function_definition", "class_definition", "decorated_definition"):
            name = _extract_symbol_name(node, source_bytes)
            if name:
                symbols.append(
                    {
                        "name": name,
                        "type": node_type.replace("_definition", ""),
                        "start_line": start_point[0] + 1,
                        "end_line": end_point[0] + 1,
                    }
                )

        children = getattr(node, "children", [])
        for child in children:
            visit_node(child)

    root_node = getattr(tree, "root_node", None)
    if root_node:
        visit_node(root_node)

    return symbols


def validate_python_ast(
    citation: Citation,
    project_root: Path,
) -> ValidationResult:
    """Validate Python symbol references using tree-sitter AST.

    This is Level 2 validation. If the citation has a symbol_name,
    verifies that symbol exists at or around the cited lines.

    Args:
        citation: The citation to validate
        project_root: Root directory of the project

    Returns:
        ValidationResult with AST_VERIFY level
    """
    # Check if tree-sitter is available
    parser = _get_python_parser()
    if parser is None:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.WARNING,
            level=ValidationLevel.AST_VERIFY,
            message="AST verification skipped: tree-sitter-python not installed",
            details={"reason": "tree_sitter_not_available"},
        )

    file_path = project_root / citation.file_path

    # File must exist
    if not file_path.exists():
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.AST_VERIFY,
            message="Cannot verify AST: file does not exist",
            details={"file_path": citation.file_path},
        )

    # Check file extension
    if file_path.suffix.lower() not in (".py", ".pyi"):
        return ValidationResult(
            citation=citation,
            status=CitationStatus.WARNING,
            level=ValidationLevel.AST_VERIFY,
            message="AST verification skipped: not a Python file",
            details={"extension": file_path.suffix},
        )

    # Read and parse file
    try:
        source_bytes = file_path.read_bytes()
        parse_method = getattr(parser, "parse", None)
        if parse_method is None:
            raise AttributeError("Parser has no parse method")
        tree = parse_method(source_bytes)
    except Exception as e:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.WARNING,
            level=ValidationLevel.AST_VERIFY,
            message=f"AST verification failed: could not parse file: {e}",
            details={"error": str(e)},
        )

    # If no symbol name specified, just verify we can find symbols at the line
    if not citation.symbol_name:
        target_line = citation.start_line - 1  # Convert to 0-indexed
        symbols = _find_symbols_at_line(tree, source_bytes, target_line)

        if symbols:
            symbol_names = [str(s["name"]) for s in symbols]
            return ValidationResult(
                citation=citation,
                status=CitationStatus.VALID,
                level=ValidationLevel.AST_VERIFY,
                message=f"Found symbols at line {citation.start_line}: {', '.join(symbol_names)}",
                details={"symbols": symbol_names, "symbol_count": len(symbols)},
            )
        else:
            # Not an error - just informational
            return ValidationResult(
                citation=citation,
                status=CitationStatus.VALID,
                level=ValidationLevel.AST_VERIFY,
                message=f"No symbol definitions at line {citation.start_line} (may be code, not definition)",
                details={"line": citation.start_line},
            )

    # Symbol name specified - verify it exists
    all_symbols = _find_all_symbols(tree, source_bytes)
    matching_symbols = [s for s in all_symbols if s["name"] == citation.symbol_name]

    if not matching_symbols:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.AST_VERIFY,
            message=f"Symbol '{citation.symbol_name}' not found in {citation.file_path}",
            details={
                "expected_symbol": citation.symbol_name,
                "available_symbols": [str(s["name"]) for s in all_symbols[:10]],  # First 10
            },
        )

    # Check if any matching symbol is at or near the cited line
    for symbol in matching_symbols:
        symbol_start = int(symbol["start_line"])
        symbol_end = int(symbol["end_line"])

        # Check if cited line is within symbol definition
        if symbol_start <= citation.start_line <= symbol_end:
            return ValidationResult(
                citation=citation,
                status=CitationStatus.VALID,
                level=ValidationLevel.AST_VERIFY,
                message=f"Symbol '{citation.symbol_name}' found at lines {symbol_start}-{symbol_end}",
                details={
                    "symbol_name": citation.symbol_name,
                    "symbol_type": str(symbol["type"]),
                    "symbol_start": symbol_start,
                    "symbol_end": symbol_end,
                },
            )

    # Symbol exists but not at the cited line
    closest_symbol = min(
        matching_symbols, key=lambda s: abs(int(s["start_line"]) - citation.start_line)
    )
    closest_start = int(closest_symbol["start_line"])

    return ValidationResult(
        citation=citation,
        status=CitationStatus.WARNING,
        level=ValidationLevel.AST_VERIFY,
        message=f"Symbol '{citation.symbol_name}' found but at different line (expected ~{citation.start_line}, actual {closest_start})",
        details={
            "expected_line": citation.start_line,
            "actual_line": closest_start,
            "symbol_name": citation.symbol_name,
        },
    )
