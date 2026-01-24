"""Console reporter using rich for colorful terminal output.

This module provides a beautiful console output with:
- Color-coded status indicators
- Progress bars during validation
- Summary tables
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from ..config import CitationStatus, DocumentReport, ValidationResult

if TYPE_CHECKING:
    from rich.console import Console

# Try to import rich for colorful output
_RICH_AVAILABLE = False
try:
    from rich.console import Console as RichConsole
    from rich.panel import Panel
    from rich.text import Text

    _RICH_AVAILABLE = True
except ImportError:
    RichConsole = None  # type: ignore[assignment, misc]


class ConsoleReporter:
    """Generate colorful console output for validation results.

    Uses the rich library for beautiful terminal output when available,
    falls back to plain text otherwise.
    """

    console: Console | None  # type: ignore[type-arg]

    def __init__(
        self,
        output: TextIO | None = None,
        errors_only: bool = False,
        verbose: bool = False,
    ) -> None:
        """Initialize console reporter.

        Args:
            output: Output stream (default: stdout)
            errors_only: Only show errors and warnings
            verbose: Show additional details
        """
        self.output = output or sys.stdout
        self.errors_only = errors_only
        self.verbose = verbose

        if _RICH_AVAILABLE and RichConsole is not None:
            self.console = RichConsole(file=self.output, force_terminal=True)
        else:
            self.console = None

    def _status_icon(self, status: CitationStatus) -> str:
        """Get status icon for a citation status.

        Args:
            status: Citation status

        Returns:
            Unicode icon string
        """
        icons = {
            CitationStatus.VALID: "[green]OK[/green]" if _RICH_AVAILABLE else "OK",
            CitationStatus.ERROR: "[red]ERR[/red]" if _RICH_AVAILABLE else "ERR",
            CitationStatus.WARNING: "[yellow]WARN[/yellow]" if _RICH_AVAILABLE else "WARN",
            CitationStatus.STALE: "[yellow]STALE[/yellow]" if _RICH_AVAILABLE else "STALE",
        }
        return icons.get(status, "?")

    def _format_result_plain(self, result: ValidationResult) -> str:
        """Format a validation result as plain text.

        Args:
            result: Validation result

        Returns:
            Formatted string
        """
        icon = self._status_icon(result.status)
        citation_str = str(result.citation)
        line_info = f"{result.citation.line_count} lines" if result.citation.is_range else "1 line"

        return f"  {icon} {citation_str} ({line_info}): {result.message}"

    def _format_result_rich(self, result: ValidationResult) -> str:
        """Format a validation result for rich console.

        Args:
            result: Validation result

        Returns:
            Rich-formatted string
        """
        icon = self._status_icon(result.status)
        citation_str = str(result.citation)
        line_info = f"{result.citation.line_count} lines" if result.citation.is_range else "1 line"

        # Color the citation path
        if result.status == CitationStatus.ERROR:
            citation_colored = f"[red]{citation_str}[/red]"
        elif result.status in {CitationStatus.WARNING, CitationStatus.STALE}:
            citation_colored = f"[yellow]{citation_str}[/yellow]"
        else:
            citation_colored = f"[green]{citation_str}[/green]"

        return f"  {icon} {citation_colored} ({line_info})"

    def report_document(self, report: DocumentReport) -> None:
        """Print validation report for a single document.

        Args:
            report: Document validation report
        """
        doc_name = Path(report.doc_path).name

        if self.console and _RICH_AVAILABLE:
            self.console.print(f"\n[bold]Validating {doc_name}...[/bold]")
        else:
            print(f"\nValidating {doc_name}...", file=self.output)

        # Group results by status for cleaner output
        for result in report.results:
            # Skip valid results if errors_only
            if self.errors_only and result.status == CitationStatus.VALID:
                continue

            if self.console and _RICH_AVAILABLE:
                line = self._format_result_rich(result)
                self.console.print(line)
                if self.verbose and result.message:
                    self.console.print(f"    [dim]{result.message}[/dim]")
            else:
                line = self._format_result_plain(result)
                print(line, file=self.output)
                if self.verbose and result.message:
                    print(f"    {result.message}", file=self.output)

    def report_summary(self, reports: list[DocumentReport]) -> None:
        """Print summary of all validation results.

        Args:
            reports: List of document validation reports
        """
        # Calculate totals
        total_citations = sum(len(r.results) for r in reports)
        total_valid = sum(r.valid_count for r in reports)
        total_errors = sum(r.error_count for r in reports)
        total_warnings = sum(r.warning_count for r in reports)
        total_stale = sum(r.stale_count for r in reports)

        if self.console and _RICH_AVAILABLE:
            # Print separator
            self.console.print("\n" + "-" * 60)

            # Create summary panel
            summary_text = Text()
            summary_text.append(f"SUMMARY: {total_citations} citations checked\n\n", style="bold")
            summary_text.append(f"  OK     {total_valid}\n", style="green")
            summary_text.append(f"  ERR    {total_errors}", style="red")
            if total_errors > 0:
                summary_text.append(" (must fix)\n", style="red")
            else:
                summary_text.append("\n")
            summary_text.append(f"  WARN   {total_warnings}\n", style="yellow")
            summary_text.append(f"  STALE  {total_stale}", style="yellow")
            if total_stale > 0:
                summary_text.append(" (docs need update)\n", style="yellow")
            else:
                summary_text.append("\n")

            self.console.print(Panel(summary_text, title="Validation Summary"))
        else:
            # Plain text summary
            print("\n" + "=" * 60, file=self.output)
            print(f"SUMMARY: {total_citations} citations checked", file=self.output)
            print(f"  OK    {total_valid}", file=self.output)
            print(
                f"  ERR   {total_errors} (must fix)" if total_errors else f"  ERR   {total_errors}",
                file=self.output,
            )
            print(f"  WARN  {total_warnings}", file=self.output)
            print(
                f"  STALE {total_stale} (stale)" if total_stale else f"  STALE {total_stale}",
                file=self.output,
            )
            print("=" * 60, file=self.output)

    def print_no_citations(self, doc_path: str) -> None:
        """Print message when no citations found in a document.

        Args:
            doc_path: Path to the document
        """
        doc_name = Path(doc_path).name
        if self.console and _RICH_AVAILABLE:
            self.console.print(f"[dim]Skipping {doc_name}: no citations found[/dim]")
        else:
            print(f"Skipping {doc_name}: no citations found", file=self.output)
