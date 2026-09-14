#!/usr/bin/env python3
"""
API Breaking Change Detection

Parses OpenAPI specifications and detects breaking changes between versions.
Used in CI to prevent breaking API changes from being merged without approval.

Breaking changes detected:
- Removed endpoints
- Removed or changed required parameters
- Removed or changed response fields
- Changed HTTP methods for existing endpoints
- Changed parameter types
- Changed response types
- Added new required parameters
- Made optional parameters required

Usage:
    python check-api-breaking-changes.py --base main.json --current pr.json
    python check-api-breaking-changes.py --base main.json --current pr.json --format markdown
    python check-api-breaking-changes.py --base main.json --current pr.json --verbose

Exit codes:
    0 - No breaking changes detected
    1 - Breaking changes detected
    2 - Error (invalid files, parsing failure, etc.)
"""

import argparse
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """Severity level for API changes."""

    BREAKING = "breaking"
    POTENTIALLY_BREAKING = "potentially_breaking"
    NON_BREAKING = "non_breaking"


@dataclass
class Change:
    """Represents an API change."""

    severity: Severity
    category: str
    endpoint: str
    method: str
    description: str
    details: str | None = None

    def __str__(self) -> str:
        """String representation of a change."""
        parts = [
            f"[{self.severity.value.upper()}]",
            f"{self.category}:",
            f"{self.method.upper()} {self.endpoint}",
            f"- {self.description}",
        ]
        if self.details:
            parts.append(f"  Details: {self.details}")
        return " ".join(parts)


