---
name: setup-guard-cache-poisoning
description: "SetupGuardMiddleware singleton TTL-caches 'no users' for 60s and poisons same-worker integration tests after api_protection's TRUNCATE; 4 modules still build raw app clients with no guard handling"
metadata:
  node_type: memory
  type: project
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-15T22:30:13.799Z
---

Discovered 2026-09-15 on PR #6542 (merged 15d7b5a2): `SetupGuardMiddleware` (backend/api/middleware/setup_guard.py)
is a singleton on the app middleware stack whose `_check_setup_complete` result is TTL-cached
(60s) and only latches positive. `test_api_protection.py`'s `unmocked_setup_client` fixture TRUNCATEs
users to exercise the pre-setup 503 contract and exits with the negative cached; any integration module
that then builds `ASGITransport(app=app)` on the same xdist worker gets 503 in ~1ms for the rest of the TTL
window. Seeding a user cannot outrun the cache.

Fixed `test_admin_api.py` by patching the guard like the shared `client` fixture
(`patch.object(SetupGuardMiddleware, "_check_setup_complete", ...)`). **Still exposed (raw app client, no guard
handling):** test_api.py, test_middleware_chain.py, test_websocket.py,
api/routes/test_cameras_baseline_config_integration.py — candidates for a follow-up hardening PR.

**Why:** failures look order-dependent/random and only appear in CI's combined -n auto run; local
single-module runs pass. See [[gh-pr-checks-no-json]] for why the CI watcher missed it.

**How to apply:** when an integration module intermittently 503s, check what ran on its xdist worker
just before (grep `\[gwN\]` in the job log) and whether it touched the users table; neutralize the guard
in the fixture rather than seeding users. Repo note: pre-commit/pre-push hooks here are lint/format-gated
only — full pytest matrix runs only in CI.
