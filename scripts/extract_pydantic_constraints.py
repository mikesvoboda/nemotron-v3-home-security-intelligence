#!/usr/bin/env python
"""Extract Pydantic field constraints from backend schemas for validation auditing.

This script parses Pydantic schema files and extracts field constraints
(min_length, max_length, ge, le, pattern) to compare with frontend validation.

Usage:
    uv run python scripts/extract_pydantic_constraints.py
    uv run python scripts/extract_pydantic_constraints.py --json
    uv run python scripts/extract_pydantic_constraints.py --schema camera

NEM-1975: Audit form fields vs Pydantic schemas
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any


@dataclass
class FieldConstraint:
    """Represents a Pydantic field's validation constraints."""

    field_name: str
    field_type: str
    min_length: int | None = None
    max_length: int | None = None
    ge: float | None = None  # greater than or equal
    le: float | None = None  # less than or equal
    gt: float | None = None  # greater than
    lt: float | None = None  # less than
    pattern: str | None = None
    default: Any = None
    required: bool = True
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, Any] = {
            "field_name": self.field_name,
            "field_type": self.field_type,
            "required": self.required,
        }
        if self.min_length is not None:
            result["min_length"] = self.min_length
        if self.max_length is not None:
            result["max_length"] = self.max_length
        if self.ge is not None:
            result["ge"] = self.ge
        if self.le is not None:
            result["le"] = self.le
        if self.gt is not None:
            result["gt"] = self.gt
        if self.lt is not None:
            result["lt"] = self.lt
        if self.pattern is not None:
            result["pattern"] = self.pattern
        if self.default is not None:
            result["default"] = self.default
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class SchemaInfo:
    """Represents a Pydantic schema class with its fields."""

    class_name: str
    file_path: str
    fields: list[FieldConstraint] = dataclass_field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "class_name": self.class_name,
            "file_path": self.file_path,
            "fields": [f.to_dict() for f in self.fields],
        }


class PydanticSchemaExtractor(ast.NodeVisitor):
    """AST visitor to extract Pydantic field constraints."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.schemas: list[SchemaInfo] = []
        self._current_class: SchemaInfo | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definitions to find Pydantic models."""
        # Check if class inherits from BaseModel
        is_pydantic = any(
            (isinstance(base, ast.Name) and base.id == "BaseModel")
            or (isinstance(base, ast.Attribute) and base.attr == "BaseModel")
            for base in node.bases
        )

        # Also check for schemas ending in common patterns
        is_schema = node.name.endswith(
            ("Create", "Update", "Response", "Request", "Config", "Schedule", "Conditions")
        )

        if is_pydantic or is_schema:
            self._current_class = SchemaInfo(
                class_name=node.name,
                file_path=self.file_path,
            )
            self.schemas.append(self._current_class)

            # Visit class body to extract fields
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    self._extract_field(item)

        self._current_class = None
        self.generic_visit(node)

    def _extract_field(self, node: ast.AnnAssign) -> None:
        """Extract field constraints from an annotated assignment."""
        if self._current_class is None:
            return

        if not isinstance(node.target, ast.Name):
            return

        field_name = node.target.id

        # Skip private/internal fields
        if field_name.startswith("_") or field_name == "model_config":
            return

        # Get field type
        field_type = self._get_type_string(node.annotation)

        # Check if it has a Field() call with constraints
        constraint = FieldConstraint(
            field_name=field_name,
            field_type=field_type,
        )

        # Check if value is a Field() call
        if isinstance(node.value, ast.Call):
            self._extract_field_constraints(node.value, constraint)
        elif node.value is not None:
            # Has a default value but not Field()
            constraint.required = False
            constraint.default = self._get_value(node.value)
        else:
            # Required field (no default)
            constraint.required = True

        self._current_class.fields.append(constraint)

    def _extract_field_constraints(self, call: ast.Call, constraint: FieldConstraint) -> None:
        """Extract constraints from a Field() call."""
        # Check if it's a Field call
        if (isinstance(call.func, ast.Name) and call.func.id == "Field") or (
            isinstance(call.func, ast.Attribute) and call.func.attr == "Field"
        ):
            pass
        else:
            return

        # Check positional args - first arg is usually default
        if call.args:
            first_arg = call.args[0]
            if isinstance(first_arg, ast.Constant) and first_arg.value is ...:
                constraint.required = True
            else:
                constraint.required = False
                constraint.default = self._get_value(first_arg)

        # Extract keyword arguments
        for keyword in call.keywords:
            if keyword.arg is None:
                continue

            value = self._get_value(keyword.value)

            match keyword.arg:
                case "min_length":
                    constraint.min_length = value
                case "max_length":
                    constraint.max_length = value
                case "ge":
                    constraint.ge = value
                case "le":
                    constraint.le = value
                case "gt":
                    constraint.gt = value
                case "lt":
                    constraint.lt = value
                case "pattern":
                    constraint.pattern = value
                case "default":
                    constraint.required = False
                    constraint.default = value
                case "description":
                    constraint.description = value

    def _get_type_string(self, node: ast.expr) -> str:
        """Convert an AST type annotation to a string."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Subscript):
            base = self._get_type_string(node.value)
            slice_str = self._get_type_string(node.slice)
            return f"{base}[{slice_str}]"
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left = self._get_type_string(node.left)
            right = self._get_type_string(node.right)
            return f"{left} | {right}"
        if isinstance(node, ast.Tuple):
            elements = ", ".join(self._get_type_string(e) for e in node.elts)
            return elements
        if isinstance(node, ast.Attribute):
            return f"{self._get_type_string(node.value)}.{node.attr}"
        if isinstance(node, ast.List):
            elements = ", ".join(self._get_type_string(e) for e in node.elts)
            return f"[{elements}]"
        return "unknown"

    def _get_value(self, node: ast.expr) -> Any:
        """Extract a literal value from an AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "None":
                return None
            if node.id == "True":
                return True
            if node.id == "False":
                return False
            return node.id
        if isinstance(node, ast.List):
            return [self._get_value(e) for e in node.elts]
        if isinstance(node, ast.Dict):
            return {
                self._get_value(k) if k else None: self._get_value(v)
                for k, v in zip(node.keys, node.values, strict=False)
            }
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            val = self._get_value(node.operand)
            if isinstance(val, (int, float)):
                return -val
        if isinstance(node, ast.Call):
            # Return string representation for complex calls
            if isinstance(node.func, ast.Name):
                return f"{node.func.id}(...)"
            if isinstance(node.func, ast.Attribute):
                return f"...{node.func.attr}(...)"
        return None


