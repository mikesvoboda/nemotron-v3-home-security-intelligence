"""Unit tests for prompt_parser.py - prompt parsing utilities."""

from backend.services.prompt_parser import (
    apply_suggestion_to_prompt,
    detect_variable_style,
    find_insertion_point,
    generate_insertion_text,
    validate_prompt_syntax,
)

# Sample prompts for testing
SAMPLE_PROMPT_CURLY = """## System Instructions
You are a security analysis AI.

## Camera & Time Context
Camera: {camera_name}
Time: {timestamp}
Day: {day_of_week}
Lighting: {time_of_day}

## Detection Information
Objects detected: {detected_objects}
"""

SAMPLE_PROMPT_ANGLE = """## System Instructions
You are a security analysis AI.

## Camera & Time Context
Camera: <camera_name>
Time: <timestamp>

## Detection Information
Objects detected: <detected_objects>
"""

SAMPLE_PROMPT_DOLLAR = """## System Instructions
You are a security analysis AI.

## Context
Camera: $camera_name
Time: $timestamp
"""

SAMPLE_PROMPT_INDENTED = """## System Instructions
You are a security analysis AI.

## Camera & Time Context
    Camera: {camera_name}
    Time: {timestamp}
    Day: {day_of_week}

## Detection Information
Objects detected: {detected_objects}
"""

SAMPLE_PROMPT_EQUALS = """## System Instructions
You are a security analysis AI.

## Context
Camera={camera_name}
Time={timestamp}
"""


class TestFindInsertionPoint:
    """Tests for find_insertion_point function."""

    def test_finds_section_and_returns_section_end_for_append(self) -> None:
        """Test that it finds the correct section and returns end position for append."""
        idx, insert_type = find_insertion_point(
            SAMPLE_PROMPT_CURLY, "Camera & Time Context", "append"
        )

        assert insert_type == "section_end"
        # The insertion point should be after "Lighting: {time_of_day}"
        # which is the last line in the Camera & Time Context section
        assert idx > 0
        # Verify it's before the next section
        assert SAMPLE_PROMPT_CURLY[idx:].startswith("\n## Detection")

    def test_finds_section_and_returns_section_start_for_prepend(self) -> None:
        """Test that it returns start position for prepend."""
        idx, insert_type = find_insertion_point(
            SAMPLE_PROMPT_CURLY, "Camera & Time Context", "prepend"
        )

        assert insert_type == "section_start"
        # The insertion point should be right after the section header line
        assert SAMPLE_PROMPT_CURLY[idx:].startswith("Camera: {camera_name}")

    def test_fallback_when_section_not_found(self) -> None:
        """Test that it falls back to end of prompt when section not found."""
        idx, insert_type = find_insertion_point(
            SAMPLE_PROMPT_CURLY, "Nonexistent Section", "append"
        )

        assert insert_type == "fallback"
        assert idx == len(SAMPLE_PROMPT_CURLY)

    def test_case_insensitive_section_matching(self) -> None:
        """Test that section matching is case-insensitive."""
        idx, insert_type = find_insertion_point(
            SAMPLE_PROMPT_CURLY, "camera & time context", "append"
        )

        assert insert_type == "section_end"
        assert idx > 0

    def test_handles_special_regex_characters_in_section_name(self) -> None:
        """Test that special regex characters in section names are handled."""
        prompt_with_special = """## Config (v2.0)
Setting: {value}

## Next Section
"""
        idx, insert_type = find_insertion_point(prompt_with_special, "Config (v2.0)", "append")

        assert insert_type == "section_end"
        assert idx > 0

    def test_empty_prompt_returns_fallback(self) -> None:
        """Test that empty prompt returns fallback at position 0."""
        idx, insert_type = find_insertion_point("", "Any Section", "append")

        assert insert_type == "fallback"
        assert idx == 0

    def test_default_insertion_point_is_append(self) -> None:
        """Test that default insertion point is append."""
        idx1, type1 = find_insertion_point(SAMPLE_PROMPT_CURLY, "Camera & Time Context")
        idx2, type2 = find_insertion_point(SAMPLE_PROMPT_CURLY, "Camera & Time Context", "append")

        assert idx1 == idx2
        assert type1 == type2 == "section_end"


