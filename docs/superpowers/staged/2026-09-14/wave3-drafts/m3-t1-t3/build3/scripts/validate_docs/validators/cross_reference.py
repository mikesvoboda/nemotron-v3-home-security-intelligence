"""Level 4 Validator: Cross-document consistency checking.

This module validates that the same file is cited consistently
across different documentation files, checking for conflicting
information about the same functions/classes.
"""

from __future__ import annotations

from collections import defaultdict

from ..config import Citation, CitationStatus, ValidationLevel, ValidationResult


class CrossReferenceIndex:
    """Index of citations across multiple documents for consistency checking.

    This class maintains an index of all citations found across documents,
    grouped by the cited file. It can then detect inconsistencies like:
    - Same symbol cited at different lines in different docs
    - Conflicting line ranges for the same file
    """

    def __init__(self) -> None:
        """Initialize empty index."""
        # Map: cited_file -> list of (citation, doc_file) tuples
        self._citations_by_file: dict[str, list[tuple[Citation, str]]] = defaultdict(list)

        # Map: (cited_file, symbol_name) -> list of (citation, doc_file) tuples
        self._citations_by_symbol: dict[tuple[str, str], list[tuple[Citation, str]]] = defaultdict(
            list
        )

    def add_citation(self, citation: Citation, doc_file: str) -> None:
        """Add a citation to the index.

        Args:
            citation: The citation to add
            doc_file: Path to the documentation file containing this citation
        """
        self._citations_by_file[citation.file_path].append((citation, doc_file))

        if citation.symbol_name:
            key = (citation.file_path, citation.symbol_name)
            self._citations_by_symbol[key].append((citation, doc_file))

    def add_citations(self, citations: list[Citation], doc_file: str) -> None:
        """Add multiple citations from a document.

        Args:
            citations: List of citations to add
            doc_file: Path to the documentation file
        """
        for citation in citations:
            self.add_citation(citation, doc_file)

    def get_citations_for_file(self, file_path: str) -> list[tuple[Citation, str]]:
        """Get all citations for a specific file.

        Args:
            file_path: Path to the cited file

        Returns:
            List of (citation, doc_file) tuples
        """
        return self._citations_by_file.get(file_path, [])

    def get_citations_for_symbol(
        self, file_path: str, symbol_name: str
    ) -> list[tuple[Citation, str]]:
        """Get all citations for a specific symbol.

        Args:
            file_path: Path to the cited file
            symbol_name: Name of the symbol

        Returns:
            List of (citation, doc_file) tuples
        """
        return self._citations_by_symbol.get((file_path, symbol_name), [])


def _check_line_consistency(
    citations: list[tuple[Citation, str]],
) -> list[dict[str, str | int | list[str]]]:
    """Check if citations to the same file have consistent line references.

    Args:
        citations: List of (citation, doc_file) tuples for the same file

    Returns:
        List of inconsistency dicts with keys: type, message, docs
    """
    inconsistencies: list[dict[str, str | int | list[str]]] = []

    # Group by symbol name (if present)
    by_symbol: dict[str | None, list[tuple[Citation, str]]] = defaultdict(list)
    for citation, doc_file in citations:
        by_symbol[citation.symbol_name].append((citation, doc_file))

    # Check each symbol group
    for symbol_name, symbol_citations in by_symbol.items():
        if symbol_name is None:
            continue

        if len(symbol_citations) < 2:
            continue

        # Check if line numbers are consistent
        line_numbers: dict[int, list[str]] = defaultdict(list)
        for citation, doc_file in symbol_citations:
            line_numbers[citation.start_line].append(doc_file)

        if len(line_numbers) > 1:
            # Different line numbers for same symbol
            lines_info = ", ".join(
                f"line {line} ({', '.join(docs)})" for line, docs in sorted(line_numbers.items())
            )
            inconsistencies.append(
                {
                    "type": "symbol_line_mismatch",
                    "message": f"Symbol '{symbol_name}' cited at different lines: {lines_info}",
                    "symbol": symbol_name,
                    "docs": [doc for _c, doc in symbol_citations],
                }
            )

    return inconsistencies


def validate_cross_references(
    citation: Citation,
    index: CrossReferenceIndex,
    current_doc: str,
) -> ValidationResult:
    """Validate cross-reference consistency for a citation.

    This is Level 4 validation. Checks that this citation is consistent
    with citations to the same file/symbol in other documents.

    Args:
        citation: The citation to validate
        index: CrossReferenceIndex containing all citations
        current_doc: Path to the current documentation file

    Returns:
        ValidationResult with CROSS_REF level
    """
    # Get other citations for the same file
    other_citations = [
        (c, doc)
        for c, doc in index.get_citations_for_file(citation.file_path)
        if doc != current_doc
    ]

    if not other_citations:
        return ValidationResult(
            citation=citation,
            status=CitationStatus.VALID,
            level=ValidationLevel.CROSS_REF,
            message="No cross-references to check (only cited in this document)",
            details={"other_docs": 0},
        )

    # If this citation has a symbol, check symbol-specific consistency
    if citation.symbol_name:
        symbol_citations = index.get_citations_for_symbol(citation.file_path, citation.symbol_name)
        other_symbol_citations = [(c, doc) for c, doc in symbol_citations if doc != current_doc]

        if other_symbol_citations:
            # Check if line numbers match
            for other_citation, other_doc in other_symbol_citations:
                if other_citation.start_line != citation.start_line:
                    return ValidationResult(
                        citation=citation,
                        status=CitationStatus.WARNING,
                        level=ValidationLevel.CROSS_REF,
                        message=f"Inconsistent line number for '{citation.symbol_name}': "
                        f"line {citation.start_line} here vs line {other_citation.start_line} in {other_doc}",
                        details={
                            "symbol": citation.symbol_name,
                            "this_line": citation.start_line,
                            "other_line": other_citation.start_line,
                            "other_doc": other_doc,
                        },
                    )

    # Check general file consistency
    inconsistencies = _check_line_consistency([(citation, current_doc), *other_citations])

    if inconsistencies:
        # Report the first inconsistency involving this citation
        for inc in inconsistencies:
            docs_list = inc.get("docs", [])
            if isinstance(docs_list, list) and current_doc in docs_list:
                # Create a properly typed details dict
                details: dict[str, str | int | float | bool | list[str] | None] = dict(inc.items())
                return ValidationResult(
                    citation=citation,
                    status=CitationStatus.WARNING,
                    level=ValidationLevel.CROSS_REF,
                    message=str(inc["message"]),
                    details=details,
                )

    # All consistent
    other_docs = list({doc for _c, doc in other_citations})
    return ValidationResult(
        citation=citation,
        status=CitationStatus.VALID,
        level=ValidationLevel.CROSS_REF,
        message=f"Consistent with {len(other_docs)} other document(s)",
        details={"other_docs_count": len(other_docs)},
    )
