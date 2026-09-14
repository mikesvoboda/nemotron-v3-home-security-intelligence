"""Tests for PEP 750 template string utilities.

This module tests the template string functions used for:
- SQL injection prevention via parameterized queries
- XSS prevention via HTML escaping
- Log injection prevention via sanitization

Related Linear issue: NEM-3221
"""

import pytest

from backend.core.template_strings import (
    ParameterizedQuery,
    format_template,
    get_interpolations,
    html,
    html_attr,
    is_template,
    safe_log,
    sql,
)

# =============================================================================
# SQL Template Processing Tests
# =============================================================================


class TestSqlTemplateProcessing:
    """Tests for SQL template processing to prevent SQL injection."""

    def test_simple_select_query(self) -> None:
        """Simple SELECT with one parameter should produce $1 placeholder."""
        user_id = "user_123"
        result = sql(t"SELECT * FROM users WHERE id = {user_id}")

        assert result.query == "SELECT * FROM users WHERE id = $1"
        assert result.params == ("user_123",)

    def test_multiple_parameters(self) -> None:
        """Multiple parameters should produce $1, $2, etc. placeholders."""
        user_id = "user_123"
        status = "active"
        limit = 10

        result = sql(
            t"SELECT * FROM users WHERE id = {user_id} AND status = {status} LIMIT {limit}"
        )

        assert result.query == "SELECT * FROM users WHERE id = $1 AND status = $2 LIMIT $3"
        assert result.params == ("user_123", "active", 10)

    def test_insert_query(self) -> None:
        """INSERT statements should properly parameterize values."""
        name = "John Doe"
        email = "john@example.com"

        result = sql(t"INSERT INTO users (name, email) VALUES ({name}, {email})")

        assert result.query == "INSERT INTO users (name, email) VALUES ($1, $2)"
        assert result.params == ("John Doe", "john@example.com")

    def test_update_query(self) -> None:
        """UPDATE statements should properly parameterize values."""
        new_status = "inactive"
        user_id = 42

        result = sql(t"UPDATE users SET status = {new_status} WHERE id = {user_id}")

        assert result.query == "UPDATE users SET status = $1 WHERE id = $2"
        assert result.params == ("inactive", 42)

    def test_delete_query(self) -> None:
        """DELETE statements should properly parameterize values."""
        user_id = 42

        result = sql(t"DELETE FROM users WHERE id = {user_id}")

        assert result.query == "DELETE FROM users WHERE id = $1"
        assert result.params == (42,)

    def test_sql_injection_attempt(self) -> None:
        """SQL injection attempts should be safely parameterized."""
        malicious_input = "'; DROP TABLE users; --"

        result = sql(t"SELECT * FROM users WHERE name = {malicious_input}")

        # The malicious input becomes a parameter value, not part of the query
        assert result.query == "SELECT * FROM users WHERE name = $1"
        assert result.params == ("'; DROP TABLE users; --",)
        # The actual SQL executed would be safe because the value is parameterized

    def test_none_value(self) -> None:
        """None values should be passed through as parameters."""
        user_id = None

        result = sql(t"SELECT * FROM users WHERE id = {user_id}")

        assert result.query == "SELECT * FROM users WHERE id = $1"
        assert result.params == (None,)

    def test_no_parameters(self) -> None:
        """Queries without parameters should work correctly."""
        result = sql(t"SELECT * FROM users")

        assert result.query == "SELECT * FROM users"
        assert result.params == ()

    def test_repeated_value(self) -> None:
        """Same value used multiple times should create multiple parameters."""
        value = "test"

        result = sql(t"SELECT * FROM t WHERE a = {value} OR b = {value}")

        assert result.query == "SELECT * FROM t WHERE a = $1 OR b = $2"
        assert result.params == ("test", "test")

    def test_complex_types(self) -> None:
        """Various Python types should be handled as parameters."""
        int_val = 42
        float_val = 3.14
        bool_val = True
        list_val = [1, 2, 3]

        result = sql(
            t"SELECT * FROM t WHERE a = {int_val} AND b = {float_val} AND c = {bool_val} AND d = {list_val}"
        )

        assert result.params == (42, 3.14, True, [1, 2, 3])


