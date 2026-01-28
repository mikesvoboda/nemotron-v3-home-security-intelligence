# CodeQL Custom Queries

This directory contains custom CodeQL security queries tailored for this project's specific tech stack and security requirements.

## Purpose

CodeQL is GitHub's semantic code analysis engine that treats code as data. These custom queries extend CodeQL's standard security analysis with project-specific patterns for:

- **FastAPI backend security** - Authentication, SQL injection, file path validation
- **React/TypeScript frontend security** - XSS, storage security, redirect validation

## Directory Structure

```
.github/codeql/custom-queries/
├── AGENTS.md                    # This file
├── python/                      # Python/FastAPI security queries
│   ├── AGENTS.md               # Python queries guide
│   ├── qlpack.yml              # CodeQL package definition
│   ├── fastapi-missing-auth.ql
│   ├── fastapi-sql-injection.ql
│   └── unsafe-file-operations.ql
└── javascript/                  # JavaScript/TypeScript/React queries
    ├── AGENTS.md               # JavaScript queries guide
    ├── qlpack.yml              # CodeQL package definition
    ├── localstorage-sensitive-data.ql
    ├── react-dangerous-html.ql
    └── unsafe-redirect.ql
```

## How CodeQL Works in CI/CD

### Workflow Trigger

CodeQL analysis runs on:

- **Every merge to `main`** (`.github/workflows/codeql.yml`)
- **Weekly schedule** (Mondays 6am UTC)

**Not on PRs** to save GitHub runner capacity. This is acceptable because:

- Pre-commit hooks catch common issues (Ruff, ESLint, Mypy)
- Semgrep runs in pre-commit for fast security feedback
- CodeQL provides deeper analysis post-merge

### Analysis Process

```yaml
# .github/workflows/codeql.yml
strategy:
  matrix:
    language: [python, javascript-typescript]

steps: 1. Initialize CodeQL with .github/codeql/codeql-config.yml
  2. Autobuild (compile/analyze source code)
  3. Run queries (standard + custom)
  4. Upload results to GitHub Security tab
```

### Query Suites Used

Defined in `.github/codeql/codeql-config.yml`:

| Suite                  | Coverage                            | Source   |
| ---------------------- | ----------------------------------- | -------- |
| `security-and-quality` | Standard security + code quality    | GitHub   |
| `security-extended`    | Additional security (broader scope) | GitHub   |
| Custom Python queries  | FastAPI-specific patterns           | This dir |
| Custom JS queries      | React/TypeScript-specific patterns  | This dir |

### Path Filtering

CodeQL ignores:

- Test files (`**/*.test.ts`, `**/test_*.py`, `**/tests/**`)
- Dependencies (`.venv/`)
- Build artifacts (dist, build, coverage directories)
- Generated files (Alembic migrations, `*.generated.ts`)

See `.github/codeql/codeql-config.yml` for full list.

## Security Coverage

### Python Queries (`python/`)

| Query                       | CWE     | Severity | Detects                           |
| --------------------------- | ------- | -------- | --------------------------------- |
| `fastapi-missing-auth.ql`   | CWE-306 | Warning  | POST/PUT/DELETE without Depends() |
| `fastapi-sql-injection.ql`  | CWE-089 | Error    | SQLAlchemy text() with f-strings  |
| `unsafe-file-operations.ql` | CWE-022 | Error    | Path traversal vulnerabilities    |

### JavaScript Queries (`javascript/`)

| Query                            | CWE     | Severity | Detects                          |
| -------------------------------- | ------- | -------- | -------------------------------- |
| `localstorage-sensitive-data.ql` | CWE-922 | Warning  | Tokens/passwords in localStorage |
| `react-dangerous-html.ql`        | CWE-079 | Warning  | dangerouslySetInnerHTML usage    |
| `unsafe-redirect.ql`             | CWE-601 | Warning  | Unvalidated URL navigation       |

## Interpreting Results

### Finding Results

After CodeQL runs:

