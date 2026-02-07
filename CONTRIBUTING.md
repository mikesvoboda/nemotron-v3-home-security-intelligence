# Contributing to Home Security Intelligence

Welcome! This project turns "dumb" security cameras into an intelligent threat detection system, running 100% locally on your hardware. We appreciate your interest in contributing.

## Hardware Requirements

This project requires an NVIDIA GPU for the AI pipeline. Here is what you need:

| Component      | Minimum            | Recommended       |
| -------------- | ------------------ | ----------------- |
| **GPU VRAM**   | 12GB               | 24GB              |
| **System RAM** | 32GB               | 64GB+             |
| **Storage**    | 50GB (core models) | 100GB+ (full zoo) |
| **CPU**        | 8 cores            | 16+ cores         |

If you do not have GPU hardware, you can still contribute to:

- **Frontend** (React / TypeScript) -- no GPU needed for UI development
- **Documentation** improvements
- **Test coverage** for backend logic
- **Backend logic** that does not touch AI services

## Quick Setup

```bash
# 1. First-time setup (creates .env, installs dependencies)
python setup.py

# 2. Sync Python dependencies
uv sync --extra dev

# 3. Sync frontend dependencies
cd frontend && bun install

# 4. Install git hooks (mandatory)
pre-commit install && pre-commit install --hook-type pre-push
```

## Running Tests

This project follows **Test-Driven Development (TDD)**. Write tests before implementation.

| Test Type           | Minimum Coverage | Command                                        |
| ------------------- | ---------------- | ---------------------------------------------- |
| Backend Unit        | 85%              | `uv run pytest backend/tests/unit/ -n auto`    |
| Backend Integration | --               | `uv run pytest backend/tests/integration/ -n0` |
| Frontend            | 83%+             | `cd frontend && npm test`                      |
| **Full validation** | --               | `./scripts/validate.sh`                        |

Always run full validation before opening a pull request:

```bash
./scripts/validate.sh   # lint + typecheck + tests
```

## Development Workflow

1. Create a branch from `main`: `git checkout -b feat/your-feature`
2. Write tests first (TDD is required)
3. Implement the feature
4. Run `./scripts/validate.sh` to confirm everything passes
5. Commit with descriptive messages
6. Open a Pull Request

## Pre-commit Hooks

Pre-commit hooks are **mandatory**. Never bypass them with `--no-verify`:

```bash
pre-commit install && pre-commit install --hook-type pre-push
```

These hooks run linting and formatting checks automatically on every commit and push. If a hook fails, fix the issue and commit again.

## Pull Request Process

- All tests must pass in CI
- TDD compliance: tests should accompany any new feature or bug fix
- Never use `--no-verify` to skip hooks
- Keep PRs focused -- one feature or fix per PR when possible
- Reference the related issue in your PR description

## Issue Tracking

- **GitHub Issues** -- for bug reports, feature requests, and discussion
- Labels: `good-first-issue`, `help-wanted`, `frontend`, `backend`, `ai`, `documentation`
- Issues sync automatically to our internal planning tool

## Finding Your Way Around

Every directory in this project contains an `AGENTS.md` file that documents purpose, key files, and patterns. **Read the `AGENTS.md` first when exploring a new area.**

Key entry points:

| Resource                                               | Description                                     |
| ------------------------------------------------------ | ----------------------------------------------- |
| [Developer Hub](docs/developer/README.md)              | Architecture, API reference, development guides |
| [Architecture Docs](docs/architecture/README.md)       | System design and key decisions                 |
| [CLAUDE.md](CLAUDE.md)                                 | Project conventions and design decisions        |
| [Testing Guide](docs/development/testing.md)           | Full testing documentation                      |
| [Git Workflow Guide](docs/development/git-workflow.md) | Branch strategy and commit conventions          |

## Project Structure

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

## Code of Conduct

Be respectful, constructive, and inclusive. We are building something useful together.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