class TestDetectVariableStyle:
    """Tests for detect_variable_style function."""

    def test_detects_curly_brace_format(self) -> None:
        """Test detection of {variable} style."""
        style = detect_variable_style(SAMPLE_PROMPT_CURLY)

        assert style["format"] == "curly"

    def test_detects_angle_bracket_format(self) -> None:
        """Test detection of <variable> style."""
        style = detect_variable_style(SAMPLE_PROMPT_ANGLE)

        assert style["format"] == "angle"

    def test_detects_dollar_format(self) -> None:
        """Test detection of $variable style."""
        style = detect_variable_style(SAMPLE_PROMPT_DOLLAR)

        assert style["format"] == "dollar"

    def test_detects_colon_label_style(self) -> None:
        """Test detection of 'Label: {var}' style."""
        style = detect_variable_style(SAMPLE_PROMPT_CURLY)

        assert style["label_style"] == "colon"

    def test_detects_equals_label_style(self) -> None:
        """Test detection of 'Label={var}' style."""
        style = detect_variable_style(SAMPLE_PROMPT_EQUALS)

        assert style["label_style"] == "equals"

    def test_detects_indentation(self) -> None:
        """Test detection of indentation pattern."""
        style = detect_variable_style(SAMPLE_PROMPT_INDENTED)

        assert style["indentation"] == "    "  # 4 spaces

    def test_no_indentation_when_not_present(self) -> None:
        """Test that no indentation is detected when lines start at column 0."""
        style = detect_variable_style(SAMPLE_PROMPT_CURLY)

        assert style["indentation"] == ""

    def test_returns_none_for_empty_prompt(self) -> None:
        """Test that empty prompt returns 'none' for all styles."""
        style = detect_variable_style("")

        assert style["format"] == "none"
        assert style["label_style"] == "none"
        assert style["indentation"] == ""

    def test_returns_none_when_no_variables(self) -> None:
        """Test that prompt without variables returns 'none' format."""
        style = detect_variable_style("Just plain text without any variables")

        assert style["format"] == "none"


class TestGenerateInsertionText:
    """Tests for generate_insertion_text function."""

    def test_generates_curly_brace_with_colon(self) -> None:
        """Test generation with curly brace and colon style."""
        style = {"format": "curly", "label_style": "colon", "indentation": ""}
        text = generate_insertion_text("Time Since Last Event", "time_since_last_event", style)

        assert text == "Time Since Last Event: {time_since_last_event}\n"

    def test_generates_angle_bracket_with_colon(self) -> None:
        """Test generation with angle bracket and colon style."""
        style = {"format": "angle", "label_style": "colon", "indentation": ""}
        text = generate_insertion_text("Time Since Last Event", "time_since_last_event", style)

        assert text == "Time Since Last Event: <time_since_last_event>\n"

    def test_generates_dollar_with_colon(self) -> None:
        """Test generation with dollar sign and colon style."""
        style = {"format": "dollar", "label_style": "colon", "indentation": ""}
        text = generate_insertion_text("Time Since Last Event", "time_since_last_event", style)

        assert text == "Time Since Last Event: $time_since_last_event\n"

    def test_generates_curly_brace_with_equals(self) -> None:
        """Test generation with curly brace and equals style."""
        style = {"format": "curly", "label_style": "equals", "indentation": ""}
        text = generate_insertion_text("Time Since Last Event", "time_since_last_event", style)

        assert text == "Time Since Last Event={time_since_last_event}\n"

    def test_respects_indentation(self) -> None:
        """Test that indentation is preserved."""
        style = {"format": "curly", "label_style": "colon", "indentation": "    "}
        text = generate_insertion_text("Time Since Last Event", "time_since_last_event", style)

        assert text == "    Time Since Last Event: {time_since_last_event}\n"

    def test_defaults_to_curly_when_format_none(self) -> None:
        """Test that format defaults to curly when 'none'."""
        style = {"format": "none", "label_style": "colon", "indentation": ""}
        text = generate_insertion_text("Test", "test_var", style)

        assert text == "Test: {test_var}\n"

    def test_defaults_to_colon_when_label_style_none(self) -> None:
        """Test that label style defaults to colon when 'none'."""
        style = {"format": "curly", "label_style": "none", "indentation": ""}
        text = generate_insertion_text("Test", "test_var", style)

        assert text == "Test: {test_var}\n"

    def test_handles_missing_keys_with_defaults(self) -> None:
        """Test that missing style keys use defaults."""
        style: dict[str, str] = {}
        text = generate_insertion_text("Test", "test_var", style)

        assert text == "Test: {test_var}\n"


