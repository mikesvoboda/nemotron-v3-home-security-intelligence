"""Package-form canonicalization for the flat service modules the tests import.

WP6.1/WP6.2 (docs/superpowers/plans/2026-09-19-swap-readiness-72h.md).

The service test files use the flat-directory import style (``from model
import ...``) because the container images COPY the module files flat into
/app — that style is fixed by section 1 of the plan. In the repo the same
files are also members of real packages, so a single pytest session imports
some of them TWICE under different names (package chain + flat path): the
second execution re-declares module-scope Prometheus metrics
(DuplicateTimeseries) — and across services, the bare names ``model`` /
``metrics`` are a single global slot that the first importer wins, so a
file whose directory is not on sys.path yet resolves ``from model import``
to *another service's* module (full-tree run: ``AUTHORITY_CATEGORIES``
"missing" from clip's model; ``SECURITY_CLASSES`` missing from enrichment's;
yolo26's metrics shadowed by enrichment's).

Root conftest hooks run before each test module is imported, so this file:

1. pins ``ai.enrichment.model_manager`` as the canonical flat
   ``model_manager`` (WP6.1 — both import styles share one Gauge object);
2. blocks ``triton`` (WP6.2, below);
3. for every collected module under a service directory in ``_FLAT_OWNERS``,
   imports that service's canonical package module once and (re)binds the
   flat name to THAT object — at collection import time (fixes the wrong-
   service ImportError) and again before each test runs (fixes
   string-target patches like ``patch("model.validate_model_path")`` and
   tests that ``del sys.modules["model"]`` themselves).

``ai/enrichment-light`` is deliberately absent: the hyphen makes it
unimportable as a package (renaming touches compose build contexts — parked
as a ruling) and its tests manage their own ``sys.modules["model"]``.

Note: importing ``ai.enrichment.model`` at collection time starts the
pyroscope profiler thread like the flat import always did — the same
behavior WP6.1's tree already had, just under the package name.
"""

from __future__ import annotations

import contextlib
import importlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# --- 1. enrichment model_manager: package object owns the flat name ------

_enrichment_dir = Path(__file__).resolve().parent / "enrichment"
if str(_enrichment_dir) not in sys.path:
    sys.path.append(str(_enrichment_dir))

_pkg_model_manager = importlib.import_module("ai.enrichment.model_manager")
sys.modules.setdefault("model_manager", _pkg_model_manager)

# --- 2. WP6.2: block the triton shadow -------------------------------------
# The repo has no pip `triton`, but the ai/ directory legitimately appears
# on sys.path (conftests and the production shim blocks in clip/yolo26/
# enrichment/nemotron model.py all insert it, matching the flat container
# layout) and contains ai/triton — the Triton *Inference Server* CLIENT
# package. `import triton` then silently binds that client, and
# torch._dynamo.utils — which probes for the triton *compiler* — dies with
# `module 'triton' has no attribute 'language'` inside transformers' lazy
# imports (6 whole-file collection errors: clip, enrichment test_model,
# person_reid, florence x3). Position is irrelevant — append was tested and
# is a verified non-fix while the real package is absent; and a
# fixture-scoped conftest fix cannot cover the production shims that insert
# ai/ at arbitrary points mid-session. Setting the entry to None makes
# `import triton` raise ImportError — exactly the graceful "triton is
# absent" state every consumer already handles (verified: transformers
# CLIPModel/GenerationMixin/AutoModelForCausalLM import fine under the
# block). If pip triton is ever installed, find_spec still sees it and only
# a literal `import triton` stays blocked — ai/triton/tests mock
# tritonclient, never bare triton.
sys.modules["triton"] = None

# --- 3. per-service owners of the colliding flat names ---------------------

# directory -> {flat module name -> canonical package module name}
# Values are LEAF-FIRST ordered tuples: a service's model imports its own
# flat siblings (``from metrics import ...``) while it executes, so each
# leaf's flat binding must be in place BEFORE the next import runs.
_FLAT_OWNERS: dict[Path, tuple[tuple[str, str], ...]] = {
    _enrichment_dir: (
        ("model_manager", "ai.enrichment.model_manager"),
        ("metrics", "ai.enrichment.metrics"),
        ("vitpose", "ai.enrichment.vitpose"),
        ("model", "ai.enrichment.model"),
    ),
    _ROOT / "ai" / "clip": (("model", "ai.clip.model"),),
    _ROOT / "ai" / "florence": (("model", "ai.florence.model"),),
    _ROOT / "ai" / "yolo26": (
        ("metrics", "ai.yolo26.metrics"),
        ("model", "ai.yolo26.model"),
    ),
}


def _owner_dir_for(nodepath: Path) -> Path | None:
    """The service directory owning this file (walks up through test subdirs)."""
    d = nodepath.parent
    while d != d.parent:
        if d in _FLAT_OWNERS:
            return d
        d = d.parent
    return None


def _ensure_canonical(owner_dir: Path) -> None:
    """Import the owner service's canonical modules, binding flat aliases.

    The owner directory is temporarily appended to sys.path so the module's
    OWN flat sibling imports resolve (the container provides them via the
    flat /app layout). Entries are leaf-first so a service module's own
    flat sibling imports bind ITS siblings, not another service's leftover.
    On success each flat name is pointed at the package object; on failure
    (GPU-only deps, missing optional backends) we leave the previous
    binding untouched — worst case stays exactly the pre-WP6.2 behavior
    for that service.
    """
    dir_str = str(owner_dir)
    added = dir_str not in sys.path
    if added:
        sys.path.append(dir_str)
    try:
        for flat_name, canonical in _FLAT_OWNERS[owner_dir]:
            mod = sys.modules.get(canonical)
            if mod is None:
                with contextlib.suppress(Exception):
                    mod = importlib.import_module(canonical)
                if mod is None:
                    continue  # degrade to legacy behavior for this name
            # NOT setdefault: a previous service may already have won this
            # slot (the bug); the file about to be imported/run belongs to
            # THIS service, so this service owns the flat name now.
            sys.modules[flat_name] = mod
    finally:
        if added:
            sys.path.remove(dir_str)


@pytest.hookimpl(trylast=True)
def pytest_collectstart(collector: pytest.Collector) -> None:
    """Rebind flat module names before a service test module is imported."""
    if not isinstance(collector, pytest.Module):
        return
    owner = _owner_dir_for(Path(str(collector.path)))
    if owner is not None:
        _ensure_canonical(owner)


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Rebind again before each test body (imports inside tests, string patches)."""
    owner = _owner_dir_for(Path(str(item.path)))
    if owner is not None:
        _ensure_canonical(owner)
