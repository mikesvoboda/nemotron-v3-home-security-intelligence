# Python CodeQL Custom Queries

This directory contains custom CodeQL security queries for Python/FastAPI backend code.

## Purpose

These queries detect security vulnerabilities specific to FastAPI web applications and Python code patterns used in this project. They complement CodeQL's standard Python security queries with project-specific checks.

## Query Files

### 1. `fastapi-missing-auth.ql`

**Detects:** FastAPI POST/PUT/DELETE/PATCH endpoints that may be missing authentication.

**CWE:** CWE-306 (Missing Authentication for Critical Function)

**Severity:** Warning (6.0/10)

**What it catches:**

```python
# VULNERABLE - No authentication dependency
@router.post("/api/admin/delete_user")
async def delete_user(user_id: str):
    # Anyone can call this!
    await db.delete_user(user_id)

# SAFE - Has authentication dependency
@router.post("/api/admin/delete_user")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user)  # ✓ Auth check
):
    await db.delete_user(user_id)
```

**Detection logic:**

1. Find FastAPI route decorators: `@router.post()`, `@router.put()`, `@router.delete()`, `@router.patch()`
2. Check if endpoint has `Depends()` with auth-related names:
   - Parameter names: `*auth*`, `*current_user*`, `*verify*`, `*require*`, `*api_key*`
   - Dependency names: Similar patterns in `Depends(get_current_user)`
3. Exempt paths: `/health`, `/ready`, `/ping`, `/version`, `/public`, `/webhook`
4. Focus on sensitive paths: `*admin*`, `*delete*`, `*config*`, `*setting*`, `*user*`

**False positives:**

- Intentionally public endpoints (add to exempt path patterns)
- Endpoints with custom middleware auth (not detectable by this query)

**How to fix:**

```python
from fastapi import Depends
from backend.core.auth import get_current_user

@router.delete("/api/cameras/{camera_id}")
async def delete_camera(
    camera_id: str,
    current_user: User = Depends(get_current_user)  # Add this
):
    # Now authenticated
    pass
```

**Note:** This project is designed for **single-user local deployment** without authentication requirements. This query serves as a safety check if auth is added in the future.

---

### 2. `fastapi-sql-injection.ql`

**Detects:** SQL injection vulnerabilities in SQLAlchemy `text()` calls using string formatting.

**CWE:** CWE-089 (SQL Injection)

**Severity:** Error (9.0/10)

**What it catches:**

```python
from sqlalchemy import text

# VULNERABLE - f-string injection
user_input = request.query_params.get("name")
query = text(f"SELECT * FROM users WHERE name = '{user_input}'")  # ❌ SQL injection!
result = await db.execute(query)

# VULNERABLE - .format() injection
query = text("SELECT * FROM users WHERE name = '{}'".format(user_input))  # ❌ Still vulnerable
result = await db.execute(query)

# VULNERABLE - % formatting
query = text("SELECT * FROM users WHERE name = '%s'" % user_input)  # ❌ Still vulnerable
result = await db.execute(query)

# SAFE - Parameterized query
query = text("SELECT * FROM users WHERE name = :name")  # ✓ Safe
result = await db.execute(query, {"name": user_input})
```

**Detection logic:**

1. Find calls to `text()` function (SQLAlchemy raw SQL)
2. Check if argument is a formatted string:
   - **f-strings** (`JoinedStr` AST node)
   - **% formatting** (`BinaryExpr` with `Mod` operator)
   - **`.format()`** (method call)
3. Flag as SQL injection risk

**Why this matters:**

```python
# Attacker input: user_input = "admin' OR '1'='1"
query = text(f"SELECT * FROM users WHERE name = '{user_input}'")
# Becomes: SELECT * FROM users WHERE name = 'admin' OR '1'='1'
# Returns ALL users!
```

**How to fix:**

```python
# Use bindparams for named parameters
from sqlalchemy import text, bindparam

query = text("SELECT * FROM users WHERE name = :name").bindparams(
    bindparam("name", type_=String)
)
result = await db.execute(query, {"name": user_input})

# Or use SQLAlchemy ORM (preferred)
from sqlalchemy import select
from backend.models import User

stmt = select(User).where(User.name == user_input)  # ✓ Automatically parameterized
result = await db.execute(stmt)
```

**Project context:**

- This project uses SQLAlchemy ORM for most queries (safe by default)
- `text()` is only used for complex queries (e.g., aggregations, analytics)
- Always use parameterized queries for user input

