"""Package-form alias for the flat service modules the tests import.

WP6.1 (docs/superpowers/plans/2026-09-19-swap-readiness-72h.md): the service
test files use the flat-directory import style (``from model import ...``)
because the container images COPY the module files flat into /app — that
style is fixed. The repo, however, also has real packages on the line
(``ai/enrichment/__init__.py``), so pytest can import the *same file* twice
under two names: as ``ai.enrichment.test_model`` (package chain executes
``ai.enrichment.model_manager`` and its module-scope Prometheus gauges) and
then via the flat ``from model import`` (binds the file again under a new
name, declaring the same gauge names again) → ``DuplicateTimeseries`` on
collection, and — because the package init re-exports the leaf modules
eagerly — the gauges get a second *distinct object* bound under them,
breaking teardown isolation between sibling test files.

Root conftest files load before any test module, so importing the package
form here pins the canonical ``model_manager`` object in ``sys.modules``
first; the test files' flat ``from model_manager import`` then resolves to
the same object via ``sys.modules.setdefault``, while anything else flat
(e.g. ``metrics``) still resolves per-directory as before. The import
touches torch/prometheus only — CPU-safe and already collected by other
tiers. ``model`` itself is deliberately NOT aliased: nothing imports it in
package form at collection time, and importing it here would start the
pyroscope profiler for every ai/ run.

Note ``ai/enrichment-light`` is deliberately untouched: the hyphen makes it
unimportable as a package (renaming touches compose build contexts — parked
as a ruling), and its tests manage their own ``sys.modules["model"]``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import ai.enrichment.model_manager as _pkg_model_manager

# The test files insert ai/enrichment at sys.path[0] at import time, so the
# canonical module must also be reachable by its flat name before their
# module-scope imports run — setdefault keeps their own insertion working
# while making it resolve to the package object instead of a second copy.
_enrichment_dir = str(Path(__file__).resolve().parent / "enrichment")
if _enrichment_dir not in sys.path:
    sys.path.append(_enrichment_dir)

sys.modules.setdefault("model_manager", _pkg_model_manager)