1. Go to repository **Security** tab
2. Click **Code scanning alerts**
3. Filter by **Tool: CodeQL**

### Result Format

Each finding includes:

- **Severity** (Error/Warning)
- **CWE identifier** (Common Weakness Enumeration)
- **File location** with line number
- **Recommendation** (how to fix)

Example:

```
File: backend/api/routes/cameras.py:45
Severity: Warning
Rule: py/fastapi-missing-auth
Message: FastAPI POST endpoint may be missing authentication: /api/cameras/{id}/delete

Recommendation: Add authentication dependency using Depends()
```

## Query Development

### Testing Custom Queries Locally

**Prerequisites:**

```bash
# Install CodeQL CLI
# macOS
brew install codeql

# Linux
wget https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip
unzip codeql-linux64.zip -d /opt
export PATH="/opt/codeql:$PATH"
```

**Create CodeQL database:**

```bash
# Python
codeql database create codeql-db-python \
  --language=python \
  --source-root=.

# JavaScript/TypeScript
codeql database create codeql-db-js \
  --language=javascript \
  --source-root=.
```

**Run custom queries:**

```bash
# Python queries
codeql query run \
  .github/codeql/custom-queries/python/fastapi-missing-auth.ql \
  --database=codeql-db-python

# JavaScript queries
codeql query run \
  .github/codeql/custom-queries/javascript/unsafe-redirect.ql \
  --database=codeql-db-js
```

### Query Language Reference

CodeQL queries use a Datalog-like language:

```ql
/**
 * @name Query title
 * @description What this query detects
 * @kind problem
 * @problem.severity error|warning|recommendation
 * @security-severity 0.0-10.0 (CVSS-like score)
 * @precision high|medium|low
 * @id unique-id (e.g., py/my-query)
 * @tags security, external/cwe/cwe-XXX
 */

import python  // or javascript

// Define classes and predicates
class MyVulnerablePattern extends SomeAstNode {
  MyVulnerablePattern() {
    // Constructor logic
  }
}

// Query body
from MyVulnerablePattern pattern
where <conditions>
select pattern, "Message with $@ link", pattern, "link text"
```

**Key concepts:**

- **Classes** - AST node types (e.g., `Call`, `Function`, `Decorator`)
- **Predicates** - Boolean conditions (e.g., `hasAuthDependency()`)
- **Exists** - Quantified expressions ("there exists...")
- **DataFlow** - Taint tracking for input validation

### Query Design Patterns

**Pattern 1: AST Pattern Matching**

```ql
// Find FastAPI routes with specific decorators
class FastApiRoute extends Function {
  FastApiRoute() {
    exists(Decorator d |
      this.getADecorator() = d and
      d.getName() = "post"
    )
  }
}
```

**Pattern 2: String Pattern Matching**

```ql
// Find sensitive localStorage keys
predicate hasSensitiveKey() {
  exists(string key |
    key = this.getKeyArg().(StringLiteral).getValue().toLowerCase() and
    (
      key.matches("%password%") or
      key.matches("%token%")
    )
  )
}
```

**Pattern 3: Data Flow Analysis**

```ql
// Track tainted data from source to sink
from UrlParamAccess source, NavigationCall sink
where DataFlow::localFlow(source, sink)
select sink, "Tainted data flows from $@ to redirect", source, "URL parameter"
```

## Adding New Queries

### Workflow

1. **Identify security pattern** - What vulnerability are you looking for?
2. **Research CWE** - What's the Common Weakness Enumeration ID?
3. **Write query** - Create `.ql` file in appropriate subdirectory
4. **Test locally** - Run against CodeQL database (see above)
5. **Tune precision** - Adjust to minimize false positives
6. **Document** - Add to tables above and commit

### Query Template