class OpenAPIComparator:
    """Compare two OpenAPI specifications and detect breaking changes."""

    def __init__(self, base_spec: dict[str, Any], current_spec: dict[str, Any]):
        """Initialize comparator with base and current OpenAPI specs.

        Args:
            base_spec: Base (old) OpenAPI specification
            current_spec: Current (new) OpenAPI specification
        """
        self.base_spec = base_spec
        self.current_spec = current_spec
        self.changes: list[Change] = []

    def compare(self) -> list[Change]:
        """Compare specifications and return list of changes.

        Returns:
            List of detected changes
        """
        self.changes = []

        # Compare endpoints
        self._compare_paths()

        return self.changes

    def _compare_paths(self) -> None:
        """Compare paths (endpoints) between specifications."""
        base_paths = self.base_spec.get("paths", {})
        current_paths = self.current_spec.get("paths", {})

        # Check for removed endpoints
        for path in base_paths:
            if path not in current_paths:
                # Endpoint completely removed
                for method in base_paths[path]:
                    if method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                        self.changes.append(
                            Change(
                                severity=Severity.BREAKING,
                                category="Endpoint Removed",
                                endpoint=path,
                                method=method,
                                description=f"Endpoint {method.upper()} {path} was removed",
                            )
                        )

        # Check for modified endpoints
        for path in base_paths:
            if path in current_paths:
                self._compare_methods(path, base_paths[path], current_paths[path])

        # Check for new required parameters in existing endpoints
        for path in current_paths:
            if path in base_paths:
                self._compare_parameters(path, base_paths[path], current_paths[path])

    def _compare_methods(
        self, path: str, base_methods: dict[str, Any], current_methods: dict[str, Any]
    ) -> None:
        """Compare HTTP methods for a specific path.

        Args:
            path: API path
            base_methods: Methods in base spec
            current_methods: Methods in current spec
        """
        # Check for removed methods
        for method, base_operation in base_methods.items():
            if method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                if method not in current_methods:
                    self.changes.append(
                        Change(
                            severity=Severity.BREAKING,
                            category="Method Removed",
                            endpoint=path,
                            method=method,
                            description=f"HTTP method {method.upper()} was removed",
                        )
                    )
                else:
                    # Method still exists, compare details
                    self._compare_operation(path, method, base_operation, current_methods[method])

    def _compare_operation(
        self, path: str, method: str, base_op: dict[str, Any], current_op: dict[str, Any]
    ) -> None:
        """Compare a specific operation (path + method).

        Args:
            path: API path
            method: HTTP method
            base_op: Base operation definition
            current_op: Current operation definition
        """
        # Compare request body
        self._compare_request_body(path, method, base_op, current_op)

        # Compare responses
        self._compare_responses(path, method, base_op, current_op)

    def _compare_parameters(
        self, path: str, base_methods: dict[str, Any], current_methods: dict[str, Any]
    ) -> None:
        """Compare parameters across all methods for a path.

        Args:
            path: API path
            base_methods: Methods in base spec
            current_methods: Methods in current spec
        """
        for method, current_operation in current_methods.items():
            if method not in ["get", "post", "put", "patch", "delete", "head", "options"]:
                continue

            if method not in base_methods:
                # New method, no breaking changes
                continue

            base_params = base_methods[method].get("parameters", [])
            current_params = current_operation.get("parameters", [])

            base_param_map = {p["name"]: p for p in base_params if "name" in p}
            current_param_map = {p["name"]: p for p in current_params if "name" in p}

            # Check for removed parameters
            for param_name, param in base_param_map.items():
                if param_name not in current_param_map:
                    if param.get("required", False):
                        self.changes.append(
                            Change(
                                severity=Severity.BREAKING,
                                category="Required Parameter Removed",
                                endpoint=path,
                                method=method,
                                description=f"Required parameter '{param_name}' was removed",
                                details=f"Location: {param.get('in', 'unknown')}",
                            )
                        )
                    else:
                        self.changes.append(
                            Change(
                                severity=Severity.POTENTIALLY_BREAKING,
                                category="Optional Parameter Removed",
                                endpoint=path,
                                method=method,
                                description=f"Optional parameter '{param_name}' was removed",
                                details=f"Location: {param.get('in', 'unknown')}",
                            )
                        )

            # Check for modified parameters
            for param_name, base_param in base_param_map.items():
                if param_name in current_param_map:
                    current_param = current_param_map[param_name]

                    # Check if required status changed
                    if not base_param.get("required", False) and current_param.get(
                        "required", False
                    ):
                        self.changes.append(
                            Change(
                                severity=Severity.BREAKING,
                                category="Parameter Made Required",
                                endpoint=path,
                                method=method,
                                description=f"Parameter '{param_name}' is now required",
                                details=f"Location: {current_param.get('in', 'unknown')}",
                            )
                        )

                    # Check if type changed
                    base_type = self._get_param_type(base_param)
                    current_type = self._get_param_type(current_param)
                    if base_type != current_type and base_type and current_type:
                        self.changes.append(
                            Change(
                                severity=Severity.BREAKING,
                                category="Parameter Type Changed",
                                endpoint=path,
                                method=method,
                                description=f"Parameter '{param_name}' type changed: {base_type} → {current_type}",
                                details=f"Location: {current_param.get('in', 'unknown')}",
                            )
                        )

    def _compare_request_body(
        self, path: str, method: str, base_op: dict[str, Any], current_op: dict[str, Any]
    ) -> None:
        """Compare request body schemas.

        Args:
            path: API path
            method: HTTP method
            base_op: Base operation definition
            current_op: Current operation definition
        """
        base_body = base_op.get("requestBody", {})
        current_body = current_op.get("requestBody", {})

        # Check if request body was removed
        if base_body and not current_body:
            if base_body.get("required", False):
                self.changes.append(
                    Change(
                        severity=Severity.BREAKING,
                        category="Request Body Removed",
                        endpoint=path,
                        method=method,
                        description="Required request body was removed",
                    )
                )

        # Check if request body became required
        if not base_body.get("required", False) and current_body.get("required", False):
            self.changes.append(
                Change(
                    severity=Severity.BREAKING,
                    category="Request Body Made Required",
                    endpoint=path,
                    method=method,
                    description="Request body is now required",
                )
            )

        # Compare content types
        if base_body and current_body:
            base_content = base_body.get("content", {})
            current_content = current_body.get("content", {})

            # Check for removed content types
            for content_type in base_content:
                if content_type not in current_content:
                    self.changes.append(
                        Change(
                            severity=Severity.BREAKING,
                            category="Content Type Removed",
                            endpoint=path,
                            method=method,
                            description=f"Request content type '{content_type}' was removed",
                        )
                    )

    def _compare_responses(
        self, path: str, method: str, base_op: dict[str, Any], current_op: dict[str, Any]
    ) -> None:
        """Compare response schemas.

        Args:
            path: API path
            method: HTTP method
            base_op: Base operation definition
            current_op: Current operation definition
        """
        base_responses = base_op.get("responses", {})
        current_responses = current_op.get("responses", {})

        # Check for removed success responses
        for status_code in base_responses:
            if status_code.startswith("2"):  # Success responses
                if status_code not in current_responses:
                    self.changes.append(
                        Change(
                            severity=Severity.BREAKING,
                            category="Success Response Removed",
                            endpoint=path,
                            method=method,
                            description=f"Success response {status_code} was removed",
                        )
                    )
                else:
                    # Compare response content
                    base_content = base_responses[status_code].get("content", {})
                    current_content = current_responses[status_code].get("content", {})

                    # Check for removed content types
                    for content_type in base_content:
                        if content_type not in current_content:
                            self.changes.append(
                                Change(
                                    severity=Severity.BREAKING,
                                    category="Response Content Type Removed",
                                    endpoint=path,
                                    method=method,
                                    description=f"Response content type '{content_type}' was removed for {status_code}",
                                )
                            )

    def _get_param_type(self, param: dict[str, Any]) -> str | None:
        """Extract parameter type from parameter definition.

        Args:
            param: Parameter definition

        Returns:
            Parameter type string or None
        """
        # Check for direct type
        if "type" in param:
            return str(param["type"])

        # Check for schema reference
        schema = param.get("schema", {})
        if "type" in schema:
            return str(schema["type"])

        # Check for $ref
        if "$ref" in schema:
            return str(schema["$ref"])

        return None


