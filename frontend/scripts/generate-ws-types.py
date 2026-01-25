#!/usr/bin/env python3
# ruff: noqa: T201 - CLI script, print statements are intentional
"""Generate TypeScript types from backend WebSocket Pydantic schemas.

This script extracts WebSocket message schemas from the backend and generates
corresponding TypeScript types. This ensures the frontend stays in sync with
the backend WebSocket message contracts.

Usage:
    ./scripts/generate-ws-types.py              # Generate types
    ./scripts/generate-ws-types.py --check      # Check if types are current (for CI)

The generated file is placed at:
    frontend/src/types/generated/websocket.ts
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set required environment variables before importing backend modules
import os  # noqa: E402

# fmt: off
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/security")  # pragma: allowlist secret
# fmt: on
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# Import all WebSocket schemas
from backend.api.schemas.websocket import (  # noqa: E402
    RiskLevel,
    WebSocketAlertAcknowledgedMessage,
    WebSocketAlertCreatedMessage,
    WebSocketAlertData,
    WebSocketAlertDismissedMessage,
    WebSocketAlertEventType,
    WebSocketAlertResolvedMessage,
    WebSocketAlertSeverity,
    WebSocketAlertStatus,
    WebSocketAlertUpdatedMessage,
    WebSocketErrorCode,
    WebSocketErrorResponse,
    WebSocketEventData,
    WebSocketEventMessage,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketPingMessage,
    WebSocketPongResponse,
    WebSocketSceneChangeData,
    WebSocketSceneChangeMessage,
    WebSocketServiceStatus,
    WebSocketServiceStatusData,
    WebSocketServiceStatusMessage,
    WebSocketSubscribeMessage,
    WebSocketUnsubscribeMessage,
)
from pydantic import BaseModel  # noqa: E402
from pydantic.fields import FieldInfo  # noqa: E402

# Output file path
OUTPUT_FILE = PROJECT_ROOT / "frontend" / "src" / "types" / "generated" / "websocket.ts"

# Header comment for generated file
HEADER_COMMENT = """/**
 * AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
 *
 * This file is generated from backend Pydantic schemas using:
 *   ./scripts/generate-ws-types.py
 *
 * To regenerate, run:
 *   ./scripts/generate-ws-types.py
 *
 * Source schemas:
 *   backend/api/schemas/websocket.py
 *
 * Generated at: {timestamp}
 *
 * Note: WebSocket messages are not covered by OpenAPI, so we generate these
 * types separately to ensure frontend/backend type synchronization.
 */

