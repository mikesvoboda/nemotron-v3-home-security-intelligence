# Unit Tests - setup_lib - Agent Guide

## Purpose

Unit tests for `setup_lib/` - the Python utilities behind `setup.py` and the deploy flow (platform/GPU detection, podman install, image pulls, model downloads, SSL certs, firewall, deployment orchestration). Landed here from the old root-level `tests/` tree.

## Directory Structure

15 test files, each named test_<module>.py after its twin module in `setup_lib/`:

| Test file                                          | Under test (`setup_lib/`)             |
| -------------------------------------------------- | ------------------------------------- |
| `test_deploy.py`, `test_deploy_phases.py`          | deploy orchestration + phases         |
| `test_platform_detect.py`, `test_nvidia_detect.py` | platform / NVIDIA driver detection    |
| `test_nvidia_toolkit.py`, `test_podman_install.py` | container runtime + GPU toolkit setup |
| `test_image_pull.py`, `test_model_downloader.py`   | image pulls, AI model downloads       |
| `test_firewall_config.py`, `test_port_scanner.py`, `test_ssl_certs.py`, `test_storage_config.py` | host configuration |
| `test_linux_optimizer.py`                          | Linux workstation tuning              |
| `test_healthcheck.py`                              | deployment health checks              |

## Running Tests

```bash
uv run pytest backend/tests/unit/setup_lib/ -v
uv run pytest backend/tests/unit/setup_lib/test_deploy.py -v
```

## Patterns and Gotchas

- Tests are pure-mock: `unittest.mock` + subprocess fakes; no real network, GPU, podman or filesystem side effects outside tmp fixtures.
- **Module coverage is 1:1 for the 15 files here.** `setup_lib`'s `core.py`, `credentials.py`, `models_config.py`, `rootful_services.py` are NOT tested in this directory - `credentials.py` lives in `setup_lib/tests/`; the other three have no unit tests.
- `backend/tests/unit/test_deploy_phases.py` (root of the unit dir) predates this directory and overlaps `test_deploy_phases.py` here - check both when touching deploy-phase behavior.

## Related

- `/setup_lib/AGENTS.md` - the modules under test
- `../AGENTS.md` - unit test patterns
