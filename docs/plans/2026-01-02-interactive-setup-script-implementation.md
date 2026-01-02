# Interactive Setup Script Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create an interactive setup script that enables new users to easily configure the home security intelligence project for their environment.

**Architecture:** Cross-platform Python script (stdlib only, optional rich) that generates `.env` and `docker-compose.override.yml` files. Two modes: quick (accept defaults with Enter) and guided (step-by-step with explanations).

**Tech Stack:** Python 3.14 (stdlib only), Docker Compose override files, Pydantic Settings, React + TypeScript

---

## Task 1: Add grafana_url Setting to Backend Config

**Files:**

- Modify: `backend/core/config.py:267-280` (near other service URLs)
- Test: `backend/tests/unit/core/test_config.py`

**Step 1: Write the failing test**

```python
# In backend/tests/unit/core/test_config.py - add to existing test class
def test_grafana_url_default_value():
    """Test that grafana_url has correct default value."""
    settings = Settings(database_url="postgresql+asyncpg://test:test@localhost:5432/test")
    assert settings.grafana_url == "http://localhost:3002"

def test_grafana_url_custom_value(monkeypatch):
    """Test that grafana_url can be customized via environment."""
    monkeypatch.setenv("GRAFANA_URL", "http://grafana.local:3000")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    # Clear cache to pick up new env var
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.grafana_url == "http://grafana.local:3000"
    get_settings.cache_clear()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/core/test_config.py::test_grafana_url_default_value -v`
Expected: FAIL with "AttributeError: 'Settings' object has no attribute 'grafana_url'"

**Step 3: Write minimal implementation**

Add to `backend/core/config.py` after the enrichment_url field (around line 280):

```python
    # Monitoring URLs
    grafana_url: str = Field(
        default="http://localhost:3002",
        description="Grafana dashboard URL for frontend link",
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/core/test_config.py::test_grafana_url_default_value backend/tests/unit/core/test_config.py::test_grafana_url_custom_value -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/core/config.py backend/tests/unit/core/test_config.py
git commit -m "feat(config): add grafana_url setting for configurable dashboard URL"
```

---

## Task 2: Add grafana_url to ConfigResponse Schema

**Files:**

- Modify: `backend/api/schemas/system.py:161-209` (ConfigResponse class)
- Test: `backend/tests/unit/api/schemas/test_system.py`

**Step 1: Write the failing test**

```python
# In backend/tests/unit/api/schemas/test_system.py
from backend.api.schemas.system import ConfigResponse

def test_config_response_includes_grafana_url():
    """Test that ConfigResponse includes grafana_url field."""
    response = ConfigResponse(
        app_name="Test App",
        version="1.0.0",
        retention_days=30,
        batch_window_seconds=90,
        batch_idle_timeout_seconds=30,
        detection_confidence_threshold=0.5,
        grafana_url="http://localhost:3002",
    )
    assert response.grafana_url == "http://localhost:3002"

    # Test serialization
    data = response.model_dump()
    assert "grafana_url" in data
    assert data["grafana_url"] == "http://localhost:3002"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/unit/api/schemas/test_system.py::test_config_response_includes_grafana_url -v`
Expected: FAIL with validation error (missing grafana_url field)

**Step 3: Write minimal implementation**

Add to `backend/api/schemas/system.py` ConfigResponse class (around line 197):

```python
    grafana_url: str = Field(
        ...,
        description="Grafana dashboard URL for frontend link",
    )
```

Update the example in model_config (around line 206):

```python
            "example": {
                "app_name": "Home Security Intelligence",
                "version": "0.1.0",
                "retention_days": 30,
                "batch_window_seconds": 90,
                "batch_idle_timeout_seconds": 30,
                "detection_confidence_threshold": 0.5,
                "grafana_url": "http://localhost:3002",
            }
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/unit/api/schemas/test_system.py::test_config_response_includes_grafana_url -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/schemas/system.py backend/tests/unit/api/schemas/test_system.py
git commit -m "feat(schemas): add grafana_url to ConfigResponse schema"
```

---

## Task 3: Expose grafana_url in System Config API Endpoint

**Files:**

- Modify: `backend/api/routes/system.py:1031-1051` (get_config endpoint)
- Test: `backend/tests/integration/api/routes/test_system.py`

**Step 1: Write the failing test**

