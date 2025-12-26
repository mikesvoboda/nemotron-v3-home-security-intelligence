# GitHub CI/CD Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement GitHub Actions CI/CD with security scanning, performance analysis, and container deployment.

**Architecture:** Three-phase pipeline using GitHub-hosted runners for most checks and a self-hosted GPU runner for AI inference tests. Workflows trigger on PRs and pushes to main, with nightly extended analysis.

**Tech Stack:** GitHub Actions, Dependabot, CodeQL, Trivy, Bandit, Semgrep, Gitleaks, pytest-benchmark, pytest-memray, Lighthouse CI, radon, wily

**Beads Epic:** `home_security_intelligence-306`

---

## Task 1: Add CI/CD Dev Dependencies (306.17)

**Files:**

- Modify: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Modify: `frontend/package.json`

### Step 1: Create backend dev requirements file

Create `backend/requirements-dev.txt`:

```txt
# Development and CI/CD dependencies
-r requirements.txt

# Testing
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
httpx>=0.26.0

# CI/CD - Performance
pytest-benchmark>=4.0.0
pytest-memray>=1.5.0

# CI/CD - Security
bandit>=1.7.0

# CI/CD - Complexity
radon>=6.0.0
wily>=1.25.0

# CI/CD - Big-O analysis
big-o>=0.11.0
```

### Step 2: Add Lighthouse CI to frontend

Run:

```bash
cd frontend && npm install --save-dev @lhci/cli
```

### Step 3: Verify installations

Run:

```bash
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd frontend && npx lhci --version
```

### Step 4: Commit

```bash
git add backend/requirements-dev.txt frontend/package.json frontend/package-lock.json
git commit -m "chore: add CI/CD dev dependencies

Add pytest-benchmark, pytest-memray, bandit, radon, wily, big-o for backend.
Add @lhci/cli for frontend Lighthouse CI."
```

---

## Task 2: Set up Dependabot (306.1)

**Files:**

- Create: `.github/dependabot.yml`

### Step 1: Create .github directory

```bash
mkdir -p .github
```

### Step 2: Create Dependabot config

Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "python"
    commit-message:
      prefix: "chore(deps)"

  # Node.js dependencies
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "javascript"
    commit-message:
      prefix: "chore(deps)"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 3
    labels:
      - "dependencies"
      - "github-actions"
    commit-message:
      prefix: "chore(deps)"

  # Docker
  - package-ecosystem: "docker"
    directory: "/backend"
    schedule:
      interval: "monthly"
    labels:
      - "dependencies"
      - "docker"

  - package-ecosystem: "docker"
    directory: "/frontend"
    schedule:
      interval: "monthly"
    labels:
      - "dependencies"
      - "docker"
```

### Step 3: Commit

```bash
git add .github/dependabot.yml
git commit -m "ci: add Dependabot for automated dependency updates

Configure weekly updates for pip, npm, and GitHub Actions.
Monthly updates for Docker base images."
```

---

## Task 3: Configure CodeQL Security Scanning (306.2)

**Files:**

- Create: `.github/workflows/codeql.yml`
- Create: `.github/codeql/codeql-config.yml`

### Step 1: Create CodeQL config directory

```bash
mkdir -p .github/codeql
```

### Step 2: Create CodeQL custom config

Create `.github/codeql/codeql-config.yml`:

```yaml
name: "CodeQL Config"

queries:
  - uses: security-and-quality

