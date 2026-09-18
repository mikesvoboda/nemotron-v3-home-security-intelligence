---
name: sandbox-recreate-vs-reboot
description: 'Sandbox recreation wipes the docker store and TEST_* env vars, so handoff "docker start" recovery steps silently fail'
metadata:
  node_type: memory
  type: project
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-16T03:48:52.580Z
---

The handoff doc `docs/superpowers/handoff-2026-09-14-power-cycle.md` tells a new session to
recover with `docker start gate-postgres gate-redis laughing_albattani`. That works after a
**reboot** of the same sandbox. On **2026-09-15** the sandbox was **recreated** instead:
`docker ps -a` showed 0 containers AND 0 images, `/etc/sandbox-persistent.sh` was empty (so
`TEST_DATABASE_URL`/`TEST_REDIS_URL` were gone, and they are not in the env backup at
`/home/agent/env-backup-gb300.env`), and `vdd` was absent.

**Why:** `docker start` on names that no longer exist fails quietly, and `validate.sh` falls back
to spawning a testcontainer per worker DB — which DiskFull-cascaded before (ledger run-5,
377 setup ERRORs). So the wrong recovery reads as "environment is fine" until a gate collapses.

**How to apply:** at session start, check `docker ps -a -q | wc -l` and `env | grep TEST_`
BEFORE trusting any handoff boot-recovery section. If empty, re-create the gate rig:
`postgres:16-alpine` (POSTGRES_USER/DB=security, POSTGRES_PASSWORD=security_dev_password,
-p 5432:5432), `redis:7-alpine` (-p 6379:6379), `eclipse-mosquitto:2.0`, then export
`TEST_DATABASE_URL=postgresql+asyncpg://security:security_dev_password@localhost:5432/security`
and `TEST_REDIS_URL=redis://localhost:6379` into `/etc/sandbox-persistent.sh`. Image pulls work
through the firewall.

**Update 2026-09-16 — the container recipe above is INERT on the current box.** Container starts
now fail outright: `/dev/fuse` and `/dev/net/tun` are missing, so `podman start`/`run` die on
fuse-overlayfs mount + pasta tap setup ("unknown argument ignored: lazytime"). The gate rig is
instead **host processes** — `redis-server *:6379` and a native `postgres` (16.15, aarch64-musl) —
both listening on 0.0.0.0, and `TEST_*_URL` already point at them. So: verify liveness with a real
client connect (asyncpg / redis-py), not `docker ps -q | wc -l`, and restore a dead service as a
host process, never a container. Zero environment skips are therefore expected — an env skip in a
gate run now signals a real regression, not a missing service. Related: [[goal-prompt-workflow]].

**Also wiped: apt-installed system libraries.** On 2026-09-15 the recreated box lacked
`libGL.so.1` (opencv-python's non-headless cv2 needs it): gate 20 attempt 1 died in the unit
tier with 2005 `ImportError: libGL.so.1` errors cascading to 1274 `module 'backend' has no
attribute 'services'` errors — 1908 failed/1417 errors in 70s. That is an environment casualty,
NOT a code regression — classify before suspecting the tree. Fix: `sudo -n apt-get install -y
libgl1 libglib2.0-0` (sudo is passwordless for `agent`), verify `uv run python -c "import cv2"`,
then re-run. Related: [[goal-prompt-workflow]], [[gate-protocol]].
