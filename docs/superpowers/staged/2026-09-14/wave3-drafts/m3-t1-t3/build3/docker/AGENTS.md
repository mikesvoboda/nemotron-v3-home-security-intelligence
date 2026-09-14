# Docker Custom Images

This directory contains custom Docker images maintained for the project.

## Directory Structure

```
docker/
├── AGENTS.md                    # This file
└── python-freethreaded/         # Python 3.14 with --disable-gil
    └── Dockerfile
```

## Images

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