class TestParameterizedQuery:
    """Tests for the ParameterizedQuery dataclass."""

    def test_to_sqlalchemy_params(self) -> None:
        """SQLAlchemy params should be named param_1, param_2, etc."""
        query = ParameterizedQuery(
            query="SELECT * FROM t WHERE a = $1 AND b = $2", params=("value1", "value2")
        )

        params = query.to_sqlalchemy_params()

        assert params == {"param_1": "value1", "param_2": "value2"}

    def test_to_sqlalchemy_query(self) -> None:
        """SQLAlchemy query should use :param_N syntax."""
        query = ParameterizedQuery(
            query="SELECT * FROM t WHERE a = $1 AND b = $2", params=("value1", "value2")
        )

        result = query.to_sqlalchemy_query()

        assert result == "SELECT * FROM t WHERE a = :param_1 AND b = :param_2"

    def test_empty_params(self) -> None:
        """Empty params should produce empty dict and unchanged query."""
        query = ParameterizedQuery(query="SELECT 1", params=())

        assert query.to_sqlalchemy_params() == {}
        assert query.to_sqlalchemy_query() == "SELECT 1"

    def test_frozen_dataclass(self) -> None:
        """ParameterizedQuery should be immutable."""
        query = ParameterizedQuery(query="SELECT 1", params=())

        with pytest.raises(AttributeError):
            query.query = "modified"  # type: ignore[misc]


# =============================================================================
# HTML Template Processing Tests
# =============================================================================


class TestHtmlTemplateProcessing:
    """Tests for HTML template processing to prevent XSS."""

    def test_safe_text(self) -> None:
        """Plain text should pass through unchanged."""
        name = "John Doe"

        result = html(t"<p>Hello, {name}!</p>")

        assert result == "<p>Hello, John Doe!</p>"

    def test_script_tag_escaped(self) -> None:
        """Script tags should be escaped to prevent XSS."""
        malicious = "<script>alert('xss')</script>"

        result = html(t"<div>{malicious}</div>")

        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert result == "<div>&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;</div>"

    def test_html_entities_escaped(self) -> None:
        """HTML special characters should be escaped."""
        text = '<a href="test" onclick="evil()">'

        result = html(t"<p>{text}</p>")

        # The angle brackets and quotes are escaped, preventing HTML parsing
        assert "&lt;a" in result
        assert "&quot;" in result
        # The text "onclick" still appears (as text, not attribute) but escaped
        assert result == "<p>&lt;a href=&quot;test&quot; onclick=&quot;evil()&quot;&gt;</p>"

    def test_ampersand_escaped(self) -> None:
        """Ampersands should be escaped."""
        text = "Tom & Jerry"

        result = html(t"<p>{text}</p>")

        assert result == "<p>Tom &amp; Jerry</p>"

    def test_quotes_escaped(self) -> None:
        """Quotes should be escaped."""
        text = 'He said "Hello"'

        result = html(t"<p>{text}</p>")

        assert result == "<p>He said &quot;Hello&quot;</p>"

    def test_single_quotes_escaped(self) -> None:
        """Single quotes should be escaped."""
        text = "It's a test"

        result = html(t"<p>{text}</p>")

        assert result == "<p>It&#x27;s a test</p>"

    def test_static_html_preserved(self) -> None:
        """Static HTML in template should not be escaped."""
        name = "World"

        result = html(t"<div class='container'><p>Hello, {name}!</p></div>")

        assert "<div class='container'>" in result
        assert "<p>Hello, World!</p>" in result

    def test_multiple_interpolations(self) -> None:
        """Multiple interpolations should all be escaped."""
        first = "<b>First</b>"
        second = "<i>Second</i>"

        result = html(t"<p>{first} and {second}</p>")

        assert "&lt;b&gt;First&lt;/b&gt;" in result
        assert "&lt;i&gt;Second&lt;/i&gt;" in result

    def test_none_value(self) -> None:
        """None values should become the string 'None'."""
        value = None

        result = html(t"<p>{value}</p>")

        assert result == "<p>None</p>"

    def test_numeric_values(self) -> None:
        """Numeric values should be converted to strings."""
        count = 42
        price = 19.99

        result = html(t"<p>Count: {count}, Price: {price}</p>")

        assert result == "<p>Count: 42, Price: 19.99</p>"