class TestValidatePromptSyntax:
    """Tests for validate_prompt_syntax function."""

    def test_valid_prompt_returns_empty_list(self) -> None:
        """Test that a valid prompt returns no warnings."""
        warnings = validate_prompt_syntax(SAMPLE_PROMPT_CURLY)

        assert warnings == []

    def test_detects_unclosed_curly_brace(self) -> None:
        """Test detection of unclosed curly braces."""
        prompt_with_unclosed = "Camera: {camera_name\nTime: {timestamp"
        warnings = validate_prompt_syntax(prompt_with_unclosed)

        assert len(warnings) == 1
        assert "Unbalanced curly braces" in warnings[0]
        assert "2 open" in warnings[0]
        assert "0 close" in warnings[0]

    def test_detects_extra_closing_brace(self) -> None:
        """Test detection of extra closing braces."""
        prompt_with_extra = "Camera: {camera_name}}\nTime: {timestamp}"
        warnings = validate_prompt_syntax(prompt_with_extra)

        assert len(warnings) == 1
        assert "Unbalanced curly braces" in warnings[0]
        assert "2 open" in warnings[0]
        assert "3 close" in warnings[0]

    def test_detects_duplicate_variables(self) -> None:
        """Test detection of duplicate variable names."""
        prompt_with_duplicates = "Camera: {camera_name}\nOther: {camera_name}\n"
        warnings = validate_prompt_syntax(prompt_with_duplicates)

        assert len(warnings) == 1
        assert "Duplicate variables" in warnings[0]
        assert "camera_name" in warnings[0]

    def test_detects_multiple_duplicate_variables(self) -> None:
        """Test detection of multiple duplicate variable names."""
        prompt_with_duplicates = "A: {var_a}\nB: {var_a}\nC: {var_b}\nD: {var_b}\n"
        warnings = validate_prompt_syntax(prompt_with_duplicates)

        assert len(warnings) == 1
        assert "Duplicate variables" in warnings[0]
        assert "var_a" in warnings[0]
        assert "var_b" in warnings[0]

    def test_detects_unclosed_angle_brackets(self) -> None:
        """Test detection of unclosed angle brackets."""
        prompt_with_unclosed = "Camera: <camera_name\nTime: <timestamp>"
        warnings = validate_prompt_syntax(prompt_with_unclosed)

        assert len(warnings) == 1
        assert "Unbalanced angle brackets" in warnings[0]

    def test_detects_multiple_issues(self) -> None:
        """Test detection of multiple issues at once."""
        prompt_with_issues = "A: {var}\nB: {var}\nC: {unclosed\nD: <also_unclosed"
        warnings = validate_prompt_syntax(prompt_with_issues)

        # Should detect: unbalanced curly braces, duplicate variables, unbalanced angle brackets
        assert len(warnings) == 3

    def test_empty_prompt_is_valid(self) -> None:
        """Test that empty prompt is considered valid."""
        warnings = validate_prompt_syntax("")

        assert warnings == []