```python
# In backend/tests/integration/api/routes/test_system.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_config_includes_grafana_url(client: AsyncClient):
    """Test that GET /api/system/config includes grafana_url."""
    response = await client.get("/api/system/config")
    assert response.status_code == 200
    data = response.json()
    assert "grafana_url" in data
    assert data["grafana_url"].startswith("http")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/integration/api/routes/test_system.py::test_get_config_includes_grafana_url -v -n0`
Expected: FAIL with KeyError or assertion error (grafana_url not in response)

**Step 3: Write minimal implementation**

Update `backend/api/routes/system.py` get_config endpoint (around line 1043-1050):

```python
@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Get public configuration settings."""
    settings = get_settings()

    return ConfigResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        retention_days=settings.retention_days,
        batch_window_seconds=settings.batch_window_seconds,
        batch_idle_timeout_seconds=settings.batch_idle_timeout_seconds,
        detection_confidence_threshold=settings.detection_confidence_threshold,
        grafana_url=settings.grafana_url,  # Add this line
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/integration/api/routes/test_system.py::test_get_config_includes_grafana_url -v -n0`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/routes/system.py backend/tests/integration/api/routes/test_system.py
git commit -m "feat(api): expose grafana_url in system config endpoint"
```

---

## Task 4: Update Frontend to Use Dynamic Grafana URL

**Files:**

- Modify: `frontend/src/components/system/SystemMonitoringPage.tsx:391`
- Modify: `frontend/src/services/api.ts` (if needed for config fetching)
- Test: `frontend/src/components/system/SystemMonitoringPage.test.tsx`

**Step 1: Write the failing test**

```typescript
// In frontend/src/components/system/SystemMonitoringPage.test.tsx
// Update the existing test or add new one

