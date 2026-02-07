# Claude Code Instructions

This project is an AI-powered home security monitoring dashboard. See `AGENTS.md` for detailed file structure, entry points, and codebase navigation.

## Quick Reference

| Resource                    | Location                                                                                                                 |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| File structure & navigation | `AGENTS.md`                                                                                                              |
| Issue tracking              | [Linear](https://linear.app/nemotron-v3-home-security/team/NEM/active) (Team ID: `998946a2-aa75-491b-a39d-189660131392`) |
| Linear integration          | Use `/linear-python` skill for all Linear operations                                                                     |
| Post-MVP roadmap            | `docs/ROADMAP.md` (pursue **after Phases 1-8 are operational**)                                                          |

## Setup

```bash
python setup.py              # First-time setup (creates .env, installs deps)
uv sync --extra dev     # Sync Python dependencies
cd frontend && bun install  # Sync frontend dependencies
pre-commit install      # Install git hooks
```

## Container Rebuilds

**Always use `--no-cache` when rebuilding containers** - cached layers may contain stale code. See [Container Rebuild Guide](docs/development/container-rebuilds.md) for details.

## Infrastructure Verification

**Always complete the verification loop after infrastructure changes.** Don't mark tasks complete until ALL checks pass.

### Post-Change Verification Checklist

After modifying Docker Compose, Prometheus configs, or any infrastructure:

```bash
# 1. Validate compose configuration
docker compose -f docker-compose.prod.yml config -q

# 2. Check all services are running
docker compose -f docker-compose.prod.yml ps

# 3. Verify Prometheus targets (if applicable)
curl -s localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# 4. Check API health
curl -s localhost:8000/api/health | jq
```

### Completion Criteria

A task involving infrastructure is **only complete** when:

- [ ] All Docker Compose services show `Up` and `healthy`
- [ ] All Prometheus targets show `health: "up"`
- [ ] API health endpoint returns success
- [ ] No error logs in `docker compose logs --tail=50`

**Use `/platform-healthcheck` skill** for standardized health verification.

## Testing

This project follows **Test-Driven Development (TDD)**. See [Testing Guide](docs/development/testing.md) for full documentation.

| Test Type           | Minimum Coverage | Command                                        |
| ------------------- | ---------------- | ---------------------------------------------- |
| Backend Unit        | 85%              | `uv run pytest backend/tests/unit/ -n auto`    |
| Backend Integration | —                | `uv run pytest backend/tests/integration/ -n0` |
| Frontend            | 83%+             | `cd frontend && npm test`                      |
| **Full validation** | —                | `./scripts/validate.sh`                        |

## Git Rules

**Never bypass pre-commit hooks.** See [Git Workflow Guide](docs/development/git-workflow.md).

```bash
pre-commit install && pre-commit install --hook-type pre-push
```

## Key Design Decisions

- **Risk scoring:** LLM-determined (Nemotron assigns 0-100 score)
- **Batch processing:** 90-second windows, 30-second idle timeout
- **Auth model:** Single-user local deployment. First-time admin registration required (SetupGuardMiddleware returns 503 until first user is created). After registration, API endpoints are open — no per-request login required. Network binding to `127.0.0.1` is the primary security boundary. Admin/destructive operations are protected by per-route dependencies (`verify_api_key`, `require_admin_access`). The global `AuthMiddleware` class exists for future multi-user support but is not active.
- **Retention:** 30 days
- **Deployment:** Containerized with GPU passthrough

## ⚠️ CRITICAL: Network Ports - .env is Single Source of Truth

**ALL network ports MUST be defined in `.env` and referenced via environment variables in `docker-compose.prod.yml`.**

```yaml
# CORRECT - Port from .env
ports:
  - '127.0.0.1:${VLLM_PORT:-8097}:8000'

# WRONG - Hardcoded port
ports:
  - '127.0.0.1:8097:8000'
```

**Port variables defined in `.env.example`:**

| Variable                | Default | Service              |
| ----------------------- | ------- | -------------------- |
| `POSTGRES_PORT`         | 5432    | PostgreSQL           |
| `REDIS_PORT`            | 6379    | Redis                |
| `API_PORT`              | 8000    | Backend API          |
| `YOLO26_PORT`           | 8095    | YOLO26 Detection     |
| `LLM_PORT`              | 8091    | Nemotron (llama.cpp) |
| `FLORENCE_PORT`         | 8092    | Florence-2           |
| `CLIP_PORT`             | 8093    | CLIP                 |
| `ENRICHMENT_PORT`       | 8094    | Enrichment (heavy)   |
| `ENRICHMENT_LIGHT_PORT` | 8096    | Enrichment (light)   |
| `VLLM_PORT`             | 8097    | vLLM (optional)      |
| `GO2RTC_API_PORT`       | 1984    | go2rtc API           |
| `GO2RTC_WEBRTC_PORT`    | 8555    | go2rtc WebRTC        |

**When adding new services:** Add port variable to `.env.example` first, then reference it in docker-compose.

## File Structure

```
backend/
  api/routes/          # FastAPI endpoints
  core/                # Database, Redis, config
  models/              # SQLAlchemy models
  services/            # Business logic
frontend/
  src/components/      # React components
  src/hooks/           # Custom hooks
  src/services/        # API client
ai/
  yolo26/              # YOLO26 detection server
  nemotron/            # Nemotron model files
```

## AGENTS.md Navigation

Every directory contains an `AGENTS.md` file documenting purpose, key files, and patterns. **Read AGENTS.md first when exploring a new directory.**

| Directory             | Purpose                           |
| --------------------- | --------------------------------- |
| `/AGENTS.md`          | Project overview and entry points |
| `/ai/AGENTS.md`       | AI pipeline overview              |
| `/backend/AGENTS.md`  | Backend architecture              |
| `/frontend/AGENTS.md` | Frontend architecture             |

## Session Workflow

1. Check [Linear Active view](https://linear.app/nemotron-v3-home-security/team/NEM/active)
2. Claim task (assign to yourself, set "In Progress")
3. Implement following TDD
4. Validate: `./scripts/validate.sh`
5. Close task in Linear, push changes

## Linear Integration

**Use ONLY `/linear-python` skill** for Linear operations. Do not use Linear MCP tools directly.

## Feature Documentation

For detailed feature-specific documentation:

- **Multi-GPU:** [docs/development/multi-gpu.md](docs/development/multi-gpu.md)
- **Video Analytics:** [docs/guides/video-analytics.md](docs/guides/video-analytics.md)
- **Zone Configuration:** [docs/guides/zone-configuration.md](docs/guides/zone-configuration.md)
- **Face Recognition:** [docs/guides/face-recognition.md](docs/guides/face-recognition.md)