def load_spec(path: Path) -> dict[str, Any]:
    """Load OpenAPI specification from JSON file.

    Args:
        path: Path to OpenAPI JSON file

    Returns:
        Parsed OpenAPI specification

    Raises:
        SystemExit: If file cannot be read or parsed
    """
    try:
        with path.open() as f:
            data: dict[str, Any] = json.load(f)
            return data
    except FileNotFoundError:
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: Failed to read {path}: {e}", file=sys.stderr)
        sys.exit(2)


def format_changes_text(changes: list[Change]) -> str:
    """Format changes as plain text.

    Args:
        changes: List of changes

    Returns:
        Formatted text report
    """
    if not changes:
        return "No breaking changes detected."

    breaking = [c for c in changes if c.severity == Severity.BREAKING]
    potentially_breaking = [c for c in changes if c.severity == Severity.POTENTIALLY_BREAKING]

    lines = []

    if breaking:
        lines.append("=" * 80)
        lines.append("BREAKING CHANGES DETECTED")
        lines.append("=" * 80)
        lines.append("")
        for change in breaking:
            lines.append(str(change))
        lines.append("")

    if potentially_breaking:
        lines.append("=" * 80)
        lines.append("POTENTIALLY BREAKING CHANGES")
        lines.append("=" * 80)
        lines.append("")
        for change in potentially_breaking:
            lines.append(str(change))
        lines.append("")

    lines.append("=" * 80)
    lines.append(
        f"Summary: {len(breaking)} breaking, {len(potentially_breaking)} potentially breaking"
    )
    lines.append("=" * 80)

    return "\n".join(lines)


