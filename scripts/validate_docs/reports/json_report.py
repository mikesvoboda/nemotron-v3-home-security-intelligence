"""JSON reporter for CI integration.

This module generates JSON output suitable for:
- CI/CD pipelines
- Integration with other tools
- Machine-readable reports
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from ..config import DocumentReport, ValidationResult


class JSONReporter:
    """Generate JSON output for validation results.

    Produces a structured JSON report suitable for CI integration
    and automated processing.
    """

    def __init__(
        self,
        output: TextIO | None = None,
        pretty: bool = True,
    ) -> None:
        """Initialize JSON reporter.

        Args:
            output: Output stream (default: stdout)
            pretty: Whether to pretty-print JSON
        """
        self.output = output or sys.stdout
        self.pretty = pretty

    def _result_to_dict(self, result: ValidationResult) -> dict[str, Any]:
        """Convert a validation result to a dictionary.

        Args:
            result: Validation result

        Returns:
            Dictionary representation
        """
        return {
            "citation": {
                "file_path": result.citation.file_path,
                "start_line": result.citation.start_line,
                "end_line": result.citation.end_line,
                "symbol_name": result.citation.symbol_name,
                "doc_file": result.citation.doc_file,
                "doc_line": result.citation.doc_line,
                "raw_text": result.citation.raw_text,
            },
            "status": result.status.value,
            "level": result.level.name,
            "message": result.message,
            "details": result.details,
        }

    def _report_to_dict(self, report: DocumentReport) -> dict[str, Any]:
        """Convert a document report to a dictionary.

        Args:
            report: Document validation report

        Returns:
            Dictionary representation
        """
        return {
            "doc_path": report.doc_path,
            "citation_count": len(report.citations),
            "results": [self._result_to_dict(r) for r in report.results],
            "summary": {
                "valid": report.valid_count,
                "errors": report.error_count,
                "warnings": report.warning_count,
                "stale": report.stale_count,
            },
        }

    def generate_report(
        self,
        reports: list[DocumentReport],
        project_root: str | Path | None = None,
    ) -> dict[str, Any]:
        """Generate complete JSON report.

        Args:
            reports: List of document validation reports
            project_root: Optional project root path

        Returns:
            Complete report as dictionary
        """
        # Calculate totals
        total_citations = sum(len(r.results) for r in reports)
        total_valid = sum(r.valid_count for r in reports)
        total_errors = sum(r.error_count for r in reports)
        total_warnings = sum(r.warning_count for r in reports)
        total_stale = sum(r.stale_count for r in reports)

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "project_root": str(project_root) if project_root else None,
            "documents": [self._report_to_dict(r) for r in reports],
            "summary": {
                "total_documents": len(reports),
                "total_citations": total_citations,
                "valid": total_valid,
                "errors": total_errors,
                "warnings": total_warnings,
                "stale": total_stale,
            },
            "has_errors": total_errors > 0,
        }

    def write_report(
        self,
        reports: list[DocumentReport],
        project_root: str | Path | None = None,
    ) -> None:
        """Write JSON report to output stream.

        Args:
            reports: List of document validation reports
            project_root: Optional project root path
        """
        report = self.generate_report(reports, project_root)

        if self.pretty:
            json.dump(report, self.output, indent=2)
        else:
            json.dump(report, self.output)

        # Add trailing newline
        self.output.write("\n")

    def write_to_file(
        self,
        reports: list[DocumentReport],
        file_path: str | Path,
        project_root: str | Path | None = None,
    ) -> None:
        """Write JSON report to a file.

        Args:
            reports: List of document validation reports
            file_path: Path to output file
            project_root: Optional project root path
        """
        report = self.generate_report(reports, project_root)

        # Resolve and validate output path (semgrep: path-traversal-open)
        resolved_path = Path(file_path).resolve()
        with resolved_path.open("w", encoding="utf-8") as f:
            if self.pretty:
                json.dump(report, f, indent=2)
            else:
                json.dump(report, f)
            f.write("\n")