"""


def python_type_to_typescript(  # noqa: PLR0911 - type mapping requires many branches
    python_type: Any, field_name: str = ""
) -> str:
    """Convert a Python type annotation to a TypeScript type.

    This function handles the full range of Python type annotations that can appear
    in Pydantic models, converting them to their TypeScript equivalents.
    The high number of branches and return statements is inherent to the type mapping logic.

    Args:
        python_type: Python type annotation
        field_name: Field name for context-specific handling

    Returns:
        TypeScript type string
    """
    # Handle None/NoneType
    if python_type is type(None):
        return "null"

    # Handle string type hints
    if isinstance(python_type, str):
        # Handle forward references
        if python_type == "str":
            return "string"
        if python_type == "int":
            return "number"
        if python_type == "float":
            return "number"
        if python_type == "bool":
            return "boolean"
        return python_type

    # Handle basic types
    if python_type is str:
        return "string"
    if python_type is int:
        return "number"
    if python_type is float:
        return "number"
    if python_type is bool:
        return "boolean"
    if python_type is Any:
        return "unknown"

    # Handle enums
    if isinstance(python_type, type) and issubclass(python_type, Enum):
        # Return union of enum values
        values = [f"'{member.value}'" for member in python_type]
        return " | ".join(values)

    # Handle generic types (List, Dict, Optional, Union, Literal)
    origin = get_origin(python_type)
    args = get_args(python_type)

    if origin is list:
        if args:
            inner_type = python_type_to_typescript(args[0], field_name)
            return f"{inner_type}[]"
        return "unknown[]"

    if origin is dict:
        if args and len(args) >= 2:
            key_type = python_type_to_typescript(args[0], field_name)
            value_type = python_type_to_typescript(args[1], field_name)
            return f"Record<{key_type}, {value_type}>"
        return "Record<string, unknown>"

    # Handle Union types (including Optional which is Union[X, None])
    if origin is type(int | str):  # Python 3.10+ union syntax
        non_none_args = [arg for arg in args if arg is not type(None)]
        has_none = len(non_none_args) < len(args)

        if len(non_none_args) == 1 and has_none:
            # Optional[X] -> X | null
            return f"{python_type_to_typescript(non_none_args[0], field_name)} | null"
        else:
            # Union[X, Y, ...] -> X | Y | ...
            ts_types = [python_type_to_typescript(arg, field_name) for arg in args]
            return " | ".join(ts_types)

    # Try handling as Union from typing module
    try:
        from typing import Union

        if origin is Union:
            non_none_args = [arg for arg in args if arg is not type(None)]
            has_none = len(non_none_args) < len(args)

            if len(non_none_args) == 1 and has_none:
                return f"{python_type_to_typescript(non_none_args[0], field_name)} | null"
            else:
                ts_types = [python_type_to_typescript(arg, field_name) for arg in args]
                return " | ".join(ts_types)
    except ImportError:
        pass

    # Handle Literal types
    try:
        from typing import Literal

        if origin is Literal:
            values = [f"'{arg}'" if isinstance(arg, str) else str(arg) for arg in args]
            return " | ".join(values)
    except ImportError:
        pass

    # Handle Pydantic models
    if isinstance(python_type, type) and issubclass(python_type, BaseModel):
        return python_type.__name__

    # Fallback
    return "unknown"


def get_field_description(field_info: FieldInfo) -> str | None:
    """Extract description from a Pydantic field.

    Args:
        field_info: Pydantic FieldInfo object

    Returns:
        Description string or None
    """
    return field_info.description if hasattr(field_info, "description") else None


def is_field_required(field_info: FieldInfo, field_type: Any) -> bool:
    """Determine if a Pydantic field is required in TypeScript output.

    A field is required (no ? marker) if:
    - It has no default value (is_required() returns True)
    - OR it's a Literal type (which are discriminants and should always be present)
    - OR it has a default that matches the Literal value (default="event" for Literal["event"])

    Args:
        field_info: Pydantic FieldInfo object
        field_type: The field's type annotation

    Returns:
        True if the field should be marked as required in TypeScript
    """
    from typing import Literal, get_origin

    from pydantic_core import PydanticUndefined

    # Check if it's a Literal type (discriminant field) - always required
    origin = get_origin(field_type)
    if origin is Literal:
        return True

    # Check if the field has no default and no default_factory
    has_no_default = field_info.default is PydanticUndefined
    has_no_factory = field_info.default_factory is None

    return has_no_default and has_no_factory


def generate_interface(model: type[BaseModel], indent: int = 0) -> str:
    """Generate TypeScript interface from a Pydantic model.

    Args:
        model: Pydantic model class
        indent: Indentation level

    Returns:
        TypeScript interface definition
    """
    lines: list[str] = []
    indent_str = "  " * indent

    # Get model docstring for JSDoc
    docstring = model.__doc__
    if docstring:
        # Clean up the docstring
        docstring = textwrap.dedent(docstring).strip()
        lines.append(f"{indent_str}/**")
        for line in docstring.split("\n"):
            # Use rstrip() to avoid trailing whitespace on empty lines
            lines.append(f"{indent_str} * {line}".rstrip())
        lines.append(f"{indent_str} */")

    lines.append(f"{indent_str}export interface {model.__name__} {{")

    # Process fields
    for field_name, field_info in model.model_fields.items():
        # Get field type
        field_type = model.model_fields[field_name].annotation
        ts_type = python_type_to_typescript(field_type, field_name)

        # Check if optional (has default value or is Optional type with None)
        is_required = is_field_required(field_info, field_type)

        # Get description for JSDoc
        description = get_field_description(field_info)

        # Add JSDoc comment if description exists
        if description:
            lines.append(f"{indent_str}  /** {description} */")

        # Add field - required fields don't have ? marker
        optional_marker = "" if is_required else "?"
        lines.append(f"{indent_str}  {field_name}{optional_marker}: {ts_type};")

    lines.append(f"{indent_str}}}")
    return "\n".join(lines)


def generate_enum(enum_class: type[Enum], indent: int = 0) -> str:
    """Generate TypeScript type from a Python Enum.

    Args:
        enum_class: Python Enum class
        indent: Indentation level

    Returns:
        TypeScript type definition
    """
    lines: list[str] = []
    indent_str = "  " * indent

    # Get enum docstring for JSDoc
    docstring = enum_class.__doc__
    if docstring:
        docstring = textwrap.dedent(docstring).strip()
        lines.append(f"{indent_str}/**")
        for line in docstring.split("\n"):
            # Use rstrip() to avoid trailing whitespace on empty lines
            lines.append(f"{indent_str} * {line}".rstrip())
        lines.append(f"{indent_str} */")

    # Generate as type union of string literals
    values = [f"'{member.value}'" for member in enum_class]
    lines.append(f"{indent_str}export type {enum_class.__name__} = {' | '.join(values)};")

    return "\n".join(lines)


def generate_error_codes(error_code_class: type) -> str:
    """Generate TypeScript const object from WebSocketErrorCode class.

    Args:
        error_code_class: Class with error code constants

    Returns:
        TypeScript const object definition
    """
    lines: list[str] = []

    # Get class docstring for JSDoc
    docstring = error_code_class.__doc__
    if docstring:
        docstring = textwrap.dedent(docstring).strip()
        lines.append("/**")
        for line in docstring.split("\n"):
            # Use rstrip() to avoid trailing whitespace on empty lines
            lines.append(f" * {line}".rstrip())
        lines.append(" */")

    lines.append("export const WebSocketErrorCode = {")

    # Get all class attributes that are error codes (uppercase, string values)
    for attr_name in dir(error_code_class):
        if attr_name.isupper() and not attr_name.startswith("_"):
            value = getattr(error_code_class, attr_name)
            if isinstance(value, str):
                lines.append(f"  {attr_name}: '{value}',")

    lines.append("} as const;")
    lines.append("")
    lines.append(
        "export type WebSocketErrorCodeType = typeof WebSocketErrorCode[keyof typeof WebSocketErrorCode];"
    )

    return "\n".join(lines)


def generate_type_guards() -> str:
    """Generate TypeScript type guard functions.

    Returns:
        TypeScript type guard function definitions
    """
    return """
// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a value is an object with a type property.
 */
function hasTypeProperty(value: unknown): value is { type: unknown } {
  return typeof value === 'object' && value !== null && 'type' in value;
}

/**
 * Type guard for WebSocketEventMessage.
 */
export function isEventMessage(value: unknown): value is WebSocketEventMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'event') return false;

  const msg = value as { type: 'event'; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return (
    ('id' in data || 'event_id' in data) &&
    'camera_id' in data &&
    'risk_score' in data &&
    'risk_level' in data &&
    'summary' in data
  );
}

/**
 * Type guard for WebSocketServiceStatusMessage.
 */
export function isServiceStatusMessage(value: unknown): value is WebSocketServiceStatusMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'service_status') return false;

  const msg = value as { type: 'service_status'; data?: unknown; timestamp?: unknown };
  if (typeof msg.timestamp !== 'string') return false;
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'service' in data && 'status' in data;
}

/**
 * Type guard for WebSocketSceneChangeMessage.
 */
export function isSceneChangeMessage(value: unknown): value is WebSocketSceneChangeMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'scene_change') return false;

  const msg = value as { type: 'scene_change'; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'id' in data && 'camera_id' in data && 'change_type' in data;
}

/**
 * Type guard for WebSocketPingMessage.
 */
export function isPingMessage(value: unknown): value is WebSocketPingMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'ping';
}

/**
 * Type guard for WebSocketPongResponse.
 */
export function isPongMessage(value: unknown): value is WebSocketPongResponse {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'pong';
}

/**
 * Type guard for WebSocketErrorResponse.
 */
