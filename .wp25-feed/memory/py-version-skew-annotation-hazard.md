---
name: py-version-skew-annotation-hazard
description: "CI resolves Python 3.14 -> 3.14.2 while the sandbox runs 3.14.4; mock only passes FORWARDREF on 3.14.4, so unquoted TYPE_CHECKING annotations pass locally but NameError at create_autospec on CI"
metadata:
  node_type: memory
  type: project
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-17T07:39:53.912Z
---

Found 2026-09-17 during WP4.1. `.python-version` says "3.14"; CI's `uv python install 3.14` resolved 3.14.2, the sandbox image carries 3.14.4. PEP 649 evaluates annotations on demand, so an unquoted param annotated with a `if TYPE_CHECKING`-only name NameErrors inside `inspect.signature` — and stdlib mock.py on 3.14.4 passes `annotation_format=Format.FORWARDREF` (mock.py:123) which tolerates it, while 3.14.2's mock passes no format at all. Local green ≠ CI green for anything that introspects signatures.

**Why:** the sweep's autospecs made this CI-only until it burned 52 security errors + unit shards; every sandbox run said green.

**How to apply:** for any introspection-dependent failure, run under 3.14.2 (`~/.local/share/uv/python/cpython-3.14.2-linux-aarch64-gnu/bin/python3.14` with `PYTHONPATH=.venv/lib/python3.14/site-packages` — CI is x86, sandbox aarch64, so site-packages are shared). Fix shape is `from __future__ import annotations` (PEP 563) — quoted annotations are NOT durable, ruff UP037 strips them on commit. Watch for future CI runner updates closing the skew in either direction. Repairs: `757be8f8` `0f0496d0` `abeb01cf` (production, PEP 563), `a51fa206` (test-side OTel patch-order). Related: [[pytest-quiet-traps]] [[wp25-resume-pack-2026-09-16]]
