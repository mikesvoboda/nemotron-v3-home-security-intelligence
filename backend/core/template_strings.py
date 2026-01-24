"""PEP 750 Template Strings for safe string interpolation.

This module provides type-safe string templating using Python 3.14's template
strings (t-strings) to prevent SQL injection and XSS vulnerabilities through
automatic escaping of interpolated values.

Key Features:
    - `sql()`: Converts t-strings to parameterized SQL queries (PostgreSQL $N style)
    - `html()`: HTML-escapes interpolated values for XSS prevention
    - `safe_log()`: Sanitizes interpolated values for safe logging

Usage Examples:

    SQL Query Building (parameterized):
        >>> user_id = "user_123"
        >>> query, params = sql(t"SELECT * FROM users WHERE id = {user_id}")
        >>> print(query)
        'SELECT * FROM users WHERE id = $1'
        >>> print(params)
        ['user_123']

    HTML Template (auto-escaped):
        >>> name = "<script>alert('xss')</script>"
        >>> html_output = html(t"<p>Hello, {name}!</p>")
        >>> print(html_output)
        '<p>Hello, &lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;!</p>'

    Safe Logging:
        >>> user_input = "malicious\\ndata"
        >>> log_msg = safe_log(t"User provided: {user_input}")
        >>> print(log_msg)
        'User provided: malicious\\ndata'

Security Notes:
    - SQL queries return (query_string, params_list) for use with SQLAlchemy's
      `session.execute(text(query), dict(enumerate(params, 1)))` or similar
    - HTML escaping follows OWASP recommendations
    - Log sanitization removes control characters that could enable log injection

Related PEP:
    - PEP 750: Template Strings (Python 3.14+)
    https://peps.python.org/pep-0750/

Linear Issue: NEM-3221
"""

from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass
from string.templatelib import Interpolation, Template
from typing import Any, Literal, overload

# -----------------------------------------------------------------------------
# SQL Template Processing
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParameterizedQuery:
    """Result of SQL template processing.

    Attributes:
        query: The parameterized SQL query string with $N placeholders
        params: List of parameter values in order
    """

    query: str
    params: tuple[Any, ...]

    def to_sqlalchemy_params(self) -> dict[str, Any]:
        """Convert params to SQLAlchemy named parameters.

        SQLAlchemy's text() expects named parameters like :param_1, :param_2.

        Returns:
            Dictionary mapping parameter names to values
        """
        return {f"param_{i}": v for i, v in enumerate(self.params, 1)}

    def to_sqlalchemy_query(self) -> str:
        """Convert query to use SQLAlchemy named parameter syntax.

        Replaces $1, $2, etc. with :param_1, :param_2, etc.

        Returns:
            Query string with :param_N style placeholders
        """
        result = self.query
        for i in range(len(self.params), 0, -1):
            result = result.replace(f"${i}", f":param_{i}")
        return result


def sql(template: Template) -> ParameterizedQuery:
    """Convert a template string to a parameterized SQL query.

    Processes t-string template to extract interpolated values as parameters,
    replacing them with PostgreSQL-style positional placeholders ($1, $2, etc.).

    This prevents SQL injection by ensuring all user values are passed as
    parameters rather than being concatenated into the query string.

    Args:
        template: A t-string template containing SQL with interpolations

    Returns:
        ParameterizedQuery with the query string and parameter values

    Example:
        >>> user_id = "abc123"
        >>> status = "active"
        >>> result = sql(t"SELECT * FROM users WHERE id = {user_id} AND status = {status}")
        >>> result.query
        'SELECT * FROM users WHERE id = $1 AND status = $2'
        >>> result.params
        ('abc123', 'active')

    Note:
        For use with SQLAlchemy, use the to_sqlalchemy_query() and
        to_sqlalchemy_params() methods:

            query = result.to_sqlalchemy_query()
            params = result.to_sqlalchemy_params()
            await session.execute(text(query), params)
    """
    sql_parts: list[str] = []
    params: list[Any] = []

    for item in template:
        if isinstance(item, str):
            sql_parts.append(item)
        elif isinstance(item, Interpolation):
            # Add parameter placeholder with 1-based index
            params.append(item.value)
            sql_parts.append(f"${len(params)}")

    return ParameterizedQuery(query="".join(sql_parts), params=tuple(params))


# -----------------------------------------------------------------------------
# HTML Template Processing
# -----------------------------------------------------------------------------


def _escape_html(value: Any) -> str:
    """Escape a value for safe HTML inclusion.

    Escapes special HTML characters to prevent XSS attacks:
    - & -> &amp;
    - < -> &lt;
    - > -> &gt;
    - " -> &quot;
    - ' -> &#x27;

    Args:
        value: The value to escape

    Returns:
        HTML-escaped string
    """
    return html_module.escape(str(value), quote=True)


