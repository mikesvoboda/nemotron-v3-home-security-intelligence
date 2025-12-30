# Test Performance Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce test time limits, detect slow tests in CI, catch slow-test anti-patterns at commit time, and enable parallel local testing.

**Architecture:** Layered enforcement - pytest-timeout for runtime limits, CI audit for trend detection, pre-commit for pattern prevention, pytest-xdist for parallel execution.

**Tech Stack:** pytest-timeout, pytest-xdist, JUnit XML, AST parsing, GitHub Actions

---

## Pre-Implementation Notes

**Already in place:**

- `pytest-timeout>=2.3.0` in requirements.txt
- `pytest-xdist>=3.5.0` in requirements.txt
- Basic `--timeout=30` in pyproject.toml
- xdist `loadgroup` scheduling in conftest.py
- `check-test-timeouts.py` for sleep detection

**Key files to modify:**

- `pyproject.toml` - pytest configuration
- `backend/tests/conftest.py` - timeout hook
- `scripts/check-test-timeouts.py` - extend pattern detection
- `.github/workflows/ci.yml` - artifacts and audit job
- New: `scripts/audit-test-durations.py`
- New: `scripts/test-fast.sh`

---

## Task 1: Update pytest Configuration

**Files:**

- Modify: `pyproject.toml:91-106`

**Step 1: Update pyproject.toml pytest settings**

Change the `[tool.pytest.ini_options]` section:

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
# Parallel by default, 1s timeout for unit tests, verbose output
addopts = "-n auto --dist=loadgroup -v --strict-markers --tb=short --timeout=1"
timeout_method = "thread"
markers = [
    "asyncio: mark test as an async test",
    "unit: mark test as a unit test",
    "integration: mark test as an integration test (5s timeout)",
    "e2e: mark test as an end-to-end test",
    "gpu: mark test as a GPU test (runs on self-hosted GPU runner)",
    "slow: mark test as legitimately slow (30s timeout)",
    "timeout(N): override timeout for specific test",
]
```

**Step 2: Run pytest to verify configuration loads**

Run: `cd /Users/msvoboda/github/home_security_intelligence && source .venv/bin/activate && pytest --co -q 2>&1 | head -20`

Expected: Collection output showing tests, no configuration errors

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "perf(tests): configure 1s default timeout and parallel execution

- Default timeout: 1s for unit tests
- Enable pytest-xdist parallel execution (-n auto)
- Use loadgroup distribution for test isolation
- Add 'slow' marker for legitimately slow tests (30s)
- Change timeout_method from signal to thread for xdist compatibility"
```

---

## Task 2: Add Timeout Assignment Hook

**Files:**

- Modify: `backend/tests/conftest.py:83-106`

**Step 1: Add the timeout hook after pytest_configure**

Insert after line 141 (after `pytest_unconfigure`):

```python
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Assign timeouts based on test location and markers.

    Timeout hierarchy (highest priority first):
    1. Explicit @pytest.mark.timeout(N) on test - unchanged
    2. @pytest.mark.slow marker - 30 seconds
    3. Integration tests (in integration/ directory) - 5 seconds
    4. Default from pyproject.toml - 1 second
    """
    import pytest

    for item in items:
        # Skip if test has explicit timeout marker
        if item.get_closest_marker("timeout"):
            continue

        # Slow-marked tests get 30s
        if item.get_closest_marker("slow"):
            item.add_marker(pytest.mark.timeout(30))
            continue

        # Integration tests get 5s
        if "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.timeout(5))
            continue

        # Unit tests use default (1s from pyproject.toml)
```

**Step 2: Run a quick test to verify hook works**

Run: `cd /Users/msvoboda/github/home_security_intelligence && source .venv/bin/activate && pytest backend/tests/unit/test_config.py -v --timeout-show 2>&1 | head -30`

Expected: Tests run with timeout information visible

**Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "perf(tests): add timeout assignment hook

