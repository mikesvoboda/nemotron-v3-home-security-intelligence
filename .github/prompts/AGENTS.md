# GitHub Prompts Directory - Agent Guide

## Purpose

This directory contains AI prompt templates used by GitHub Actions workflows for automated code review and analysis.

## Directory Contents

```
prompts/
  AGENTS.md                 # This file
  code-review.prompt.md     # System prompt for AI code review
```

## Key Files

### code-review.prompt.md

**Purpose:** System prompt for AI-powered code review in pull requests.

**Used by:** `.github/workflows/ai-code-review.yml`

**Review Guidelines:**

1. **Security (CRITICAL)**

   - SQL injection, command injection, XSS vulnerabilities
   - API input validation with Pydantic schemas
   - No hardcoded secrets or credentials
   - Path traversal in file handling
   - Authentication/authorization where needed

2. **Performance**

   - N+1 query patterns in SQLAlchemy
   - Unnecessary re-renders in React components
   - Appropriate async/await usage
   - Memory leaks in event handlers

3. **Code Quality**

   - TypeScript types (no `any`)
   - Python type hints
   - Comprehensive error handling
   - Code duplication

4. **Testing**
   - New code has corresponding tests
   - Edge cases are covered

**Response Format:**

```markdown
### Summary

One-line summary of changes and quality.

### Issues Found

- **Critical**: Must fix before merge
- **Warning**: Should fix, but not blocking
- **Suggestion**: Nice to have improvements

### What's Good

Positive aspects of the code.
```

## Tech Stack Context

The prompt provides context about the project tech stack:

- **Backend**: Python 3.14, FastAPI, SQLAlchemy, Redis, PostgreSQL
- **Frontend**: React 18, TypeScript, Tailwind CSS, Tremor, Vite
- **AI Pipeline**: RT-DETRv2 (object detection), Nemotron via llama.cpp
- **Infrastructure**: Docker/Podman, NVIDIA RTX A5500 GPU

## Usage

### AI Code Review Workflow

The `ai-code-review.yml` workflow:

1. Extracts PR diff
2. Truncates to 20KB (token limits)
3. Prepends system prompt
4. Calls GPT-4o via GitHub Models
5. Posts review as PR comment

### Modifying the Prompt

1. Edit `code-review.prompt.md`
2. Test by creating a PR
3. AI review will use updated prompt

### Adding New Prompts

1. Create new `.prompt.md` file in this directory
2. Reference in workflow with:
   ```yaml
   - name: Load prompt
     run: cat .github/prompts/my-prompt.prompt.md > prompt.txt
   ```

## Best Practices

### Prompt Structure

- Be specific about tech stack
- Prioritize security issues
- Provide clear response format
- Keep prompt concise (token limits)

### Review Quality

- Focus on significant issues
- Avoid nitpicking style
- Provide actionable feedback
- Be positive about good code

## Related Files

- `../workflows/ai-code-review.yml` - Workflow using this prompt
- `../copilot-instructions.md` - GitHub Copilot context
- `CLAUDE.md` - Project development guidelines
