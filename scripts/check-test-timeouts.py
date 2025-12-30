#!/usr/bin/env python3
"""Pre-commit hook to detect potentially slow patterns in test files.

This script analyzes test files to find:
1. asyncio.sleep() and time.sleep() calls >= 1 second without mocking
2. HTTP library calls without mocking (requests, httpx, urllib, aiohttp)
3. subprocess calls without mocking

Safe patterns (allowed):
- Sleep inside a function that is later cancelled via task.cancel()
- Sleep wrapped in asyncio.wait_for(..., timeout=<short>)
- Sleep/HTTP/subprocess value is mocked/patched
- Pattern is inside a mock function definition used as a side_effect
- Mock context detected in surrounding code

Unsafe patterns (flagged):
- Direct await of sleep(>=1) in test body without timeout wrapper
- Real HTTP calls to external services
- Subprocess calls that spawn real processes
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

# HTTP libraries that should be mocked in tests
HTTP_LIBRARIES = {
    "requests": ["get", "post", "put", "patch", "delete", "head", "options", "request"],
    "httpx": ["get", "post", "put", "patch", "delete", "head", "options", "request"],
    "urllib.request": ["urlopen", "urlretrieve"],
    "aiohttp": ["ClientSession"],
}

# Subprocess calls that should be mocked
SUBPROCESS_CALLS = [
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_output",
    "subprocess.check_call",
    "subprocess.Popen",
    "os.system",
    "os.popen",
]

# Patterns in mock context that indicate proper mocking
MOCK_PATTERNS = [
    "mocker.patch",
    "mock.patch",
    "patch(",
    "@patch",
    "MagicMock",
    "AsyncMock",
    "Mock(",
    "responses.add",
    "httpretty",
    "respx",
    "aioresponses",
]


class SlowPatternVisitor(ast.NodeVisitor):
    """AST visitor to find potentially slow patterns in tests."""

    def __init__(self, source_lines: list[str], filename: str, source: str):
        self.source_lines = source_lines
        self.filename = filename
        self.source = source
        self.issues: list[tuple[int, str, str]] = []
        self.in_mock_function = False
        self.in_wait_for = False
        self.current_function_name = ""
        self.imported_modules: set[str] = set()
        self.has_mock_context = self._check_mock_context()

    def _check_mock_context(self) -> bool:
        """Check if file has mock imports/decorators."""
        return any(pattern in self.source for pattern in MOCK_PATTERNS)

    def visit_Import(self, node: ast.Import) -> None:
        """Track imports."""
        for alias in node.names:
            self.imported_modules.add(alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track from imports."""
        if node.module:
            self.imported_modules.add(node.module.split(".")[0])
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function definitions to identify mock functions."""
        old_name = self.current_function_name
        self.current_function_name = node.name

        is_mock_func = any(
            pattern in node.name.lower() for pattern in ["mock_", "slow_", "fake_", "stub_"]
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
        """Check for slow patterns: sleep, HTTP calls, subprocess."""
        # Check wait_for wrapper
        if self._is_wait_for_call(node):
            old_in_wait_for = self.in_wait_for
            self.in_wait_for = True
            self.generic_visit(node)
            self.in_wait_for = old_in_wait_for
            return

        # Check sleep calls
        sleep_value = self._get_sleep_value(node)
        if sleep_value is not None and sleep_value >= SLEEP_THRESHOLD:
            if not self._is_safe_context(node):
                line = self._get_line(node.lineno)
                self.issues.append(
                    (
                        node.lineno,
                        f"sleep({sleep_value}) - may cause slow tests",
                        line.strip(),
                    )
                )

        # Check HTTP library calls
        http_issue = self._check_http_call(node)
        if http_issue and not self._is_safe_context(node):
            line = self._get_line(node.lineno)
            self.issues.append((node.lineno, http_issue, line.strip()))

        # Check subprocess calls
        subprocess_issue = self._check_subprocess_call(node)
        if subprocess_issue and not self._is_safe_context(node):
            line = self._get_line(node.lineno)
            self.issues.append((node.lineno, subprocess_issue, line.strip()))

        self.generic_visit(node)

    def _get_line(self, lineno: int) -> str:
        """Safely get a source line."""
        if lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1]
        return ""

    def _is_wait_for_call(self, node: ast.Call) -> bool:
        """Check if this is an asyncio.wait_for call."""
        return (isinstance(node.func, ast.Attribute) and node.func.attr == "wait_for") or (
            isinstance(node.func, ast.Name) and node.func.id == "wait_for"
        )

    def _get_sleep_value(self, node: ast.Call) -> float | None:
        """Extract sleep value from asyncio.sleep() or time.sleep() call."""
        func = node.func
        is_sleep = False

        if (isinstance(func, ast.Attribute) and func.attr == "sleep") or (
            isinstance(func, ast.Name) and func.id == "sleep"
        ):
            is_sleep = True

        if not is_sleep:
            return None

        if node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int | float):
                return float(arg.value)
        return None

    def _check_http_call(self, node: ast.Call) -> str | None:
        """Check if this is an unmocked HTTP library call."""
        func = node.func

        # Check for module.method pattern (e.g., requests.get)
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                module = func.value.id
                method = func.attr
                if module in HTTP_LIBRARIES:
                    if method in HTTP_LIBRARIES[module]:
                        return f"{module}.{method}() - real HTTP call, should be mocked"

        return None

    def _check_subprocess_call(self, node: ast.Call) -> str | None:
        """Check if this is an unmocked subprocess call."""
        func = node.func

        # Check for module.function pattern
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                full_name = f"{func.value.id}.{func.attr}"
                if full_name in SUBPROCESS_CALLS:
                    return f"{full_name}() - spawns process, should be mocked"

        return None

    def _is_safe_context(self, node: ast.Call) -> bool:
        """Check if the call is in a safe context (mocked, etc.)."""
        if self.in_mock_function:
            return True
        if self.in_wait_for:
            return True

        # Check for safe comments on same line
        if node.lineno <= len(self.source_lines):
            line = self.source_lines[node.lineno - 1].lower()
            if any(comment in line for comment in SAFE_COMMENTS):
                return True

        # Check if this specific call appears to be mocked nearby
        # Look at surrounding lines for patch/mock context
        start_line = max(0, node.lineno - 10)
        end_line = min(len(self.source_lines), node.lineno + 3)
        context = "\n".join(self.source_lines[start_line:end_line])

        return any(pattern in context for pattern in MOCK_PATTERNS)


def check_file(filepath: Path) -> list[tuple[int, str, str]]:
    """Check a single file for slow patterns."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
        lines = source.splitlines()

        visitor = SlowPatternVisitor(lines, str(filepath), source)
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
        print("SLOW TEST PATTERNS DETECTED")
        print("=" * 70)
        print()
        print("The following patterns may cause slow tests:")
        print("  - sleep() calls >= 1 second without mocking")
        print("  - HTTP library calls without mocking (requests, httpx, etc.)")
        print("  - subprocess calls without mocking")
        print()
        print("Safe patterns:")
        print("  - Use mocker.patch() / @patch decorator")
        print("  - Define in mock_*/slow_*/fake_* function")
        print("  - Wrap sleep in asyncio.wait_for(..., timeout=<short>)")
        print("  - Add comment: # mocked, # patched, # cancelled")
        print()

        for filepath, line_no, message, line_content in all_issues:
            print(f"{filepath}:{line_no}: {message}")
            print(f"    {line_content}")
            print()

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
