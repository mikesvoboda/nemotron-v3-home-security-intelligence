# syntax=docker/dockerfile:1
# Multi-stage Dockerfile for backend (dev and production targets)
# Uses Debian slim for PyTorch/ultralytics compatibility (Alpine's musl libc is incompatible)
#
# Security Features:
#   - Non-root user execution
#   - Minimal production image (no build tools)
#   - Health checks for container orchestration
#   - Read-only root filesystem compatible (mark volumes as needed)
#
# Usage:
#   docker build --target dev -t backend:dev .
#   docker build --target prod -t backend:prod .

# =============================================================================
# Base stage: shared dependencies (backend-specific extensions to base image)
#
# Builds FROM python:3.14-slim-bookworm DIRECTLY and adds the backend's own
# system dependencies and build tools. (The earlier comment here said this stage
# "extends the shared ghcr.io/mikesvoboda/nemotron-base image"; that stopped
# being true when the FROM moved — no FROM line in the repo consumes nemotron-
# base any more, though CI still publishes it. Read 2026-10-04 across every
# tracked Dockerfile; guarded by
# backend/tests/unit/scripts/test_backend_image_trivy_clean.py.)
#
# Python Image Options:
#   Standard (GIL enabled):     python:3.14-slim-bookworm
#   Free-threaded (no GIL):     ghcr.io/mikesvoboda/python:3.14t-slim-bookworm
#
# To enable free-threading, uncomment the GHCR image below and comment out
# the standard image. The application in backend/core/free_threading.py will
# automatically detect and utilize free-threading when available.
#
# Free-threading benefits: ~4x speedup for CPU-bound multi-threaded workloads
# Free-threading overhead: ~5-10% slower for single-threaded code
# =============================================================================
# Standard Python 3.14 (GIL enabled).  GIL starvation is mitigated via targeted
# fixes: inotify observer, CUDA-only model guards, and skip fuse() on CPU — all
# committed in the source.  See docs on free-threading option above if needed.
FROM python:3.14-slim-bookworm AS base

# OCI Image Labels (org.opencontainers.image.*)
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Backend API Server"
LABEL org.opencontainers.image.description="FastAPI backend for home security monitoring dashboard with WebSocket support"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"
LABEL org.opencontainers.image.documentation="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/docs"
LABEL org.opencontainers.image.authors="home-security-intelligence"
# Must name the image this stage actually FROMs (below). It previously said
# ghcr.io/mikesvoboda/python:3.14t-slim-bookworm — the FREE-THREADED option
# documented in the comment above, not the base in use — so the published
# provenance and every SBOM read a GIL-disabled interpreter this image does not
# have. The prod stage labels itself correctly.
# Guard: TestBaseLabelMatchesFrom.
LABEL org.opencontainers.image.base.name="python:3.14-slim-bookworm"

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install ALL system dependencies in one layer:
# - Build tools (gcc, libc6-dev, libffi-dev) for Python C extensions
# - Backend runtime deps (wget, curl, ffmpeg, OpenGL/glib for video processing)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libffi-dev \
    wget \
    curl \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy base requirements (shared dependencies from docker/base.Dockerfile)
COPY requirements-base.txt .

# Install base Python dependencies with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache -r requirements-base.txt

# Copy project dependency files
COPY pyproject.toml uv.lock ./

# =============================================================================
# Development target: includes dev dependencies, has build tools
# =============================================================================
FROM base AS dev

# Install all dependencies including dev (for development container)
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Create non-root user before copying files (for COPY --chown)
RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup -s /usr/sbin/nologin appuser

# Copy application code with proper ownership (avoids separate chown layer)
COPY --chown=appuser:appgroup backend/ ./backend/

# Copy the recorded schema upgrades: backend/migrations reads its SQL text from this path at
# startup, and docs/ is otherwise dockerignored (.dockerignore re-includes only this directory).
# Without this line the container boots a database that owes an upgrade with a loud UpgradeError
# instead of silently skipping the upgrade.
COPY --chown=appuser:appgroup docs/api/migrations ./docs/api/migrations

# Create data directory for logs and thumbnails with proper ownership
RUN mkdir -p /app/data/thumbnails /app/data/logs && \
    chown -R appuser:appgroup /app/data /app/.venv

# Add venv to PATH
ENV PATH=/app/.venv/bin:$PATH

# Default API port (configurable via environment variable)
ENV API_PORT=8000

# Expose FastAPI port
EXPOSE 8000