export function isErrorMessage(value: unknown): value is WebSocketErrorResponse {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'error') return false;

  const msg = value as { type: 'error'; message?: unknown };
  return typeof msg.message === 'string';
}

/**
 * Type guard for WebSocketAlertMessage (any alert event type).
 */
export function isAlertMessage(value: unknown): value is WebSocketAlertMessage {
  if (!hasTypeProperty(value)) return false;
  const alertTypes = ['alert_created', 'alert_updated', 'alert_acknowledged', 'alert_dismissed', 'alert_resolved'];
  if (!alertTypes.includes(value.type as string)) return false;

  const msg = value as { type: string; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'id' in data && 'event_id' in data && 'severity' in data && 'status' in data;
}

/**
 * Type guard for WebSocketAlertCreatedMessage.
 */
export function isAlertCreatedMessage(value: unknown): value is WebSocketAlertCreatedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_created' && isAlertMessage(value);
}

/**
 * Type guard for WebSocketAlertUpdatedMessage.
 */
export function isAlertUpdatedMessage(value: unknown): value is WebSocketAlertUpdatedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_updated' && isAlertMessage(value);
}

/**
 * Type guard for WebSocketAlertAcknowledgedMessage.
 */
export function isAlertAcknowledgedMessage(value: unknown): value is WebSocketAlertAcknowledgedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_acknowledged' && isAlertMessage(value);
}

/**
 * Type guard for WebSocketAlertDismissedMessage.
 */
export function isAlertDismissedMessage(value: unknown): value is WebSocketAlertDismissedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_dismissed' && isAlertMessage(value);
}

/**
 * Type guard for WebSocketAlertResolvedMessage.
 */
export function isAlertResolvedMessage(value: unknown): value is WebSocketAlertResolvedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_resolved' && isAlertMessage(value);
}
"""


def generate_discriminated_union() -> str:
    """Generate discriminated union type and utilities.

    Returns:
        TypeScript discriminated union type definitions
    """
    return """
// ============================================================================
// Discriminated Union Types
// ============================================================================

/**
 * All alert-related WebSocket message types.
 */
export type WebSocketAlertMessage =
  | WebSocketAlertCreatedMessage
  | WebSocketAlertUpdatedMessage
  | WebSocketAlertAcknowledgedMessage
  | WebSocketAlertDismissedMessage
  | WebSocketAlertResolvedMessage;

/**
 * All server-to-client WebSocket message types.
 * The `type` field serves as the discriminant for type narrowing.
 */
export type WebSocketServerMessage =
  | WebSocketEventMessage
  | WebSocketServiceStatusMessage
  | WebSocketSceneChangeMessage
  | WebSocketAlertMessage
  | WebSocketPongResponse
  | WebSocketErrorResponse
  | { type: 'ping' };  // Server heartbeat

/**
 * All client-to-server WebSocket message types.
 */
export type WebSocketClientMessage =
  | WebSocketPingMessage
  | WebSocketSubscribeMessage
  | WebSocketUnsubscribeMessage
  | { type: 'pong' };  // Client heartbeat response

/**
 * All WebSocket message types (both directions).
 */
export type AnyWebSocketMessage = WebSocketServerMessage | WebSocketClientMessage;

/**
 * Extract message type by discriminant.
 */
export type MessageByType<T extends AnyWebSocketMessage['type']> = Extract<
  AnyWebSocketMessage,
  { type: T }
>;

/**
 * Type-safe message handler function.
 */
export type MessageHandler<T extends AnyWebSocketMessage> = (message: T) => void;

/**
 * Map of message types to their handlers.
 */
export type MessageHandlerMap = {
  [K in AnyWebSocketMessage['type']]?: MessageHandler<MessageByType<K>>;
};

/**
 * Create a type-safe message dispatcher.
 *
 * @example
 * ```ts
 * const dispatch = createMessageDispatcher({
 *   event: (msg) => console.log(msg.data.risk_score),
 *   service_status: (msg) => console.log(msg.data.status),
 *   alert_created: (msg) => console.log('New alert:', msg.data.id),
 *   ping: () => ws.send(JSON.stringify({ type: 'pong' })),
 * });
 *
 * ws.onmessage = (event) => {
 *   const message = JSON.parse(event.data);
 *   dispatch(message);
 * };
 * ```
 */
