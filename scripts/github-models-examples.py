#!/usr/bin/env python3
"""
GitHub Models Integration Examples

This script demonstrates various ways to use GitHub Models for AI-assisted
development tasks in the Nemotron v3 Home Security Intelligence project.

Usage:
    # Set your GitHub token
    export GH_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

    # Run examples
    python scripts/github-models-examples.py

    # Run specific example
    python scripts/github-models-examples.py --example pr-description
    python scripts/github-models-examples.py --example code-review
    python scripts/github-models-examples.py --example test-generation
    python scripts/github-models-examples.py --example security-analysis

Requirements:
    - requests library (pip install requests)
    - GitHub token with models:read permission
    - gh CLI (optional, for CLI examples)

For more information, see: docs/GITHUB_MODELS.md
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Check for requests library
try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# GitHub Models API endpoint
GITHUB_MODELS_API = "https://models.github.ai/inference/chat/completions"

# Default models
DEFAULT_MODEL = "openai/gpt-4o"
FALLBACK_MODEL = "openai/gpt-4o-mini"
CODE_MODEL = "mistral/codestral-2501"


def get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GH_TOKEN or GITHUB_TOKEN environment variable required")
        print("Set your token with: export GH_TOKEN='ghp_xxxxxxxxxxxxxxxxxxxx'")
        sys.exit(1)
    return token


def call_github_models(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: int = 60,
) -> str:
    """
    Call GitHub Models API.

    Args:
        prompt: User prompt to send
        model: Model identifier (e.g., "openai/gpt-4o")
        system_prompt: Optional system message for context
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum response tokens
        timeout: Request timeout in seconds

    Returns:
        Model response text

    Raises:
        requests.HTTPError: If API call fails
    """
    token = get_github_token()

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = requests.post(
        GITHUB_MODELS_API,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )

    # Handle rate limiting
    if response.status_code == 429:
        print("Rate limited. Waiting 60 seconds...")
        time.sleep(60)
        return call_github_models(prompt, model, system_prompt, temperature, max_tokens, timeout)

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


def call_with_fallback(prompt: str, system_prompt: str | None = None) -> str:
    """Call with automatic fallback to smaller model."""
    try:
        return call_github_models(prompt, model=DEFAULT_MODEL, system_prompt=system_prompt)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (429, 503):
            print(f"Primary model unavailable, falling back to {FALLBACK_MODEL}...")
            return call_github_models(prompt, model=FALLBACK_MODEL, system_prompt=system_prompt)
        raise


# =============================================================================
# Example: PR Description Generation
# =============================================================================


def example_pr_description() -> None:
    """Generate a PR description from git diff."""
    print("\n" + "=" * 60)
    print("Example: PR Description Generation")
    print("=" * 60 + "\n")

    # Get git diff (staged changes or last commit)
    git_path = shutil.which("git") or "/usr/bin/git"
    try:
        diff = subprocess.check_output(  # noqa: S603
            [git_path, "diff", "--cached"],
            cwd=PROJECT_ROOT,
            text=True,
        )
        if not diff.strip():
            diff = subprocess.check_output(  # noqa: S603
                [git_path, "diff", "HEAD~1"],
                cwd=PROJECT_ROOT,
                text=True,
            )
    except subprocess.CalledProcessError:
        diff = "No git diff available (not a git repository or no changes)"

    # Truncate if too large
    if len(diff) > 15000:
        diff = diff[:15000] + "\n... [truncated]"

    system_prompt = """You are a technical writer helping create pull request descriptions.
The project is a home security monitoring dashboard with:
- Backend: Python FastAPI, SQLAlchemy, Redis
- Frontend: React, TypeScript, Tailwind CSS, Tremor
- AI: RT-DETRv2 (object detection), Nemotron (risk analysis)

Generate a clear, concise PR description with:
1. A summary section (2-3 bullet points)
2. What changed and why
3. A test plan section with checkboxes"""

    prompt = f"""Generate a pull request description for these changes:

```diff
{diff}
```"""

    print("Generating PR description...\n")
    response = call_with_fallback(prompt, system_prompt)
    print(response)


# =============================================================================
# Example: Code Review
# =============================================================================


def example_code_review() -> None:
    """Perform AI code review on a file."""
    print("\n" + "=" * 60)
    print("Example: Code Review")
    print("=" * 60 + "\n")

    # Find a Python file to review
    sample_files = [
        PROJECT_ROOT / "backend" / "services" / "batch_aggregator.py",
        PROJECT_ROOT / "backend" / "services" / "detector_client.py",
        PROJECT_ROOT / "backend" / "api" / "routes" / "events.py",
    ]

    code = None
    file_path = None
    for f in sample_files:
        if f.exists():
            code = f.read_text()
            file_path = f
            break

    if not code:
        print("No sample file found for review")
        return

    # Truncate if needed
    if len(code) > 10000:
        code = code[:10000] + "\n# ... [truncated]"

    system_prompt = """You are an expert code reviewer for a home security monitoring application.