class TestApplySuggestionToPrompt:
    """Tests for apply_suggestion_to_prompt function - end-to-end tests."""

    def test_applies_suggestion_to_correct_section(self) -> None:
        """Test that suggestion is applied to the correct section."""
        result = apply_suggestion_to_prompt(
            SAMPLE_PROMPT_CURLY,
            "Camera & Time Context",
            "append",
            "Time Since Last Event",
            "time_since_last_event",
        )

        # The new variable should be added
        assert "Time Since Last Event: {time_since_last_event}" in result
        # Original content should still be there
        assert "Camera: {camera_name}" in result
        assert "## Detection Information" in result

    def test_preserves_variable_style(self) -> None:
        """Test that the variable style is preserved from the original prompt."""
        result = apply_suggestion_to_prompt(
            SAMPLE_PROMPT_ANGLE,
            "Camera & Time Context",
            "append",
            "New Var",
            "new_var",
        )

        # Should use angle brackets to match existing style
        assert "New Var: <new_var>" in result

    def test_fallback_appends_to_end(self) -> None:
        """Test that suggestion is appended to end when section not found."""
        result = apply_suggestion_to_prompt(
            SAMPLE_PROMPT_CURLY,
            "Nonexistent Section",
            "append",
            "New Var",
            "new_var",
        )

        # Should be at the end
        assert result.endswith("New Var: {new_var}\n")

    def test_prepend_adds_at_section_start(self) -> None:
        """Test that prepend adds at the start of the section content."""
        result = apply_suggestion_to_prompt(
            SAMPLE_PROMPT_CURLY,
            "Camera & Time Context",
            "prepend",
            "Priority",
            "priority_level",
        )

        # The new variable should appear before Camera
        camera_idx = result.index("Camera: {camera_name}")
        priority_idx = result.index("Priority: {priority_level}")
        assert priority_idx < camera_idx

    def test_handles_empty_prompt(self) -> None:
        """Test handling of empty prompt."""
        result = apply_suggestion_to_prompt(
            "",
            "Any Section",
            "append",
            "Test",
            "test_var",
        )

        # Should just contain the new variable with curly braces (default)
        assert result == "Test: {test_var}\n"

    def test_preserves_indentation(self) -> None:
        """Test that indentation is preserved from original prompt."""
        result = apply_suggestion_to_prompt(
            SAMPLE_PROMPT_INDENTED,
            "Camera & Time Context",
            "append",
            "New Var",
            "new_var",
        )

        # Should preserve the 4-space indentation
        assert "    New Var: {new_var}" in result

    def test_preserves_equals_label_style(self) -> None:
        """Test that equals label style is preserved."""
        result = apply_suggestion_to_prompt(
            SAMPLE_PROMPT_EQUALS,
            "Context",
            "append",
            "New Var",
            "new_var",
        )

        # Should use equals sign to match existing style
        assert "New Var={new_var}" in result


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_prompt_with_only_headers(self) -> None:
        """Test prompt that has headers but no content."""
        prompt = "## Section A\n## Section B\n"
        _idx, insert_type = find_insertion_point(prompt, "Section A", "append")

        # Should find the section even if it's empty
        assert insert_type == "section_end"

    def test_section_at_end_of_prompt(self) -> None:
        """Test finding section that's at the very end of the prompt."""
        prompt = "## First\nContent\n## Last\nFinal content"
        idx, insert_type = find_insertion_point(prompt, "Last", "append")

        assert insert_type == "section_end"
        # Verify the insertion happens at the end of the Last section
        assert prompt[idx:] == ""  # Nothing after the section

    def test_multiline_section_content(self) -> None:
        """Test section with multiple lines of content."""
        prompt = """## Multi Line
Line 1
Line 2
Line 3

## Next
"""
        idx, insert_type = find_insertion_point(prompt, "Multi Line", "append")

        assert insert_type == "section_end"
        # Should be after "Line 3\n" (including the blank line)
        remaining = prompt[idx:]
        assert remaining.startswith("\n## Next")

    def test_variable_with_uppercase_ignored(self) -> None:
        """Test that variables with uppercase letters are not detected."""
        # Our regex only looks for lowercase variables
        prompt = "Variable: {CamelCase}"
        style = detect_variable_style(prompt)

        assert style["format"] == "none"  # CamelCase not matched by [a-z_]+

    def test_nested_braces_counted_correctly(self) -> None:
        """Test that nested braces are counted correctly."""
        prompt = "Outer: {outer {inner}}"
        warnings = validate_prompt_syntax(prompt)

        # 2 open, 2 close - balanced even if nested (which is unusual)
        assert warnings == []

    def test_whitespace_variations_in_section_header(self) -> None:
        """Test that various whitespace in section headers is handled."""
        prompt = "##   Camera & Time Context   \nContent: {var}\n## Next\n"
        _idx, insert_type = find_insertion_point(prompt, "Camera & Time Context", "append")

        assert insert_type == "section_end"