class TestHtmlAttr:
    """Tests for HTML attribute escaping."""

    def test_simple_attribute(self) -> None:
        """Simple text should be returned as-is."""
        assert html_attr("simple") == "simple"

    def test_double_quotes_escaped(self) -> None:
        """Double quotes should be escaped."""
        assert html_attr('hello "world"') == "hello &quot;world&quot;"

    def test_single_quotes_escaped(self) -> None:
        """Single quotes should be escaped."""
        assert html_attr("it's") == "it&#x27;s"

    def test_none_returns_empty(self) -> None:
        """None should return empty string."""
        assert html_attr(None) == ""

    def test_angle_brackets_escaped(self) -> None:
        """Angle brackets should be escaped."""
        assert html_attr("<test>") == "&lt;test&gt;"


# =============================================================================
# Log Sanitization Tests
# =============================================================================


class TestSafeLogProcessing:
    """Tests for safe log message processing to prevent log injection."""

    def test_simple_message(self) -> None:
        """Simple messages should pass through."""
        user_id = "user_123"

        result = safe_log(t"User {user_id} logged in")

        assert result == "User user_123 logged in"

    def test_newline_escaped(self) -> None:
        """Newlines should be escaped to prevent log forging."""
        malicious = "test\nFake log entry: CRITICAL ERROR"

        result = safe_log(t"User input: {malicious}")

        # The newline character in the INTERPOLATED value is escaped
        # Note: We're checking that the actual newline char is replaced
        # The result contains the literal backslash-n sequence
        assert "test" in result
        assert "Fake log entry" in result
        # The newline is replaced with literal \n (escaped)
        assert "\nFake" not in result  # The raw newline is gone

    def test_carriage_return_escaped(self) -> None:
        """Carriage returns should be escaped."""
        malicious = "test\rOverwrite"

        result = safe_log(t"Input: {malicious}")

        # The carriage return is replaced with literal \n
        assert "\r" not in result
        assert "test" in result
        assert "Overwrite" in result

    def test_control_characters_replaced(self) -> None:
        """Control characters should be replaced."""
        malicious = "test\x00\x07\x1bdata"

        result = safe_log(t"Input: {malicious}")

        assert "\x00" not in result
        assert "\x07" not in result
        assert "\x1b" not in result
        assert "[CTRL]" in result

    def test_long_value_truncated(self) -> None:
        """Very long values should be truncated."""
        long_value = "x" * 2000

        result = safe_log(t"Data: {long_value}")

        assert len(result) < 1100  # "Data: " + 1000 chars max + "..."
        assert result.endswith("...")

    def test_multiple_interpolations(self) -> None:
        """Multiple interpolations should all be sanitized."""
        input1 = "normal"
        input2 = "evil\nlog"

        result = safe_log(t"First: {input1}, Second: {input2}")

        # Both values are sanitized, newline is escaped
        assert "First: normal" in result
        assert "evil" in result
        assert "log" in result
        assert "\nlog" not in result  # Raw newline is escaped

    def test_tab_preserved(self) -> None:
        """Tabs should be preserved (common in structured output)."""
        data = "col1\tcol2\tcol3"

        result = safe_log(t"Data: {data}")

        assert "\t" in result
        assert result == "Data: col1\tcol2\tcol3"

    def test_static_text_preserved(self) -> None:
        """Static parts of template should not be modified."""
        value = "test"

        result = safe_log(t"INFO: Processing complete\nValue: {value}")

        # Note: static \n in template is preserved, only interpolated values are sanitized
        assert result == "INFO: Processing complete\nValue: test"


# =============================================================================
# Format Template Tests
# =============================================================================


