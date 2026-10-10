"""B2.2's owner-run script: ``scripts/reid_parity_check.py``.

It runs the owner's crops through the backend's CPU OSNet path and the gateway's
GPU path with the production weights, and reports parity and timing (ruling 68:
"a command in the PR body that checks parity on the owner's host with the
production weights"). These tests pin its arithmetic and its verdict; the
paths themselves are exercised by the run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "reid_parity_check.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("reid_parity_check", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["reid_parity_check"] = module
    spec.loader.exec_module(module)
    return module


def _unit(v: list[float]) -> np.ndarray:
    a = np.asarray(v, dtype=np.float32)
    return a / np.linalg.norm(a)


class TestCosine:
    def test_identical_vectors_score_one(self, script) -> None:
        v = _unit([1, 2, 3])
        assert script.cosine(v, v) == pytest.approx(1.0)

    def test_normalises_both_inputs(self, script) -> None:
        assert script.cosine(np.array([2.0, 0.0]), np.array([5.0, 0.0])) == pytest.approx(1.0)


class TestTimings:
    def test_summary_reports_median_p95_and_per_event(self, script) -> None:
        summary = script.timing_summary([10.0, 20.0, 30.0, 40.0], crops_per_event=3)

        assert summary["median_ms"] == pytest.approx(25.0)
        assert summary["p95_ms"] == pytest.approx(38.5)
        # An event embeds its crops one after another (vlm_specialists.py:756).
        assert summary["per_event_ms"] == pytest.approx(75.0)


class TestVerdict:
    def test_passes_at_and_above_the_gate(self, script) -> None:
        assert script.verdict([0.9995, 0.999], model_ids_match=True) == "PASS"

    def test_fails_below_the_gate_and_is_never_loosened(self, script) -> None:
        assert script.PARITY_GATE == 0.999
        assert script.verdict([0.9995, 0.9989], model_ids_match=True) == "FAIL"

    def test_fails_when_the_gateway_names_other_weights(self, script) -> None:
        assert script.verdict([1.0], model_ids_match=False) == "FAIL"

    def test_fails_with_no_crops(self, script) -> None:
        assert script.verdict([], model_ids_match=True) == "FAIL"
