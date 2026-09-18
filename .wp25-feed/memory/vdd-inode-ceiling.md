---
name: vdd-inode-ceiling
description: /var/lib/docker (vdd) has a fixed 655k-inode ceiling; an orphaned anonymous postgres volume caused transient ENOSPC at 21% blocks — disk samplers must track inodes
metadata:
  node_type: memory
  type: project
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-15T05:44:43.489Z
---

vdd (/var/lib/docker, 9.8G ext4) is formatted with only **655,360 inodes**. Postgres test-DB churn
consumes them fast: each per-gate postgres datadir accumulated ~400k inodes, and an **orphaned
anonymous volume** from a previous gate-postgres (anonymous volumes survive `docker rm` of their
container) held 409k of them — 62% of the whole filesystem — before a run even started.

**Symptom class (gate-20 attempt 4, 2026-09-15):** `psycopg2.errors.DiskFull: could not create
directory "base/..."` / `asyncpg DiskFullError` on ~10 scattered setup/teardowns while block usage
sat at 19–21% with 7.5GB free. Inode exhaustion is transient *during* the run (create/drop of 8
worker DBs), so a blocks-only sampler never sees it. Downstream: DiskFull-interrupted tests abort
cleanup, leaving rows (e.g. live 'Test Camera' vs `idx_cameras_name_unique`) that poison the next
same-worker insert — UniqueViolations are SECONDARY, not test bugs. Classify against inodes before
touching tests.

**How to apply:** before any heavy gate, check `df -i /var/lib/docker` (needs ≥~100k free inodes)
and sweep orphans: `docker volume ls` + per-volume `find <mnt> | wc -l`; `docker volume rm` the
anonymous postgres ones. Gate samplers must log `df -i` alongside `df -h`. Fix that day: removed
orphan volume → inodes 65%→3%. Related: [[sandbox-recreate-vs-reboot]] (same box, other rig
casualties: libGL, TEST_* env).
