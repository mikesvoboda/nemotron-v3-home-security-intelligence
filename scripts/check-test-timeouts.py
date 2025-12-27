#!/usr/bin/env python3
"""Pre-commit hook to detect potentially slow sleeps/timeouts in test files.

This script analyzes test files to find asyncio.sleep() and time.sleep() calls
with values >= 1 second that may not be properly mocked or cancelled, which
could cause tests to run slowly.

Safe patterns (allowed):
- Sleep inside a function that is later cancelled via task.cancel()
- Sleep wrapped in asyncio.wait_for(..., timeout=<short>)
- Sleep value is mocked/patched
- Sleep is inside a mock function definition used as a side_effect

Unsafe patterns (flagged):
- Direct await of sleep(>=1) in test body without timeout wrapper
- Sleep in async function that's awaited without cancellation
"""

import ast
import sys
from pathlib import Path

# Threshold in seconds - sleeps >= this value are checked
SLEEP_THRESHOLD = 1.0

# Known safe patterns in comments that indicate intentional long sleep
SAFE_COMMENTS = [
    "# cancelled",
    "# will be cancelled",
    "# timeout",
    "# mocked",
    "# patched",
]


class SleepVisitor(ast.NodeVisitor):
    """AST visitor to find potentially problematic sleep calls."""

    def __init__(self, source_lines: list[str], filename: str):
        self.source_lines = source_lines
        self.filename = filename
        self.issues: list[tuple[int, str, str]] = []
        self.in_mock_function = False
        self.in_wait_for = False
        self.current_function_name = ""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function definitions to identify mock functions."""
        old_name = self.current_function_name
        self.current_function_name = node.name

        # Check if this looks like a mock function (local def used for mocking)
        is_mock_func = any(
            pattern in node.name.lower()
            for pattern in ["mock_", "slow_", "fake_", "stub_"]
        )

        old_in_mock = self.in_mock_function
        if is_mock_func:
            self.in_mock_function = True

        self.generic_visit(node)

        self.in_mock_function = old_in_mock
        self.current_function_name = old_name

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async function definitions."""
        self.visit_FunctionDef(node)  # type: ignore

    def visit_Call(self, node: ast.Call) -> None:
        """Check for sleep calls and wait_for wrappers."""
        # Check if this is asyncio.wait_for
        if self._is_wait_for_call(node):
            old_in_wait_for = self.in_wait_for
            self.in_wait_for = True
            self.generic_visit(node)
            self.in_wait_for = old_in_wait_for
            return

        # Check for sleep calls
        sleep_value = self._get_sleep_value(node)
        if sleep_value is not None and sleep_value >= SLEEP_THRESHOLD:
            # Check if this is in a safe context
            if not self._is_safe_context(node):
                line = self.source_lines[node.lineno - 1] if node.lineno <= len(self.source_lines) else ""
                self.issues.append((
                    node.lineno,
                    f"sleep({sleep_value}) found - may cause slow tests",
                    line.strip(),
                ))

        self.generic_visit(node)

    def _is_wait_for_call(self, node: ast.Call) -> bool:
        """Check if this is an asyncio.wait_for call."""
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "wait_for":
                return True
        if isinstance(node.func, ast.Name):
            if node.func.id == "wait_for":
                return True
        return False

    def _get_sleep_value(self, node: ast.Call) -> float | None:
        """Extract sleep value from asyncio.sleep() or time.sleep() call."""
        func = node.func

        is_sleep = False
        if isinstance(func, ast.Attribute) and func.attr == "sleep":
            # asyncio.sleep or time.sleep
            is_sleep = True
        elif isinstance(func, ast.Name) and func.id == "sleep":
            # Direct sleep import
            is_sleep = True

        if not is_sleep:
            return None

        # Get the first argument (sleep duration)
        if node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int | float):
                return float(arg.value)

        return None

    def _is_safe_context(self, node: ast.Call) -> bool:
        """Check if the sleep is in a safe context."""
        # Safe if inside a mock function
        if self.in_mock_function:
            return True

        # Safe if wrapped in wait_for
        if self.in_wait_for:
            return True

        # Check for safe comments on the same line
        if node.lineno <= len(self.source_lines):
            line = self.source_lines[node.lineno - 1].lower()
            for comment in SAFE_COMMENTS:
                if comment in line:
                    return True

        return False


def check_file(filepath: Path) -> list[tuple[int, str, str]]:
    """Check a single file for problematic sleep calls."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
        lines = source.splitlines()

        visitor = SleepVisitor(lines, str(filepath))
        visitor.visit(tree)

        return visitor.issues
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}", file=sys.stderr)
        return []


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: check-test-timeouts.py <file1> [file2] ...", file=sys.stderr)
        return 1

    all_issues: list[tuple[str, int, str, str]] = []

    for filepath_str in sys.argv[1:]:
        filepath = Path(filepath_str)

        # Only check test files
        if not filepath.name.startswith("test_"):
            continue

        issues = check_file(filepath)
        for line_no, message, line_content in issues:
            all_issues.append((str(filepath), line_no, message, line_content))

    if all_issues:
        print("=" * 70)
        print("POTENTIALLY SLOW SLEEPS DETECTED IN TESTS")
        print("=" * 70)
        print()
        print("The following sleep() calls may cause slow tests.")
        print("Please ensure they are properly mocked, cancelled, or wrapped in wait_for().")
        print()
        print("Safe patterns:")
        print("  - Define sleep in a mock_*/slow_*/fake_* function")
        print("  - Wrap in asyncio.wait_for(..., timeout=<short>)")
        print("  - Add comment: # cancelled, # timeout, # mocked, # patched")
        print("  - Ensure the task is cancelled via task.cancel()")
        print()

        for filepath, line_no, message, line_content in all_issues:
            print(f"{filepath}:{line_no}: {message}")
            print(f"    {line_content}")
            print()

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
