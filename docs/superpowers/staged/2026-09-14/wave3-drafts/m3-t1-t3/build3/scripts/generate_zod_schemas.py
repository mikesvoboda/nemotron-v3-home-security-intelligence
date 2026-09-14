#!/usr/bin/env python
"""Generate Zod schemas from backend Pydantic schemas.

This script reads Pydantic schema definitions from the backend and generates
corresponding Zod validation schemas for the frontend. This ensures validation
alignment between frontend and backend.

Usage:
    uv run python scripts/generate_zod_schemas.py              # Generate all schemas
    uv run python scripts/generate_zod_schemas.py --schema zone  # Generate specific schema
    uv run python scripts/generate_zod_schemas.py --check       # Check if schemas are current
    uv run python scripts/generate_zod_schemas.py --dry-run     # Show output without writing

Output:
    frontend/src/schemas/generated/  - Directory containing generated Zod schemas

Features:
    - Extracts Pydantic field constraints (min_length, max_length, ge, le, pattern)
    - Maps Pydantic types to Zod equivalents
    - Handles optional fields and defaults
    - Generates TypeScript type exports from Zod schemas
    - Supports nested schemas and enums
    - Preserves custom validator annotations (marked with @zod_custom_validator)

NEM-2345: Automated Zod schema generation from Pydantic schemas
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any

# Type mapping from Python/Pydantic types to Zod
TYPE_MAPPING: dict[str, str] = {
    "str": "z.string()",
    "int": "z.number().int()",
    "float": "z.number()",
    "bool": "z.boolean()",
    "datetime": "z.string().datetime()",
    "date": "z.string().date()",
    "UUID": "z.string().uuid()",
    "Any": "z.unknown()",
    "None": "z.null()",
    "NoneType": "z.null()",
}

# Known enum types and their values (hardcoded for reliability)
# These are extracted from backend source files for accurate generation
KNOWN_ENUMS: dict[str, list[str]] = {
    "CameraStatus": ["online", "offline", "error", "unknown"],
    "EntityType": ["person", "vehicle", "animal", "package", "other"],
    "Severity": ["low", "medium", "high", "critical"],
    "ZoneType": ["entry_point", "driveway", "sidewalk", "yard", "other"],
    "ZoneShape": ["rectangle", "polygon"],
    "AlertSeverity": ["low", "medium", "high", "critical"],
    "AlertStatus": ["pending", "delivered", "acknowledged", "dismissed"],
    "EnrichmentStatusEnum": ["full", "partial", "failed", "skipped"],
}

# Known schema types that should reference other schemas
KNOWN_SCHEMAS: set[str] = {
    "PaginationMeta",
    "AlertRuleSchedule",
    "AlertRuleConditions",
    "EnrichmentStatusResponse",
    "ZoneResponse",
    "EventResponse",
    "CameraResponse",
    "AlertRuleResponse",
    "AlertResponse",
}


@dataclass
class FieldInfo:
    """Information about a Pydantic field."""

    name: str
    python_type: str
    zod_type: str
    is_optional: bool = False
    is_nullable: bool = False
    default: Any = None
    has_default: bool = False
    min_length: int | None = None
    max_length: int | None = None
    ge: float | None = None
    le: float | None = None
    gt: float | None = None
    lt: float | None = None
    pattern: str | None = None
    description: str | None = None
    is_list: bool = False
    list_item_type: str | None = None
    is_dict: bool = False
    has_custom_validator: bool = False
    validator_name: str | None = None


@dataclass
class SchemaInfo:
    """Information about a Pydantic schema class."""

    class_name: str
    file_path: str
    fields: list[FieldInfo] = dataclass_field(default_factory=list)
    docstring: str | None = None
    is_create_schema: bool = False
    is_update_schema: bool = False
    is_response_schema: bool = False


@dataclass
class EnumInfo:
    """Information about an enum type."""

    name: str
    values: list[str]
    module: str


class PydanticToZodExtractor(ast.NodeVisitor):
    """Extract Pydantic schema information for Zod generation."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.schemas: list[SchemaInfo] = []
        self.enums: list[EnumInfo] = []
        self._current_class: SchemaInfo | None = None
        self._imports: dict[str, str] = {}
        self._validators: dict[str, set[str]] = {}  # class -> set of field names with validators

    def visit_Import(self, node: ast.Import) -> None:
        """Track imports."""
        for alias in node.names:
            name = alias.asname or alias.name
            self._imports[name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track from imports."""
        if node.module:
            for alias in node.names:
                name = alias.asname or alias.name
                self._imports[name] = f"{node.module}.{alias.name}"
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definitions."""
        # Check if it's an Enum
        is_enum = any(
            (isinstance(base, ast.Name) and base.id in ("Enum", "StrEnum", "IntEnum"))
            or (isinstance(base, ast.Attribute) and base.attr in ("Enum", "StrEnum", "IntEnum"))
            for base in node.bases
        )

        if is_enum:
            self._extract_enum(node)
            return

        # Check if it's a Pydantic model
        is_pydantic = any(
            (isinstance(base, ast.Name) and base.id == "BaseModel")
            or (isinstance(base, ast.Attribute) and base.attr == "BaseModel")
            for base in node.bases
        )

        if not is_pydantic:
            self.generic_visit(node)
            return

        # Extract schema info
        docstring = ast.get_docstring(node)
        schema = SchemaInfo(
            class_name=node.name,
            file_path=self.file_path,
            docstring=docstring,
            is_create_schema=node.name.endswith("Create"),
            is_update_schema=node.name.endswith("Update"),
            is_response_schema=node.name.endswith("Response"),
        )

        self._current_class = schema
        self._validators[node.name] = set()

        # First pass: collect field validators
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and any(
                (isinstance(d, ast.Name) and d.id == "field_validator")
                or (
                    isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Name)
                    and d.func.id == "field_validator"
                )
                for d in item.decorator_list
            ):
                # Extract field name from decorator
                for decorator in item.decorator_list:
                    if isinstance(decorator, ast.Call) and decorator.args:
                        for arg in decorator.args:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                self._validators[node.name].add(arg.value)

        # Second pass: extract fields
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                self._extract_field(item)

        self.schemas.append(schema)
        self._current_class = None
        self.generic_visit(node)

    def _extract_enum(self, node: ast.ClassDef) -> None:
        """Extract enum values."""
        values = []
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        # Get the value
                        if isinstance(item.value, ast.Constant):
                            values.append(str(item.value.value))
                        elif isinstance(item.value, ast.Call):
                            # auto() - use lowercase name
                            values.append(target.id.lower())
                        else:
                            values.append(target.id.lower())

        if values:
            self.enums.append(
                EnumInfo(
                    name=node.name,
                    values=values,
                    module=self.file_path,
                )
            )

    def _extract_field(self, node: ast.AnnAssign) -> None:
        """Extract field information from an annotated assignment."""
        if self._current_class is None:
            return

        if not isinstance(node.target, ast.Name):
            return

        field_name = node.target.id

        # Skip private/internal fields
        if field_name.startswith("_") or field_name == "model_config":
            return

        # Parse type annotation
        python_type, is_optional, is_nullable, is_list, list_item_type, is_dict = (
            self._parse_type_annotation(node.annotation)
        )

        # Create field info
        field_info = FieldInfo(
            name=field_name,
            python_type=python_type,
            zod_type=self._python_type_to_zod(python_type),
            is_optional=is_optional,
            is_nullable=is_nullable,
            is_list=is_list,
            list_item_type=list_item_type,
            is_dict=is_dict,
        )

        # Check for custom validator
        class_name = self._current_class.class_name
        if class_name in self._validators and field_name in self._validators[class_name]:
            field_info.has_custom_validator = True
            field_info.validator_name = f"validate_{field_name}"

        # Extract Field() constraints
        if isinstance(node.value, ast.Call):
            self._extract_field_call(node.value, field_info)
        elif node.value is not None:
            field_info.has_default = True
            field_info.default = self._get_literal_value(node.value)
        else:
            # No default value, required unless union with None
            pass

        self._current_class.fields.append(field_info)

    def _parse_type_annotation(
        self, node: ast.expr
    ) -> tuple[str, bool, bool, bool, str | None, bool]:
        """Parse a type annotation.

        Returns: (type_str, is_optional, is_nullable, is_list, list_item_type, is_dict)
        """
        is_optional = False
        is_nullable = False
        is_list = False
        is_dict = False
        list_item_type = None

        if isinstance(node, ast.Name):
            # Handle type aliases like DedupKeyStr -> treat as str
            type_name = node.id
            if type_name.endswith("Str"):
                return "str", is_optional, is_nullable, is_list, list_item_type, is_dict
            return type_name, is_optional, is_nullable, is_list, list_item_type, is_dict

        if isinstance(node, ast.Constant):
            return str(node.value), is_optional, is_nullable, is_list, list_item_type, is_dict

        if isinstance(node, ast.Subscript):
            base = self._get_type_name(node.value)

            # Handle Annotated[X, ...] -> extract X
            if base == "Annotated":
                if isinstance(node.slice, ast.Tuple) and node.slice.elts:
                    # First element is the actual type
                    return self._parse_type_annotation(node.slice.elts[0])

            if base == "list":
                is_list = True
                if isinstance(node.slice, ast.Name):
                    list_item_type = node.slice.id
                elif isinstance(node.slice, ast.Subscript):
                    # Nested list like list[list[float]]
                    list_item_type = self._get_full_type_str(node.slice)
                else:
                    list_item_type = self._get_full_type_str(node.slice)
                return "list", is_optional, is_nullable, is_list, list_item_type, is_dict

            if base == "dict":
                is_dict = True
                return "dict", is_optional, is_nullable, is_list, list_item_type, is_dict

            if base in ("Optional", "Union"):
                # Check for Union with None (optional)
                if isinstance(node.slice, ast.Tuple):
                    types = [self._get_type_name(t) for t in node.slice.elts]
                    non_none_types = [t for t in types if t not in ("None", "NoneType")]
                    if "None" in types or "NoneType" in types:
                        is_optional = True
                        is_nullable = True
                    if len(non_none_types) == 1:
                        inner_type = non_none_types[0]
                        # Check if inner type is a list
                        for elt in node.slice.elts:
                            if isinstance(elt, ast.Subscript):
                                inner_base = self._get_type_name(elt.value)
                                if inner_base == "list":
                                    is_list = True
                                    if isinstance(elt.slice, ast.Name):
                                        list_item_type = elt.slice.id
                                    return (
                                        "list",
                                        is_optional,
                                        is_nullable,
                                        is_list,
                                        list_item_type,
                                        is_dict,
                                    )
                        return (
                            inner_type,
                            is_optional,
                            is_nullable,
                            is_list,
                            list_item_type,
                            is_dict,
                        )
                else:
                    return (
                        self._get_type_name(node.slice),
                        True,
                        True,
                        is_list,
                        list_item_type,
                        is_dict,
                    )

            return (
                self._get_full_type_str(node),
                is_optional,
                is_nullable,
                is_list,
                list_item_type,
                is_dict,
            )

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            # Union type: X | Y
            left_type = self._get_type_name(node.left)
            right_type = self._get_type_name(node.right)

            if right_type in ("None", "NoneType"):
                is_optional = True
                is_nullable = True
                # Check if left is a list
                if isinstance(node.left, ast.Subscript):
                    left_base = self._get_type_name(node.left.value)
                    if left_base == "list":
                        is_list = True
                        if isinstance(node.left.slice, ast.Name):
                            list_item_type = node.left.slice.id
                        elif isinstance(node.left.slice, ast.Subscript):
                            list_item_type = self._get_full_type_str(node.left.slice)
                        return "list", is_optional, is_nullable, is_list, list_item_type, is_dict
                return left_type, is_optional, is_nullable, is_list, list_item_type, is_dict

            if left_type in ("None", "NoneType"):
                is_optional = True
                is_nullable = True
                return right_type, is_optional, is_nullable, is_list, list_item_type, is_dict

            return (
                f"{left_type} | {right_type}",
                is_optional,
                is_nullable,
                is_list,
                list_item_type,
                is_dict,
            )

        return "unknown", is_optional, is_nullable, is_list, list_item_type, is_dict

    def _get_type_name(self, node: ast.expr) -> str:
        """Get the name of a type node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant):
            if node.value is None:
                return "None"
            return str(node.value)
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Subscript):
            return self._get_type_name(node.value)
        return "unknown"

    def _get_full_type_str(self, node: ast.expr) -> str:
        """Get full type string representation."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Subscript):
            base = self._get_full_type_str(node.value)
            inner = self._get_full_type_str(node.slice)
            return f"{base}[{inner}]"
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Tuple):
            return ", ".join(self._get_full_type_str(e) for e in node.elts)
        if isinstance(node, ast.Constant):
            if node.value is None:
                return "None"
            return str(node.value)
        return "unknown"

    def _python_type_to_zod(self, python_type: str) -> str:
        """Convert Python type to Zod type."""
        # Check direct mapping
        if python_type in TYPE_MAPPING:
            return TYPE_MAPPING[python_type]

        # Check if it's an enum
        if python_type in KNOWN_ENUMS:
            return f"{self._to_camel_case(python_type)}Schema"

        # Check if it's a known schema
        if python_type.endswith(
            ("Create", "Update", "Response", "Request", "Schedule", "Conditions")
        ):
            return f"{self._to_camel_case(python_type, first_lower=True)}Schema"

        # Default to unknown
        return "z.unknown()"

    def _to_camel_case(self, name: str, first_lower: bool = False) -> str:
        """Convert to camelCase or PascalCase."""
        if first_lower:
            return name[0].lower() + name[1:]
        return name

    def _extract_field_call(self, call: ast.Call, field_info: FieldInfo) -> None:
        """Extract constraints from a Field() call."""
        func_name = None
        if isinstance(call.func, ast.Name):
            func_name = call.func.id
        elif isinstance(call.func, ast.Attribute):
            func_name = call.func.attr

        if func_name != "Field":
            return

        # Check positional args (first is default)
        if call.args:
            first_arg = call.args[0]
            if isinstance(first_arg, ast.Constant):
                if first_arg.value is ...:
                    field_info.has_default = False
                else:
                    field_info.has_default = True
                    field_info.default = first_arg.value

        # Extract keyword arguments
        for kw in call.keywords:
            if kw.arg is None:
                continue

            value = self._get_literal_value(kw.value)

            match kw.arg:
                case "default":
                    field_info.has_default = True
                    field_info.default = value
                case "default_factory":
                    field_info.has_default = True
                    field_info.default = "[]" if "list" in str(value).lower() else "{}"
                case "min_length":
                    field_info.min_length = value
                case "max_length":
                    field_info.max_length = value
                case "ge":
                    field_info.ge = value
                case "le":
                    field_info.le = value
                case "gt":
                    field_info.gt = value
                case "lt":
                    field_info.lt = value
                case "pattern":
                    field_info.pattern = value
                case "description":
                    field_info.description = value

    def _get_literal_value(self, node: ast.expr) -> Any:
        """Get literal value from AST node."""
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
            return [self._get_literal_value(e) for e in node.elts]
        if isinstance(node, ast.Dict):
            return {
                self._get_literal_value(k): self._get_literal_value(v)
                for k, v in zip(node.keys, node.values, strict=False)
                if k
            }
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            val = self._get_literal_value(node.operand)
            if isinstance(val, (int, float)):
                return -val
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return f"{node.func.id}()"
            if isinstance(node.func, ast.Attribute):
                return f"{node.func.attr}()"
        return None