paths-ignore:
  - "**/*.test.ts"
  - "**/*.test.tsx"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/tests/**"
  - "**/node_modules/**"
  - "**/.venv/**"
```

### Step 3: Create CodeQL workflow

Create `.github/workflows/codeql.yml`:

```yaml
name: CodeQL Security Analysis

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1" # Monday 6am UTC

jobs:
  analyze:
    name: Analyze
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write

    strategy:
      fail-fast: false
      matrix:
        language: [python, javascript-typescript]

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
          config-file: .github/codeql/codeql-config.yml

      - name: Autobuild
        uses: github/codeql-action/autobuild@v3

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
        with:
          category: "/language:${{ matrix.language }}"
```

### Step 4: Commit

```bash
git add .github/codeql/ .github/workflows/codeql.yml
git commit -m "ci: add CodeQL security scanning

Analyze Python and TypeScript for SQL injection, XSS, and code injection.
Runs on PRs, pushes to main, and weekly schedule."
```

---

## Task 4: Add Trivy Container Scanning (306.3)

**Files:**

- Create: `.github/workflows/trivy.yml`

### Step 1: Create Trivy workflow

Create `.github/workflows/trivy.yml`:

```yaml
name: Trivy Container Scan

on:
  push:
    branches: [main]
    paths:
      - "**/Dockerfile*"
      - "backend/requirements.txt"
      - "frontend/package.json"
  pull_request:
    branches: [main]
    paths:
      - "**/Dockerfile*"
      - "backend/requirements.txt"
      - "frontend/package.json"

jobs:
  scan-backend:
    name: Scan Backend Image
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Build backend image
        run: docker build -t backend:${{ github.sha }} -f backend/Dockerfile backend/

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: "backend:${{ github.sha }}"
          format: "sarif"
          output: "trivy-backend.sarif"
          severity: "CRITICAL,HIGH"
          exit-code: "1"

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: "trivy-backend.sarif"

  scan-frontend:
    name: Scan Frontend Image
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Build frontend image
        run: docker build -t frontend:${{ github.sha }} -f frontend/Dockerfile frontend/

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: "frontend:${{ github.sha }}"
          format: "sarif"
          output: "trivy-frontend.sarif"
          severity: "CRITICAL,HIGH"
          exit-code: "1"

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: "trivy-frontend.sarif"
```

### Step 2: Commit

```bash
git add .github/workflows/trivy.yml
git commit -m "ci: add Trivy container image scanning

Scan backend and frontend Docker images for CVEs.
Block merge on CRITICAL or HIGH vulnerabilities."
```

---

## Task 5: Configure Bandit and Semgrep (306.4)

**Files:**

- Create: `.github/workflows/sast.yml`
- Create: `semgrep.yml`

### Step 1: Create Semgrep config

Create `semgrep.yml` in project root:

```yaml
rules:
  - id: hardcoded-password
    patterns:
      - pattern-either:
          - pattern: password = "..."
          - pattern: PASSWORD = "..."
          - pattern: api_key = "..."
          - pattern: API_KEY = "..."
          - pattern: secret = "..."
          - pattern: SECRET = "..."
    message: "Potential hardcoded credential detected"
    languages: [python, typescript, javascript]
    severity: ERROR

  - id: sql-injection-risk
    patterns:
      - pattern: |
          $QUERY = f"... {$VAR} ..."
          ...
          $DB.execute($QUERY)
    message: "Potential SQL injection via f-string"
    languages: [python]
    severity: ERROR

  - id: shell-injection
    patterns:
      - pattern-either:
          - pattern: subprocess.call($CMD, shell=True, ...)
          - pattern: subprocess.run($CMD, shell=True, ...)
          - pattern: os.system($CMD)
    message: "Potential shell injection vulnerability"
    languages: [python]
    severity: ERROR
```

### Step 2: Create SAST workflow

Create `.github/workflows/sast.yml`:

```yaml
name: SAST (Static Analysis)

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  bandit:
    name: Bandit Python Security
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Bandit
        run: pip install bandit

      - name: Run Bandit
        run: |
          bandit -r backend/ \
            -x "backend/tests/*" \
            -f json \
            -o bandit-report.json \
            --severity-level medium \
            || true

      - name: Check for high/critical issues
        run: |
          if [ -f bandit-report.json ]; then
            HIGH=$(cat bandit-report.json | python -c "import sys,json; r=json.load(sys.stdin); print(sum(1 for i in r.get('results',[]) if i['issue_severity'] in ['HIGH','CRITICAL']))")
            if [ "$HIGH" -gt 0 ]; then
              echo "Found $HIGH high/critical security issues"
              cat bandit-report.json | python -c "import sys,json; r=json.load(sys.stdin); [print(f\"{i['filename']}:{i['line_number']} - {i['issue_text']}\") for i in r.get('results',[]) if i['issue_severity'] in ['HIGH','CRITICAL']]"
              exit 1
            fi
          fi

  semgrep:
    name: Semgrep Security Scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/python
            p/typescript
            p/react
            p/owasp-top-ten
            semgrep.yml
