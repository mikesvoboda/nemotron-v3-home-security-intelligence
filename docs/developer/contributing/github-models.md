# GitHub Models Integration Guide

Comprehensive guide for using GitHub Models in the Nemotron v3 Home Security Intelligence project. GitHub Models provides free access to cutting-edge AI models directly from GitHub.

## Table of Contents

- [Overview](#overview)
- [Available Models](#available-models)
- [Rate Limits](#rate-limits)
- [Authentication](#authentication)
- [Using the gh CLI](#using-the-gh-cli)
- [Using the REST API](#using-the-rest-api)
- [Current Project Usage](#current-project-usage)
- [Use Cases for This Project](#use-cases-for-this-project)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

GitHub Models provides free access to AI models for experimentation and prototyping. The service is integrated into GitHub Actions and can be used via:

1. **GitHub CLI Extension** (`gh models`)
2. **REST API** (https://models.github.ai)
3. **Python SDK** (via OpenAI-compatible API)

**Marketplace:** [https://github.com/marketplace/models](https://github.com/marketplace/models)

### Key Benefits

- **Free tier available** for experimentation
- **No separate account needed** - uses GitHub authentication
- **GitHub Actions integration** - uses existing `GITHUB_TOKEN`
- **Multiple model providers** - OpenAI, Meta, Microsoft, Mistral

## Available Models

### OpenAI Models

| Model                | Context Window | Best For                       | Rate Tier |
| -------------------- | -------------- | ------------------------------ | --------- |
| `openai/gpt-4o`      | 128K tokens    | Complex reasoning, code review | High      |
| `openai/gpt-4o-mini` | 128K tokens    | Fast, cost-effective tasks     | Low       |
| `openai/o1`          | 200K tokens    | Deep reasoning, math           | High      |
| `openai/o1-mini`     | 128K tokens    | Faster reasoning tasks         | Low       |
| `openai/o3-mini`     | 200K tokens    | Latest reasoning model         | High      |

### Meta Llama Models

| Model                         | Context Window | Best For          | Rate Tier |
| ----------------------------- | -------------- | ----------------- | --------- |
| `meta/llama-3.3-70b-instruct` | 128K tokens    | General purpose   | High      |
| `meta/llama-3.1-8b-instruct`  | 128K tokens    | Lightweight tasks | Low       |
| `meta/llama-3.2-90b-vision`   | 128K tokens    | Vision + text     | High      |

### Microsoft Phi Models

| Model                    | Context Window | Best For            | Rate Tier |
| ------------------------ | -------------- | ------------------- | --------- |
| `microsoft/phi-4`        | 16K tokens     | Efficient reasoning | Low       |
| `microsoft/phi-3.5-mini` | 128K tokens    | Fast inference      | Low       |

### Mistral Models

| Model                        | Context Window | Best For         | Rate Tier |
| ---------------------------- | -------------- | ---------------- | --------- |
| `mistral/mistral-large-2411` | 128K tokens    | Enterprise tasks | High      |
| `mistral/mistral-small-2503` | 32K tokens     | Cost-effective   | Low       |
| `mistral/codestral-2501`     | 256K tokens    | Code generation  | Low       |

## Rate Limits

GitHub Models has two rate tiers based on model capability:

### High-Tier Models (GPT-4o, o1, Llama-70B, etc.)

| Limit Type          | Free Tier Limit     |
| ------------------- | ------------------- |
| Requests per minute | 10 requests/minute  |
| Requests per day    | 50 requests/day     |
| Tokens per minute   | 8,000 tokens/minute |
| Tokens per day      | 16,000 tokens/day   |

### Low-Tier Models (GPT-4o-mini, Phi, Mistral-small, etc.)

| Limit Type          | Free Tier Limit      |
| ------------------- | -------------------- |
| Requests per minute | 15 requests/minute   |
| Requests per day    | 150 requests/day     |
| Tokens per minute   | 15,000 tokens/minute |
| Tokens per day      | 150,000 tokens/day   |

### Rate Limit Headers

API responses include rate limit headers:

```
x-ratelimit-limit-requests: 50
x-ratelimit-remaining-requests: 45
x-ratelimit-limit-tokens: 16000
x-ratelimit-remaining-tokens: 14500
```

### Handling Rate Limits

```python
import time

def call_with_retry(prompt, max_retries=3):
    """Call GitHub Models with exponential backoff."""
    for attempt in range(max_retries):
        response = call_github_models(prompt)
        if response.status_code == 429:
            wait_time = 2 ** attempt * 10  # 10s, 20s, 40s
            print(f"Rate limited. Waiting {wait_time}s...")
            time.sleep(wait_time)
            continue
        return response
    raise Exception("Max retries exceeded")
```

## Authentication

### In GitHub Actions

GitHub Actions automatically provides a `GITHUB_TOKEN` with `models: read` permission:

```yaml
permissions:
  contents: read
  models: read

steps:
  - name: Call Model
    env:
      GH_TOKEN: ${{ github.token }}
    run: |
      gh models run openai/gpt-4o "Hello, world!"
```

### Local Development

For local development, use a GitHub Personal Access Token (PAT):

```bash
# Set environment variable
export GH_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

# Or use gh auth
gh auth login
```

**Required Token Permissions:**

- `models:read` - Access to GitHub Models API

### Token Generation

1. Go to: [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)" or "Fine-grained token"
3. For fine-grained: Select "Account permissions" > "GitHub Copilot" (includes Models)
4. For classic: Check the `copilot` scope

## Using the gh CLI

### Installation

```bash
# Install gh-models extension
gh extension install github/gh-models

# Verify installation
gh models --help
```

### Basic Usage

```bash
# Simple prompt
gh models run openai/gpt-4o "Explain async/await in Python"

# Interactive mode
gh models run openai/gpt-4o

# Pipe input
echo "What is this code doing?" | gh models run openai/gpt-4o

# With file context
cat script.py | gh models run openai/gpt-4o "Review this code"
```

### Model Selection

```bash
# List available models
gh models list

# Use specific model
gh models run meta/llama-3.3-70b-instruct "Prompt here"
gh models run openai/gpt-4o-mini "Prompt here"
gh models run mistral/codestral-2501 "Prompt here"
```

### Advanced Options

```bash
# Set temperature (0.0-2.0, default 1.0)
gh models run openai/gpt-4o --temperature 0.7 "Be creative"

# Set max tokens
gh models run openai/gpt-4o --max-tokens 500 "Short answer"

# System prompt
gh models run openai/gpt-4o \
  --system "You are a security expert" \
  "Review this code for vulnerabilities"
```

## Using the REST API

### Endpoint

```
POST https://models.github.ai/inference/chat/completions
```

### Python Example

```python
#!/usr/bin/env python3
"""GitHub Models API client example."""

import os
import requests

def call_github_models(
    prompt: str,
    model: str = "openai/gpt-4o",
    temperature: float = 0.7,
    max_tokens: int = 1000,
    system_prompt: str | None = None,
) -> str:
    """
    Call GitHub Models API.

    Args:
        prompt: User prompt
        model: Model identifier (e.g., "openai/gpt-4o")
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum response tokens
        system_prompt: Optional system prompt

    Returns:
        Model response text
    """
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GH_TOKEN or GITHUB_TOKEN environment variable required")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = requests.post(
        "https://models.github.ai/inference/chat/completions",
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
        timeout=60,
    )
    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


if __name__ == "__main__":
    result = call_github_models("What is 2 + 2?")
    print(result)
```

### Using OpenAI SDK (Compatible)

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=os.environ["GH_TOKEN"],
)

response = client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ],
)
print(response.choices[0].message.content)
```

## Current Project Usage

### AI Code Review Workflow

This project uses GitHub Models for automated code review on pull requests:

**File:** `.github/workflows/ai-code-review.yml`

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]
    branches: [main]

permissions:
  contents: read
  pull-requests: write
  models: read

jobs:
  ai-review:
    name: GPT-5 Code Review
    runs-on: ubuntu-latest
    if: github.event.pull_request.draft == false

    steps:
      - name: Install gh-models extension
        run: gh extension install github/gh-models || true

      - name: Run AI Code Review
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # Review prompt with tech stack context
          cat << 'PROMPT_END' > review_prompt.txt
          You are an expert code reviewer for a home security application.
          Tech stack: Python FastAPI, React TypeScript, YOLO26, Nemotron.

          Review for:
          1. Security Issues
          2. Performance
          3. Best Practices
          4. Bugs
          PROMPT_END

          cat pr_diff.txt >> review_prompt.txt

          # Call GPT-4o with fallback to mini
          REVIEW=$(cat review_prompt.txt | gh models run openai/gpt-4o 2>&1) || \
          REVIEW=$(cat review_prompt.txt | gh models run openai/gpt-4o-mini 2>&1)

          echo "$REVIEW" > review_output.md
```

**Key Features:**

- Automatic trigger on PR open/sync
- Diff truncation for token limits
- Fallback from GPT-4o to GPT-4o-mini
- Posted as PR comment

## Use Cases for This Project

### 1. AI Code Review (Implemented)

Already implemented in `.github/workflows/ai-code-review.yml`. Reviews PRs for:

- Security vulnerabilities
- Performance issues
- Code style
- Logic errors

### 2. Documentation Generation

Generate or update documentation from code:

```bash
# Generate docstrings
cat backend/services/detector_client.py | \
  gh models run openai/gpt-4o "Add comprehensive docstrings to this Python code"

# Generate README section
cat backend/api/routes/*.py | \
  gh models run openai/gpt-4o "Create API documentation in markdown format"
```

### 3. Test Case Suggestions

Generate test cases for new code:

```bash
# Suggest unit tests
cat backend/services/batch_aggregator.py | \
  gh models run openai/gpt-4o \
  --system "You are a Python testing expert using pytest" \
  "Suggest comprehensive test cases for this service"

# Generate test file skeleton
cat backend/services/nemotron_analyzer.py | \
  gh models run mistral/codestral-2501 \
  "Generate pytest test file with fixtures and edge cases"
```

### 4. Security Analysis

Analyze code for security issues:

```bash
# Security review
cat backend/api/routes/events.py | \
  gh models run openai/gpt-4o \
  --system "You are a security expert. Focus on OWASP Top 10" \
  "Analyze this code for security vulnerabilities"

# SQL injection check
grep -r "execute\|raw_sql" backend/ | \
  gh models run openai/gpt-4o "Check for SQL injection risks"
```

### 5. PR Description Generation

Generate PR descriptions from diffs:

```bash
# Generate PR description
gh pr diff 123 | \
  gh models run openai/gpt-4o \
  --system "Generate a clear PR description with summary and test plan" \
  "Describe these changes"
```

### 6. Commit Message Generation

Generate commit messages from staged changes:

```bash
# Generate commit message
git diff --cached | \
  gh models run openai/gpt-4o-mini \
  "Generate a conventional commit message (feat/fix/docs/refactor)"
```

### 7. Detection Prompt Refinement

Improve Nemotron prompts for risk analysis:

```bash
# Refine risk analysis prompt
cat docs/plans/2024-12-21-dashboard-mvp-design.md | \
  grep -A 50 "Nemotron Prompt" | \
  gh models run openai/gpt-4o \
  "Suggest improvements for this security risk analysis prompt"
```

## Best Practices

### 1. Use Appropriate Models

| Task                | Recommended Model        | Reason             |
| ------------------- | ------------------------ | ------------------ |
| Complex code review | `openai/gpt-4o`          | Best reasoning     |
| Simple formatting   | `openai/gpt-4o-mini`     | Fast, saves quota  |
| Code generation     | `mistral/codestral-2501` | Optimized for code |
| General tasks       | `meta/llama-3.3-70b`     | Good balance       |

### 2. Implement Fallbacks

```bash
# Fallback chain
RESPONSE=$(gh models run openai/gpt-4o "$PROMPT" 2>&1) || \
RESPONSE=$(gh models run openai/gpt-4o-mini "$PROMPT" 2>&1) || \
RESPONSE="Model unavailable"
```

### 3. Truncate Large Inputs

```bash
# Limit to ~20KB (leaves room for prompt overhead)
head -c 20000 large_file.txt > truncated.txt
cat truncated.txt | gh models run openai/gpt-4o "..."
```

### 4. Use System Prompts

```bash
gh models run openai/gpt-4o \
  --system "You are reviewing code for a home security system. \
            The stack is Python FastAPI, React TypeScript, PostgreSQL, Redis. \
            AI models are YOLO26 (detection) and Nemotron (reasoning)." \
  "Review this code"
```

### 5. Cache Results When Possible

For deterministic queries, cache results to avoid hitting rate limits:

```python
import hashlib
import json
from pathlib import Path

CACHE_DIR = Path(".github-models-cache")

def cached_query(prompt: str, model: str = "openai/gpt-4o") -> str:
    """Query with file-based caching."""
    cache_key = hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()[:16]
    cache_file = CACHE_DIR / f"{cache_key}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text())["response"]

    response = call_github_models(prompt, model=model)

    CACHE_DIR.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps({"prompt": prompt, "response": response}))

    return response
```

### 6. Handle Errors Gracefully

```python
import requests

try:
    response = call_github_models(prompt)
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 429:
        print("Rate limited - try again later")
    elif e.response.status_code == 401:
        print("Authentication failed - check GH_TOKEN")
    elif e.response.status_code == 400:
        print(f"Bad request: {e.response.text}")
    else:
        raise
```

## Troubleshooting

### "gh: command not found"

Install GitHub CLI:

```bash
# macOS
brew install gh

# Ubuntu/Debian
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
  sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
  https://cli.github.com/packages stable main" | \
  sudo tee /etc/apt/sources.list.d/github-cli.list
sudo apt update && sudo apt install gh

# Fedora
sudo dnf install gh
```

### "gh models: command not found"

Install the extension:

```bash
gh extension install github/gh-models
```

### "401 Unauthorized"

Check authentication:

```bash
# Verify token is set
echo $GH_TOKEN

# Test authentication
gh auth status

# Re-authenticate if needed
gh auth login
```

### "429 Rate Limited"

You've exceeded the rate limit:

```bash
# Check current limits (in workflow)
echo "Remaining: ${{ github.event.rate_limit.remaining }}"

# Wait and retry
sleep 60
```

### "Model not found"

Verify model name:

```bash
# List available models
gh models list

# Use exact name from list
gh models run openai/gpt-4o "test"
```

### Large Response Truncated

Increase max tokens:

```bash
gh models run openai/gpt-4o --max-tokens 4000 "Generate detailed output"
```

### Timeout Errors

Increase timeout in Python:

```python
response = requests.post(url, json=data, timeout=120)  # 2 minutes
```

## Additional Resources

- [GitHub Models Marketplace](https://github.com/marketplace/models)
- [GitHub Models Documentation](https://docs.github.com/en/github-models)
- [gh-models Extension](https://github.com/github/gh-models)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference) (compatible format)
- Project AI Code Review: `.github/workflows/ai-code-review.yml`
- Project CI/CD: `.github/workflows/ci.yml`
