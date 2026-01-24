"""Level 2 Validator: TypeScript/JavaScript AST verification using tree-sitter.

This module validates that cited symbols (functions, classes, constants)
exist at the specified lines in TypeScript/JavaScript files.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..config import Citation, CitationStatus, ValidationLevel, ValidationResult

# Try to import tree-sitter
_TREE_SITTER_AVAILABLE = False
_ts_typescript = None

try:
    import tree_sitter_typescript as ts_typescript

    _ts_typescript = ts_typescript
    _TREE_SITTER_AVAILABLE = True
except ImportError:
    pass


@lru_cache(maxsize=2)
def _get_typescript_parser(tsx: bool = False) -> object | None:
    """Get a cached TypeScript/TSX tree-sitter parser.

    Args:
        tsx: If True, return TSX parser; otherwise return TypeScript parser

    Returns:
        Parser instance or None if tree-sitter is not available
    """
    if not _TREE_SITTER_AVAILABLE or _ts_typescript is None:
        return None

    try:
        from tree_sitter import Language, Parser

        if tsx:
            language = Language(_ts_typescript.language_tsx())
        else:
            language = Language(_ts_typescript.language_typescript())

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

    # TypeScript/JavaScript definition node types
    definition_types = {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "variable_declarator",
        "lexical_declaration",
        "export_statement",
        "interface_declaration",
        "type_alias_declaration",
    }

    def visit_node(node: object) -> None:
        """Visit a node and check for symbol definitions."""
        node_type = getattr(node, "type", "")
        start_point = getattr(node, "start_point", (0, 0))
        end_point = getattr(node, "end_point", (0, 0))

        if node_type in definition_types:
            start_line = start_point[0]
            end_line = end_point[0]

            if start_line <= target_line <= end_line:
                name = _extract_symbol_name(node, source_bytes)
                if name:
                    symbols.append(
                        {
                            "name": name,
                            "type": node_type.replace("_declaration", "").replace(
                                "_definition", ""
                            ),
                            "start_line": start_line + 1,
                            "end_line": end_line + 1,
                        }
                    )

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

    # Handle export statements
    if node_type == "export_statement":
        children = getattr(node, "children", [])
        for child in children:
            name = _extract_symbol_name(child, source_bytes)
            if name:
                return name
        return None

    # Handle lexical declarations (const, let, var)
    if node_type == "lexical_declaration":
        children = getattr(node, "children", [])
        for child in children:
            child_type = getattr(child, "type", "")
            if child_type == "variable_declarator":
                return _extract_symbol_name(child, source_bytes)
        return None

    # Look for identifier or property_identifier child
    children = getattr(node, "children", [])
    for child in children:
        child_type = getattr(child, "type", "")
        if child_type in ("identifier", "property_identifier", "type_identifier"):
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

    definition_types = {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "variable_declarator",
        "interface_declaration",
        "type_alias_declaration",
    }

    def visit_node(node: object) -> None:
        """Visit a node and collect symbol definitions."""
        node_type = getattr(node, "type", "")
        start_point = getattr(node, "start_point", (0, 0))
        end_point = getattr(node, "end_point", (0, 0))

        if node_type in definition_types:
            name = _extract_symbol_name(node, source_bytes)
            if name:
                symbols.append(
                    {
                        "name": name,
                        "type": node_type.replace("_declaration", "").replace("_definition", ""),
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


def validate_typescript_ast(
    citation: Citation,
    project_root: Path,
) -> ValidationResult:
    """Validate TypeScript/JavaScript symbol references using tree-sitter AST.

    This is Level 2 validation. If the citation has a symbol_name,
    verifies that symbol exists at or around the cited lines.

    Args:
        citation: The citation to validate
        project_root: Root directory of the project

    Returns:
        ValidationResult with AST_VERIFY level
    """
    file_path = project_root / citation.file_path
    suffix = file_path.suffix.lower()

    # Check if this is a TypeScript/JavaScript file
    if suffix not in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
        return ValidationResult(
            citation=citation,
            status=CitationStatus.WARNING,
            level=ValidationLevel.AST_VERIFY,
            message="AST verification skipped: not a TypeScript/JavaScript file",
            details={"extension": suffix},
        )

    # Get appropriate parser
    is_tsx = suffix in (".tsx", ".jsx")
    parser = _get_typescript_parser(tsx=is_tsx)

    if parser is None:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.WARNING,
            level=ValidationLevel.AST_VERIFY,
            message="AST verification skipped: tree-sitter-typescript not installed",
            details={"reason": "tree_sitter_not_available"},
        )

    # File must exist
    if not file_path.exists():
        return ValidationResult(
            citation=citation,
            status=CitationStatus.ERROR,
            level=ValidationLevel.AST_VERIFY,
            message="Cannot verify AST: file does not exist",
            details={"file_path": citation.file_path},
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
                "available_symbols": [str(s["name"]) for s in all_symbols[:10]],
            },
        )

    # Check if any matching symbol is at or near the cited line
    for symbol in matching_symbols:
        symbol_start = int(symbol["start_line"])
        symbol_end = int(symbol["end_line"])

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