---

### 3. `unsafe-file-operations.ql`

**Detects:** File operations using paths that may contain user input without validation.

**CWE:** CWE-022 (Path Traversal)

**Severity:** Error (8.0/10)

**What it catches:**

```python
from pathlib import Path

# VULNERABLE - User can specify arbitrary path
@router.get("/api/images/{filename}")
async def get_image(filename: str):
    # Attacker input: filename = "../../etc/passwd"
    path = Path(f"/export/foscam/{filename}")  # ❌ Path traversal!
    return path.read_bytes()

# VULNERABLE - Direct concatenation
@router.get("/api/logs/{log_file}")
async def get_log(log_file: str):
    # Attacker input: log_file = "../../../root/.ssh/id_rsa"
    with open(f"/var/log/{log_file}", "r") as f:  # ❌ Can read any file!
        return f.read()

# SAFE - Validate path stays within bounds
@router.get("/api/images/{filename}")
async def get_image(filename: str):
    base_dir = Path("/export/foscam")
    requested_path = (base_dir / filename).resolve()

    # Ensure path is still under base_dir
    if not requested_path.is_relative_to(base_dir):  # ✓ Path validation
        raise HTTPException(403, "Invalid path")

    return requested_path.read_bytes()
```

**Detection logic:**

1. Find file operations:
   - `open()` builtin
   - `Path.read_text()`, `Path.read_bytes()`, `Path.write_text()`, `Path.write_bytes()`
   - `Path.unlink()`, `Path.rmdir()`, `Path.rename()`, `Path.remove()`
2. Check if path argument is a formatted string (f-string)
3. Flag as potential path traversal

**Attack examples:**

```python
# Attacker can read any file:
filename = "../../../etc/passwd"
filename = "../../root/.ssh/id_rsa"

# Attacker can write to any location:
filename = "../../../var/www/html/shell.php"
```

**How to fix:**

```python
from pathlib import Path
from fastapi import HTTPException

def validate_safe_path(base_dir: Path, user_input: str) -> Path:
    """Ensure path resolves within base_dir."""
    requested_path = (base_dir / user_input).resolve()

    # Check 1: No ".." components
    if ".." in user_input:
        raise HTTPException(403, "Invalid path: contains '..'")

    # Check 2: Resolved path is under base_dir
    if not requested_path.is_relative_to(base_dir):
        raise HTTPException(403, "Invalid path: outside allowed directory")

    # Check 3: Path exists and is a file (not directory)
    if not requested_path.is_file():
        raise HTTPException(404, "File not found")

    return requested_path

# Usage
@router.get("/api/images/{filename}")
async def get_image(filename: str):
    base_dir = Path("/export/foscam")
    safe_path = validate_safe_path(base_dir, filename)  # ✓ Validated
    return safe_path.read_bytes()
```

**Project context:**

- Camera images uploaded to `/export/foscam/{camera_name}/`
- Frontend requests images by filename
- Must validate paths to prevent traversal outside camera directories

---

## Package Definition

### `qlpack.yml`

```yaml
name: home-security-python-queries
version: 1.0.0
description: Custom CodeQL queries for FastAPI/Python security patterns
dependencies:
  codeql/python-all: '*'
extractor: python
```

**Purpose:**

- Defines this directory as a CodeQL query pack
- Declares dependency on `codeql/python-all` (standard Python library)
- Specifies `python` as the language extractor

**Usage in CI:**

```yaml
# .github/codeql/codeql-config.yml
queries:
  - uses: ./.github/codeql/custom-queries/python # References this pack
```

---

## Testing Queries Locally

### Prerequisites

```bash
# Install CodeQL CLI
# macOS
brew install codeql

# Linux
wget https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip
unzip codeql-linux64.zip -d /opt
export PATH="/opt/codeql:$PATH"
```

### Create CodeQL Database

```bash
# From project root
codeql database create codeql-db-python \
  --language=python \
  --source-root=. \
  --overwrite

# This creates a database in codeql-db-python/
# Takes ~2-5 minutes for this project
```

### Run Individual Query

```bash
# Test SQL injection query
codeql query run \
  .github/codeql/custom-queries/python/fastapi-sql-injection.ql \
  --database=codeql-db-python \
  --output=results.bqrs

# Format results as CSV
codeql bqrs decode results.bqrs --format=csv --output=results.csv
```

