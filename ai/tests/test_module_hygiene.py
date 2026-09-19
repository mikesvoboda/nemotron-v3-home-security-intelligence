"""WP6.1 collection-hygiene guards for the ai/ tier.

``ai/enrichment/test_model.py`` used to install fake ``ai`` /
``ai.enrichment`` / ``ai.enrichment.vitpose`` ModuleType objects into
``sys.modules`` at import time. That poisoned the whole rest of the tree
during a full run (12 of the 19 collection errors). The file itself
could not collect either: pytest imports it as ``ai.enrichment.test_model``
so the package chain registers model_manager's Prometheus gauges via the
package path, and the file's own flat ``from model import`` bound the same
file a second time — ``DuplicateTimeseries`` on
``enrichment_vram_usage_bytes``.

The guards run each collection in a SUBPROCESS because the poisoning is
process-global and nested in-process runs contaminate each other through
the flat ``model`` binding. The real-package assertion runs inside that
subprocess via ``wp61_poison_probe`` (a tiny plugin dropped in a tmp dir),
i.e. at the moment where contamination would actually break CI.

Full-tree collection still has errors (WP6.2 triton shadowing, WP6.3/6.4)
— this guard deliberately asserts ONLY the poisoning, not rc==0, until
those land.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Collection runs a cold import of torch & friends per subprocess.
RUN_TIMEOUT = 240

# Neutralize the pyproject addopts that must not apply here: xdist and
# randomized collection order. CLI args land after addopts; last wins.
NESTED_OVERRIDES = ["--collect-only", "-q", "--color=no", "-n0", "-p", "no:randomly"]

# Written to a tmp dir, put on PYTHONPATH, loaded with -p into the nested
# run. After the nested ai/ session finishes, assert sys.modules["ai"] is
# still the real repo package (a ModuleType mock has no __file__) and
# record the verdict for the parent.
PROBE_PLUGIN = '''\
"""pytest plugin: after collection, report whether sys.modules["ai"] is real."""
import os
import sys
from pathlib import Path


def pytest_sessionfinish(session, exitstatus):
    verdict = "CLEAN"
    mod = sys.modules.get("ai")
    if mod is None:
        verdict = "POISONED:absent"
    elif getattr(mod, "__file__", None) is None:
        verdict = "POISONED:mock-module"
    else:
        root = Path(os.environ["WP61_REPO_ROOT"]).resolve()
        expected = root / "ai" / "__init__.py"
        if Path(mod.__file__).resolve() != expected:
            verdict = f"POISONED:{mod.__file__}"
    marker = os.environ["WP61_VERDICT_FILE"]
    Path(marker).write_text(verdict, encoding="utf-8")
'''


def _run_nested(tmp_path: Path, *paths: Path) -> subprocess.CompletedProcess[str]:
    """Run a collection pass in a subprocess with the poison probe loaded."""
    probe_dir = tmp_path / "probe"
    probe_dir.mkdir(exist_ok=True)
    (probe_dir / "wp61_poison_probe.py").write_text(PROBE_PLUGIN, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(probe_dir), *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])]
    )
    env["WP61_VERDICT_FILE"] = str(tmp_path / "verdict.txt")
    env["WP61_REPO_ROOT"] = str(REPO_ROOT)
    return subprocess.run(  # noqa: S603  # intentional - runs our own pytest on our own tree
        [
            sys.executable,
            "-m",
            "pytest",
            *NESTED_OVERRIDES,
            "-p",
            "wp61_poison_probe",
            *(str(p) for p in paths),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT,
        check=False,
    )


@pytest.mark.timeout(RUN_TIMEOUT + 30)
def test_enrichment_test_model_collects_alone(tmp_path: Path) -> None:
    """The double-import + mock blocked collection of this one file.

    A file-local failure must not need any other ai/ file fixed first:
    this passes even while the rest of the tier is still being repaired.
    """
    result = _run_nested(tmp_path, REPO_ROOT / "ai" / "enrichment" / "test_model.py")
    assert result.returncode == 0, (
        f"ai/enrichment/test_model.py failed to collect (rc={result.returncode}):\n"
        f"{result.stdout[-4000:]}\n{result.stderr[-2000:]}"
    )


@pytest.mark.timeout(RUN_TIMEOUT + 30)
def test_full_ai_collection_leaves_real_ai_package(tmp_path: Path) -> None:
    """After a full ai/ collection, sys.modules["ai"] is the real package."""
    result = _run_nested(tmp_path, REPO_ROOT / "ai")
    # rc==2 (collection errors) is still possible here — WP6.2 (triton
    # shadowing) and WP6.3/6.4 own those; the whole-tree collect-only gate
    # lands in WP6.5 once they're green. This guard owns ONLY the poison
    # assertion, which the probe evaluates inside the nested process.
    verdict_path = tmp_path / "verdict.txt"
    assert verdict_path.exists(), "nested run did not reach sessionfinish"
    verdict = verdict_path.read_text(encoding="utf-8")
    assert verdict == "CLEAN", (
        f"sys.modules['ai'] after full ai/ collection: {verdict!r} — "
        "something in ai/ mutates sys.modules at import time"
    )