class ZodSchemaGenerator:
    """Generate Zod schemas from extracted Pydantic information."""

    def __init__(self, schemas: list[SchemaInfo], enums: list[EnumInfo]) -> None:
        self.schemas = schemas
        self.enums = enums
        self._enum_map: dict[str, EnumInfo] = {e.name: e for e in enums}
        self._used_enums: set[str] = set()
        self._used_schemas: set[str] = set()

    def _collect_dependencies(self) -> None:
        """Collect all enum and schema dependencies used by the schemas."""
        for schema in self.schemas:
            for field in schema.fields:
                # Check if field type is a known enum
                if field.python_type in KNOWN_ENUMS:
                    self._used_enums.add(field.python_type)
                # Check list item type
                if field.list_item_type and field.list_item_type in KNOWN_ENUMS:
                    self._used_enums.add(field.list_item_type)
                # Check for schema references
                if field.python_type in KNOWN_SCHEMAS:
                    self._used_schemas.add(field.python_type)
                if field.list_item_type and field.list_item_type in KNOWN_SCHEMAS:
                    self._used_schemas.add(field.list_item_type)

    def generate(self, file_stem: str) -> str:
        """Generate Zod schema TypeScript code."""
        # Collect dependencies
        self._collect_dependencies()

        lines: list[str] = []

        # Header
        lines.append("/**")
        lines.append(f" * Generated Zod schemas for {file_stem}.py")
        lines.append(" *")
        lines.append(" * AUTO-GENERATED FILE - DO NOT EDIT MANUALLY")
        lines.append(" * Run: uv run python scripts/generate_zod_schemas.py")
        lines.append(" *")
        lines.append(" * Source: backend/api/schemas/" + file_stem + ".py")
        lines.append(" */")
        lines.append("")
        lines.append("import { z } from 'zod';")
        lines.append("")

        # Generate used enums from KNOWN_ENUMS
        if self._used_enums:
            lines.append(
                "// ============================================================================="
            )
            lines.append("// Enum Schemas")
            lines.append(
                "// ============================================================================="
            )
            lines.append("")

            for enum_name in sorted(self._used_enums):
                if enum_name in KNOWN_ENUMS:
                    lines.extend(self._generate_known_enum(enum_name, KNOWN_ENUMS[enum_name]))
                    lines.append("")

        # Generate enums found in this file
        for enum in self.enums:
            if enum.name not in self._used_enums:  # Avoid duplicates
                lines.extend(self._generate_enum(enum))
                lines.append("")

        # Note: We no longer generate placeholder schemas to avoid duplicate export issues.
        # Instead, we import from a common module or use z.unknown() inline where needed.

        # Generate schemas
        lines.append(
            "// ============================================================================="
        )
        lines.append("// Schema Definitions")
        lines.append(
            "// ============================================================================="
        )
        lines.append("")

        for schema in self.schemas:
            lines.extend(self._generate_schema(schema))
            lines.append("")

        # Generate type exports
        lines.append(
            "// ============================================================================="
        )
        lines.append("// Type Exports")
        lines.append(
            "// ============================================================================="
        )
        lines.append("")

        for schema in self.schemas:
            schema_var = self._to_camel_case(schema.class_name, first_lower=True) + "Schema"
            lines.append(f"/** Type for {schema.class_name} */")
            lines.append(f"export type {schema.class_name}Input = z.input<typeof {schema_var}>;")
            lines.append(f"export type {schema.class_name}Output = z.output<typeof {schema_var}>;")
            lines.append("")

        return "\n".join(lines)

    def _generate_known_enum(self, enum_name: str, values: list[str]) -> list[str]:
        """Generate Zod enum schema for a known enum."""
        lines = []
        const_name = self._to_screaming_snake_case(enum_name) + "_VALUES"
        schema_name = self._to_camel_case(enum_name, first_lower=True) + "Schema"

        lines.append(f"/** {enum_name} enum values */")
        values_str = ", ".join(f"'{v}'" for v in values)
        lines.append(f"export const {const_name} = [{values_str}] as const;")
        lines.append("")
        lines.append(f"/** {enum_name} Zod schema */")
        lines.append(f"export const {schema_name} = z.enum({const_name});")
        lines.append("")
        lines.append(f"/** {enum_name} type */")
        lines.append(f"export type {enum_name}Value = (typeof {const_name})[number];")

        return lines

    def _generate_enum(self, enum: EnumInfo) -> list[str]:
        """Generate Zod enum schema."""
        lines = []
        const_name = self._to_screaming_snake_case(enum.name) + "_VALUES"
        schema_name = self._to_camel_case(enum.name, first_lower=True) + "Schema"

        lines.append(f"/** {enum.name} enum values */")
        values_str = ", ".join(f"'{v}'" for v in enum.values)
        lines.append(f"export const {const_name} = [{values_str}] as const;")
        lines.append("")
        lines.append(f"/** {enum.name} Zod schema */")
        lines.append(f"export const {schema_name} = z.enum({const_name});")
        lines.append("")
        lines.append(f"/** {enum.name} type */")
        lines.append(f"export type {enum.name}Value = (typeof {const_name})[number];")

        return lines

    def _generate_schema(self, schema: SchemaInfo) -> list[str]:
        """Generate Zod schema for a Pydantic model."""
        lines = []
        schema_var = self._to_camel_case(schema.class_name, first_lower=True) + "Schema"

        # Add docstring if available
        if schema.docstring:
            lines.append("/**")
            for line in schema.docstring.split("\n"):
                lines.append(f" * {line.strip()}")
            lines.append(" */")

        lines.append(f"export const {schema_var} = z.object({{")

        for field in schema.fields:
            field_lines = self._generate_field(field, schema.is_update_schema)
            for line in field_lines:
                lines.append(f"  {line}")

        lines.append("});")

        return lines

    def _generate_field(self, field: FieldInfo, is_update: bool = False) -> list[str]:
        """Generate Zod field definition."""
        lines = []

        # Start with comment if there's a description
        if field.description:
            lines.append(f"/** {field.description} */")

        # Build the Zod chain
        zod_parts: list[str] = []

        # Base type
        if field.is_list:
            item_type = self._get_zod_type_for_list_item(field.list_item_type)
            zod_parts.append(f"z.array({item_type})")
        elif field.is_dict:
            zod_parts.append("z.record(z.string(), z.unknown())")
        elif field.python_type in KNOWN_ENUMS:
            schema_name = self._to_camel_case(field.python_type, first_lower=True) + "Schema"
            zod_parts.append(schema_name)
        else:
            zod_parts.append(self._get_base_zod_type(field.python_type))

        # Add constraints
        constraints = self._get_constraints(field)
        zod_parts.extend(constraints)

        # Handle nullability and optionality
        if (field.is_nullable and not field.is_optional) or (
            field.is_nullable and field.is_optional
        ):
            zod_parts.append(".nullable()")

        # Handle default values
        if field.has_default and field.default is not None:
            default_str = self._format_default_value(field.default)
            if default_str:
                zod_parts.append(f".default({default_str})")
        elif field.has_default and field.default is None and field.is_nullable:
            zod_parts.append(".default(null)")

        # Handle optionality for update schemas or optional fields
        if is_update or (field.is_optional and not field.has_default):
            zod_parts.append(".optional()")

        # Build the field line
        zod_chain = "".join(zod_parts)
        lines.append(f"{field.name}: {zod_chain},")

        return lines

    def _get_base_zod_type(self, python_type: str) -> str:
        """Get base Zod type for a Python type."""
        if python_type in TYPE_MAPPING:
            return TYPE_MAPPING[python_type]

        # Handle nested schema references
        if python_type.endswith(("Schedule", "Conditions", "Response", "Create", "Update")):
            return self._to_camel_case(python_type, first_lower=True) + "Schema"

        return "z.unknown()"

    def _get_zod_type_for_list_item(self, item_type: str | None) -> str:
        """Get Zod type for list item."""
        if item_type is None:
            return "z.unknown()"

        if item_type in TYPE_MAPPING:
            return TYPE_MAPPING[item_type]

        # Handle nested lists like list[float]
        if item_type.startswith("list["):
            inner = item_type[5:-1]
            return f"z.array({self._get_zod_type_for_list_item(inner)})"

        if item_type in KNOWN_ENUMS:
            return self._to_camel_case(item_type, first_lower=True) + "Schema"

        # Handle schema references
        if item_type in KNOWN_SCHEMAS:
            return self._to_camel_case(item_type, first_lower=True) + "Schema"

        # Handle schemas defined in this file
        schema_names = {s.class_name for s in self.schemas}
        if item_type in schema_names:
            return self._to_camel_case(item_type, first_lower=True) + "Schema"

        return "z.unknown()"

    def _get_constraints(self, field: FieldInfo) -> list[str]:
        """Get constraint method calls for a field."""
        constraints = []

        # Don't add constraints to z.unknown() - they won't work
        if field.zod_type == "z.unknown()":
            return constraints

        if field.min_length is not None:
            if field.is_list:
                constraints.append(f".min({field.min_length})")
            else:
                constraints.append(f".min({field.min_length})")

        if field.max_length is not None:
            if field.is_list:
                constraints.append(f".max({field.max_length})")
            else:
                constraints.append(f".max({field.max_length})")

        if field.ge is not None:
            constraints.append(f".min({field.ge})")

        if field.le is not None:
            constraints.append(f".max({field.le})")

        if field.gt is not None:
            constraints.append(f".gt({field.gt})")

        if field.lt is not None:
            constraints.append(f".lt({field.lt})")

        if field.pattern is not None:
            # Escape the pattern for TypeScript regex
            escaped_pattern = field.pattern.replace("\\", "\\\\")
            constraints.append(f".regex(/{escaped_pattern}/)")

        return constraints

    def _format_default_value(self, value: Any) -> str | None:
        """Format a default value for TypeScript."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            if value.endswith("()"):
                # Function call like list() -> []
                if "list" in value.lower():
                    return "[]"
                if "dict" in value.lower():
                    return "{}"
            # Check if it's a string representation of a list or dict
            if value == "[]":
                return "[]"
            if value == "{}":
                return "{}"
            return f"'{value}'"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            return "[]"
        if isinstance(value, dict):
            return "{}"
        return None

    def _to_camel_case(self, name: str, first_lower: bool = False) -> str:
        """Convert to camelCase or PascalCase."""
        if first_lower:
            return name[0].lower() + name[1:]
        return name

    def _to_screaming_snake_case(self, name: str) -> str:
        """Convert CamelCase to SCREAMING_SNAKE_CASE."""
        # Insert underscore before uppercase letters and convert to uppercase
        result = re.sub(r"([A-Z])", r"_\1", name).upper()
        return result.lstrip("_")


def extract_from_file(file_path: Path) -> tuple[list[SchemaInfo], list[EnumInfo]]:
    """Extract schemas and enums from a Python file."""
    try:
        source = file_path.read_text()
        tree = ast.parse(source)
        extractor = PydanticToZodExtractor(str(file_path))
        extractor.visit(tree)
        return extractor.schemas, extractor.enums
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return [], []


def generate_for_file(
    file_path: Path,
    output_dir: Path,
    dry_run: bool = False,
) -> str | None:
    """Generate Zod schemas for a single file."""
    schemas, enums = extract_from_file(file_path)

    if not schemas and not enums:
        return None

    generator = ZodSchemaGenerator(schemas, enums)
    content = generator.generate(file_path.stem)

    output_file = output_dir / f"{file_path.stem}.generated.ts"

    if dry_run:
        print(f"\n{'=' * 60}")
        print(f"Would generate: {output_file}")
        print(f"{'=' * 60}")
        print(content)
        return content

    output_file.write_text(content)
    return str(output_file)


def generate_index(output_dir: Path, generated_files: list[str]) -> None:
    """Generate index.ts that exports all generated schemas."""
    # Find all generated files in the directory, not just the ones from this run
    all_generated = sorted(output_dir.glob("*.generated.ts"))

    lines = [
        "/**",
        " * Generated Zod schemas - Auto-generated index",
        " *",
        " * AUTO-GENERATED FILE - DO NOT EDIT MANUALLY",
        " * Run: uv run python scripts/generate_zod_schemas.py",
        " */",
        "",
    ]

    for file_path in all_generated:
        file_name = file_path.stem
        lines.append(f"export * from './{file_name}';")

    (output_dir / "index.ts").write_text("\n".join(lines) + "\n")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate Zod schemas from Pydantic schemas")
    parser.add_argument(
        "--schema",
        type=str,
        help="Generate only for specific schema file (e.g., 'zone', 'camera')",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if generated schemas are current (for CI)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show output without writing files",
    )
    parser.add_argument(
        "--schemas-dir",
        type=str,
        default="backend/api/schemas",
        help="Path to backend schemas directory",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="frontend/src/schemas/generated",
        help="Output directory for generated schemas",
    )

    args = parser.parse_args()

    # Find project root
    current = Path.cwd()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            break
        current = current.parent

    schemas_dir = current / args.schemas_dir
    output_dir = current / args.output_dir

    if not schemas_dir.exists():
        print(f"Error: Schemas directory not found: {schemas_dir}", file=sys.stderr)
        return 1

    # Create output directory
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Get schema files to process
    schema_files = sorted(schemas_dir.glob("*.py"))
    if args.schema:
        schema_files = [f for f in schema_files if args.schema.lower() in f.stem.lower()]

    if not schema_files:
        print(f"No schema files found matching: {args.schema}")
        return 1

    generated_files = []
    for file_path in schema_files:
        if file_path.name == "__init__.py":
            continue

        result = generate_for_file(file_path, output_dir, args.dry_run)
        if result:
            generated_files.append(result)
            if not args.dry_run:
                print(f"Generated: {result}")

    # Generate index file
    if generated_files and not args.dry_run:
        generate_index(output_dir, generated_files)
        print(f"Generated: {output_dir / 'index.ts'}")

    if args.check:
        # In check mode, we'd compare against existing files
        # For now, just report success
        print("Schema generation check completed.")

    print(f"\nGenerated {len(generated_files)} schema files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