### Run All Python Queries

```bash
# Run entire query pack
codeql database analyze codeql-db-python \
  .github/codeql/custom-queries/python \
  --format=sarif-latest \
  --output=results.sarif

# View results
cat results.sarif | jq '.runs[0].results'
```

---

## Query Structure

### Standard Query Format

All queries follow this structure:

```ql
/**
 * @name [User-facing title]
 * @description [What vulnerability this detects and impact]
 * @kind problem
 * @problem.severity error|warning|recommendation
 * @security-severity [0.0-10.0 CVSS-like score]
 * @precision high|medium|low
 * @id py/[unique-identifier]
 * @tags security
 *       external/cwe/cwe-[XXX]
 */

import python  // Standard Python library

// Define AST pattern classes
class VulnerablePattern extends [BaseClass] {
  VulnerablePattern() {
    // Constructor - defines what nodes match this pattern
  }

  // Helper predicates
  predicate isSafe() {
    // Returns true if this pattern has mitigations
  }
}

// Query body
from VulnerablePattern vuln
where vuln.isVulnerable() and not vuln.isSafe()
select vuln, "Message explaining the issue and how to fix it"
```

### Key Components

**Metadata:**

- `@name` - Appears in GitHub Security tab
- `@security-severity` - 0.0 (info) to 10.0 (critical)
- `@precision` - Affects false positive rate
- `@id` - Unique identifier (format: `py/[query-name]`)
- `@tags` - Must include `security` and `external/cwe/cwe-XXX`

**Class definitions:**

- Extend AST node types: `Call`, `Function`, `Decorator`, `Parameter`, etc.
- Constructor defines pattern matching logic
- Predicates define conditional checks

**Query body:**

- `from` - Variables and their types
- `where` - Filter conditions
- `select` - What to report and message

---

## CodeQL Python API

### Common AST Node Types

| Type            | Represents           | Example                      |
| --------------- | -------------------- | ---------------------------- |
| `Function`      | Function definition  | `def foo(): pass`            |
| `Call`          | Function/method call | `db.execute(query)`          |
| `Decorator`     | Function decorator   | `@router.post("/api/users")` |
| `Parameter`     | Function parameter   | `async def foo(x: int)`      |
| `Attribute`     | Attribute access     | `obj.method_name`            |
| `StringLiteral` | String literal       | `"hello"` or `'world'`       |
| `JoinedStr`     | f-string             | `f"Hello {name}"`            |
| `BinaryExpr`    | Binary operation     | `a + b` or `"foo" % bar`     |
| `AssignExpr`    | Assignment           | `x = 5`                      |
| `Name`          | Variable reference   | `my_variable`                |

### Common Predicates

| Predicate                | Returns                           |
| ------------------------ | --------------------------------- | ----- | --------------------------------- |
| `getADecorator()`        | A decorator on this function      |
| `getAnArg()`             | An argument to this function      |
| `getArg(n)`              | The nth argument (0-indexed)      |
| `getFunc()`              | The callable being invoked        |
| `getName()`              | The name of this symbol           |
| `getValue()`             | The value of this expression      |
| `getText()`              | Source text of this node          |
| `getEnclosingFunction()` | The function containing this node |
| `exists(T x              | ...                               | ...)` | True if there exists a matching x |

### Example: Finding FastAPI Routes

```ql
class FastApiRoute extends Function {
  Decorator routeDecorator;
  string httpMethod;

  FastApiRoute() {
    // Find decorators like @router.post("/path")
    exists(Call call, Attribute attr |
      this.getADecorator() = routeDecorator and
      routeDecorator.getValue() = call and
      call.getFunc() = attr and
      (
        attr.getName() = "get" and httpMethod = "GET"
        or
        attr.getName() = "post" and httpMethod = "POST"
        or
        attr.getName() = "put" and httpMethod = "PUT"
        or
        attr.getName() = "delete" and httpMethod = "DELETE"
      )
    )
  }

  string getHttpMethod() { result = httpMethod }

  string getPath() {
    exists(Call call, StringLiteral path |
      routeDecorator.getValue() = call and
      call.getArg(0) = path and
      result = path.getText()
    )
  }
}
```

---

## Common Patterns

### Pattern 1: Find Calls to Specific Function

```ql
class TextCall extends Call {
  TextCall() {
    // text() function from SQLAlchemy
    exists(Name name |
      this.getFunc() = name and
      name.getId() = "text"
    )
  }
}

from TextCall tc
select tc, "Found call to text()"
```