def extract_schemas_from_file(file_path: Path) -> list[SchemaInfo]:
    """Extract Pydantic schemas from a Python file."""
    try:
        source = file_path.read_text()
        tree = ast.parse(source)
        extractor = PydanticSchemaExtractor(str(file_path))
        extractor.visit(tree)
        return extractor.schemas
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return []


def find_schema_files(schemas_dir: Path) -> list[Path]:
    """Find all Python schema files."""
    return sorted(schemas_dir.glob("*.py"))


def format_table_row(
    field_name: str,
    field_type: str,
    constraints: str,
    required: str,
) -> str:
    """Format a table row for markdown output."""
    return f"| {field_name:20} | {field_type:25} | {constraints:40} | {required:8} |"


def format_constraints(field: FieldConstraint) -> str:
    """Format field constraints as a string."""
    parts: list[str] = []

    if field.min_length is not None:
        parts.append(f"min_length={field.min_length}")
    if field.max_length is not None:
        parts.append(f"max_length={field.max_length}")
    if field.ge is not None:
        parts.append(f"ge={field.ge}")
    if field.le is not None:
        parts.append(f"le={field.le}")
    if field.gt is not None:
        parts.append(f"gt={field.gt}")
    if field.lt is not None:
        parts.append(f"lt={field.lt}")
    if field.pattern is not None:
        parts.append(f"pattern={field.pattern[:20]}...")

    return ", ".join(parts) if parts else "-"


def print_markdown_report(schemas: list[SchemaInfo], schema_filter: str | None) -> None:
    """Print a markdown-formatted report of schema constraints."""
    print("# Pydantic Schema Constraints Report\n")
    print("Auto-generated by `scripts/extract_pydantic_constraints.py`\n")

    # Group by file
    schemas_by_file: dict[str, list[SchemaInfo]] = {}
    for schema in schemas:
        file_name = Path(schema.file_path).stem
        if schema_filter and schema_filter.lower() not in file_name.lower():
            continue
        if file_name not in schemas_by_file:
            schemas_by_file[file_name] = []
        schemas_by_file[file_name].append(schema)

    for file_name, file_schemas in sorted(schemas_by_file.items()):
        print(f"\n## {file_name}.py\n")

        for schema in file_schemas:
            if not schema.fields:
                continue

            print(f"\n### {schema.class_name}\n")
            print("| Field | Type | Constraints | Required |")
            print("|-------|------|-------------|----------|")

            for schema_field in schema.fields:
                constraints_str = format_constraints(schema_field)
                required_str = "Yes" if schema_field.required else "No"
                print(
                    format_table_row(
                        schema_field.field_name,
                        schema_field.field_type[:25],
                        constraints_str[:40],
                        required_str,
                    )
                )


def print_json_report(schemas: list[SchemaInfo], schema_filter: str | None) -> None:
    """Print a JSON report of schema constraints."""
    filtered = schemas
    if schema_filter:
        filtered = [s for s in schemas if schema_filter.lower() in Path(s.file_path).stem.lower()]

    output = [s.to_dict() for s in filtered]
    print(json.dumps(output, indent=2))


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract Pydantic field constraints from backend schemas"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format instead of markdown",
    )
    parser.add_argument(
        "--schema",
        type=str,
        help="Filter to specific schema file (e.g., 'camera', 'zone', 'alerts')",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="backend/api/schemas",
        help="Path to schemas directory",
    )

    args = parser.parse_args()

    # Find project root (look for pyproject.toml)
    current = Path.cwd()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            break
        current = current.parent

    schemas_dir = current / args.dir

    if not schemas_dir.exists():
        print(f"Error: Schemas directory not found: {schemas_dir}", file=sys.stderr)
        sys.exit(1)

    # Extract schemas from all files
    all_schemas: list[SchemaInfo] = []
    for file_path in find_schema_files(schemas_dir):
        if file_path.name == "__init__.py":
            continue
        schemas = extract_schemas_from_file(file_path)
        all_schemas.extend(schemas)

    if args.json:
        print_json_report(all_schemas, args.schema)
    else:
        print_markdown_report(all_schemas, args.schema)


if __name__ == "__main__":
    main()