The tech stack is:
- Backend: Python FastAPI, SQLAlchemy, Redis
- Frontend: React, TypeScript, Tailwind CSS, Tremor
- AI: RT-DETRv2 (object detection), Nemotron (risk analysis)

Review the code for:
1. **Security Issues**: Vulnerabilities, injection risks, unsafe patterns
2. **Performance**: Bottlenecks, inefficient code, memory leaks
3. **Best Practices**: Code style, naming, architectural concerns
4. **Bugs**: Logic errors, edge cases not handled

Be concise but thorough. Only mention significant issues.
If the code looks good, say so briefly."""

    prompt = f"""Review this code from {file_path.name}:

```python
{code}
```"""

    print(f"Reviewing {file_path.relative_to(PROJECT_ROOT)}...\n")
    response = call_with_fallback(prompt, system_prompt)
    print(response)


# =============================================================================
# Example: Test Generation
# =============================================================================


def example_test_generation() -> None:
    """Generate test cases for a service."""
    print("\n" + "=" * 60)
    print("Example: Test Generation")
    print("=" * 60 + "\n")

    # Find a service file
    service_files = [
        PROJECT_ROOT / "backend" / "services" / "detector_client.py",
        PROJECT_ROOT / "backend" / "services" / "batch_aggregator.py",
        PROJECT_ROOT / "backend" / "services" / "nemotron_analyzer.py",
    ]

    code = None
    file_path = None
    for f in service_files:
        if f.exists():
            code = f.read_text()
            file_path = f
            break

    if not code:
        print("No service file found for test generation")
        return

    # Truncate if needed
    if len(code) > 8000:
        code = code[:8000] + "\n# ... [truncated]"

    system_prompt = """You are a Python testing expert using pytest.
Generate comprehensive test cases including:
- Unit tests for each public method
- Edge cases and error conditions
- Fixture suggestions
- Mock strategies for external dependencies

Use pytest conventions:
- test_ prefix for test functions
- @pytest.fixture for fixtures
- @pytest.mark.parametrize for parameterized tests
- pytest.raises for exception testing"""

    prompt = f"""Generate pytest test cases for this service ({file_path.name}):

```python
{code}
```

Include:
1. Test class with descriptive name
2. Fixtures for common setup
3. Tests for happy path
4. Tests for error cases
5. Tests for edge cases"""

    print(f"Generating tests for {file_path.relative_to(PROJECT_ROOT)}...\n")
    response = call_github_models(
        prompt,
        model=CODE_MODEL,  # Use code-optimized model
        system_prompt=system_prompt,
        max_tokens=3000,
    )
    print(response)


# =============================================================================
# Example: Security Analysis
# =============================================================================


def example_security_analysis() -> None:
    """Perform security analysis on API routes."""
    print("\n" + "=" * 60)
    print("Example: Security Analysis")
    print("=" * 60 + "\n")

    # Find API route files
    routes_dir = PROJECT_ROOT / "backend" / "api" / "routes"
    if not routes_dir.exists():
        print("Routes directory not found")
        return

    # Collect route files
    code_snippets = []
    for route_file in routes_dir.glob("*.py"):
        if route_file.name.startswith("_"):
            continue
        content = route_file.read_text()
        if len(content) > 3000:
            content = content[:3000] + "\n# ... [truncated]"
        code_snippets.append(f"# File: {route_file.name}\n{content}")

    if not code_snippets:
        print("No route files found")
        return

    combined_code = "\n\n".join(code_snippets[:3])  # Limit to 3 files

    system_prompt = """You are a security expert specializing in web application security.
Focus on OWASP Top 10 vulnerabilities:
1. Injection (SQL, Command, etc.)
2. Broken Authentication
3. Sensitive Data Exposure
4. XML External Entities (XXE)
5. Broken Access Control
6. Security Misconfiguration
7. Cross-Site Scripting (XSS)
8. Insecure Deserialization
9. Using Components with Known Vulnerabilities
10. Insufficient Logging & Monitoring

Provide:
- Specific vulnerability found (if any)
- Affected code location
- Risk level (High/Medium/Low)
- Remediation suggestion"""

    prompt = f"""Analyze these FastAPI route files for security vulnerabilities:

```python
{combined_code}
```

