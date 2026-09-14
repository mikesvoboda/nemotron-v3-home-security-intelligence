"""
Unit tests for check-api-breaking-changes.py script.

Tests the API breaking change detection logic.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def base_spec() -> dict:
    """Create a base OpenAPI specification."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {"application/json": {"schema": {"type": "array"}}},
                        }
                    },
                },
                "post": {
                    "summary": "Create user",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {}},
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            },
            "/users/{id}": {
                "get": {
                    "summary": "Get user",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {"application/json": {}},
                        }
                    },
                }
            },
        },
    }


def run_script(base_spec: dict, current_spec: dict, format: str = "text") -> tuple[int, str, str]:
    """Run the check-api-breaking-changes.py script.

    Args:
        base_spec: Base OpenAPI specification
        current_spec: Current OpenAPI specification
        format: Output format (text, markdown, json)

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    with (
        tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as base_f,
        tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as current_f,
    ):
        json.dump(base_spec, base_f)
        base_path = base_f.name

        json.dump(current_spec, current_f)
        current_path = current_f.name

    try:
        result = subprocess.run(  # noqa: S603  # intentional - tests our own script
            [  # noqa: S607  # partial path OK for test script
                "python",
                "scripts/check-api-breaking-changes.py",
                "--base",
                base_path,
                "--current",
                current_path,
                "--format",
                format,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr
    finally:
        Path(base_path).unlink(missing_ok=True)
        Path(current_path).unlink(missing_ok=True)


def test_no_breaking_changes(base_spec: dict):
    """Test when there are no breaking changes."""
    # Add a new optional parameter (non-breaking)
    current_spec = json.loads(json.dumps(base_spec))
    current_spec["paths"]["/users"]["get"]["parameters"].append(
        {"name": "offset", "in": "query", "required": False, "schema": {"type": "integer"}}
    )

    exit_code, stdout, _stderr = run_script(base_spec, current_spec)

    assert exit_code == 0
    assert "No breaking changes detected" in stdout


def test_removed_endpoint(base_spec: dict):
    """Test detection of removed endpoint."""
    current_spec = json.loads(json.dumps(base_spec))
    del current_spec["paths"]["/users/{id}"]

    exit_code, stdout, _stderr = run_script(base_spec, current_spec)

    assert exit_code == 1
    assert "Endpoint Removed" in stdout or "Method Removed" in stdout
    assert "/users/{id}" in stdout


def test_removed_method(base_spec: dict):
    """Test detection of removed HTTP method."""
    current_spec = json.loads(json.dumps(base_spec))
    del current_spec["paths"]["/users"]["post"]

    exit_code, stdout, _stderr = run_script(base_spec, current_spec)

    assert exit_code == 1
    assert "Method Removed" in stdout
    assert "POST /users" in stdout


def test_parameter_made_required(base_spec: dict):
    """Test detection of optional parameter becoming required."""
    current_spec = json.loads(json.dumps(base_spec))
    current_spec["paths"]["/users"]["get"]["parameters"][0]["required"] = True

    exit_code, stdout, _stderr = run_script(base_spec, current_spec)

    assert exit_code == 1
    assert "Parameter Made Required" in stdout
    assert "limit" in stdout


def test_parameter_type_changed(base_spec: dict):
    """Test detection of parameter type change."""
    current_spec = json.loads(json.dumps(base_spec))
    current_spec["paths"]["/users"]["get"]["parameters"][0]["schema"]["type"] = "string"

    exit_code, stdout, _stderr = run_script(base_spec, current_spec)

    assert exit_code == 1
    assert "Parameter Type Changed" in stdout
    assert "integer" in stdout and "string" in stdout


def test_removed_required_parameter(base_spec: dict):
    """Test detection of removed required parameter."""
    current_spec = json.loads(json.dumps(base_spec))
    current_spec["paths"]["/users/{id}"]["get"]["parameters"] = []

    exit_code, stdout, _stderr = run_script(base_spec, current_spec)

    assert exit_code == 1
    assert "Required Parameter Removed" in stdout
    assert "id" in stdout


def test_request_body_removed(base_spec: dict):
    """Test detection of removed request body."""
    current_spec = json.loads(json.dumps(base_spec))
    del current_spec["paths"]["/users"]["post"]["requestBody"]

    exit_code, stdout, _stderr = run_script(base_spec, current_spec)

    assert exit_code == 1
    assert "Request Body Removed" in stdout


def test_multiple_breaking_changes(base_spec: dict):
    """Test detection of multiple breaking changes."""
    current_spec = json.loads(json.dumps(base_spec))

    # Remove endpoint
    del current_spec["paths"]["/users/{id}"]

    # Remove method
    del current_spec["paths"]["/users"]["post"]

    # Make parameter required
    current_spec["paths"]["/users"]["get"]["parameters"][0]["required"] = True

    exit_code, stdout, _stderr = run_script(base_spec, current_spec)

    assert exit_code == 1
    assert "Summary: 3 breaking" in stdout or "3 breaking" in stdout.lower()


def test_markdown_output(base_spec: dict):
    """Test markdown output format."""
    current_spec = json.loads(json.dumps(base_spec))
    del current_spec["paths"]["/users"]["post"]

    exit_code, stdout, _stderr = run_script(base_spec, current_spec, format="markdown")

    assert exit_code == 1
    assert "## 🚨 Breaking Changes Detected" in stdout
    assert "**Method Removed**" in stdout
    assert "`POST /users`" in stdout


def test_json_output(base_spec: dict):
    """Test JSON output format."""
    current_spec = json.loads(json.dumps(base_spec))
    del current_spec["paths"]["/users"]["post"]

    exit_code, stdout, _stderr = run_script(base_spec, current_spec, format="json")

    assert exit_code == 1
    output = json.loads(stdout)
    assert "breaking_changes" in output
    assert "summary" in output
    assert len(output["breaking_changes"]) > 0


def test_invalid_spec_file():
    """Test handling of invalid spec files."""
    result = subprocess.run(  # intentional - tests our own script
        [  # noqa: S607  # partial path OK for test script
            "python",
            "scripts/check-api-breaking-changes.py",
            "--base",
            "/nonexistent/file.json",
            "--current",
            "/nonexistent/file2.json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Error" in result.stderr or "not found" in result.stderr.lower()
