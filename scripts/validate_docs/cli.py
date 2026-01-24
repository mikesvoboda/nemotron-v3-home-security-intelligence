"""CLI interface for documentation validation.

This module provides the command-line interface for the validation script.

Usage:
    python -m validate_docs docs/architecture/
    python -m validate_docs docs/architecture/ai-pipeline.md --format json
    python -m validate_docs docs/architecture/ --errors-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import (
    Citation,
    CitationStatus,
    DocumentReport,
    ValidationConfig,
    ValidationLevel,
    ValidationResult,
    supports_ast_verification,
)
from .parsers import (
    extract_code_block_citations,
    extract_markdown_citations,
    extract_mermaid_citations,
)
from .parsers.code_blocks import extract_code_block_content
from .reports import ConsoleReporter, JSONReporter
from .validators import (
    validate_code_match,
    validate_cross_references,
    validate_file_exists,
    validate_line_bounds,
    validate_staleness,
)
from .validators.cross_reference import CrossReferenceIndex

# Import AST validators (may be None if tree-sitter not installed)
try:
    from .validators import validate_python_ast, validate_typescript_ast
except ImportError:
    validate_python_ast = None  # type: ignore[assignment, misc]
    validate_typescript_ast = None  # type: ignore[assignment, misc]


def find_project_root(start_path: Path) -> Path:
    """Find the project root by looking for pyproject.toml or .git.

    Args:
        start_path: Starting path for search

    Returns:
        Project root path

    Raises:
        RuntimeError: If project root cannot be found
    """
    current = start_path.resolve()

    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent

    # Fall back to start path if nothing found
    raise RuntimeError(
        f"Could not find project root (no pyproject.toml or .git) starting from {start_path}"
    )


def collect_documents(path: Path) -> list[Path]:
    """Collect all markdown documents from a path.

    Args:
        path: File or directory path

    Returns:
        List of markdown file paths
    """
    if path.is_file():
        if path.suffix.lower() in (".md", ".markdown"):
            return [path]
        return []

    if path.is_dir():
        return list(path.rglob("*.md"))

    return []


def extract_all_citations(content: str, doc_path: str) -> list[Citation]:
    """Extract all citations from a document using all parsers.

    Args:
        content: Document content
        doc_path: Path to the document

    Returns:
        Deduplicated list of citations
    """
    citations: list[Citation] = []

    # Extract from markdown prose and frontmatter
    citations.extend(extract_markdown_citations(content, doc_path))

    # Extract from mermaid diagrams
    citations.extend(extract_mermaid_citations(content, doc_path))

    # Extract from code blocks
    citations.extend(extract_code_block_citations(content, doc_path))

    # Deduplicate by (file_path, start_line, end_line)
    seen: set[tuple[str, int, int | None]] = set()
    unique_citations: list[Citation] = []

    for citation in citations:
        key = (citation.file_path, citation.start_line, citation.end_line)
        if key not in seen:
            seen.add(key)
            unique_citations.append(citation)

    return unique_citations


def validate_citation(
    citation: Citation,
    config: ValidationConfig,
    content: str,
    cross_ref_index: CrossReferenceIndex,
) -> list[ValidationResult]:
    """Validate a single citation at all enabled levels.

    Args:
        citation: Citation to validate
        config: Validation configuration
        content: Document content (for code block matching)
        cross_ref_index: Cross-reference index for Level 4

    Returns:
        List of validation results (one per level)
    """
    results: list[ValidationResult] = []

    # Level 1a: File exists
    file_result = validate_file_exists(citation, config.project_root)
    results.append(file_result)

    if file_result.status == CitationStatus.ERROR:
        # Can't continue if file doesn't exist
        return results

    # Level 1b: Line bounds
    line_result = validate_line_bounds(citation, config.project_root)
    results.append(line_result)

    if line_result.status == CitationStatus.ERROR:
        # Can't continue if lines are invalid
        return results

    # Level 2: AST verification (if enabled and file type supported)
    if config.enable_ast and supports_ast_verification(citation.file_path):
        suffix = Path(citation.file_path).suffix.lower()

        if suffix in (".py", ".pyi") and validate_python_ast is not None:
            ast_result = validate_python_ast(citation, config.project_root)
            results.append(ast_result)
        elif (
            suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs") and validate_typescript_ast is not None
        ):
            ast_result = validate_typescript_ast(citation, config.project_root)
            results.append(ast_result)

    # Level 3: Code block matching (if enabled)
    if config.enable_code_match:
        documented_code = extract_code_block_content(content, citation)
        if documented_code:
            code_result = validate_code_match(
                citation,
                config.project_root,
                documented_code,
                config.fuzzy_match_threshold,
            )
            results.append(code_result)

    # Level 4: Cross-reference consistency (if enabled)
    if config.enable_cross_ref:
        cross_result = validate_cross_references(
            citation,
            cross_ref_index,
            citation.doc_file,
        )
        results.append(cross_result)

    # Level 5: Staleness detection (if enabled)
    if config.enable_staleness:
        stale_result = validate_staleness(
            citation,
            config.project_root,
            config.staleness_days,
        )
        results.append(stale_result)

    return results


def validate_document(
    doc_path: Path,
    config: ValidationConfig,
    cross_ref_index: CrossReferenceIndex,
) -> DocumentReport:
    """Validate all citations in a document.

    Args:
        doc_path: Path to the documentation file
        config: Validation configuration
        cross_ref_index: Cross-reference index for Level 4

    Returns:
        Document validation report
    """
    report = DocumentReport(doc_path=str(doc_path))

    # Read document content
    try:
        content = doc_path.read_text(encoding="utf-8")
    except OSError as e:
        # Return report with error
        report.results.append(
            ValidationResult(
                citation=Citation(
                    file_path=str(doc_path),
                    start_line=1,
                    doc_file=str(doc_path),
                ),
                status=CitationStatus.ERROR,
                level=ValidationLevel.FILE_EXISTS,
                message=f"Cannot read document: {e}",
            )
        )
        return report

    # Extract citations
    citations = extract_all_citations(content, str(doc_path))
    report.citations = citations

    # Add to cross-reference index
    cross_ref_index.add_citations(citations, str(doc_path))

    # Validate each citation
    for citation in citations:
        results = validate_citation(citation, config, content, cross_ref_index)

        # Only add the most significant result for each citation
        # Priority order: ERROR > STALE > WARNING > VALID
        if results:
            # Find most significant result
            priority_order = [
                CitationStatus.ERROR,
                CitationStatus.STALE,
                CitationStatus.WARNING,
                CitationStatus.VALID,
            ]
            most_significant = min(results, key=lambda r: priority_order.index(r.status))
            report.results.append(most_significant)

    return report


def main(args: list[str] | None = None) -> int:
    """Main entry point for CLI.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 = success, 1 = errors found)
    """
    parser = argparse.ArgumentParser(
        prog="validate_docs",
        description="Validate documentation code citations against the actual codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Validate all docs in a directory
    python -m validate_docs docs/architecture/

    # Validate a single file
    python -m validate_docs docs/architecture/ai-pipeline.md

    # Output as JSON for CI
    python -m validate_docs docs/architecture/ --format json

    # Show only errors and warnings
    python -m validate_docs docs/architecture/ --errors-only

    # Disable AST verification (faster)
    python -m validate_docs docs/architecture/ --no-ast

Validation Levels:
    1. File Exists & Line Bounds - Basic existence checks
    2. AST Verification - tree-sitter symbol verification
    3. Code Block Match - Fenced code content matching
    4. Cross-Reference - Cross-document consistency
    5. Staleness - Git-based staleness detection
        """,
    )

    parser.add_argument(
        "path",
        type=Path,
        help="Path to documentation file or directory",
    )

    parser.add_argument(
        "--format",
        "-f",
        choices=["console", "json"],
        default="console",
        help="Output format (default: console)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file for JSON format (default: stdout)",
    )

    parser.add_argument(
        "--errors-only",
        "-e",
        action="store_true",
        help="Only show errors and warnings",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show additional details",
    )

    parser.add_argument(
        "--no-ast",
        action="store_true",
        help="Disable AST verification (Level 2)",
    )

    parser.add_argument(
        "--no-code-match",
        action="store_true",
        help="Disable code block matching (Level 3)",
    )

    parser.add_argument(
        "--no-cross-ref",
        action="store_true",
        help="Disable cross-reference checking (Level 4)",
    )

    parser.add_argument(
        "--no-staleness",
        action="store_true",
        help="Disable staleness detection (Level 5)",
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root directory (auto-detected if not specified)",
    )

    parsed = parser.parse_args(args)

    # Find project root
    try:
        if parsed.project_root:
            project_root = parsed.project_root.resolve()
        else:
            project_root = find_project_root(parsed.path)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Create configuration
    config = ValidationConfig(
        project_root=project_root,
        enable_ast=not parsed.no_ast,
        enable_code_match=not parsed.no_code_match,
        enable_cross_ref=not parsed.no_cross_ref,
        enable_staleness=not parsed.no_staleness,
    )

    # Collect documents
    doc_path = parsed.path.resolve()
    if not doc_path.exists():
        print(f"Error: Path does not exist: {doc_path}", file=sys.stderr)
        return 1

    documents = collect_documents(doc_path)

    if not documents:
        print(f"Error: No markdown documents found in {doc_path}", file=sys.stderr)
        return 1

    # Create cross-reference index
    cross_ref_index = CrossReferenceIndex()

    # Validate documents
    reports: list[DocumentReport] = []

    # Create reporters
    json_reporter: JSONReporter | None = None
    console_reporter: ConsoleReporter | None = None

    if parsed.format == "json":
        json_reporter = JSONReporter()
    else:
        console_reporter = ConsoleReporter(
            errors_only=parsed.errors_only,
            verbose=parsed.verbose,
        )

    # First pass: extract all citations for cross-reference index
    for doc in documents:
        try:
            content = doc.read_text(encoding="utf-8")
            citations = extract_all_citations(content, str(doc))
            cross_ref_index.add_citations(citations, str(doc))
        except OSError:
            pass  # Will be caught in validation pass

    # Second pass: validate
    for doc in sorted(documents):
        report = validate_document(doc, config, cross_ref_index)

        if report.citations:
            reports.append(report)

            if console_reporter is not None:
                console_reporter.report_document(report)
        elif console_reporter is not None and parsed.verbose:
            console_reporter.print_no_citations(str(doc))

    # Output results
    if json_reporter is not None:
        if parsed.output:
            json_reporter.write_to_file(reports, parsed.output, project_root)
        else:
            json_reporter.write_report(reports, project_root)
    elif console_reporter is not None:
        console_reporter.report_summary(reports)

    # Return exit code
    total_errors = sum(r.error_count for r in reports)
    return 1 if total_errors > 0 else 0