- Integration tests: 5s timeout
- @pytest.mark.slow tests: 30s timeout
- Unit tests: 1s default (from pyproject.toml)
- Explicit @pytest.mark.timeout(N) takes precedence"
```

---

## Task 3: Create CI Timing Audit Script

**Files:**

- Create: `scripts/audit-test-durations.py`

**Step 1: Write the audit script**

```python
#!/usr/bin/env python3
"""Analyze JUnit XML test results and flag slow tests.

This script parses JUnit XML files from CI test runs and:
1. Identifies tests exceeding their category threshold
2. Warns about tests approaching the threshold (>80%)
3. Exits non-zero if any test exceeds its limit

Usage:
    python scripts/audit-test-durations.py <results-dir>

Environment variables:
    UNIT_TEST_THRESHOLD: Max seconds for unit tests (default: 1.0)
    INTEGRATION_TEST_THRESHOLD: Max seconds for integration tests (default: 5.0)
    WARN_THRESHOLD_PERCENT: Warn at this % of limit (default: 80)
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def get_thresholds() -> tuple[float, float, float]:
    """Get threshold values from environment or defaults."""
    unit = float(os.environ.get("UNIT_TEST_THRESHOLD", "1.0"))
    integration = float(os.environ.get("INTEGRATION_TEST_THRESHOLD", "5.0"))
    warn_pct = float(os.environ.get("WARN_THRESHOLD_PERCENT", "80")) / 100
    return unit, integration, warn_pct


def categorize_test(classname: str, name: str) -> str:
    """Determine if a test is unit or integration based on path."""
    full_path = f"{classname}.{name}".lower()
    if "integration" in full_path:
        return "integration"
    return "unit"


def parse_junit_xml(filepath: Path) -> list[dict]:
    """Parse a JUnit XML file and extract test timing data."""
    tests = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        # Handle both <testsuites> and <testsuite> root elements
        if root.tag == "testsuites":
            testsuites = root.findall("testsuite")
        else:
            testsuites = [root]

        for testsuite in testsuites:
            for testcase in testsuite.findall("testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_str = testcase.get("time", "0")

                try:
                    duration = float(time_str)
                except ValueError:
                    duration = 0.0

                # Skip tests with 0 duration (likely skipped)
                if duration > 0:
                    tests.append({
                        "classname": classname,
                        "name": name,
                        "duration": duration,
                        "category": categorize_test(classname, name),
                        "file": str(filepath),
                    })
    except ET.ParseError as e:
        print(f"Warning: Could not parse {filepath}: {e}", file=sys.stderr)

    return tests


def analyze_tests(results_dir: Path) -> tuple[list[dict], list[dict]]:
    """Analyze all JUnit XML files in directory."""
    unit_threshold, integration_threshold, warn_pct = get_thresholds()

    failures = []
    warnings = []

    # Find all XML files
    xml_files = list(results_dir.glob("**/*.xml"))
    if not xml_files:
        print(f"Warning: No XML files found in {results_dir}", file=sys.stderr)
        return [], []

    for xml_file in xml_files:
        tests = parse_junit_xml(xml_file)

        for test in tests:
            # Determine threshold based on category
            if test["category"] == "integration":
                threshold = integration_threshold
            else:
                threshold = unit_threshold

            test["threshold"] = threshold

            # Check if exceeds threshold
            if test["duration"] > threshold:
                failures.append(test)
            # Check if approaching threshold
            elif test["duration"] > threshold * warn_pct:
                warnings.append(test)

    # Sort by duration descending
    failures.sort(key=lambda x: x["duration"], reverse=True)
    warnings.sort(key=lambda x: x["duration"], reverse=True)

    return failures, warnings


def format_test_name(test: dict) -> str:
    """Format test name for display."""
    return f"{test['classname']}::{test['name']}"


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: audit-test-durations.py <results-dir>", file=sys.stderr)
        return 1

    results_dir = Path(sys.argv[1])
    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}", file=sys.stderr)
        return 1

    failures, warnings = analyze_tests(results_dir)

    print("=" * 70)
    print("TEST PERFORMANCE AUDIT")
    print("=" * 70)
    print()

    unit_threshold, integration_threshold, warn_pct = get_thresholds()
    print(f"Thresholds: unit={unit_threshold}s, integration={integration_threshold}s")
    print(f"Warning at: {warn_pct * 100:.0f}% of threshold")
    print()

    if failures:
        print("FAILURES (exceeded threshold):")
        print("-" * 40)
        for test in failures:
            print(
                f"  {test['duration']:.2f}s (limit: {test['threshold']:.1f}s) "
                f"[{test['category']}]"
            )
            print(f"    {format_test_name(test)}")
        print()

    if warnings:
        print("WARNINGS (>80% of threshold):")
        print("-" * 40)
        for test in warnings:
            pct = (test["duration"] / test["threshold"]) * 100
            print(
                f"  {test['duration']:.2f}s ({pct:.0f}% of {test['threshold']:.1f}s) "
                f"[{test['category']}]"
            )
            print(f"    {format_test_name(test)}")
        print()

    # Summary
    print("=" * 70)
    if failures:
        print(f"RESULT: FAIL - {len(failures)} test(s) exceeded time limit")
        return 1
    elif warnings:
        print(f"RESULT: PASS with {len(warnings)} warning(s)")
        return 0
    else:
        print("RESULT: PASS - All tests within time limits")
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Make script executable and test with sample XML**

Run: `chmod +x scripts/audit-test-durations.py`

**Step 3: Commit**

```bash
git add scripts/audit-test-durations.py
git commit -m "feat(ci): add test duration audit script

Parses JUnit XML from CI runs to detect slow tests:
- Fails if any test exceeds category threshold
- Warns at 80% of threshold
- Configurable via environment variables"
```

---

## Task 4: Extend Pre-commit Pattern Detection

**Files:**

- Modify: `scripts/check-test-timeouts.py`

**Step 1: Add HTTP and subprocess detection**

Add these constants after line 33 (after `SAFE_COMMENTS`):

```python
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
```

**Step 2: Update SleepVisitor to track imports and detect HTTP/subprocess**

Replace the `SleepVisitor` class with an extended version:

```python
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
                self.issues.append((
                    node.lineno,
                    f"sleep({sleep_value}) - may cause slow tests",
                    line.strip(),
                ))

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
        if isinstance(node.func, ast.Attribute) and node.func.attr == "wait_for":
            return True
        if isinstance(node.func, ast.Name) and node.func.id == "wait_for":
            return True
        return False

    def _get_sleep_value(self, node: ast.Call) -> float | None:
        """Extract sleep value from asyncio.sleep() or time.sleep() call."""
        func = node.func
        is_sleep = False

        if isinstance(func, ast.Attribute) and func.attr == "sleep":
            is_sleep = True
        elif isinstance(func, ast.Name) and func.id == "sleep":
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
            for comment in SAFE_COMMENTS:
                if comment in line:
                    return True

        # Check if this specific call appears to be mocked nearby
        # Look at surrounding lines for patch/mock context
        start_line = max(0, node.lineno - 10)
        end_line = min(len(self.source_lines), node.lineno + 3)
        context = "\n".join(self.source_lines[start_line:end_line])

        for pattern in MOCK_PATTERNS:
            if pattern in context:
                return True

        return False
```

**Step 3: Update check_file function**

Replace the `check_file` function:

```python
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
```

**Step 4: Update main function output messages**

Update the print statements in `main()` to reflect the broader scope:

```python
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
```

**Step 5: Run the updated script on existing tests**

Run: `python scripts/check-test-timeouts.py backend/tests/unit/test_*.py`

Expected: Either passes or shows legitimate issues to address

**Step 6: Commit**

```bash
git add scripts/check-test-timeouts.py
git commit -m "feat(pre-commit): extend slow pattern detection

Now detects:
- HTTP library calls without mocking (requests, httpx, urllib, aiohttp)
- subprocess calls without mocking
- Sleep calls >= 1s without mocking

Recognizes mock context from surrounding code to reduce false positives."
```

---

## Task 5: Update CI Workflow for JUnit XML Artifacts

**Files:**

- Modify: `.github/workflows/ci.yml`

**Step 1: Update unit-tests job to output JUnit XML**

In the `unit-tests` job, update the pytest command (around line 115-124):

```yaml
- name: Run unit tests with coverage
  run: |
    pytest backend/tests/unit/ \
      --cov=backend \
      --cov-config=pyproject.toml \
      --cov-report=xml:coverage-unit.xml \
      --cov-report=term-missing \
      --cov-fail-under=92 \
      --junit-xml=test-results-unit.xml \
      --durations=20 \
      -v

- name: Upload unit test results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: test-results-unit
    path: test-results-unit.xml
    retention-days: 7
```

**Step 2: Update integration-tests job similarly**

In the `integration-tests` job, update the pytest command (around line 211-224):

```yaml
- name: Run integration tests with coverage
  run: |
    pytest backend/tests/integration/ \
      --cov=backend \
      --cov-report=xml:coverage-integration.xml \
      --cov-report=term-missing \
      --cov-fail-under=50 \
      --junit-xml=test-results-integration.xml \
      --durations=20 \
      -v

- name: Upload integration test results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: test-results-integration
    path: test-results-integration.xml
    retention-days: 7
```

**Step 3: Update frontend-tests job**

In the `frontend-tests` job, update to output JUnit XML (around line 326):

```yaml
- name: Run tests with coverage
  run: cd frontend && npm run test:coverage -- --run --reporter=junit --outputFile=test-results-frontend.xml

- name: Upload frontend test results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: test-results-frontend
    path: frontend/test-results-frontend.xml
    retention-days: 7
```

**Step 4: Add the test-performance-audit job**

Add after the `security-validation` job (around line 560):

```yaml
# ============================================================================
# Test Performance Audit Job
# ============================================================================

test-performance-audit:
  name: Test Performance Audit
  runs-on: ubuntu-latest
  needs: [unit-tests, integration-tests, frontend-tests]
  if: always() && (needs.unit-tests.result == 'success' || needs.integration-tests.result == 'success')
  steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_VERSION }}

    - name: Download all test results
      uses: actions/download-artifact@v4
      with:
        pattern: test-results-*
        path: test-results/
        merge-multiple: true

    - name: List downloaded artifacts
      run: find test-results/ -type f -name "*.xml" | head -20

    - name: Analyze test durations
      run: python scripts/audit-test-durations.py test-results/
      env:
        UNIT_TEST_THRESHOLD: "1.0"
        INTEGRATION_TEST_THRESHOLD: "5.0"
        WARN_THRESHOLD_PERCENT: "80"
```

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "feat(ci): add test performance audit job

- Unit/integration tests now output JUnit XML
- New audit job analyzes test durations
- Fails CI if any test exceeds category threshold
- Warns at 80% of threshold for early detection"
```

---

## Task 6: Create Local Test Runner Script

**Files:**

- Create: `scripts/test-fast.sh`

**Step 1: Write the script**

```bash
#!/bin/bash
# Fast parallel test runner with timing report
#
# Usage:
#   ./scripts/test-fast.sh                    # Run all unit tests
#   ./scripts/test-fast.sh backend/tests/     # Run specific path
#   ./scripts/test-fast.sh unit 8             # Run unit tests with 8 workers
#   ./scripts/test-fast.sh integration        # Run integration tests
#
set -e

# Parse arguments
TARGET="${1:-unit}"
WORKERS="${2:-auto}"

# Map shorthand to full paths
case "$TARGET" in
    unit)
        TARGET_PATH="backend/tests/unit/"
        ;;
    integration)
        TARGET_PATH="backend/tests/integration/"
        ;;
    all)
        TARGET_PATH="backend/tests/"
        ;;
    *)
        TARGET_PATH="$TARGET"
        ;;
esac

echo "========================================"
echo "Fast Parallel Test Runner"
echo "========================================"
echo "Target: $TARGET_PATH"
echo "Workers: $WORKERS"
echo "========================================"
echo

# Activate virtual environment if not already active
if [[ -z "$VIRTUAL_ENV" ]]; then
    if [[ -f ".venv/bin/activate" ]]; then
        source .venv/bin/activate
    fi
fi

# Run tests with parallel execution and timing
pytest "$TARGET_PATH" \
    -n "$WORKERS" \
    --dist=loadgroup \
    --durations=20 \
    -v \
    "${@:3}"

echo
echo "========================================"
echo "Test run complete"
echo "========================================"
```

**Step 2: Make executable**

Run: `chmod +x scripts/test-fast.sh`

**Step 3: Test the script**

Run: `./scripts/test-fast.sh unit 4 --co -q`

Expected: Shows test collection with parallel info

**Step 4: Commit**

```bash
git add scripts/test-fast.sh
git commit -m "feat(scripts): add fast parallel test runner

Usage:
  ./scripts/test-fast.sh              # All unit tests, auto workers
  ./scripts/test-fast.sh integration  # Integration tests
  ./scripts/test-fast.sh unit 8       # Unit tests with 8 workers"
```

---

## Task 7: Run Full Test Suite and Fix Slow Tests

**Files:**

- Various test files that exceed thresholds

**Step 1: Run tests with timing to identify slow tests**

Run: `./scripts/test-fast.sh unit 4 --durations=0 2>&1 | grep -E "^\d+\.\d+s" | sort -rn | head -30`

**Step 2: For each slow test, either:**

a) Add `@pytest.mark.slow` if legitimately slow:

```python
@pytest.mark.slow
def test_complex_batch_processing():
    ...
```

b) Add explicit timeout if needs more than 1s but less than 30s:

```python
@pytest.mark.timeout(3)
def test_moderate_operation():
    ...
```

c) Fix the test to be faster (mock slow operations)

**Step 3: Re-run and verify all tests pass**

Run: `./scripts/test-fast.sh unit`

Expected: All tests pass within their time limits

**Step 4: Commit any test fixes**

```bash
git add backend/tests/
git commit -m "fix(tests): add timeout markers to legitimately slow tests"
```

---

## Task 8: Final Validation

**Step 1: Run pre-commit on all files**

Run: `pre-commit run --all-files`

Expected: All hooks pass

**Step 2: Run full test suite**

Run: `./scripts/test-fast.sh all`

Expected: All tests pass

**Step 3: Verify CI workflow syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`

Expected: No errors

**Step 4: Create final commit if needed**

```bash
git status
# If any uncommitted changes:
git add -A
git commit -m "chore: final test performance optimization cleanup"
```

---

## Success Criteria Checklist

- [ ] `pyproject.toml` has 1s default timeout and `-n auto`
- [ ] `conftest.py` assigns 5s to integration, 30s to slow-marked tests
- [ ] `scripts/audit-test-durations.py` exists and parses JUnit XML
- [ ] `scripts/check-test-timeouts.py` detects HTTP/subprocess patterns
- [ ] `scripts/test-fast.sh` runs tests in parallel locally
- [ ] `.github/workflows/ci.yml` uploads JUnit XML and runs audit job
- [ ] All existing tests pass within their time limits
- [ ] `pre-commit run --all-files` passes