class TestFormatTemplate:
    """Tests for format specifier support in templates."""

    def test_float_precision(self) -> None:
        """Float precision format should be applied."""
        price = 19.99

        result = format_template(t"Price: ${price:.2f}")

        assert result == "Price: $19.99"

    def test_integer_width(self) -> None:
        """Integer width format should be applied."""
        num = 42

        result = format_template(t"Number: {num:5d}")

        assert result == "Number:    42"

    def test_string_padding(self) -> None:
        """String padding format should be applied."""
        name = "test"

        result = format_template(t"Name: {name:>10}")

        assert result == "Name:       test"

    def test_no_format_spec(self) -> None:
        """Values without format spec should be converted to string."""
        value = 42

        result = format_template(t"Value: {value}")

        assert result == "Value: 42"

    def test_mixed_formatted_and_plain(self) -> None:
        """Mix of formatted and plain interpolations should work."""
        name = "test"
        price = 9.99
        count = 5

        result = format_template(t"{name}: ${price:.2f} x {count}")

        assert result == "test: $9.99 x 5"


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestIsTemplate:
    """Tests for is_template utility function."""

    def test_template_returns_true(self) -> None:
        """Template strings should return True."""
        template = t"Hello, {1 + 1}"
        assert is_template(template) is True

    def test_regular_string_returns_false(self) -> None:
        """Regular strings should return False."""
        assert is_template("Hello") is False

    def test_none_returns_false(self) -> None:
        """None should return False."""
        assert is_template(None) is False

    def test_other_types_return_false(self) -> None:
        """Other types should return False."""
        assert is_template(42) is False
        assert is_template([1, 2, 3]) is False
        assert is_template({"a": 1}) is False


class TestGetInterpolations:
    """Tests for get_interpolations utility function."""

    def test_simple_interpolation(self) -> None:
        """Simple interpolations should return expression and value."""
        x = 42
        result = get_interpolations(t"Value: {x}")

        assert len(result) == 1
        assert result[0] == ("x", 42)

    def test_expression_interpolation(self) -> None:
        """Expression interpolations should return the expression and computed value."""
        x = 1
        y = 2
        result = get_interpolations(t"Sum: {x + y}")

        assert len(result) == 1
        assert result[0][0] == "x + y"
        assert result[0][1] == 3

    def test_multiple_interpolations(self) -> None:
        """Multiple interpolations should all be returned."""
        a = 1
        b = 2
        c = 3
        result = get_interpolations(t"{a}, {b}, {c}")

        assert len(result) == 3
        assert result[0] == ("a", 1)
        assert result[1] == ("b", 2)
        assert result[2] == ("c", 3)

    def test_no_interpolations(self) -> None:
        """Templates without interpolations should return empty list."""
        result = get_interpolations(t"Plain text")

        assert result == []


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for real-world usage patterns."""

    def test_sql_with_sqlalchemy_integration(self) -> None:
        """Test SQL template produces valid SQLAlchemy-compatible output."""
        camera_id = "cam_123"
        status = "active"

        result = sql(t"SELECT * FROM cameras WHERE id = {camera_id} AND status = {status}")

        # Verify we can get SQLAlchemy format
        sa_query = result.to_sqlalchemy_query()
        sa_params = result.to_sqlalchemy_params()

        assert sa_query == "SELECT * FROM cameras WHERE id = :param_1 AND status = :param_2"
        assert sa_params == {"param_1": "cam_123", "param_2": "active"}

    def test_html_email_template(self) -> None:
        """Test HTML template for email notifications."""
        alert_id = "alert_123"
        severity = "<script>HIGH</script>"  # Malicious input
        message = "Camera detected unusual activity"

        result = html(
            t"""
            <div class="alert">
                <h2>Security Alert: {alert_id}</h2>
                <p><strong>Severity:</strong> {severity}</p>
                <p><strong>Message:</strong> {message}</p>
            </div>
            """
        )

        # Verify structure preserved
        assert '<div class="alert">' in result
        assert "<h2>Security Alert: alert_123</h2>" in result

        # Verify malicious content escaped
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_log_message_with_user_data(self) -> None:
        """Test log sanitization with potentially malicious user data."""
        user_id = "user_123"
        action = "login"
        ip_address = "192.168.1.1\nFake log: user admin promoted to superuser"

        result = safe_log(t"User {user_id} performed {action} from {ip_address}")

        # Verify structure preserved
        assert "User user_123 performed login from" in result

        # Verify log injection prevented - the raw newline is escaped
        assert "192.168.1.1" in result
        assert "Fake log" in result
        # The newline character is replaced, preventing log forging
        assert "\nFake" not in result