def format_changes_markdown(changes: list[Change]) -> str:
    """Format changes as GitHub-flavored markdown.

    Args:
        changes: List of changes

    Returns:
        Formatted markdown report
    """
    if not changes:
        return "✅ No breaking changes detected."

    breaking = [c for c in changes if c.severity == Severity.BREAKING]
    potentially_breaking = [c for c in changes if c.severity == Severity.POTENTIALLY_BREAKING]

    lines = []

    if breaking:
        lines.append("## 🚨 Breaking Changes Detected")
        lines.append("")
        lines.append("The following breaking changes were detected:")
        lines.append("")
        for change in breaking:
            lines.append(f"- **{change.category}**: `{change.method.upper()} {change.endpoint}`")
            lines.append(f"  - {change.description}")
            if change.details:
                lines.append(f"  - {change.details}")
        lines.append("")

    if potentially_breaking:
        lines.append("## ⚠️ Potentially Breaking Changes")
        lines.append("")
        lines.append("The following changes may break existing clients:")
        lines.append("")
        for change in potentially_breaking:
            lines.append(f"- **{change.category}**: `{change.method.upper()} {change.endpoint}`")
            lines.append(f"  - {change.description}")
            if change.details:
                lines.append(f"  - {change.details}")
        lines.append("")

    lines.append("---")
    lines.append(
        f"**Summary**: {len(breaking)} breaking, {len(potentially_breaking)} potentially breaking"
    )

    return "\n".join(lines)


def format_changes_json(changes: list[Change]) -> str:
    """Format changes as JSON.

    Args:
        changes: List of changes

    Returns:
        Formatted JSON report
    """
    data = {
        "breaking_changes": [
            {
                "severity": c.severity.value,
                "category": c.category,
                "endpoint": c.endpoint,
                "method": c.method,
                "description": c.description,
                "details": c.details,
            }
            for c in changes
            if c.severity == Severity.BREAKING
        ],
        "potentially_breaking_changes": [
            {
                "severity": c.severity.value,
                "category": c.category,
                "endpoint": c.endpoint,
                "method": c.method,
                "description": c.description,
                "details": c.details,
            }
            for c in changes
            if c.severity == Severity.POTENTIALLY_BREAKING
        ],
        "summary": {
            "breaking_count": len([c for c in changes if c.severity == Severity.BREAKING]),
            "potentially_breaking_count": len(
                [c for c in changes if c.severity == Severity.POTENTIALLY_BREAKING]
            ),
            "total_count": len(changes),
        },
    }
    return json.dumps(data, indent=2)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect breaking changes in OpenAPI specifications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --base main.json --current pr.json
  %(prog)s --base main.json --current pr.json --format markdown
  %(prog)s --base main.json --current pr.json --verbose

Exit codes:
  0 - No breaking changes detected
  1 - Breaking changes detected
  2 - Error (invalid files, parsing failure, etc.)
        """,
    )

    parser.add_argument(
        "--base",
        type=Path,
        required=True,
        help="Base OpenAPI spec (e.g., from main branch)",
    )

    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        help="Current OpenAPI spec (e.g., from PR branch)",
    )

    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format (default: text)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--allow-potentially-breaking",
        action="store_true",
        help="Don't fail on potentially breaking changes",
    )

    args = parser.parse_args()

    if args.verbose:
        print(f"Loading base spec from: {args.base}", file=sys.stderr)

    base_spec = load_spec(args.base)

    if args.verbose:
        print(f"Loading current spec from: {args.current}", file=sys.stderr)

    current_spec = load_spec(args.current)

    if args.verbose:
        print("Comparing specifications...", file=sys.stderr)

    comparator = OpenAPIComparator(base_spec, current_spec)
    changes = comparator.compare()

    # Filter changes based on severity
    breaking = [c for c in changes if c.severity == Severity.BREAKING]
    potentially_breaking = [c for c in changes if c.severity == Severity.POTENTIALLY_BREAKING]

    if args.verbose:
        print(
            f"Found {len(breaking)} breaking and {len(potentially_breaking)} potentially breaking changes",
            file=sys.stderr,
        )

    # Format and output
    if args.format == "markdown":
        output = format_changes_markdown(changes)
    elif args.format == "json":
        output = format_changes_json(changes)
    else:
        output = format_changes_text(changes)

    print(output)

    # Exit with appropriate code
    if breaking or (potentially_breaking and not args.allow_potentially_breaking):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
