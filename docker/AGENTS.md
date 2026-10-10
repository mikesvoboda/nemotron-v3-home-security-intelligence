# Docker Custom Images

This directory contains custom Docker images maintained for the project.

## Directory Structure

```
docker/
├── AGENTS.md                    # This file
├── fake-ai/                     # The fake AI stack's image (O2.1)
│   └── Dockerfile
└── python-freethreaded/         # Python 3.14 with --disable-gil
    └── Dockerfile
```

## Images

### fake-ai

**Purpose:** Serves the deterministic fake in `backend/ai_contract/fake/` as the VLM engine and the detector, so a stack with no GPU boots a backend that passes its startup gates and scores events.

It is built `FROM` the backend image, because the fake imports `backend.ai_contract`, which registers the backend's AI clients. On top of that it adds:

- `jsonschema`, pinned to `uv.lock`;
- this checkout's `backend/`;
- an empty `ENTRYPOINT`, because the fake needs no database.

**Used by:** `docker-compose.fake-ai.yml`, an overlay on `docker-compose.ci.yml` that is never a default. It runs the image twice: as `ai-vlm` on 8098 and as `ai-gateway` on 8090.

### python-freethreaded

**Purpose:** Python 3.14 built with `--disable-gil` for true multi-threaded parallelism (no GIL).

**Image:** `ghcr.io/mikesvoboda/python:3.14t-slim-bookworm`

**Why custom?** Official Docker Hub Python images don't include free-threaded builds. This image is identical to `python:3.14-slim-bookworm` except for the `--disable-gil` configure flag.

**Build workflow:** `.github/workflows/python-freethreaded.yml`

- Rebuilds weekly (Monday 3am UTC)
- Triggered on changes to `docker/python-freethreaded/`
- Supports manual dispatch for immediate rebuilds

**Usage in backend:**

```dockerfile
# Standard Python (GIL enabled)
FROM python:3.14-slim-bookworm AS base

# Free-threaded Python (GIL disabled)
FROM ghcr.io/mikesvoboda/python:3.14t-slim-bookworm AS base
```

**Verify free-threading:**

```bash
docker run --rm ghcr.io/mikesvoboda/python:3.14t-slim-bookworm \
  python -c "import sysconfig; print(bool(sysconfig.get_config_var('Py_GIL_DISABLED')))"
# Output: True
```

## Maintenance

### Updating Python Version

1. Check latest version at https://www.python.org/downloads/
2. Get SHA256 from https://www.python.org/ftp/python/{version}/
3. Update `docker/python-freethreaded/Dockerfile`:
   - `ENV PYTHON_VERSION x.x.x`
   - `ENV PYTHON_SHA256 ...`
4. Commit and push - workflow will rebuild automatically

### Performance Notes

- **Single-threaded overhead:** ~5-10% slower than GIL-enabled Python
- **Multi-threaded CPU-bound:** Up to 4x faster with true parallelism
- **I/O-bound async:** No significant difference (async already bypasses GIL)

## References

- [Python Free-Threading Guide](https://py-free-threading.github.io/)
- [PEP 703 - Making the GIL Optional](https://peps.python.org/pep-0703/)
- [Official Python Dockerfile](https://github.com/docker-library/python)