# =============================================================================
# Property-Based Tests (Hypothesis)
# =============================================================================

from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from backend.tests.strategies import variable_names

# Variable names matching the prompt_parser.py regex: [a-z_]+
# Does NOT include digits to match the actual regex pattern in detect_variable_style
variable_names_lowercase = st.from_regex(r"[a-z][a-z_]{0,19}", fullmatch=True)


class TestFindInsertionPointProperties:
    """Property-based tests for find_insertion_point function."""

    @given(
        prompt=st.text(min_size=0, max_size=500),
        section=st.text(min_size=1, max_size=50),
        mode=st.sampled_from(["append", "prepend"]),
    )
    @hypothesis_settings(max_examples=100)
    def test_insertion_point_within_bounds(self, prompt: str, section: str, mode: str) -> None:
        """Property: Insertion point is always within prompt bounds."""
        idx, _insert_type = find_insertion_point(prompt, section, mode)
        assert 0 <= idx <= len(prompt)

    @given(
        prompt=st.text(min_size=0, max_size=500),
        section=st.text(min_size=1, max_size=50),
    )
    @hypothesis_settings(max_examples=50)
    def test_insertion_type_is_valid(self, prompt: str, section: str) -> None:
        """Property: Insertion type is one of the valid values."""
        _idx, insert_type = find_insertion_point(prompt, section)
        assert insert_type in ["section_end", "section_start", "fallback"]

    @given(
        prompt=st.text(min_size=0, max_size=500),
        section=st.text(min_size=1, max_size=50),
    )
    @hypothesis_settings(max_examples=50)
    def test_insertion_point_is_deterministic(self, prompt: str, section: str) -> None:
        """Property: Same inputs produce same outputs."""
        result1 = find_insertion_point(prompt, section)
        result2 = find_insertion_point(prompt, section)
        assert result1 == result2

    @given(section=st.text(min_size=1, max_size=30))
    @hypothesis_settings(max_examples=50)
    def test_empty_prompt_always_returns_fallback(self, section: str) -> None:
        """Property: Empty prompt always returns fallback at position 0."""
        idx, insert_type = find_insertion_point("", section)
        assert idx == 0
        assert insert_type == "fallback"