def html(template: Template) -> str:
    """Process a template string with automatic HTML escaping.

    All interpolated values are automatically HTML-escaped to prevent XSS
    vulnerabilities. Static string parts are preserved as-is (they are
    assumed to be trusted HTML from your source code).

    Args:
        template: A t-string template containing HTML with interpolations

    Returns:
        Safe HTML string with all interpolated values escaped

    Example:
        >>> name = "<script>alert('xss')</script>"
        >>> html(t"<div>Hello, {name}!</div>")
        "<div>Hello, &lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;!</div>"

    Security Note:
        Only interpolated values are escaped. The template's static strings
        are trusted. Never construct templates from untrusted sources.

    Warning:
        For HTML attributes, be careful with unquoted values:

        SAFE:   t'<div class="{cls}">...'  (quoted attribute)
        UNSAFE: t'<div class={cls}>...'    (unquoted - escaping insufficient)

        Always use quoted attributes when interpolating values.
    """
    parts: list[str] = []

    for item in template:
        if isinstance(item, str):
            # Static strings from source code are trusted
            parts.append(item)
        elif isinstance(item, Interpolation):
            # Interpolated values are escaped
            parts.append(_escape_html(item.value))

    return "".join(parts)


@overload
def html_attr(value: str) -> str: ...


@overload
def html_attr(value: None) -> Literal[""]: ...


def html_attr(value: str | None) -> str:
    """Escape a value for use in an HTML attribute.

    Escapes the value and returns it ready for use in a quoted attribute.
    Returns empty string for None values.

    Args:
        value: The attribute value to escape

    Returns:
        Escaped string safe for use in HTML attributes

    Example:
        >>> html_attr('hello "world"')
        'hello &quot;world&quot;'
        >>> html_attr(None)
        ''
    """
    if value is None:
        return ""
    return _escape_html(value)


# -----------------------------------------------------------------------------
# Log Message Processing
# -----------------------------------------------------------------------------

# Control characters that could enable log injection/forging
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Newlines that could create fake log entries
_NEWLINE_PATTERN = re.compile(r"[\r\n]")


def _escape_newline(match: re.Match[str]) -> str:
    """Replace newline characters with escaped representation."""
    char = match.group(0)
    if char == "\n":
        return "\\n"
    return "\\r"


def _sanitize_log_value(value: Any) -> str:
    """Sanitize a value for safe inclusion in log messages.

    Removes/escapes characters that could enable log injection:
    - Control characters (NULL, backspace, etc.)
    - Newlines (could create fake log entries)
    - Tabs are preserved (common in structured output)

    Args:
        value: The value to sanitize

    Returns:
        Sanitized string safe for logging
    """
    text = str(value)

    # Replace control characters with placeholder
    text = _CONTROL_CHAR_PATTERN.sub("[CTRL]", text)

    # Escape newlines (represent them visually)
    # Use callable to ensure literal backslash sequences in output
    text = _NEWLINE_PATTERN.sub(_escape_newline, text)

    # Limit length to prevent log flooding
    max_length = 1000
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."

    return text


def safe_log(template: Template) -> str:
    """Process a template string with automatic log sanitization.

    Sanitizes interpolated values to prevent log injection attacks:
    - Control characters are replaced with [CTRL]
    - Newlines are escaped as \\n
    - Very long values are truncated

    Static string parts are preserved as-is (trusted source code).

    Args:
        template: A t-string template for log messages

    Returns:
        Safe log message string

    Example:
        >>> user_input = "malicious\\nFake log entry"
        >>> safe_log(t"User submitted: {user_input}")
        'User submitted: malicious\\nFake log entry'

    Security Note:
        This prevents attackers from forging log entries by injecting
        newlines or other control characters into logged values.
    """
    parts: list[str] = []

    for item in template:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, Interpolation):
            parts.append(_sanitize_log_value(item.value))

    return "".join(parts)


# -----------------------------------------------------------------------------
# Format Specifier Support
# -----------------------------------------------------------------------------


def format_template(template: Template) -> str:
    """Process a template string applying format specifiers to interpolations.

    Unlike the basic processors above, this function respects format specifiers
    (like {value:.2f} or {value:>10}) while still providing safe processing.

    This is useful when you need formatted output but still want the benefits
    of template string processing.

    Args:
        template: A t-string template with optional format specifiers

    Returns:
        Formatted string with all specifiers applied

    Example:
        >>> price = 19.99
        >>> qty = 5
        >>> format_template(t"Price: ${price:.2f} x {qty:3d}")
        'Price: $19.99 x   5'
    """
    parts: list[str] = []

    for item in template:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, Interpolation):
            # Apply format spec if present
            if item.format_spec:
                formatted = format(item.value, item.format_spec)
            else:
                formatted = str(item.value)
            parts.append(formatted)

    return "".join(parts)


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def is_template(obj: Any) -> bool:
    """Check if an object is a template string.

    Args:
        obj: Object to check

    Returns:
        True if obj is a Template instance
    """
    return isinstance(obj, Template)


def get_interpolations(template: Template) -> list[tuple[str, Any]]:
    """Extract all interpolated expressions and their values from a template.

    Useful for debugging or introspecting template contents.

    Args:
        template: A t-string template

    Returns:
        List of (expression, value) tuples for each interpolation

    Example:
        >>> x = 1
        >>> y = 2
        >>> get_interpolations(t"sum: {x + y}")
        [('x + y', 3)]
    """
    result: list[tuple[str, Any]] = []

    for item in template:
        if isinstance(item, Interpolation):
            result.append((item.expression, item.value))

    return result
