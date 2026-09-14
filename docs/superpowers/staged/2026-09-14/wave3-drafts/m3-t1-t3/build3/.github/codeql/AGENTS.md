# CodeQL Configuration Directory - Agent Guide

## Purpose

This directory contains configuration files for GitHub CodeQL, a semantic code analysis engine that identifies security vulnerabilities and code quality issues.

## Directory Contents

```
codeql/
  AGENTS.md             # This file
  codeql-config.yml     # CodeQL analysis configuration
  custom-queries/       # Custom CodeQL security queries
    AGENTS.md           # Custom queries overview
    javascript/         # JavaScript/TypeScript queries
      AGENTS.md         # JavaScript queries guide
      qlpack.yml        # CodeQL package definition
      localstorage-sensitive-data.ql  # Storage security query
      react-dangerous-html.ql         # XSS prevention query
      unsafe-redirect.ql              # Open redirect query
    python/             # Python/FastAPI queries
      AGENTS.md         # Python queries guide
      qlpack.yml        # CodeQL package definition
      fastapi-missing-auth.ql         # Auth check query
      fastapi-sql-injection.ql        # SQL injection query
      unsafe-file-operations.ql       # Path traversal query
```

## Key Files

### codeql-config.yml

**Purpose:** Configures CodeQL analysis behavior for security scanning.

**Configuration:**

| Setting     | Value                | Description                                   |
| ----------- | -------------------- | --------------------------------------------- |
| Query Suite | security-and-quality | Includes both security and code quality rules |

**Excluded Paths:**

Test files are excluded from security analysis to reduce noise:

- `**/*.test.ts` - TypeScript test files
- `**/*.test.tsx` - React test files
- `**/test_*.py` - Python test files (prefix convention)
- `**/*_test.py` - Python test files (suffix convention)
- `**/tests/**` - Test directories
- `**/node_modules/**` - NPM dependencies
- `**/.venv/**` - Python virtual environment

## Usage

### CodeQL Workflow

This configuration is used by `.github/workflows/codeql.yml`:

1. **Trigger:** Push/PR to main, weekly schedule (Monday 6am UTC)
2. **Languages:** Python, JavaScript/TypeScript
3. **Output:** Results uploaded to GitHub Security tab

### Viewing Results

```bash
# View CodeQL alerts via CLI
gh api /repos/{owner}/{repo}/code-scanning/alerts

# Or view in GitHub UI: Security > Code scanning alerts
```

### Adding Custom Queries

To add custom CodeQL queries:

1. Create a `.ql` file in the appropriate subdirectory (e.g., `custom-queries/python/` or `custom-queries/javascript/`)
2. Add the query with proper metadata
3. The queries are already referenced in the config via `custom-queries/`

### Modifying Exclusions

To exclude additional paths from analysis:

```yaml
paths-ignore:
  - '**/*.test.ts'
  - '**/fixtures/**' # Add new exclusion
```

## Best Practices

### Path Exclusions

- Exclude test files (they often have intentional vulnerabilities for testing)
- Exclude generated code
- Exclude vendored dependencies
- Keep production code paths included

### Query Selection

- `security-and-quality` - Recommended for most projects
- `security-extended` - More queries, more false positives
- `security-experimental` - Cutting-edge detection, may have issues

## Related Files

- `../workflows/codeql.yml` - Workflow that uses this config
- `../AGENTS.md` - Parent directory overview
- `CLAUDE.md` - Project security requirements