```ql
/**
 * @name [Descriptive title]
 * @description [What this detects and why it's a security issue]
 * @kind problem
 * @problem.severity error|warning
 * @security-severity [0.0-10.0]
 * @precision high|medium|low
 * @id [language]/[query-name]
 * @tags security
 *       external/cwe/cwe-[XXX]
 */

import [python|javascript]

// Define vulnerable pattern
class VulnerablePattern extends [BaseClass] {
  VulnerablePattern() {
    // Constructor logic
  }
}

// Query
from VulnerablePattern vuln
where [conditions]
select vuln, "[User-facing message with remediation advice]"
```

## Precision Levels

CodeQL queries have precision levels that affect signal-to-noise ratio:

| Precision    | False Positive Rate | Use Case                    |
| ------------ | ------------------- | --------------------------- |
| **high**     | < 10%               | Block merges, critical bugs |
| **medium**   | 10-30%              | Review required             |
| **low**      | 30-60%              | Manual triage               |
| **very-low** | > 60%               | Filtered out (too noisy)    |

**Current project policy:** `very-low` precision queries are excluded (`.github/codeql/codeql-config.yml`).

## Comparison with Other Tools

### CodeQL vs Semgrep

| Feature             | CodeQL                   | Semgrep (pre-commit)   |
| ------------------- | ------------------------ | ---------------------- |
| **Speed**           | Slow (minutes)           | Fast (seconds)         |
| **When**            | Post-merge to main       | Every commit           |
| **Analysis depth**  | Deep (control/data flow) | Shallow (AST patterns) |
| **False positives** | Lower (high precision)   | Higher (simpler rules) |
| **Use case**        | Deep security audit      | Quick feedback loop    |

**Strategy:** Use both:

- Semgrep catches obvious issues fast (pre-commit)
- CodeQL catches complex vulnerabilities (post-merge weekly)

### CodeQL vs Static Type Checking

| Feature      | CodeQL                   | Mypy/TypeScript    |
| ------------ | ------------------------ | ------------------ |
| **Focus**    | Security vulnerabilities | Type correctness   |
| **Coverage** | Specific patterns        | All type errors    |
| **When**     | Post-merge               | Pre-commit         |
| **Fixes**    | Manual review            | Auto-fix available |

**Overlap:** Both catch some issues (e.g., SQL injection type safety), but serve different purposes.

## Maintenance

### When to Update Queries

- **New CWE discovered** - Add query for emerging vulnerability class
- **False positives** - Tune query predicates to exclude benign patterns
- **New framework patterns** - Update for FastAPI/React API changes
- **Performance issues** - Optimize slow queries (check CodeQL logs)

### Query Performance

If CodeQL analysis times out (> 2 hours):

1. Check query complexity (`codeql query run --measure`)
2. Add predicates to narrow search space
3. Use `not exists(...)` sparingly (expensive)
4. Consider splitting into multiple queries

### Security Review Cycle

1. **Weekly automated runs** (Monday 6am UTC)
2. **Results triage** - Review new findings in Security tab
3. **Create issues** - For confirmed vulnerabilities
4. **Fix and verify** - Re-run CodeQL after fix

## Related Documentation

- **Pre-commit security:** See `/CLAUDE.md` (Semgrep, Hadolint)
- **Python security patterns:** See `backend/AGENTS.md`
- **React security patterns:** See `frontend/AGENTS.md`
- **CI/CD workflows:** See `.github/workflows/AGENTS.md`

## External Resources

- [CodeQL documentation](https://codeql.github.com/docs/)
- [CodeQL query reference](https://codeql.github.com/docs/codeql-language-guides/)
- [Common Weakness Enumeration](https://cwe.mitre.org/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

## Key Takeaways

1. **Custom queries extend standard analysis** - Project-specific security patterns
2. **Post-merge analysis** - Runs after merge to main (not on PRs)
3. **Complement existing tools** - Works alongside Semgrep, Mypy, ESLint
4. **Security tab** - View results in GitHub Security > Code scanning alerts
5. **6 custom queries** - 3 Python (FastAPI), 3 JavaScript (React)
6. **Deep analysis** - Control flow, data flow, taint tracking
