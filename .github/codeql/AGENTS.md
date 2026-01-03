# CodeQL Configuration Directory - Agent Guide

## Purpose

This directory contains configuration files for GitHub CodeQL, a semantic code analysis engine that identifies security vulnerabilities and code quality issues.

## Directory Contents

```
codeql/
  AGENTS.md           # This file
  codeql-config.yml   # CodeQL analysis configuration
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

1. Create a `queries/` subdirectory
2. Add `.ql` files with custom queries
3. Reference in config:

```yaml
queries:
  - uses: security-and-quality
  - uses: ./queries
```

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

- `../.github/workflows/codeql.yml` - Workflow that uses this config
- `../.github/AGENTS.md` - Parent directory overview
- `CLAUDE.md` - Project security requirements