### Pattern 2: Check Function Parameters

```ql
class EndpointWithAuth extends Function {
  predicate hasAuthParam() {
    exists(Parameter p |
      p = this.getAnArg() and
      (
        p.getName().toLowerCase().matches("%auth%") or
        p.getDefault().(Call).getFunc().(Name).getId() = "Depends"
      )
    )
  }
}

from EndpointWithAuth f
where not f.hasAuthParam()
select f, "Endpoint missing auth parameter"
```

### Pattern 3: String Pattern Matching

```ql
class SensitiveStorageKey extends Call {
  predicate hasSensitiveKey() {
    exists(string key |
      key = this.getArg(0).(StringLiteral).getValue().toLowerCase() and
      (
        key.matches("%password%") or
        key.matches("%token%") or
        key.matches("%secret%")
      )
    )
  }
}
```

---

## Integration with CI/CD

### Workflow

1. **Trigger:** Merge to `main` or weekly schedule (Monday 6am UTC)
2. **Initialize:** CodeQL action loads `.github/codeql/codeql-config.yml`
3. **Build database:** CodeQL analyzes Python source code
4. **Run queries:**
   - Standard security queries (`security-and-quality`, `security-extended`)
   - Custom Python queries (this directory)
5. **Upload results:** SARIF format to GitHub Security tab

### Viewing Results

```bash
# In GitHub UI:
Repository → Security → Code scanning alerts → Filter by "CodeQL"

# Results include:
# - Rule ID (e.g., py/fastapi-missing-auth)
# - Severity (Error/Warning)
# - File location with line number
# - Recommendation text
```

### Suppressing False Positives

If a finding is a false positive (safe by design):

```python
# Option 1: Inline comment (if CodeQL supports it in future)
# codeql[py/fastapi-missing-auth]: Public endpoint by design
@router.post("/api/public/subscribe")
async def subscribe(email: str):
    pass

# Option 2: Refactor to match exempt pattern
# Add to health check paths: /health, /ready, /public
@router.post("/api/public/subscribe")  # "public" in path → exempt
async def subscribe(email: str):
    pass

# Option 3: Add authentication (preferred)
@router.post("/api/public/subscribe")
async def subscribe(
    email: str,
    api_key: str = Depends(verify_api_key)  # Add auth
):
    pass
```

---

## Maintenance

### Adding New Queries

1. **Identify vulnerability pattern** - What are you looking for?
2. **Research CWE** - Find appropriate Common Weakness Enumeration
3. **Write query** - Follow template above
4. **Test locally** - Create database and run query
5. **Tune precision** - Adjust to minimize false positives
6. **Update AGENTS.md** - Document in this file

### Query Performance Tips

- **Use `exists()` efficiently** - Avoid nested exists when possible
- **Filter early** - Apply cheap filters before expensive ones
- **Limit scope** - Use `getEnclosingFunction()` instead of project-wide searches
- **Cache results** - Store intermediate results in predicates

### When to Update

- **New FastAPI patterns** - Framework API changes
- **False positives** - Users report safe code flagged as vulnerable
- **New vulnerabilities** - OWASP/CWE publish new attack vectors
- **Performance issues** - Query takes > 5 minutes

---

## Related Documentation

- **Parent directory:** See `../AGENTS.md` for CodeQL overview
- **JavaScript queries:** See `../javascript/AGENTS.md`
- **FastAPI security:** See `/backend/AGENTS.md`
- **CI/CD workflows:** See `/.github/workflows/codeql.yml`

## External Resources

- [CodeQL Python docs](https://codeql.github.com/docs/codeql-language-guides/codeql-for-python/)
- [Python AST reference](https://codeql.github.com/codeql-standard-libraries/python/)
- [CWE database](https://cwe.mitre.org/)
- [OWASP API Security](https://owasp.org/www-project-api-security/)

## Key Takeaways

1. **3 custom Python queries** - Missing auth, SQL injection, path traversal
2. **Target FastAPI patterns** - Project-specific web framework security
3. **High severity focus** - SQL injection and path traversal are errors (8.0-9.0)
4. **Local testing available** - Install CodeQL CLI and create database
5. **Complements other tools** - Works alongside Semgrep (pre-commit) and Mypy
6. **Results in Security tab** - View findings in GitHub UI after merge to main