Check for:
- SQL injection
- Path traversal
- Command injection
- Missing authentication
- Missing authorization
- Input validation issues
- Sensitive data exposure"""

    print("Analyzing API routes for security issues...\n")
    response = call_with_fallback(prompt, system_prompt)
    print(response)


# =============================================================================
# Example: CLI Usage
# =============================================================================


def example_cli_usage() -> None:
    """Show examples of using gh CLI with models."""
    print("\n" + "=" * 60)
    print("Example: GitHub CLI Usage")
    print("=" * 60 + "\n")

    print("The gh CLI provides a simple way to use GitHub Models.\n")

    examples = [
        (
            "Simple prompt",
            'gh models run openai/gpt-4o "Explain async/await in Python"',
        ),
        (
            "Code review from stdin",
            'cat backend/services/detector_client.py | gh models run openai/gpt-4o "Review this code"',
        ),
        (
            "With system prompt",
            'gh models run openai/gpt-4o --system "You are a security expert" "Check for vulnerabilities"',
        ),
        (
            "Generate commit message",
            'git diff --cached | gh models run openai/gpt-4o-mini "Generate conventional commit message"',
        ),
        (
            "PR description from diff",
            'gh pr diff 123 | gh models run openai/gpt-4o "Create PR description with summary and test plan"',
        ),
        (
            "List available models",
            "gh models list",
        ),
        (
            "Interactive mode",
            "gh models run openai/gpt-4o",
        ),
    ]

    for title, command in examples:
        print(f"# {title}")
        print(f"$ {command}")
        print()


# =============================================================================
# Example: Batch Processing
# =============================================================================


def example_batch_processing() -> None:
    """Demonstrate batch processing with rate limit handling."""
    print("\n" + "=" * 60)
    print("Example: Batch Processing")
    print("=" * 60 + "\n")

    print("""
Batch processing example for analyzing multiple files.
This demonstrates rate limit handling and progress tracking.

Note: This is a demonstration only (not actually calling the API).
""")

    code = '''
import time
from pathlib import Path

def analyze_files(directory: Path, file_pattern: str = "*.py"):
    """Analyze multiple files with rate limit handling."""
    files = list(directory.glob(file_pattern))
    results = []

    for i, file_path in enumerate(files):
        print(f"Processing {i+1}/{len(files)}: {file_path.name}")

        try:
            code = file_path.read_text()
            if len(code) > 5000:
                code = code[:5000]

            result = call_github_models(
                f"Summarize this code in 2-3 sentences:\\n```python\\n{code}\\n```",
                model="openai/gpt-4o-mini",  # Use cheaper model for batch
                max_tokens=200,
            )
            results.append({"file": str(file_path), "summary": result})

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print("Rate limited, waiting 60s...")
                time.sleep(60)
                # Retry this file
                i -= 1
                continue
            else:
                results.append({"file": str(file_path), "error": str(e)})

        # Rate limit: 15 req/min for low-tier models
        time.sleep(4)  # ~15 requests per minute

    return results

# Usage:
# results = analyze_files(Path("backend/services"))
# for r in results:
#     print(f"{r['file']}: {r.get('summary', r.get('error'))}")
'''
    print(code)


# =============================================================================
# Main
# =============================================================================

EXAMPLES: dict[str, tuple[callable, str]] = {
    "pr-description": (example_pr_description, "Generate PR description from git diff"),
    "code-review": (example_code_review, "Perform AI code review on a file"),
    "test-generation": (example_test_generation, "Generate pytest test cases"),
    "security-analysis": (example_security_analysis, "Analyze code for security issues"),
    "cli-usage": (example_cli_usage, "Show gh CLI usage examples"),
    "batch-processing": (example_batch_processing, "Demonstrate batch processing"),
}


def main() -> None:
    """Run GitHub Models examples."""
    parser = argparse.ArgumentParser(
        description="GitHub Models Integration Examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/github-models-examples.py                    # Run all examples
  python scripts/github-models-examples.py --example cli-usage
  python scripts/github-models-examples.py --list

Environment:
  GH_TOKEN    GitHub token with models:read permission

For more information, see: docs/GITHUB_MODELS.md
        """,
    )
    parser.add_argument(
        "--example",
        "-e",
        choices=list(EXAMPLES.keys()),
        help="Run specific example",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available examples",
    )

    args = parser.parse_args()

    if args.list:
        print("\nAvailable Examples:")
        print("-" * 40)
        for name, (_, desc) in EXAMPLES.items():
            print(f"  {name:20} - {desc}")
        print()
        return

    if args.example:
        # Run specific example
        example_fn, _ = EXAMPLES[args.example]
        example_fn()
    else:
        # Run non-API examples by default (to avoid rate limits)
        print("GitHub Models Integration Examples")
        print("=" * 60)
        print("\nRunning non-API examples (safe for rate limits):\n")

        example_cli_usage()
        example_batch_processing()

        print("\n" + "=" * 60)
        print("To run API examples, use:")
        print("  python scripts/github-models-examples.py --example pr-description")
        print("  python scripts/github-models-examples.py --example code-review")
        print("  python scripts/github-models-examples.py --example test-generation")
        print("  python scripts/github-models-examples.py --example security-analysis")
        print("\nMake sure GH_TOKEN is set with models:read permission.")


if __name__ == "__main__":
    main()