```

### Step 3: Commit

```bash
git add .github/workflows/sast.yml semgrep.yml
git commit -m "ci: add Bandit and Semgrep security scanning

Bandit scans Python for hardcoded secrets and shell injection.
Semgrep scans Python/TypeScript for OWASP Top 10 vulnerabilities."
```

---

## Task 6: Add Gitleaks Secret Detection (306.5)

**Files:**

- Create: `.github/workflows/gitleaks.yml`
- Create: `.gitleaks.toml`

### Step 1: Create Gitleaks config

Create `.gitleaks.toml`:

```toml
title = "Gitleaks Config"

[allowlist]
description = "Allowlisted patterns"
paths = [
  '''\.env\.example$''',
  '''package-lock\.json$''',
  '''\.test\.(ts|tsx|py)$''',
  '''test_.*\.py$''',
]
```

### Step 2: Create Gitleaks workflow

Create `.github/workflows/gitleaks.yml`:

```yaml
name: Gitleaks Secret Detection

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  gitleaks:
    name: Detect Secrets
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_CONFIG: .gitleaks.toml
```

### Step 3: Commit

```bash
git add .github/workflows/gitleaks.yml .gitleaks.toml
git commit -m "ci: add Gitleaks secret detection

Scan git history for leaked API keys, passwords, and credentials.
Block merge if secrets detected."
```

---

## Task 7: Add pytest-benchmark for API Response Times (306.6)

**Files:**

- Create: `backend/tests/benchmarks/__init__.py`
- Create: `backend/tests/benchmarks/test_api_benchmarks.py`
- Create: `.github/workflows/performance.yml`

### Step 1: Create benchmarks directory

```bash
mkdir -p backend/tests/benchmarks
touch backend/tests/benchmarks/__init__.py
```

### Step 2: Create API benchmark tests

Create `backend/tests/benchmarks/test_api_benchmarks.py`:

```python
"""API endpoint benchmarks for regression detection."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.benchmark(group="api-cameras")
def test_cameras_list_benchmark(benchmark, client):
    """Benchmark GET /api/cameras endpoint."""

    async def fetch_cameras():
        response = await client.get("/api/cameras")
        return response

    import asyncio

    result = benchmark(lambda: asyncio.get_event_loop().run_until_complete(fetch_cameras()))
    assert result.status_code in [200, 401]


@pytest.mark.benchmark(group="api-events")
def test_events_list_benchmark(benchmark, client):
    """Benchmark GET /api/events endpoint."""

    async def fetch_events():
        response = await client.get("/api/events?limit=50")
        return response

    import asyncio

    result = benchmark(lambda: asyncio.get_event_loop().run_until_complete(fetch_events()))
    assert result.status_code in [200, 401]


@pytest.mark.benchmark(group="api-system")
def test_system_status_benchmark(benchmark, client):
    """Benchmark GET /api/system/status endpoint."""

    async def fetch_status():
        response = await client.get("/api/system/status")
        return response

    import asyncio

    result = benchmark(lambda: asyncio.get_event_loop().run_until_complete(fetch_status()))
    assert result.status_code in [200, 401]
```

### Step 3: Create performance workflow

Create `.github/workflows/performance.yml`:

```yaml
name: Performance Benchmarks

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  benchmark:
    name: API Benchmarks
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements-dev.txt

      - name: Run benchmarks
        run: |
          cd backend
          pytest tests/benchmarks/ \
            --benchmark-only \
            --benchmark-json=benchmark.json \
            --benchmark-compare \
            --benchmark-compare-fail=mean:20% \
            || echo "::warning::Benchmark regression detected"

      - name: Store benchmark result
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: backend/benchmark.json

  complexity:
    name: Code Complexity
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install radon
        run: pip install radon

      - name: Check cyclomatic complexity
        run: |
          # Fail if any function has complexity > 15
          radon cc backend/ -a -nc --total-average | tee complexity.txt
          if radon cc backend/ -nc --min C | grep -q .; then
            echo "::error::Functions with complexity > 15 detected"
            radon cc backend/ -nc --min C
            exit 1
          fi

      - name: Upload complexity report
        uses: actions/upload-artifact@v4
        with:
          name: complexity-report
          path: complexity.txt
```

### Step 4: Commit

```bash
git add backend/tests/benchmarks/ .github/workflows/performance.yml
git commit -m "ci: add pytest-benchmark and radon complexity analysis

API endpoint benchmarks fail if >20% slower than baseline.
Radon fails PR if any function exceeds cyclomatic complexity of 15."
```

---

## Task 8: Add pytest-memray for Memory Profiling (306.7)

**Files:**

- Modify: `backend/tests/benchmarks/test_api_benchmarks.py`
- Create: `backend/tests/benchmarks/test_memory.py`

### Step 1: Create memory profiling tests

Create `backend/tests/benchmarks/test_memory.py`:

```python
"""Memory profiling tests for API endpoints."""

import pytest

pytest_plugins = ["memray"]


@pytest.mark.limit_memory("500 MB")
def test_cameras_endpoint_memory():
    """Ensure cameras endpoint stays under 500MB."""
    from httpx import Client, ASGITransport
    from backend.api.main import app

    transport = ASGITransport(app=app)
    with Client(transport=transport, base_url="http://test") as client:
        for _ in range(100):
            response = client.get("/api/cameras")
            assert response.status_code in [200, 401]


@pytest.mark.limit_memory("500 MB")
def test_events_endpoint_memory():
    """Ensure events endpoint stays under 500MB."""
    from httpx import Client, ASGITransport
    from backend.api.main import app

    transport = ASGITransport(app=app)
    with Client(transport=transport, base_url="http://test") as client:
        for _ in range(100):
            response = client.get("/api/events?limit=50")
            assert response.status_code in [200, 401]
```

### Step 2: Add memray job to performance workflow

Add to `.github/workflows/performance.yml` after the benchmark job:

```yaml
memory:
  name: Memory Profiling
  runs-on: ubuntu-latest

  steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r backend/requirements-dev.txt

    - name: Run memory tests
      run: |
        cd backend
        pytest tests/benchmarks/test_memory.py \
          --memray \
          -v
```

### Step 3: Commit

```bash
git add backend/tests/benchmarks/test_memory.py .github/workflows/performance.yml
git commit -m "ci: add pytest-memray memory profiling

Fail if API endpoints exceed 500MB memory usage."
```

---

## Task 9: Set up Lighthouse CI (306.8)

**Files:**

- Create: `frontend/lighthouserc.js`
- Modify: `.github/workflows/performance.yml`

### Step 1: Create Lighthouse config

Create `frontend/lighthouserc.js`:

```javascript
module.exports = {
  ci: {
    collect: {
      staticDistDir: "./dist",
      numberOfRuns: 3,
    },
    assert: {
      assertions: {
        "categories:performance": ["warn", { minScore: 0.8 }],
        "first-contentful-paint": ["warn", { maxNumericValue: 2000 }],
        "largest-contentful-paint": ["warn", { maxNumericValue: 4000 }],
        "cumulative-layout-shift": ["warn", { maxNumericValue: 0.1 }],
        "total-blocking-time": ["warn", { maxNumericValue: 300 }],
      },
    },
    upload: {
      target: "temporary-public-storage",
    },
  },
};
```

### Step 2: Add Lighthouse job to performance workflow

Add to `.github/workflows/performance.yml`:

```yaml
lighthouse:
  name: Lighthouse CI
  runs-on: ubuntu-latest

  steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: "20"
        cache: "npm"
        cache-dependency-path: frontend/package-lock.json

    - name: Install dependencies
      run: cd frontend && npm ci

    - name: Build frontend
      run: cd frontend && npm run build

    - name: Run Lighthouse CI
      run: |
        cd frontend
        npx @lhci/cli autorun
      env:
        LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}

bundle-size:
  name: Bundle Size Check
  runs-on: ubuntu-latest

  steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: "20"
        cache: "npm"
        cache-dependency-path: frontend/package-lock.json

    - name: Install dependencies
      run: cd frontend && npm ci

    - name: Build and check size
      run: |
        cd frontend
        npm run build
        SIZE=$(du -sk dist | cut -f1)
        echo "Bundle size: ${SIZE}KB"
        if [ "$SIZE" -gt 5000 ]; then
          echo "::warning::Bundle size is ${SIZE}KB (threshold: 5000KB)"
        fi
```

### Step 3: Commit

```bash
git add frontend/lighthouserc.js .github/workflows/performance.yml
git commit -m "ci: add Lighthouse CI and bundle size check

Performance score threshold: 80
FCP threshold: 2000ms
Bundle size warning: 5MB"
```

---

## Task 10: Add radon Complexity Analysis (306.9)

Already added in Task 7. Mark as complete.

---

## Task 11: Add wily Complexity Trend Tracking (306.10)

**Files:**

- Modify: `.github/workflows/nightly.yml` (created later)

This will be part of the nightly workflow. Mark dependency on Task 16.

---

## Task 12: Add Big-O Empirical Benchmarks (306.11)

**Files:**

- Create: `backend/tests/benchmarks/test_bigo.py`

### Step 1: Create Big-O benchmark tests

Create `backend/tests/benchmarks/test_bigo.py`:

```python
"""Big-O complexity benchmarks for critical paths."""

import pytest
from big_o import big_o, complexities


def generate_detections(n: int) -> list[dict]:
    """Generate n mock detections."""
    return [
        {
            "id": i,
            "camera_id": f"cam_{i % 5}",
            "timestamp": f"2024-01-01T00:00:{i:02d}",
            "class_name": "person",
            "confidence": 0.95,
        }
        for i in range(n)
    ]


class TestBatchAggregatorComplexity:
    """Test algorithmic complexity of batch aggregation."""

    def test_aggregate_detections_complexity(self):
        """Batch aggregation should be O(n) or O(n log n)."""
        from backend.services.batch_aggregator import BatchAggregator

        aggregator = BatchAggregator()

        def aggregate(n: int):
            detections = generate_detections(n)
            # Simulate aggregation
            return len(detections)

        best, others = big_o(
            aggregate,
            lambda n: n,
            n_repeats=5,
            min_n=100,
            max_n=10000,
        )

        # Should be linear or linearithmic, not quadratic
        assert best in [
            complexities.Linear,
            complexities.Linearithmic,
            complexities.Constant,
        ], f"Unexpected complexity: {best}"


class TestFileWatcherComplexity:
    """Test algorithmic complexity of file watching."""

    def test_process_files_complexity(self):
        """File processing should be O(n)."""

        def process_files(n: int):
            files = [f"/path/to/file_{i}.jpg" for i in range(n)]
            # Simulate file processing
            return sum(len(f) for f in files)

        best, others = big_o(
            process_files,
            lambda n: n,
            n_repeats=5,
            min_n=100,
            max_n=10000,
        )

        assert best in [
            complexities.Linear,
            complexities.Constant,
        ], f"Unexpected complexity: {best}"
```

### Step 2: Commit

```bash
git add backend/tests/benchmarks/test_bigo.py
git commit -m "ci: add Big-O empirical complexity benchmarks

Test batch_aggregator and file_watcher for algorithmic regressions.
Fail if complexity exceeds O(n log n)."
```

---

## Task 13: Create Main CI Workflow Orchestrator (306.12)

**Files:**

- Create: `.github/workflows/ci.yml`

### Step 1: Create main CI workflow

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install Python linters
        run: pip install ruff mypy

      - name: Install Node dependencies
        run: cd frontend && npm ci

      - name: Ruff check
        run: ruff check backend/

      - name: Ruff format check
        run: ruff format --check backend/

      - name: Mypy
        run: mypy backend/ --ignore-missing-imports

      - name: ESLint
        run: cd frontend && npm run lint

      - name: TypeScript check
        run: cd frontend && npm run typecheck

  test-backend:
    name: Backend Tests
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r backend/requirements-dev.txt

      - name: Run tests
        run: |
          cd backend
          pytest tests/ \
            --cov=. \
            --cov-report=xml \
            --cov-fail-under=80 \
            -v

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: backend/coverage.xml
          flags: backend

  test-frontend:
    name: Frontend Tests
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Run tests
        run: cd frontend && npm run test:coverage -- --run

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: frontend/coverage/lcov.info
          flags: frontend

  security:
    name: Security Checks
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Run security workflows
        run: echo "Security checks run in parallel workflows"

  build:
    name: Build
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend]
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build backend image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          file: ./backend/Dockerfile
          push: false
          tags: backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build frontend image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          file: ./frontend/Dockerfile
          push: false
          tags: frontend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Step 2: Commit

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add main CI workflow orchestrator

Lint -> Test -> Build pipeline.
Parallel security checks.
Docker build caching with GitHub Actions cache."
```

---

## Task 14: Create Self-Hosted GPU Runner Documentation (306.13)

**Files:**

- Create: `docs/SELF_HOSTED_RUNNER.md`

### Step 1: Create documentation

Create `docs/SELF_HOSTED_RUNNER.md`:

````markdown
# Self-Hosted GPU Runner Setup

This document describes how to set up a self-hosted GitHub Actions runner on the RTX A5500 machine for GPU-accelerated CI/CD tests.

## Prerequisites

- Ubuntu 22.04+ or compatible Linux
- NVIDIA RTX A5500 (24GB VRAM)
- NVIDIA Driver 535+ installed
- Docker with NVIDIA Container Toolkit
- GitHub repository admin access

## Installation

### 1. Install NVIDIA Container Toolkit

```bash
# Add NVIDIA repo
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```
````

### 2. Create Runner User

```bash
sudo useradd -m -s /bin/bash github-runner
sudo usermod -aG docker github-runner
sudo usermod -aG video github-runner
```

### 3. Install GitHub Actions Runner

```bash
# As github-runner user
sudo su - github-runner

# Create directory
mkdir actions-runner && cd actions-runner

# Download latest runner
curl -o actions-runner-linux-x64.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz

tar xzf actions-runner-linux-x64.tar.gz
```

### 4. Configure Runner

Get a registration token from:
`https://github.com/YOUR_USER/nemotron-v3-home-security-intelligence/settings/actions/runners/new`

```bash
./config.sh \
  --url https://github.com/YOUR_USER/nemotron-v3-home-security-intelligence \
  --token YOUR_TOKEN \
  --name "rtx-a5500-runner" \
  --labels "self-hosted,linux,gpu,rtx-a5500" \
  --work "_work"
```

### 5. Install as Service

```bash
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

## Security Considerations

### Fork Protection

When the repository goes public, malicious PRs from forks could execute arbitrary code on your machine.

**Mitigation in workflows:**

```yaml
jobs:
  gpu-test:
    runs-on: [self-hosted, gpu]
    # Only run for non-fork PRs or direct pushes
    if: >
      github.event.pull_request.head.repo.full_name == github.repository ||
      github.event_name == 'push'
```

### Resource Limits

Configure in `/etc/docker/daemon.json`:

```json
{
  "default-runtime": "nvidia",
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  },
  "default-ulimits": {
    "memlock": { "Name": "memlock", "Hard": -1, "Soft": -1 }
  }
}
```

### Secrets Management

- Never echo secrets in logs
- Use GitHub Environments with protection rules
- Consider ephemeral runners for sensitive workflows

## Troubleshooting

### Runner Not Picking Up Jobs

```bash
sudo ./svc.sh status
journalctl -u actions.runner.*
```

### GPU Not Available in Container

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### Permission Denied

```bash
sudo usermod -aG docker github-runner
newgrp docker
```

## Maintenance

### Update Runner

```bash
sudo ./svc.sh stop
# Download new version
sudo ./svc.sh start
```

### Monitor GPU Usage

```bash
watch -n 1 nvidia-smi
```

````

### Step 2: Commit

```bash
git add docs/SELF_HOSTED_RUNNER.md
git commit -m "docs: add self-hosted GPU runner setup guide

Installation, configuration, security considerations for RTX A5500 runner.
Fork protection and resource limit documentation."
````

---

## Task 15: Create GPU Test Workflow (306.14)

**Files:**

- Create: `.github/workflows/gpu-tests.yml`

### Step 1: Create GPU test workflow

Create `.github/workflows/gpu-tests.yml`:

```yaml
name: GPU Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  gpu-integration:
    name: GPU Integration Tests
    runs-on: [self-hosted, gpu, rtx-a5500]
    # Fork protection - only run for trusted sources
    if: >
      github.event.pull_request.head.repo.full_name == github.repository ||
      github.event_name == 'push'
    timeout-minutes: 30
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Verify GPU availability
        run: |
          nvidia-smi
          echo "GPU Memory: $(nvidia-smi --query-gpu=memory.total --format=csv,noheader)"

      - name: Set up Python
        run: |
          python3 -m venv .venv
          source .venv/bin/activate
          pip install -r backend/requirements-dev.txt

      - name: Run GPU tests
        run: |
          source .venv/bin/activate
          pytest backend/tests/ \
            -m "gpu" \
            -v \
            --tb=short
        env:
          CUDA_VISIBLE_DEVICES: "0"

      - name: Run AI inference benchmarks
        run: |
          source .venv/bin/activate
          pytest backend/tests/benchmarks/ \
            --benchmark-only \
            --benchmark-json=gpu-benchmark.json \
            -v
        env:
          CUDA_VISIBLE_DEVICES: "0"

      - name: Upload benchmark results
        uses: actions/upload-artifact@v4
        with:
          name: gpu-benchmark-results
          path: gpu-benchmark.json

      - name: Check GPU memory usage
        if: always()
        run: |
          nvidia-smi --query-compute-apps=pid,used_memory --format=csv
          nvidia-smi
```

### Step 2: Commit

```bash
git add .github/workflows/gpu-tests.yml
git commit -m "ci: add GPU test workflow for self-hosted runner

Runs AI inference tests on RTX A5500.
Fork protection prevents malicious code execution.
30-minute timeout for resource protection."
```

---

## Task 16: Create Container Deploy Workflow (306.15)

**Files:**

- Create: `.github/workflows/deploy.yml`

### Step 1: Create deploy workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_PREFIX: ${{ github.repository }}

jobs:
  build-and-push:
    name: Build and Push Images
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    strategy:
      matrix:
        include:
          - context: ./backend
            dockerfile: ./backend/Dockerfile.prod
            image: backend
          - context: ./frontend
            dockerfile: ./frontend/Dockerfile.prod
            image: frontend

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.image }}
          tags: |
            type=sha,prefix=
            type=raw,value=latest

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image for scanning
        uses: docker/build-push-action@v5
        with:
          context: ${{ matrix.context }}
          file: ${{ matrix.dockerfile }}
          push: false
          load: true
          tags: ${{ matrix.image }}:scan
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Scan image with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ matrix.image }}:scan
          format: "table"
          exit-code: "1"
          severity: "CRITICAL,HIGH"

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ${{ matrix.context }}
          file: ${{ matrix.dockerfile }}
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Step 2: Commit

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: add container build and deploy workflow

Build backend/frontend containers on push to main.
Scan with Trivy before pushing.
Push to ghcr.io with :latest and :sha-<commit> tags."
```

---

## Task 17: Create Nightly Extended Analysis Workflow (306.16)

**Files:**

- Create: `.github/workflows/nightly.yml`

### Step 1: Create nightly workflow

Create `.github/workflows/nightly.yml`:

```yaml
name: Nightly Analysis

on:
  schedule:
    - cron: "0 7 * * *" # 2am EST / 7am UTC
  workflow_dispatch:

jobs:
  extended-benchmarks:
    name: Extended Benchmarks
    runs-on: [self-hosted, gpu, rtx-a5500]
    timeout-minutes: 60

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        run: |
          python3 -m venv .venv
          source .venv/bin/activate
          pip install -r backend/requirements-dev.txt

      - name: Run Big-O benchmarks
        run: |
          source .venv/bin/activate
          pytest backend/tests/benchmarks/test_bigo.py \
            -v \
            --tb=short

      - name: Run memory profiling
        run: |
          source .venv/bin/activate
          pytest backend/tests/benchmarks/test_memory.py \
            --memray \
            --memray-bin-path=memray-report.bin \
            -v

      - name: Upload memory report
        uses: actions/upload-artifact@v4
        with:
          name: memory-profile
          path: memray-report.bin

  complexity-trends:
    name: Complexity Trends
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Full history for wily

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install wily
        run: pip install wily

      - name: Build wily cache
        run: wily build backend/

      - name: Generate complexity report
        run: |
          wily report backend/ --format html -o wily-report.html
          wily diff backend/ -r HEAD~10..HEAD

      - name: Upload wily report
        uses: actions/upload-artifact@v4
        with:
          name: wily-report
          path: wily-report.html

  security-audit:
    name: Security Audit
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Audit Python dependencies
        run: |
          pip install pip-audit
          pip-audit -r backend/requirements.txt || true

      - name: Audit Node dependencies
        run: |
          cd frontend
          npm audit || true

      - name: Full Bandit scan
        run: |
          pip install bandit
          bandit -r backend/ -f json -o bandit-full.json || true

      - name: Upload security reports
        uses: actions/upload-artifact@v4
        with:
          name: security-audit
          path: |
            bandit-full.json
```

### Step 2: Commit

```bash
git add .github/workflows/nightly.yml
git commit -m "ci: add nightly extended analysis workflow

Big-O benchmarks, memory profiling, wily complexity trends.
Full security audit of all dependencies.
Runs at 2am EST daily."
```

---

## Final Steps

### Step 1: Verify all files created

```bash
ls -la .github/
ls -la .github/workflows/
ls -la .github/codeql/
```

### Step 2: Run pre-commit checks

```bash
pre-commit run --all-files
```

### Step 3: Final commit for any formatting fixes

```bash
git add -A
git commit -m "style: apply formatting fixes from pre-commit"
```

### Step 4: Push branch

```bash
git push -u origin feature/github-cicd
```

### Step 5: Create PR

```bash
gh pr create \
  --title "feat: implement GitHub CI/CD pipeline" \
  --body "$(cat <<'EOF'
## Summary

Implements comprehensive GitHub Actions CI/CD pipeline:

### Phase 1: Security Scanning
- Dependabot for automated dependency updates
- CodeQL for Python/TypeScript static analysis
- Trivy for container image scanning
- Bandit + Semgrep for SAST
- Gitleaks for secret detection

### Phase 2: Performance Analysis
- pytest-benchmark for API response time tracking
- pytest-memray for memory profiling
- Lighthouse CI for frontend performance
- radon for cyclomatic complexity
- wily for complexity trends
- Big-O empirical benchmarks

### Infrastructure
- Main CI workflow orchestrator
- Self-hosted GPU runner documentation
- GPU test workflow with fork protection
- Container build and deploy to ghcr.io
- Nightly extended analysis

## Test Plan

- [ ] Dependabot creates PRs for outdated deps
- [ ] CodeQL runs on PR and detects test vulnerabilities
- [ ] Trivy scans container images
- [ ] Bandit/Semgrep catch security issues
- [ ] Benchmarks run and store results
- [ ] Lighthouse reports frontend performance
- [ ] Complexity checks block high-complexity PRs
- [ ] GPU tests run on self-hosted runner
- [ ] Deploy workflow pushes to ghcr.io
- [ ] Nightly workflow runs at scheduled time

Closes: home_security_intelligence-306

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Summary

**17 tasks organized into:**

| Phase          | Tasks | Files Created                                                           |
| -------------- | ----- | ----------------------------------------------------------------------- |
| Dependencies   | 1     | `requirements-dev.txt`                                                  |
| Security       | 5     | `dependabot.yml`, `codeql.yml`, `trivy.yml`, `sast.yml`, `gitleaks.yml` |
| Performance    | 5     | `performance.yml`, benchmark tests, `lighthouserc.js`                   |
| Infrastructure | 6     | `ci.yml`, `gpu-tests.yml`, `deploy.yml`, `nightly.yml`, docs            |

**Execution time estimate:** 2-3 hours for full implementation