export function createMessageDispatcher(handlers: MessageHandlerMap) {
  return (message: AnyWebSocketMessage): void => {
    const handler = handlers[message.type];
    if (handler) {
      (handler as (msg: AnyWebSocketMessage) => void)(message);
    }
  };
}

/**
 * Utility function for exhaustive checking in switch statements.
 */
export function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${JSON.stringify(value)}`);
}
"""


def generate_typescript_file() -> str:
    """Generate the complete TypeScript file content.

    Returns:
        Complete TypeScript file content
    """
    parts: list[str] = []

    # Add header
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts.append(HEADER_COMMENT.format(timestamp=timestamp))

    # Add enums
    parts.append("// ============================================================================")
    parts.append("// Enums and Constants")
    parts.append("// ============================================================================")
    parts.append("")
    parts.append(generate_enum(RiskLevel))
    parts.append("")
    parts.append(generate_enum(WebSocketMessageType))
    parts.append("")
    parts.append(generate_enum(WebSocketServiceStatus))
    parts.append("")
    parts.append(generate_enum(WebSocketAlertEventType))
    parts.append("")
    parts.append(generate_enum(WebSocketAlertSeverity))
    parts.append("")
    parts.append(generate_enum(WebSocketAlertStatus))
    parts.append("")
    parts.append(generate_error_codes(WebSocketErrorCode))
    parts.append("")

    # Add data interfaces
    parts.append("// ============================================================================")
    parts.append("// Data Payload Interfaces")
    parts.append("// ============================================================================")
    parts.append("")
    parts.append(generate_interface(WebSocketEventData))
    parts.append("")
    parts.append(generate_interface(WebSocketServiceStatusData))
    parts.append("")
    parts.append(generate_interface(WebSocketSceneChangeData))
    parts.append("")
    parts.append(generate_interface(WebSocketAlertData))
    parts.append("")

    # Add message interfaces
    parts.append("// ============================================================================")
    parts.append("// Message Envelope Interfaces")
    parts.append("// ============================================================================")
    parts.append("")
    parts.append(generate_interface(WebSocketPingMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketPongResponse))
    parts.append("")
    parts.append(generate_interface(WebSocketSubscribeMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketUnsubscribeMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketErrorResponse))
    parts.append("")
    parts.append(generate_interface(WebSocketEventMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketServiceStatusMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketSceneChangeMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketAlertCreatedMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketAlertUpdatedMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketAlertAcknowledgedMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketAlertDismissedMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketAlertResolvedMessage))
    parts.append("")
    parts.append(generate_interface(WebSocketMessage))
    parts.append("")

    # Add discriminated union types
    parts.append(generate_discriminated_union())
    parts.append("")

    # Add type guards
    parts.append(generate_type_guards())

    return "\n".join(parts)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Generate TypeScript types from WebSocket Pydantic schemas"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if generated types are current (for CI)",
    )
    args = parser.parse_args()

    # Generate TypeScript content
    content = generate_typescript_file()

    if args.check:
        # Check mode - compare with existing file
        if not OUTPUT_FILE.exists():
            print(f"ERROR: Generated types file does not exist: {OUTPUT_FILE}")
            print("Run './scripts/generate-ws-types.py' to generate types")
            return 1

        existing_content = OUTPUT_FILE.read_text()

        # Compare ignoring timestamp line
        def normalize(text: str) -> str:
            lines = text.split("\n")
            return "\n".join(
                line for line in lines if not line.strip().startswith("* Generated at:")
            )

        if normalize(content) != normalize(existing_content):
            print("ERROR: WebSocket types are out of date!")
            print()
            print("The WebSocket schemas have changed. Please regenerate types:")
            print("  ./scripts/generate-ws-types.py")
            print()
            print("Then commit the updated types file.")
            return 1

        print("OK: WebSocket types are current")
        return 0

    # Generate mode - write to file
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content)
    print(f"Generated WebSocket types: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