# Switch to non-root user
USER appuser

# Health check - use /ready endpoint to verify database/redis connectivity
# Uses API_PORT environment variable for configurable port
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, httpx; port=os.getenv('API_PORT', '8000'); exit(0 if httpx.get(f'http://localhost:{port}/api/system/health/ready').status_code == 200 else 1)"

# Use entrypoint script to run Alembic migrations before starting the server
# The entrypoint runs migrations with retry logic, then executes CMD
ENTRYPOINT ["/app/backend/entrypoint.sh"]

# Run FastAPI with uvicorn (hot reload enabled for dev)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Builder stage: install production dependencies only
# =============================================================================
FROM base AS builder

# Install production dependencies only (no dev/test deps)
# [r307b]: the face leg calls the gateway's /enrich-lt/face-detect and
# /enrich-lt/face-recognize routes, so the CPU [face] extra (onnxruntime) is retired.
# Use BuildKit cache mount to cache uv downloads between builds (~5-10x faster)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# =============================================================================
# Production target: minimal runtime image without build tools
# =============================================================================
FROM python:3.14-slim-bookworm AS prod

# OCI Image Labels (org.opencontainers.image.*)
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="Backend API Server"
LABEL org.opencontainers.image.description="FastAPI backend for home security monitoring dashboard with WebSocket support"
LABEL org.opencontainers.image.licenses="MPL-2.0"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"
LABEL org.opencontainers.image.documentation="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/docs"
LABEL org.opencontainers.image.authors="home-security-intelligence"
LABEL org.opencontainers.image.base.name="python:3.14-slim-bookworm"

WORKDIR /app

# Install runtime dependencies only (no build tools like gcc)
# ffmpeg for video processing, libgl1 and libglib2.0-0 for OpenCV (required by ultralytics)
# procps for pgrep (needed by profiler)
# libexpat1: the f9778503 Trivy scan found 2.5.0-1+deb12u3 installed in the
# built image, flagged by six HIGH CVEs (CVE-2024-28757, CVE-2025-59375,
# CVE-2026-25210, CVE-2026-45186, CVE-2026-66046, CVE-2026-93990; fixed in
# 2.5.0-1+deb12u4). Measured against the current base digest: u3 is on no
# mirror anymore — the only candidates are u2 (bookworm/12.15) and u4
# (bookworm-security, already in these sources) — and the runtime install
# below pulls libexpat1 transitively at u4; the -s simulation confirms
# "Inst libexpat1 (2.5.0-1+deb12u4 Debian-Security...)". --only-upgrade
# covers the other leg: when a base digest or cached layer DOES carry an
# older installed copy, it moves it to the candidate, and once the base
# absorbs the fix it no-ops (exit 0) — unlike a version pin it cannot rot
# into a build failure. Guard: test_backend_image_trivy_clean.py
#
# The rest of the --only-upgrade names are the 2026-10-04 upgradeable-CVE
# sweep; .trivyignore's REMOVED block records the entries it deleted. Three
# classes, measured (amd64 CI install log, run 37208159907 @ 6b33a2af; the base
# image's own dpkg status; a live upgrade simulation in the base — rc 0,
# "1 upgraded, 0 newly installed"):
#
#   MOVED TODAY: libpcre2-8-0 — the only line that changes what the image
#   installs. CVE-2026-103111 (HIGH), installed 10.42-1+deb12u1, fixed
#   10.42-1+deb12u2 (bookworm "resolved"); it arrives via the BASE image, whose
#   digest predates the point release. The tip scan is RED on it, exactly one
#   finding. (Alpine carries the same CVE; frontend/Dockerfile fixes its half.)
#
#   BASE-OWNED, AT/ABOVE THE FIX TODAY: libc6/libc-bin 2.36-9+deb12u14,
#   libpam* 1.5.2-6+deb12u2, gpgv 2.2.40-1.1+deb12u2. --only-upgrade is the
#   only lever that can move a package the base owns, and the base can be old:
#   a pinned digest, a cached FROM layer, or an upstream that hasn't rebuilt
#   carries an older copy back in with no test noticing. These names close
#   that silent-rollback vector; today they run empty (rc 0 no-op).
#
#   INSTALLED BY THIS VERY RUN, AT ARCHIVE-NEWEST: libpng16-16 u5,
#   libglib2.0-0 u9, libgdk-pixbuf-2.0-0 u4, libzvbi0+libzvbi-common u1,
#   libssh-gcrypt-4 u2 — ffmpeg's closure. apt fetched these from the same
#   lists minutes apart, so the upgrade can never move them; the names are the
#   register's pin-forward record for the deleted CVEs and keep its promise
#   honest if the RUN is ever restructured (pinned versions, holds, a split
#   layer). libzvbi0 hard-pins libzvbi-common (= same version), so both must
#   be named or apt holds libzvbi0 back.
#
# Safety, measured: --only-upgrade no-ops (exit 0) when the installed version
# is already newest, and SKIPS (exit 0, "not installed") a real package that
# isn't present — so this line cannot grow the image or fail when the base
# stops shipping one of these. It fails (exit 100) only on a name absent from
# the archive entirely, which is why every name here is bookworm-stable.
# Guards: TestProdStageUpgradesPcre2 / TestProdStageCoversTrackerResolvedPkgs.
#
# 2026-10-05 (perl-base): the first image build after the wave-5 Python merge
# (main 0f8277c0, scan job 111815714866) came back RED with seven findings on
# ONE source package: perl-base 5.36.0-7+deb12u3, fixed 5.36.0-7+deb12u4 in
# bookworm-security (DLA-4821-1) — CVE-2026-13221 CRITICAL + CVE-2026-42496/
# 8376/42497/48962/57432/57433 HIGH. All seven are tracker-resolved for
# bookworm, so they are fix-AVAILABLE: the ignore-unfixed filter that hides
# this scan's no-fix rows does not hide these, and an ignore entry for a
# fix-available CVE is exactly what the register's own rule forbids. The
# preceding head eea4cfd5 scanned GREEN on the same base — between the two
# builds the vuln DB caught up and the fix became reachable, the same
# MOVED-TODAY class as libpcre2-8-0 above (the frontend Alpine leg stayed
# green: perl-base exists only on the Debian half). Measured in the base image
# pulled today: candidate u4 from bookworm-security; the upgrade below gives
# rc 0 "1 upgraded, 0 newly installed" landing u4, then rc 0 as a no-op —
# cannot grow the image, cannot rot into a build failure when the base absorbs
# u4. Guard: TestProdStageUpgradesPerlBase / TestPerlBaseCvesStayOutOfIgnore.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    procps \
    curl \
    && apt-get install -y --only-upgrade \
         libexpat1 \
         libpcre2-8-0 \
         perl-base \
         libc6 \
         libc-bin \
         libpng16-16 \
         libglib2.0-0 \
         libgdk-pixbuf-2.0-0 \
         libzvbi0 \
         libzvbi-common \
         libssh-gcrypt-4 \
         libpam-modules \
         libpam0g \
         gpgv \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install py-spy for continuous profiling (pushes to Pyroscope)