class TestDetectVariableStyleProperties:
    """Property-based tests for detect_variable_style function."""

    @given(prompt=st.text(min_size=0, max_size=500))
    @hypothesis_settings(max_examples=100)
    def test_always_returns_valid_structure(self, prompt: str) -> None:
        """Property: Always returns a dict with expected keys."""
        result = detect_variable_style(prompt)
        assert isinstance(result, dict)
        assert "format" in result
        assert "label_style" in result
        assert "indentation" in result

    @given(prompt=st.text(min_size=0, max_size=500))
    @hypothesis_settings(max_examples=100)
    def test_format_is_valid_value(self, prompt: str) -> None:
        """Property: Format is one of the valid values."""
        result = detect_variable_style(prompt)
        assert result["format"] in ["curly", "angle", "dollar", "none"]

    @given(prompt=st.text(min_size=0, max_size=500))
    @hypothesis_settings(max_examples=100)
    def test_label_style_is_valid_value(self, prompt: str) -> None:
        """Property: Label style is one of the valid values."""
        result = detect_variable_style(prompt)
        assert result["label_style"] in ["colon", "equals", "none"]

    @given(prompt=st.text(min_size=0, max_size=500))
    @hypothesis_settings(max_examples=50)
    def test_detection_is_deterministic(self, prompt: str) -> None:
        """Property: Same input produces same output."""
        result1 = detect_variable_style(prompt)
        result2 = detect_variable_style(prompt)
        assert result1 == result2

    @given(var_name=variable_names_lowercase)
    @hypothesis_settings(max_examples=50)
    def test_curly_brace_detection(self, var_name: str) -> None:
        """Property: Curly braces are detected."""
        prompt = f"Label: {{{var_name}}}"
        result = detect_variable_style(prompt)
        assert result["format"] == "curly"

    @given(var_name=variable_names_lowercase)
    @hypothesis_settings(max_examples=50)
    def test_angle_bracket_detection(self, var_name: str) -> None:
        """Property: Angle brackets are detected."""
        prompt = f"Label: <{var_name}>"
        result = detect_variable_style(prompt)
        assert result["format"] == "angle"

    @given(var_name=variable_names_lowercase)
    @hypothesis_settings(max_examples=50)
    def test_dollar_sign_detection(self, var_name: str) -> None:
        """Property: Dollar sign is detected."""
        prompt = f"Label: ${var_name}"
        result = detect_variable_style(prompt)
        assert result["format"] == "dollar"


class TestGenerateInsertionTextProperties:
    """Property-based tests for generate_insertion_text function."""

    @given(
        label=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
        variable=variable_names,
        fmt=st.sampled_from(["curly", "angle", "dollar", "none"]),
        label_style=st.sampled_from(["colon", "equals", "none"]),
        indent=st.text(alphabet=" \t", max_size=8),
    )
    @hypothesis_settings(max_examples=100)
    def test_generated_text_ends_with_newline(
        self,
        label: str,
        variable: str,
        fmt: str,
        label_style: str,
        indent: str,
    ) -> None:
        """Property: Generated text always ends with newline."""
        style = {"format": fmt, "label_style": label_style, "indentation": indent}
        result = generate_insertion_text(label, variable, style)
        assert result.endswith("\n")

    @given(
        label=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
        variable=variable_names,
    )
    @hypothesis_settings(max_examples=100)
    def test_generated_text_contains_label(self, label: str, variable: str) -> None:
        """Property: Generated text contains the label."""
        style = {"format": "curly", "label_style": "colon", "indentation": ""}
        result = generate_insertion_text(label, variable, style)
        assert label in result

    @given(
        label=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
        variable=variable_names,
    )
    @hypothesis_settings(max_examples=100)
    def test_generated_text_contains_variable(self, label: str, variable: str) -> None:
        """Property: Generated text contains the variable."""
        style = {"format": "curly", "label_style": "colon", "indentation": ""}
        result = generate_insertion_text(label, variable, style)
        assert variable in result

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
        indent=st.text(alphabet=" \t", min_size=1, max_size=4),
    )
    @hypothesis_settings(max_examples=50)
    def test_generated_text_starts_with_indentation(
        self, label: str, variable: str, indent: str
    ) -> None:
        """Property: Generated text starts with specified indentation."""
        style = {"format": "curly", "label_style": "colon", "indentation": indent}
        result = generate_insertion_text(label, variable, style)
        assert result.startswith(indent)

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
    )
    @hypothesis_settings(max_examples=50)
    def test_curly_format_produces_braces(self, label: str, variable: str) -> None:
        """Property: Curly format produces curly braces."""
        style = {"format": "curly", "label_style": "colon", "indentation": ""}
        result = generate_insertion_text(label, variable, style)
        assert f"{{{variable}}}" in result

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
    )
    @hypothesis_settings(max_examples=50)
    def test_angle_format_produces_brackets(self, label: str, variable: str) -> None:
        """Property: Angle format produces angle brackets."""
        style = {"format": "angle", "label_style": "colon", "indentation": ""}
        result = generate_insertion_text(label, variable, style)
        assert f"<{variable}>" in result

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
    )
    @hypothesis_settings(max_examples=50)
    def test_dollar_format_produces_dollar_sign(self, label: str, variable: str) -> None:
        """Property: Dollar format produces dollar sign."""
        style = {"format": "dollar", "label_style": "colon", "indentation": ""}
        result = generate_insertion_text(label, variable, style)
        assert f"${variable}" in result

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
    )
    @hypothesis_settings(max_examples=50)
    def test_colon_style_produces_colon_separator(self, label: str, variable: str) -> None:
        """Property: Colon label style produces colon separator."""
        style = {"format": "curly", "label_style": "colon", "indentation": ""}
        result = generate_insertion_text(label, variable, style)
        assert ": " in result

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
    )
    @hypothesis_settings(max_examples=50)
    def test_equals_style_produces_equals_separator(self, label: str, variable: str) -> None:
        """Property: Equals label style produces equals separator."""
        style = {"format": "curly", "label_style": "equals", "indentation": ""}
        result = generate_insertion_text(label, variable, style)
        assert "=" in result
        assert ": " not in result