describe('Grafana link', () => {
  it('uses grafana_url from config API', async () => {
    // Mock the config API response
    server.use(
      rest.get('/api/system/config', (req, res, ctx) => {
        return res(ctx.json({
          app_name: 'Home Security Intelligence',
          version: '0.1.0',
          retention_days: 30,
          batch_window_seconds: 90,
          batch_idle_timeout_seconds: 30,
          detection_confidence_threshold: 0.5,
          grafana_url: 'http://custom-grafana:3333',
        }));
      })
    );

    render(<SystemMonitoringPage />);

    // Wait for config to load
    await waitFor(() => {
      const grafanaLink = screen.getByRole('link', { name: /grafana/i });
      expect(grafanaLink).toHaveAttribute('href', 'http://custom-grafana:3333');
    });
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run SystemMonitoringPage.test.tsx`
Expected: FAIL (grafana link still has hardcoded URL)

**Step 3: Write minimal implementation**

Update `frontend/src/components/system/SystemMonitoringPage.tsx`:

1. Add state for grafana URL:

```typescript
const [grafanaUrl, setGrafanaUrl] = useState<string>("http://localhost:3002");
```

2. Fetch config on mount:

```typescript
useEffect(() => {
  const fetchConfig = async () => {
    try {
      const response = await fetch("/api/system/config");
      if (response.ok) {
        const config = await response.json();
        if (config.grafana_url) {
          setGrafanaUrl(config.grafana_url);
        }
      }
    } catch (error) {
      console.error("Failed to fetch config:", error);
    }
  };
  fetchConfig();
}, []);
```

3. Replace hardcoded URL (line 391):

```typescript
// Before:
href = "http://localhost:3002";

// After:
href = { grafanaUrl };
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run SystemMonitoringPage.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/system/SystemMonitoringPage.tsx frontend/src/components/system/SystemMonitoringPage.test.tsx
git commit -m "feat(frontend): use dynamic grafana_url from config API"
```

---

## Task 5: Update Vite Config for Configurable Dev Proxy

**Files:**

- Modify: `frontend/vite.config.ts:14-22`
- Test: Manual verification (Vite config)

**Step 1: Document current hardcoded values**

Current hardcoded values in `frontend/vite.config.ts`:

- Line 15: `target: 'http://localhost:8000'`
- Line 19: `target: 'ws://localhost:8000'`

**Step 2: Write implementation**

Update `frontend/vite.config.ts`:

```typescript
export default defineConfig(({ mode }) => {
  // Load env file based on mode
  const env = loadEnv(mode, process.cwd(), "");

  const backendUrl = env.VITE_DEV_BACKEND_URL || "http://localhost:8000";
  const wsBackendUrl = backendUrl.replace(/^http/, "ws");

  return {
    plugins: [react()],
    cacheDir: ".vitest",
    server: {
      port: 5173,
      strictPort: true,
      host: true,
      proxy: {
        "/api": {
          target: backendUrl,
          changeOrigin: true,
        },
        "/ws": {
          target: wsBackendUrl,
          ws: true,
          changeOrigin: true,
        },
      },
    },
    // ... rest of config
  };
});
```

**Step 3: Add import for loadEnv**

```typescript
import { defineConfig, loadEnv } from "vite";
```

**Step 4: Verify configuration**

Run: `cd frontend && npm run dev`
Expected: Dev server starts with default localhost:8000 proxy

**Step 5: Commit**

```bash
git add frontend/vite.config.ts
git commit -m "feat(frontend): make dev proxy URL configurable via VITE_DEV_BACKEND_URL"
```

---

## Task 6: Create Setup Script Core Module

**Files:**

- Create: `setup.py`
- Test: `tests/test_setup.py`

**Step 1: Write the failing test**

```python
# tests/test_setup.py
import pytest
import socket
from unittest.mock import patch, MagicMock

# Import will fail until setup.py exists
from setup import check_port_available, find_available_port, generate_password

def test_check_port_available_open_port():
    """Test detecting an available port."""
    # Find a port that's likely free
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', 0))
        port = s.getsockname()[1]
    # Port is now closed, should be available
    assert check_port_available(port) is True

def test_check_port_available_used_port():
    """Test detecting a port in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', 0))
        port = s.getsockname()[1]
        s.listen(1)
        # Port is bound, should not be available
        assert check_port_available(port) is False

def test_find_available_port():
    """Test finding next available port."""
    port = find_available_port(49000)
    assert port >= 49000
    assert check_port_available(port)

def test_generate_password_length():
    """Test password generation length."""
    password = generate_password(16)
    assert len(password) == 16

def test_generate_password_unique():
    """Test passwords are unique."""
    p1 = generate_password(16)
    p2 = generate_password(16)
    assert p1 != p2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_setup.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

Create `setup.py`:

```python
#!/usr/bin/env python3
"""Interactive setup script for Home Security Intelligence.

Generates .env and docker-compose.override.yml files for user environment.
Supports two modes:
- Quick mode (default): Accept defaults with Enter
- Guided mode (--guided): Step-by-step with explanations
"""

import os
import secrets
import socket
import sys
from pathlib import Path

# Service definitions with default ports
SERVICES = {
    "backend": {"port": 8000, "category": "Core", "desc": "Backend API"},
    "frontend": {"port": 5173, "category": "Core", "desc": "Frontend web UI"},
    "postgres": {"port": 5432, "category": "Core", "desc": "PostgreSQL database"},
    "redis": {"port": 6379, "category": "Core", "desc": "Redis cache/queue"},
    "rtdetr": {"port": 8090, "category": "AI", "desc": "RT-DETRv2 object detection"},
    "nemotron": {"port": 8091, "category": "AI", "desc": "Nemotron LLM reasoning"},
    "florence": {"port": 8092, "category": "AI", "desc": "Florence-2 vision-language"},
    "clip": {"port": 8093, "category": "AI", "desc": "CLIP embeddings"},
    "enrichment": {"port": 8094, "category": "AI", "desc": "Entity enrichment"},
    "grafana": {"port": 3002, "category": "Monitoring", "desc": "Grafana dashboards"},
    "prometheus": {"port": 9090, "category": "Monitoring", "desc": "Prometheus metrics"},
    "alertmanager": {"port": 3000, "category": "Monitoring", "desc": "Alert manager"},
    "redis_exporter": {"port": 9121, "category": "Monitoring", "desc": "Redis exporter"},
    "json_exporter": {"port": 7979, "category": "Monitoring", "desc": "JSON exporter"},
}


def check_port_available(port: int) -> bool:
    """Check if a port is available for binding.

    Args:
        port: Port number to check

    Returns:
        True if port is available, False if in use
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0


def find_available_port(start: int) -> int:
    """Find the next available port starting from a given port.

    Args:
        start: Starting port number

    Returns:
        First available port >= start
    """
    port = start
    while not check_port_available(port):
        port += 1
        if port > 65535:
            raise RuntimeError(f"No available ports found starting from {start}")
    return port


def generate_password(length: int = 16) -> str:
    """Generate a secure random password.

    Args:
        length: Desired password length

    Returns:
        URL-safe random string of specified length
    """
    return secrets.token_urlsafe(length)[:length]


if __name__ == "__main__":
    print("Setup script placeholder - full implementation in next task")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_setup.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add setup.py tests/test_setup.py
git commit -m "feat(setup): add core setup script functions with tests"
```

---

## Task 7: Implement Setup Script Quick Mode

**Files:**

- Modify: `setup.py`
- Test: `tests/test_setup.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_setup.py
from setup import generate_env_content, generate_docker_override_content

def test_generate_env_content():
    """Test .env file content generation."""
    config = {
        "camera_path": "/export/foscam",
        "ai_models_path": "/export/ai_models",
        "postgres_password": "testpass123",
        "ftp_password": "ftppass456",
        "ports": {
            "backend": 8000,
            "postgres": 5432,
            "redis": 6379,
            "grafana": 3002,
        },
    }
    content = generate_env_content(config)
    assert "CAMERA_PATH=/export/foscam" in content
    assert "POSTGRES_PASSWORD=testpass123" in content
    assert "GRAFANA_URL=http://localhost:3002" in content

def test_generate_docker_override_content():
    """Test docker-compose.override.yml generation."""
    config = {
        "camera_path": "/export/foscam",
        "ai_models_path": "/export/ai_models",
        "ports": {
            "backend": 8000,
            "frontend": 5173,
            "postgres": 5432,
        },
    }
    content = generate_docker_override_content(config)
    assert "services:" in content
    assert '"8000:8000"' in content or "'8000:8000'" in content
    assert "backend:" in content
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_setup.py::test_generate_env_content -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

Add to `setup.py`:

```python
from datetime import datetime

def generate_env_content(config: dict) -> str:
    """Generate .env file content from configuration.

    Args:
        config: Configuration dictionary with paths, passwords, and ports

    Returns:
        Complete .env file content as string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ports = config.get("ports", {})

    lines = [
        f"# Generated by setup.py on {timestamp}",
        "# " + "=" * 59,
        "",
        "# -- Paths " + "-" * 50,
        f"CAMERA_PATH={config.get('camera_path', '/export/foscam')}",
        f"AI_MODELS_PATH={config.get('ai_models_path', '/export/ai_models')}",
        "",
        "# -- Credentials " + "-" * 44,
        f"POSTGRES_PASSWORD={config.get('postgres_password', '')}",
        f"FTP_PASSWORD={config.get('ftp_password', '')}",
        "",
        "# -- Database " + "-" * 47,
        "POSTGRES_USER=security",
        "POSTGRES_DB=security",
        f"DATABASE_URL=postgresql+asyncpg://security:{config.get('postgres_password', '')}@postgres:{ports.get('postgres', 5432)}/security",
        "",
        "# -- Service URLs " + "-" * 43,
        f"RTDETR_URL=http://ai-detector:{ports.get('rtdetr', 8090)}",
        f"NEMOTRON_URL=http://ai-llm:{ports.get('nemotron', 8091)}",
        f"FLORENCE_URL=http://ai-florence:{ports.get('florence', 8092)}",
        f"CLIP_URL=http://ai-clip:{ports.get('clip', 8093)}",
        f"ENRICHMENT_URL=http://ai-enrichment:{ports.get('enrichment', 8094)}",
        f"REDIS_URL=redis://redis:{ports.get('redis', 6379)}",
        "",
        "# -- Frontend Runtime Config " + "-" * 32,
        f"GRAFANA_URL=http://localhost:{ports.get('grafana', 3002)}",
        "",
    ]
    return "\n".join(lines)


def generate_docker_override_content(config: dict) -> str:
    """Generate docker-compose.override.yml content.

    Args:
        config: Configuration dictionary with paths and ports

    Returns:
        Complete docker-compose.override.yml content as string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ports = config.get("ports", {})
    camera_path = config.get("camera_path", "/export/foscam")

    # Build YAML content
    lines = [
        f"# Generated by setup.py on {timestamp}",
        "# This file is auto-merged with docker-compose.prod.yml",
        "",
        "services:",
    ]

    service_configs = {
        "postgres": {"port": ports.get("postgres", 5432), "internal": 5432},
        "redis": {"port": ports.get("redis", 6379), "internal": 6379},
        "backend": {
            "port": ports.get("backend", 8000),
            "internal": 8000,
            "volumes": [f"{camera_path}:/cameras:ro"],
        },
        "ai-detector": {"port": ports.get("rtdetr", 8090), "internal": 8090},
        "ai-llm": {"port": ports.get("nemotron", 8091), "internal": 8091},
        "ai-florence": {"port": ports.get("florence", 8092), "internal": 8092},
        "ai-clip": {"port": ports.get("clip", 8093), "internal": 8093},
        "ai-enrichment": {"port": ports.get("enrichment", 8094), "internal": 8094},
        "frontend": {"port": ports.get("frontend", 5173), "internal": 80},
        "grafana": {"port": ports.get("grafana", 3002), "internal": 3000},
        "prometheus": {"port": ports.get("prometheus", 9090), "internal": 9090},
        "alertmanager": {"port": ports.get("alertmanager", 3000), "internal": 9093},
        "redis-exporter": {"port": ports.get("redis_exporter", 9121), "internal": 9121},
        "json-exporter": {"port": ports.get("json_exporter", 7979), "internal": 7979},
    }

    for service, cfg in service_configs.items():
        lines.append(f"  {service}:")
        lines.append("    ports:")
        lines.append(f'      - "{cfg["port"]}:{cfg["internal"]}"')
        if "volumes" in cfg:
            lines.append("    volumes:")
            for vol in cfg["volumes"]:
                lines.append(f"      - {vol}")
        lines.append("")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_setup.py::test_generate_env_content tests/test_setup.py::test_generate_docker_override_content -v`
Expected: PASS

**Step 5: Commit**

```bash
git add setup.py tests/test_setup.py
git commit -m "feat(setup): implement env and docker override file generation"
```

---

## Task 8: Implement Setup Script Interactive Prompts

**Files:**

- Modify: `setup.py`
- Test: `tests/test_setup.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_setup.py
from setup import prompt_with_default, run_quick_mode
from io import StringIO
from unittest.mock import patch

def test_prompt_with_default_accepts_default():
    """Test prompt accepts default value on empty input."""
    with patch('builtins.input', return_value=''):
        result = prompt_with_default("Test", "default_value")
    assert result == "default_value"

def test_prompt_with_default_accepts_custom():
    """Test prompt accepts custom value."""
    with patch('builtins.input', return_value='custom_value'):
        result = prompt_with_default("Test", "default_value")
    assert result == "custom_value"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_setup.py::test_prompt_with_default_accepts_default -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

Add to `setup.py`:

```python
def prompt_with_default(prompt: str, default: str) -> str:
    """Prompt user for input with a default value.

    Args:
        prompt: Prompt text to display
        default: Default value if user presses Enter

    Returns:
        User input or default value
    """
    try:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def run_quick_mode() -> dict:
    """Run quick setup mode with minimal prompts.

    Returns:
        Configuration dictionary
    """
    print("=" * 60)
    print("  Home Security Intelligence - Quick Setup")
    print("=" * 60)
    print()

    # Check port conflicts
    print("Checking for port conflicts...")
    conflicts = []
    ports = {}
    for service, info in SERVICES.items():
        default_port = info["port"]
        if check_port_available(default_port):
            ports[service] = default_port
        else:
            available = find_available_port(default_port)
            ports[service] = available
            conflicts.append(f"  {service}: {default_port} -> {available}")

    if conflicts:
        print("⚠ Port conflicts detected, using alternatives:")
        for c in conflicts:
            print(c)
    else:
        print("✓ All default ports available")
    print()

    # Paths
    print("-- Paths " + "-" * 52)
    camera_path = prompt_with_default("Camera upload path", "/export/foscam")
    ai_models_path = prompt_with_default("AI models path", "/export/ai_models")
    print()

    # Credentials
    print("-- Credentials " + "-" * 46)
    postgres_password = prompt_with_default("Database password", generate_password())
    ftp_password = prompt_with_default("FTP password", generate_password())
    print()

    # Ports (optional customization)
    print("-- Ports (press Enter to keep defaults) " + "-" * 21)
    for service, info in SERVICES.items():
        suggested = ports[service]
        custom = prompt_with_default(f"{info['desc']}", str(suggested))
        try:
            ports[service] = int(custom)
        except ValueError:
            ports[service] = suggested
    print()

    return {
        "camera_path": camera_path,
        "ai_models_path": ai_models_path,
        "postgres_password": postgres_password,
        "ftp_password": ftp_password,
        "ports": ports,
    }
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_setup.py::test_prompt_with_default_accepts_default tests/test_setup.py::test_prompt_with_default_accepts_custom -v`
Expected: PASS

**Step 5: Commit**

```bash
git add setup.py tests/test_setup.py
git commit -m "feat(setup): implement interactive prompts and quick mode"
```

---

## Task 9: Implement Setup Script File Writing and Main Entry

**Files:**

- Modify: `setup.py`
- Test: `tests/test_setup.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_setup.py
import tempfile
from pathlib import Path
from setup import write_config_files

def test_write_config_files_creates_env():
    """Test that write_config_files creates .env file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "camera_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {"backend": 8000, "postgres": 5432, "redis": 6379, "grafana": 3002},
        }
        write_config_files(config, output_dir=tmpdir)

        env_path = Path(tmpdir) / ".env"
        assert env_path.exists()
        content = env_path.read_text()
        assert "CAMERA_PATH=/test/cameras" in content

def test_write_config_files_creates_docker_override():
    """Test that write_config_files creates docker-compose.override.yml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "camera_path": "/test/cameras",
            "ai_models_path": "/test/models",
            "postgres_password": "testpass",
            "ftp_password": "ftppass",
            "ports": {"backend": 8000, "frontend": 5173},
        }
        write_config_files(config, output_dir=tmpdir)

        override_path = Path(tmpdir) / "docker-compose.override.yml"
        assert override_path.exists()
        content = override_path.read_text()
        assert "services:" in content
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_setup.py::test_write_config_files_creates_env -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

Add to `setup.py`:

```python
import argparse
import platform
import shutil
import subprocess


def write_config_files(config: dict, output_dir: str = ".") -> tuple[Path, Path]:
    """Write configuration files to disk.

    Args:
        config: Configuration dictionary
        output_dir: Directory to write files to

    Returns:
        Tuple of (env_path, override_path)
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    env_path = output / ".env"
    override_path = output / "docker-compose.override.yml"

    env_content = generate_env_content(config)
    override_content = generate_docker_override_content(config)

    env_path.write_text(env_content)
    override_path.write_text(override_content)

    return env_path, override_path


def configure_firewall(ports: list[int]) -> bool:
    """Configure Linux firewall to allow specified ports.

    Args:
        ports: List of port numbers to open

    Returns:
        True if successful, False otherwise
    """
    if platform.system() != 'Linux':
        return False

    # Try firewall-cmd (Fedora/RHEL/CentOS)
    if shutil.which('firewall-cmd'):
        try:
            for port in ports:
                subprocess.run(
                    ['firewall-cmd', '--permanent', f'--add-port={port}/tcp'],
                    check=True,
                    capture_output=True,
                )
            subprocess.run(['firewall-cmd', '--reload'], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    # Try ufw (Ubuntu/Debian)
    if shutil.which('ufw'):
        try:
            for port in ports:
                subprocess.run(
                    ['ufw', 'allow', f'{port}/tcp'],
                    check=True,
                    capture_output=True,
                )
            return True
        except subprocess.CalledProcessError:
            return False

    return False


def main():
    """Main entry point for setup script."""
    parser = argparse.ArgumentParser(
        description="Interactive setup for Home Security Intelligence"
    )
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Run in guided mode with detailed explanations",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory for generated files (default: current directory)",
    )
    args = parser.parse_args()

    try:
        if args.guided:
            print("Guided mode not yet implemented")
            config = run_quick_mode()  # Fallback to quick mode
        else:
            config = run_quick_mode()

        # Write configuration files
        env_path, override_path = write_config_files(config, args.output_dir)

        print("=" * 60)
        print("Generated:")
        print(f"  • {env_path}")
        print(f"  • {override_path}")
        print()

        # Offer firewall configuration on Linux
        if platform.system() == 'Linux':
            frontend_port = config["ports"].get("frontend", 5173)
            grafana_port = config["ports"].get("grafana", 3002)

            answer = prompt_with_default(
                f"Open firewall ports for frontend ({frontend_port}) and Grafana ({grafana_port})?",
                "n"
            )
            if answer.lower() in ('y', 'yes'):
                if configure_firewall([frontend_port, grafana_port]):
                    print("✓ Firewall configured")
                else:
                    print("⚠ Could not configure firewall (may need sudo)")

        print()
        print("Ready! Run: docker-compose -f docker-compose.prod.yml up -d")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_setup.py::test_write_config_files_creates_env tests/test_setup.py::test_write_config_files_creates_docker_override -v`
Expected: PASS

**Step 5: Commit**

```bash
git add setup.py tests/test_setup.py
git commit -m "feat(setup): implement file writing and main entry point"
```

---

## Task 10: Create Shell Wrapper Scripts

**Files:**

- Create: `setup.sh` (Linux/macOS)
- Create: `setup.bat` (Windows)

**Step 1: Create setup.sh**

```bash
#!/bin/bash
# setup.sh - Linux/macOS wrapper for setup.py
# Usage: ./setup.sh [--guided]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/setup.py" "$@"
```

**Step 2: Create setup.bat**

```batch
@echo off
REM setup.bat - Windows wrapper for setup.py
REM Usage: setup.bat [--guided]

python "%~dp0setup.py" %*
```

**Step 3: Make setup.sh executable**

Run: `chmod +x setup.sh`

**Step 4: Verify wrappers work**

Run: `./setup.sh --help`
Expected: Shows help message from setup.py

**Step 5: Commit**

```bash
git add setup.sh setup.bat
git commit -m "feat(setup): add shell wrapper scripts for cross-platform execution"
```

---

## Task 11: Implement Guided Mode

**Files:**

- Modify: `setup.py`
- Test: `tests/test_setup.py`

**Step 1: Write implementation**

Add to `setup.py`:

```python
def run_guided_mode() -> dict:
    """Run guided setup mode with detailed explanations.

    Returns:
        Configuration dictionary
    """
    ports = {service: info["port"] for service, info in SERVICES.items()}

    # Step 1: Camera Path
    print("=" * 60)
    print("  Step 1 of 5: Camera Upload Path")
    print("=" * 60)
    print()
    print("This is where your Foscam cameras upload images via FTP.")
    print("The backend watches this directory for new files.")
    print()
    print("Requirements:")
    print("  • Must exist and be readable by Docker")
    print("  • Recommended: SSD or fast storage for real-time processing")
    print("  • Typical size: 10-50GB depending on camera count/retention")
    print()
    camera_path = prompt_with_default("Enter camera upload path", "/export/foscam")

    # Validate path exists
    if Path(camera_path).exists():
        print("✓ Directory exists and is readable")
    else:
        print(f"⚠ Directory does not exist: {camera_path}")
        create = prompt_with_default("Create it now?", "n")
        if create.lower() in ('y', 'yes'):
            try:
                Path(camera_path).mkdir(parents=True, exist_ok=True)
                print("✓ Directory created")
            except PermissionError:
                print("⚠ Permission denied - you may need to create it manually")
    print()

    # Step 2: AI Models Path
    print("=" * 60)
    print("  Step 2 of 5: AI Models Path")
    print("=" * 60)
    print()
    print("This is where AI model weights are stored.")
    print("The AI services load models from this directory.")
    print()
    print("Requirements:")
    print("  • Requires ~15GB of disk space for all models")
    print("  • Must be readable by Docker containers")
    print()
    ai_models_path = prompt_with_default("Enter AI models path", "/export/ai_models")

    # Check disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage(Path(ai_models_path).parent)
        free_gb = free / (1024**3)
        if free_gb < 15:
            print(f"⚠ Warning: Only {free_gb:.1f}GB free space (15GB recommended)")
        else:
            print(f"✓ {free_gb:.1f}GB free space available")
    except Exception:
        pass
    print()

    # Step 3: Credentials
    print("=" * 60)
    print("  Step 3 of 5: Security Credentials")
    print("=" * 60)
    print()
    print("Strong passwords will be auto-generated if you press Enter.")
    print()
    postgres_password = prompt_with_default("Database password", generate_password())
    ftp_password = prompt_with_default("FTP password", generate_password())
    print()

    # Step 4: Port Configuration
    print("=" * 60)
    print("  Step 4 of 5: Port Configuration")
    print("=" * 60)
    print()
    print("Checking for port conflicts...")

    for service, info in SERVICES.items():
        default_port = info["port"]
        if not check_port_available(default_port):
            available = find_available_port(default_port)
            print(f"⚠ {info['desc']} ({service}): port {default_port} in use")
            ports[service] = int(prompt_with_default(f"  Alternative port", str(available)))
        else:
            print(f"✓ {info['desc']}: {default_port}")
            ports[service] = default_port
    print()

    # Step 5: Summary
    print("=" * 60)
    print("  Step 5 of 5: Configuration Summary")
    print("=" * 60)
    print()
    print(f"Camera Path:    {camera_path}")
    print(f"AI Models Path: {ai_models_path}")
    print(f"Database Port:  {ports['postgres']}")
    print(f"Frontend Port:  {ports['frontend']}")
    print(f"Grafana Port:   {ports['grafana']}")
    print()
    confirm = prompt_with_default("Proceed with this configuration?", "y")
    if confirm.lower() not in ('y', 'yes'):
        print("Setup cancelled.")
        sys.exit(0)

    return {
        "camera_path": camera_path,
        "ai_models_path": ai_models_path,
        "postgres_password": postgres_password,
        "ftp_password": ftp_password,
        "ports": ports,
    }
```

Update main() to use guided mode:

```python
def main():
    # ... existing code ...

    try:
        if args.guided:
            config = run_guided_mode()
        else:
            config = run_quick_mode()

        # ... rest of main() ...
```

**Step 2: Test guided mode**

Run: `./setup.sh --guided`
Expected: Step-by-step guided setup with explanations

**Step 3: Commit**

```bash
git add setup.py
git commit -m "feat(setup): implement guided mode with step-by-step explanations"
```

---

## Task 12: Update Documentation

**Files:**

- Modify: `README.md`
- Modify: `docs/getting-started/installation.md` (if exists)
- Modify: `CLAUDE.md`

**Step 1: Update README.md Quick Start**

Add/update the Quick Start section:

````markdown
## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/nemotron-v3-home-security-intelligence.git
   cd nemotron-v3-home-security-intelligence
   ```
````

2. Run the setup script:

   ```bash
   ./setup.sh              # Quick mode (accept defaults with Enter)
   ./setup.sh --guided     # Guided mode (step-by-step with explanations)
   ```

3. Start the services:

   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. Open the dashboard:
   - Frontend: http://localhost:5173
   - Grafana: http://localhost:3002

````

**Step 2: Update CLAUDE.md**

Add setup script information to the deployment section:

```markdown
## Setup Script

The project includes an interactive setup script that generates configuration files:

```bash
./setup.sh              # Quick mode
./setup.sh --guided     # Guided mode with explanations
````

Generated files:

- `.env` - Environment variables (paths, credentials, service URLs)
- `docker-compose.override.yml` - Port mappings and volume mounts

The setup script:

- Detects port conflicts and suggests alternatives
- Generates secure random passwords
- Optionally configures Linux firewall (firewall-cmd/ufw)
- Validates paths exist

````

**Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: update documentation for interactive setup script"
````

---

## Task 13: Run Full Test Suite and Verify

**Step 1: Run all backend tests**

```bash
uv run pytest backend/tests/unit/ -n auto --dist=worksteal
uv run pytest backend/tests/integration/ -n0
```

**Step 2: Run frontend tests**

```bash
cd frontend && npm test
```

**Step 3: Run setup script tests**

```bash
uv run pytest tests/test_setup.py -v
```

**Step 4: Verify setup script works end-to-end**

```bash
# Create temp directory for testing
mkdir -p /tmp/setup-test
./setup.sh --output-dir /tmp/setup-test <<< $'\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n'
cat /tmp/setup-test/.env
cat /tmp/setup-test/docker-compose.override.yml
rm -rf /tmp/setup-test
```

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: address test failures and edge cases"
```

---

## Task 14: Create PR and Cleanup

**Step 1: Push branch**

```bash
git push -u origin feat/interactive-setup-script
```

**Step 2: Create PR**

```bash
gh pr create --title "feat: interactive setup script for easy onboarding" --body "$(cat <<'EOF'
## Summary
- Add interactive setup script (setup.py) with quick and guided modes
- Add grafana_url to backend config for dynamic frontend configuration
- Update frontend to fetch grafana_url from API instead of hardcoded value
- Add configurable dev proxy URL in Vite config
- Add comprehensive tests for all new functionality

## Test plan
- [x] Unit tests for setup script functions pass
- [x] Backend unit tests pass
- [x] Backend integration tests pass
- [x] Frontend tests pass
- [x] Manual test: setup.sh generates valid .env and docker-compose.override.yml
- [x] Manual test: setup.sh --guided provides step-by-step walkthrough
- [x] Manual test: Frontend fetches grafana_url from config API

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Step 3: Note PR URL**

The PR URL will be returned by the `gh pr create` command.