# `uv tool install` builds an isolated env under /root/.local that exists ONLY
# to produce this one binary, then is never read again. Removing it after the
# copy shrinks the runtime image and cuts scan surface. `cp -L` because the
# removal must not strand a symlink, and `py-spy --version` runs AFTER the rm so
# a cleanup that broke the profiler fails the BUILD instead of shipping.
# (This does NOT address pip's vendored findings — pip itself is removed further
#  down this stage (r295), which retires that whole class and the five
#  .trivyignore entries. Verified by listing the built image: the only dist-info
#  present are msgpack-1.2.2 and setuptools-84.0.0, both clean.)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv tool install py-spy && \
    cp -L /root/.local/bin/py-spy /usr/local/bin/py-spy && \
    chmod +x /usr/local/bin/py-spy && \
    test -x /usr/local/bin/py-spy && \
    rm -rf /root/.local /root/.cache && \
    py-spy --version

# Copy profiler script
COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh

# Drop pip from the image (r295). pip 26.2.1 ships IN the python:3.14-slim-
# bookworm base image — its package tree (with the _vendor bundle Trivy reports
# under the bare "Python (python-pkg)" target), its dist-info, and its
# pip/pip3/pip3.14 entry scripts (all measured in the base image, 2026-10-21).
# Nothing in this stage needs it: uv does every install, the app's venv comes
# in via COPY from the builder, and the app names pip only in "Install with: …"
# error strings. Every vendored finding this class produced (msgpack
# GHSA-6v7p-g79w-8964, setuptools CVE-2025-47273, urllib3 CVE-2026-97687/97689,
# certifi GHSA-6q48-6c7w-9gw2) leaves the image with it, and the five
# .trivyignore entries leave the register in the same PR (ruling 295). The
# image's own pip wheels under ensurepip's _bundled/ are stdlib data, not an
# installed package — no scan target reads them, so they stay. Runs while the
# stage is still root (before USER appuser) because pip's files are root-owned.
# Guard: TestPipLeavesTheProdImage / TestPipBundleEntriesLeaveTheRegister.
# hadolint ignore=DL3008 — see the apt RUN above for the pin-shape precedent.
RUN rm -rf /usr/local/lib/python3.14/site-packages/pip \
         /usr/local/lib/python3.14/site-packages/pip-26.2.1.dist-info \
         /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.14 \
    && test ! -e /usr/local/lib/python3.14/site-packages/pip \
    && test ! -e /usr/local/bin/pip