class TestValidatePromptSyntaxProperties:
    """Property-based tests for validate_prompt_syntax function."""

    @given(prompt=st.text(min_size=0, max_size=500))
    @hypothesis_settings(max_examples=100)
    def test_always_returns_list(self, prompt: str) -> None:
        """Property: Always returns a list."""
        result = validate_prompt_syntax(prompt)
        assert isinstance(result, list)

    @given(prompt=st.text(min_size=0, max_size=500))
    @hypothesis_settings(max_examples=100)
    def test_all_warnings_are_strings(self, prompt: str) -> None:
        """Property: All warnings are strings."""
        result = validate_prompt_syntax(prompt)
        assert all(isinstance(w, str) for w in result)

    @given(n=st.integers(min_value=1, max_value=10))
    @hypothesis_settings(max_examples=50)
    def test_balanced_braces_no_brace_warning(self, n: int) -> None:
        """Property: Balanced braces produce no brace warnings."""
        # Generate prompt with n balanced brace pairs
        prompt = " ".join(f"Var{i}: {{var{i}}}" for i in range(n))
        warnings = validate_prompt_syntax(prompt)
        brace_warnings = [w for w in warnings if "braces" in w.lower()]
        assert len(brace_warnings) == 0

    @given(n=st.integers(min_value=1, max_value=10))
    @hypothesis_settings(max_examples=50)
    def test_unbalanced_braces_produce_warning(self, n: int) -> None:
        """Property: Unbalanced braces produce warnings."""
        # Generate prompt with n open braces but no close braces
        prompt = " ".join(f"Var{i}: {{var{i}" for i in range(n))
        warnings = validate_prompt_syntax(prompt)
        brace_warnings = [w for w in warnings if "braces" in w.lower()]
        assert len(brace_warnings) == 1
        assert f"{n} open" in brace_warnings[0]

    @given(var_name=variable_names_lowercase)
    @hypothesis_settings(max_examples=50)
    def test_duplicate_variable_produces_warning(self, var_name: str) -> None:
        """Property: Duplicate variables produce warnings."""
        prompt = f"A: {{{var_name}}}\nB: {{{var_name}}}"
        warnings = validate_prompt_syntax(prompt)
        dup_warnings = [w for w in warnings if "Duplicate" in w]
        assert len(dup_warnings) == 1
        assert var_name in dup_warnings[0]

    @given(
        var_names=st.lists(variable_names_lowercase, min_size=1, max_size=5, unique=True),
    )
    @hypothesis_settings(max_examples=50)
    def test_unique_variables_no_duplicate_warning(self, var_names: list[str]) -> None:
        """Property: Unique variables produce no duplicate warnings."""
        prompt = "\n".join(f"Var{i}: {{{v}}}" for i, v in enumerate(var_names))
        warnings = validate_prompt_syntax(prompt)
        dup_warnings = [w for w in warnings if "Duplicate" in w]
        assert len(dup_warnings) == 0

    def test_empty_prompt_is_valid(self) -> None:
        """Property: Empty prompt produces no warnings."""
        warnings = validate_prompt_syntax("")
        assert warnings == []


