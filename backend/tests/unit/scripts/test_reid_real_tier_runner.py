"""Unit tests for scripts/uplevel/reid_real_tier.sh ([r157], rulings 157 + 159).

ABOUTME: The committed runner's mode sequence is machine-pinned, because the
parity arm's correctness is invisible to every CPU-only check CI can run (the
GPU legs and the gateway leg need the serving host). Two facts make the pin
load-bearing: Triton's reid model declares ``backend: "tensorrt"``
(ai/triton/model_repository/reid/config.pbtxt), so the gateway can serve ONLY
from a compiled ``model.plan``; and every invocation allocates a FRESH run
directory (``RUN="$(mktemp -d ...)"``), so no earlier invocation can leave a
plan behind for a later one to find. The owner's ``o24-run-safe.sh`` compiled
at STEP 2b before serving; the first rebuild under ruling 159 dropped that
step, leaving default ``parity`` mode unable to serve at all (correction
posted on #7087 as 6158002348). Pins below: the parity arm compiles its FP16
plan BEFORE it serves; the stages arm still compiles both precisions; and the
header tells the truth about where the sequence differs from o24-run-safe.sh.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = PROJECT_ROOT / "scripts" / "uplevel" / "reid_real_tier.sh"


def _arm(text: str, name: str) -> str:
    """Return the body of one ``case "$MODE"`` arm, by arm label."""
    marker = f"  {name})\n"
    assert marker in text, f"mode arm {name!r} missing from the runner"
    rest = text[text.index(marker) + len(marker) :]
    nxt = re.search(r"^  \w+\)\n|^esac\n", rest, re.M)
    assert nxt is not None, f"arm {name!r} never terminates"
    return rest[: nxt.start()]


@pytest.fixture(scope="module")
def script_text() -> str:
    return SCRIPT.read_text()


def test_runner_syntax_is_valid(script_text: str, tmp_path: Path) -> None:
    """bash -n on the committed runner: a syntax error here fails the owner's
    real-tier run before it prints RUN=, i.e. before any log they can read."""
    probe = tmp_path / "reid_real_tier_syntax.sh"
    probe.write_text(script_text)  # copy, so the repo file is never the target
    done = subprocess.run(
        ["bash", "-n", str(probe)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, f"bash -n failed: {done.stderr}"


def test_parity_mode_compiles_plan_before_serving(script_text: str) -> None:
    """STEP 2b, restored: default parity mode must call ``compile_plan fp16``
    before its first ``start_gateway``. Without it the read-only cache holds
    only model.onnx while Triton asks for a .plan — the run dies in serve, and
    because the near-miss FP32 retry copies model.plan before recompiling, even
    the retry path is unreachable. This is the pin that was red on main."""
    arm = _arm(script_text, "parity")
    serve = arm.find("start_gateway")
    compile_at = arm.find("compile_plan fp16")
    assert serve != -1, "parity arm must serve the gateway"
    assert compile_at != -1, (
        "parity arm never calls compile_plan fp16 — the gateway would serve "
        "an empty read-only cache and Triton's tensorrt backend has no plan"
    )
    assert compile_at < serve, "parity compiles AFTER it serves: plan not in cache"


def test_parity_compile_is_fp16_only(script_text: str) -> None:
    """The restored step matches o24-run-safe.sh: FP16 before serving, and the
    FP32 leg stays exactly where ruling 159 put it — the near-miss retry. A
    second compile_plan call before the serve would silently change what the
    parity numbers measure."""
    arm = _arm(script_text, "parity")
    serve = arm.find("start_gateway")
    pre_serve = arm[:serve]
    assert pre_serve.count("compile_plan") == 1, (
        "exactly one plan compile belongs before the parity serve (fp16); "
        "pre-serving fp32 would reroute the parity check off the served plan"
    )


def test_stages_mode_still_compiles_both_precisions(script_text: str) -> None:
    """Control for the fix above, and it is green on main: stages mode compiles
    both precisions inside ``run_stages`` (STEP S3: fp32, copy, fp16, copy),
    which is what makes stage 3 vs stage 4 answerable at all. Read the FUNCTION
    body, not the arm — the arm only calls ``run_stages``. The parity restore
    must not disturb it."""
    assert "run_stages\n" in _arm(script_text, "stages"), (
        "stages mode dispatches to run_stages(); if that indirection is gone, "
        "this pin reads the wrong region and would pass vacuously"
    )
    start = script_text.index("run_stages() {")
    body = script_text[start : script_text.index("\n}\n", start)]
    assert body.count("compile_plan fp32") == 1
    assert body.count("compile_plan fp16") == 1
    assert body.index("compile_plan fp32") < body.index("compile_plan fp16")


def test_header_states_the_sequence_difference(script_text: str) -> None:
    """The header's opening paragraph claims the sequence is o24-run-safe.sh's
    except the four arguments. Once STEP 2b is restored that claim was false
    as written (it described the run the owner could NOT execute); pin the
    honest wording instead of trusting prose. Checked on the first ~12 lines,
    the paragraph that makes the claim — not anywhere in the file, which any
    later 'STEP 2b' echo would satisfy vacuously."""
    header = "\n".join(script_text.splitlines()[:12])
    assert "Nothing else about the sequence changed" not in header
    assert "STEP 2b" in header, "header must name the one restored sequence step"