# Create non-root user for security (no login shell for additional security)
RUN useradd -m -u 1000 -s /usr/sbin/nologin appuser

# Copy Python virtual environment from builder (no dev deps, no build tools)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code with proper ownership
COPY --chown=appuser:appuser backend/ ./backend/

# Copy the recorded schema upgrades (see the dev stage above): backend/migrations reads the SQL
# text from this path at startup and docs/ is otherwise dockerignored. This is the stage that
# boots real databases, so a missing COPY here means a production boot failure, not a dev annoyance.
COPY --chown=appuser:appuser docs/api/migrations ./docs/api/migrations

# Copy unified model configuration (single source of truth for model_zoo.py)
COPY --chown=appuser:appuser models.yml ./

# Create data directory for logs and thumbnails with proper ownership
RUN mkdir -p /app/data/thumbnails /app/data/logs && \
    chown -R appuser:appuser /app/data

# Add venv to PATH
ENV PATH=/app/.venv/bin:$PATH

# Default API port (configurable via environment variable)
ENV API_PORT=8000

# Switch to non-root user
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Health check - use /ready endpoint to verify database/redis connectivity
# Uses API_PORT environment variable for configurable port
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, httpx; port=os.getenv('API_PORT', '8000'); exit(0 if httpx.get(f'http://localhost:{port}/api/system/health/ready').status_code == 200 else 1)"

# ============================================================================
# IMPORTANT: Single Worker Requirement for In-Process Background Services
# ============================================================================
# This application runs background services (FileWatcher, PipelineWorkerManager,
# SystemBroadcaster) in the FastAPI lifespan context.
#
# Running multiple uvicorn workers (--workers > 1) would cause:
# - Duplicate file processing: Each worker starts its own FileWatcher
# - Race conditions: Multiple PipelineWorkerManagers processing the same queues
# - Duplicate WebSocket broadcasts: Multiple SystemBroadcasters sending duplicates
#
# For scaling beyond a single worker, extract background services to separate
# containers using: python -m backend.services.pipeline_workers
# See: backend/services/pipeline_workers.py for standalone worker mode.
# ============================================================================

# Use entrypoint script to run Alembic migrations before starting the server
# The entrypoint runs migrations with retry logic, then executes CMD
ENTRYPOINT ["/app/backend/entrypoint.sh"]

# ============================================================================
# Proxy Headers Configuration for Nginx Reverse Proxy
# ============================================================================
# This application runs behind an nginx reverse proxy that sets X-Forwarded-*
# headers. The following flags are critical for correct operation:
#
# --proxy-headers: Enables uvicorn to trust and parse X-Forwarded-For,
#                  X-Forwarded-Proto, X-Forwarded-Host headers from reverse proxy
#
# --forwarded-allow-ips "*": Trusts all IPs to set proxy headers. This is safe
#                            in containerized environments where only the nginx
#                            reverse proxy can reach the backend container.
#
# These headers are essential for:
# - IP-based rate limiting to use actual client IP (not nginx container IP)
# - Security logging with correct client addresses
# - HSTS and other protocol-dependent headers using X-Forwarded-Proto
# - Correct client detection in request.client for audit trails
#
# ============================================================================
# Security Hardening Flags
# ============================================================================
# --no-server-header: Prevents uvicorn from exposing 'Server: uvicorn' header
#                     Combined with nginx 'server_tokens off', this minimizes
#                     server software disclosure to potential attackers.
#
# --timeout-graceful-shutdown 30: Gives in-flight requests 30 seconds to complete
#                                 before forceful shutdown. Aligns with the app's
#                                 batch_idle_timeout_seconds (30s) to ensure
#                                 batch processing can complete during restarts.
# ============================================================================

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header", "--timeout-graceful-shutdown", "30"]
