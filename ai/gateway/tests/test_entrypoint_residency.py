"""File-content pins for the entrypoint's residency step (Phase 1.4, rev 6).

The pruning logic itself is unit-tested in test_residency.py; these pins
cover the wiring: the step EXISTS, it runs BEFORE Triton starts (a prune
after the scan does nothing — Triton already loaded everything), and its
failure is FATAL. The contrast is deliberate: patch_triton_configs.py is
cosmetic (wrong instance_group kind still serves), but a failed residency
prune leaves the retired models in the repository for Triton to load —
exactly what spec rev 6 forbids — so the container must stop, not proceed
degraded. Same reasoning as --strict-config: wrong footprint beats wrong
uptime.
"""

from __future__ import annotations

import re
from pathlib import Path

ENTRYPOINT = Path(__file__).resolve().parents[1] / "entrypoint.sh"


def _text() -> str:
    return ENTRYPOINT.read_text()


class TestResidencyStep:
    def test_residency_step_invokes_the_module(self) -> None:
        assert re.search(r"python3 -m ai\.gateway\.residency", _text()), (
            "entrypoint must prune the repository via ai.gateway.residency"
        )

    def test_residency_runs_before_triton_starts(self) -> None:
        text = _text()
        call = text.index("ai.gateway.residency")
        start = text.index("tritonserver \\")
        assert call < start, "residency prune must precede the Triton scan"

    def test_residency_runs_after_the_cache_symlinks(self) -> None:
        """0c links exported weights into every repo model dir; pruning the
        repository after that moves whole dirs with their links, so a pruned
        model never leaves a dangling symlink behind."""
        text = _text()
        link = text.index("Linking model cache")
        call = text.index("ai.gateway.residency")
        assert link < call

    def test_residency_failure_is_fatal(self) -> None:
        """No '|| echo' swallow on the residency line — unlike the patcher,
        a failed prune must stop the container (see module docstring)."""
        for line in _text().splitlines():
            if "ai.gateway.residency" in line and not line.lstrip().startswith("#"):
                assert "||" not in line, f"residency failure must be fatal: {line!r}"
                break
        else:  # pragma: no cover
            raise AssertionError("residency call not found")