class TestApplySuggestionProperties:
    """Property-based tests for apply_suggestion_to_prompt function."""

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
        section=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        mode=st.sampled_from(["append", "prepend"]),
    )
    @hypothesis_settings(max_examples=100)
    def test_result_contains_new_variable(
        self,
        label: str,
        variable: str,
        section: str,
        mode: str,
    ) -> None:
        """Property: Result always contains the new variable."""
        prompt = f"## {section}\nExisting: {{existing}}\n## Other\n"
        result = apply_suggestion_to_prompt(prompt, section, mode, label, variable)
        assert variable in result

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
        section=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
    )
    @hypothesis_settings(max_examples=50)
    def test_result_preserves_original_content(
        self,
        label: str,
        variable: str,
        section: str,
    ) -> None:
        """Property: Result preserves original prompt content."""
        original_var = "existing_var"
        prompt = f"## {section}\nExisting: {{{original_var}}}\n## Other\nOther: {{other}}\n"
        result = apply_suggestion_to_prompt(prompt, section, "append", label, variable)
        assert original_var in result
        assert "other" in result.lower()

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
    )
    @hypothesis_settings(max_examples=50)
    def test_empty_prompt_produces_valid_result(
        self,
        label: str,
        variable: str,
    ) -> None:
        """Property: Applying to empty prompt produces valid result."""
        result = apply_suggestion_to_prompt("", "AnySection", "append", label, variable)
        assert len(result) > 0
        assert variable in result
        assert result.endswith("\n")

    @given(
        label=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        variable=variable_names,
    )
    @hypothesis_settings(max_examples=50)
    def test_result_is_longer_than_original(
        self,
        label: str,
        variable: str,
    ) -> None:
        """Property: Result is always longer than the original prompt."""
        prompt = "## Section\nContent: {var}\n"
        result = apply_suggestion_to_prompt(prompt, "Section", "append", label, variable)
        assert len(result) > len(prompt)


class TestPromptOperationsIdempotence:
    """Property-based tests for idempotence of prompt operations."""

    @given(prompt=st.text(min_size=0, max_size=200))
    @hypothesis_settings(max_examples=50)
    def test_detect_style_is_idempotent(self, prompt: str) -> None:
        """Property: detect_variable_style is idempotent."""
        result1 = detect_variable_style(prompt)
        result2 = detect_variable_style(prompt)
        assert result1 == result2

    @given(prompt=st.text(min_size=0, max_size=200))
    @hypothesis_settings(max_examples=50)
    def test_validate_syntax_is_idempotent(self, prompt: str) -> None:
        """Property: validate_prompt_syntax is idempotent."""
        result1 = validate_prompt_syntax(prompt)
        result2 = validate_prompt_syntax(prompt)
        assert result1 == result2

    @given(
        prompt=st.text(min_size=0, max_size=200),
        section=st.text(min_size=1, max_size=30),
    )
    @hypothesis_settings(max_examples=50)
    def test_find_insertion_is_idempotent(self, prompt: str, section: str) -> None:
        """Property: find_insertion_point is idempotent."""
        result1 = find_insertion_point(prompt, section)
        result2 = find_insertion_point(prompt, section)
        assert result1 == result2
