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

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = PROJECT_ROOT / "scripts" / "uplevel" / "reid_real_tier.sh"


def _code(text: str) -> str:
    """Blank out shell comment lines, keeping every line position intact.

    Several pins here hunt for a token on a *statement* (``start_gateway``,
    ``cosine_table.py``, ``|| true``). The runner explains itself heavily in
    comments that name those same tokens, so a grep over raw text can be
    satisfied -- or poisoned -- by prose: a comment mentioning a bare
    ``start_gateway`` makes a guarded call look bare, and a comment containing
    ``|| true`` lands inside a ``tail`` window and reads as a swallowed exit
    code. Both are false verdicts, and they fail in OPPOSITE directions, so
    neither shows up as a consistent signal. Same reasoning ``_heredoc`` states
    for the embedded programs: anchor on the code, never on a mention.

    Lines are blanked rather than dropped so character offsets stay comparable
    across a strip -- ordering assertions (this before that) keep meaning.
    """
    return "\n".join("" if ln.lstrip().startswith("#") else ln for ln in text.splitlines())


def _heredoc(text: str, written_name: str, tag: str) -> str:
    """Return one embedded python program the runner writes with ``cat > ...
    <<'TAG'``. These programs are the runner's actual measuring code (the probe
    and the cosine table), so they are testable -- the table is pure stdlib and
    runs on this host. Anchored on the exact redirect line so a stray mention of
    the tag in prose cannot be mistaken for the program."""
    opener = f"<<'{tag}'\n"
    assert opener in text, f"heredoc {tag!r} missing from the runner"
    rest = text[text.index(opener) + len(opener) :]
    end = f"\n{tag}\n"
    assert end in rest, f"heredoc {tag!r} never terminates"
    body = rest[: rest.index(end)]
    assert written_name in text[: text.index(opener)], (
        f"heredoc {tag!r} is not written to {written_name} — this helper read the wrong program"
    )
    return body


_MOUNT_ARG = re.compile(r'-v\s+((?:"[^"]*"|[^\s\\])+)')


def _bind_mounts(text: str) -> list[tuple[str, str]]:
    """Every ``-v`` bind mount in a shell script, as (source, full-spec).

    Two shell-quoting shapes are legal to podman and BOTH appear in this repo's
    scripts: quotes round the source only (``-v "$RUN/zoo":/zoo:ro``) and quotes
    round the whole spec (``-v "/a:/b:ro"``). A parser that matches only the
    first — the shape the committed runner happens to use — will not see a mount
    written the second way, and then every absence clause over mounts passes
    vacuously. (That is how M12, a mounted podman socket, survived the first
    draft of the UR-134 pin.) So: capture the whole argument whatever its quoting,
    drop the quotes, and split on ``:`` exactly as the engine would.
    """
    out: list[tuple[str, str]] = []
    for arg in _MOUNT_ARG.findall(text):
        spec = arg.replace('"', "")
        if ":" not in spec:
            continue  # `command -v docker` matches the -v shape but is not a mount
        out.append((spec.split(":", 1)[0], spec))
    return out


def _fn_body(text: str, name: str) -> str:
    """Return the body of one shell function, ``name() { ... }``, by name.

    The runner's load-bearing sequencing lives INSIDE functions (``run_stages``
    dispatches from the mode arm, ``compile_plan`` wraps the one container that
    touches the GPU), so a pin that reads the arm sees only a call. Same
    anchored-read as ``_gw_body``: start at the definition, stop at the first
    line that is just ``}``.
    """
    start = text.index(f"{name}() {{")
    return text[start : text.index("\n}\n", start)]


def _gw_body(text: str) -> str:
    """Return the body of ``start_gateway()`` -- the one container the runner
    serves to the host, so the only place a UR-134 or UR-133 violation could
    reach outside the run directory with intent."""
    start = text.index("start_gateway() {")
    return text[start : text.index("\n}\n", start)]


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
    done = subprocess.run(  # real: bash -n on our own script IS the test  # noqa: S603
        ["bash", "-n", str(probe)],  # noqa: S607 - bash resolved on PATH, fixed argv
        capture_output=True,
        text=True,
        check=False,
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


def test_plan_probe_prints_the_binding_as_bound(script_text: str) -> None:
    """Ruling 157 bullet 2 is verbatim: stages 3 and 4 run the plan "with
    Triton's input and output names, shapes and layout printed as they are
    bound." The first build read that metadata and DISCARDED it -- the only
    prints were the row/width count and the cosine table's crop-filename column
    -- so the owner's single posted run could not name which name/shape/layout
    mismatch breaks stage 5, which is the one stage the owner's run implicated.
    Pin the print, on the probe's own text, and pin that it reads the metadata
    off the ENGINE (get_tensor_mode/get_tensor_dtype) rather than restating the
    constants we already know."""
    probe = _heredoc(script_text, "stage_probe.py", "PROBE")
    trt = probe[probe.index("def _trt_run(") :]
    # Anchor the engine-read check on the helper that BUILDS THE PRINTED STRING,
    # not on _trt_run at large. Two reasons, both measured here: the enumeration
    # loop above also calls get_tensor_mode (so a whole-function needle is
    # satisfied by a call unrelated to the print), and this file's own comment
    # prose names get_tensor_mode/get_tensor_shape/get_tensor_dtype (so a mutant
    # that hardcodes the printed string outright still passes a substring check
    # over the function -- that was M4). Pinning the _io body is the only region
    # where those calls are load-bearing.
    io = trt[trt.index("def _io(") : trt.index('print(f"plan')]
    for call in ("get_tensor_mode", "get_tensor_shape", "get_tensor_dtype"):
        assert f"engine.{call}(" in io, (
            f"the printed binding must come from engine.{call}() -- the engine's "
            "own view -- not from restated constants"
        )
    # The print BLOCK, sliced by anchors, not the lines starting with `print(`:
    # the probe-feeds line is a multi-line call, so a per-line filter would drop
    # its continuation lines and this pin would fail on correct code.
    block = trt[trt.index('print(f"plan') : trt.index("out = np.empty")]
    assert block.count("print(") >= 3, f"expected the three binding prints, got:\n{block}"
    assert "in_names[0]" in block and "out_names[0]" in block, (
        "the plan probe must PRINT the bound input and output names; computing "
        "them to drive execution is not the deliverable bullet 2 asks for"
    )
    assert "BATCH.shape" in block, "the print must show the layout actually fed"


def test_gateway_leg_prints_triton_s_bound_names(script_text: str) -> None:
    """Stage 5's suspect IS the Triton binding (the header says so), so the
    gateway leg owes the same print from the OTHER side: Triton's own
    ``/v2/models/reid/config``. Port 8000 is never published to the host --
    only 8090 is, on loopback -- so it has to be read with ``podman exec``,
    which is the shape this pin holds. It is deliberately non-fatal: a missing
    curl must not fail a run whose job is the cosine, but it must WARN."""
    gw = script_text[script_text.index("start_gateway() {") :]
    gw = gw[: gw.index("\n}\n")]
    assert "/v2/models/reid/config" in gw, (
        "the gateway leg must read Triton's own view of reid's names/shapes"
    )
    assert "podman exec" in gw, (
        "Triton's HTTP port is not published to the host, so the config read "
        "must go through podman exec, not a host-side curl"
    )
    assert "WARN" in gw, "an unreadable binding must print, not stay silent"


def test_deployment_keeps_ur134(script_text: str) -> None:
    """UR-134's three clauses, on the runner's own text: ``ORCHESTRATOR_ENABLED
    =false``, no container-engine socket in any container, no writable bind mount
    outside the run's own directory. The review that raised this verified the
    latter two BY HAND at the previous head; a hand check is not a pin, and a
    body that asserts a rule the file does not hold is the UR-31 defect this
    package keeps getting caught for, so all three are held here.

    Mounts are parsed by shape (``-v "SRC":DEST[:MODE]``), not by listing the
    good ones, and the parse's own yield is asserted first -- a regex that
    matches nothing would make the socket clause pass vacuously. (Scanning the
    whole file for ``.sock`` instead would be a FALSE RED: the runner's own port
    probe calls ``socket.socket()``, and a substring needle has no idea a mount
    is what it is talking about.)
    """
    gw = _gw_body(script_text)
    assert "-e ORCHESTRATOR_ENABLED=false" in gw, (
        "UR-134 is unconditional. The flag is inert in this image (the gateway "
        "image carries no backend code -- ai/gateway/Dockerfile copies only "
        "ai/gateway and ai/triton) but a container that later gains the backend "
        "must not inherit this script with the orchestrator enabled."
    )
    mounts = _bind_mounts(script_text)
    assert len(mounts) >= 6, (
        f"parsed {len(mounts)} bind mounts; the runner has at least 6 on every "
        "path, so a smaller number means the extractor matched the wrong shape "
        "and the two clauses below would pass vacuously"
    )
    assert any(s == "$RUN/zoo" for s, _ in mounts), (
        "the extractor found mounts but not the zoo mount; it is reading the "
        "wrong region and cannot certify the socket clause"
    )
    for src, spec in mounts:
        assert ".sock" not in spec, f"container-engine socket mounted: {spec} -- UR-134"
        assert src == "$RUN" or src.startswith("$RUN/"), (
            f"bind mount outside the run directory: {spec} -- UR-134"
        )


def test_the_mount_extractor_sees_both_quoting_shapes() -> None:
    """Positive control for the UR-134 pin above, ON THE EXTRACTOR. An absence
    claim is only as good as the parse it runs over, and the committed runner
    uses one shell-quoting shape, so nothing in the suite otherwise proves the
    parser can see the other one. M12 -- mounting /run/podman/podman.sock in
    whole-spec quotes, the shape podman also accepts -- survived the first draft
    for exactly this reason: the regex demanded a `"` right before the `:` that
    only the source-quoted form has. If this pin ever goes red, every mount
    absence claim in the file above is void, not just this one.
    """
    sample = (
        'podman run -v "$RUN/zoo":/zoo:ro -v "/run/podman/podman.sock:/s:ro" \\\n'
        "  -v $RUN/cache:/out:ro command -v docker\n"
    )
    found = [spec for _, spec in _bind_mounts(sample)]
    assert "$RUN/zoo:/zoo:ro" in found, f"missed source-quoted mount: {found}"
    assert "/run/podman/podman.sock:/s:ro" in found, f"missed whole-spec-quoted mount: {found}"
    assert "$RUN/cache:/out:ro" in found, f"missed unquoted mount: {found}"
    assert "docker" not in " ".join(found), f"`command -v docker` read as a mount: {found}"


def test_stage_plan_never_falls_back_to_the_cache_plan(script_text: str) -> None:
    """The cache copy is whatever compile_plan wrote LAST, and run_stages
    compiles fp32 THEN fp16 -- so the old fallback meant a stage-3 whose
    ``cp`` had failed measured the FP16 plan and reported it FP32-clean. That is
    not a small wrong number, it is the exact question this diagnostic exists to
    answer (FP32 vs FP16 is what separates "the plan is wrong" from "FP16 is not
    enough"), answered backwards and silently. Pin: the fallback is gone and a
    missing per-precision plan RAISES so the stage reads unknown."""
    probe = _heredoc(script_text, "stage_probe.py", "PROBE")
    start = probe.index("def stage_plan(")
    end = probe.index("\nBUILDERS = {", start)  # the real next top-level construct
    sp = probe[start:end]
    assert 'RUN / "cache"' not in sp, (
        "stage_plan must not fall back to the cache plan: that file holds the "
        "LAST compiled precision, so stage 3 could measure FP16 as FP32"
    )
    assert "raise SystemExit" in sp, (
        "a missing per-precision plan must fail the stage (the table then reads "
        "unknown) rather than substitute a plan from a different precision"
    )


def _run_table(table_src: str, tmp_path: Path, stages: dict[str, list[float] | None]):
    """Write the runner's real cosine table and run it over synthetic stage
    files, returning (rc, stdout). Each value is the vector for that stage, or
    ``None`` for "the leg never ran" (file absent). Standard-library only, so
    this is the shipped program, not a reimplementation of it."""
    run = tmp_path / "run"
    run.mkdir()
    for num, vec in stages.items():
        if vec is None:
            continue
        (run / f"stage-{num}.json").write_text(
            json.dumps({"names": ["a.jpg", "b.jpg"], "vectors": [vec, vec]})
        )
    script = tmp_path / "cosine_table.py"
    script.write_text(table_src)
    done = subprocess.run(  # real: the shipped table IS the test  # noqa: S603 - fixed argv
        [sys.executable, "-I", str(script), str(run)],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


CLEAN = [1.0, 0.0]
BROKEN = [0.6, 0.8]  # cosine 0.6 against CLEAN: under the 0.999 gate


def test_dead_legs_cannot_post_as_a_clean_run(script_text: str, tmp_path: Path) -> None:
    """The owner runs this ONCE on maui and posts that run. All three GPU/host
    legs are ``|| true``-swallowed on purpose -- a raising stage must leave its
    file rather than kill the run -- so a run whose legs died still reached the
    table, and the first build printed ``RESULT: no stage below the 0.999 gate``
    at exit 0 with stages 3/4/5 unreadable (the reviewer measured exactly that).
    The headline and the exit code both read clean while three legs never ran.
    Pin the behaviour, not the wording: a table with any ``unknown`` row exits
    non-zero. ``unknown`` stays VISIBLE -- that is the point of the row."""
    table = _heredoc(script_text, "cosine_table.py", "TABLE")
    rc, out = _run_table(table, tmp_path, {"1": CLEAN, "2": CLEAN, "3": None, "4": None, "5": None})
    assert "unknown" in out, "the dead legs must be printed, not hidden"
    assert "no stage below the 0.999 gate" not in out, (
        "a run with unreadable stages must not print the clean headline"
    )
    assert rc != 0, f"a diagnostic with dead legs exited {rc} -- it must fail, not post clean"


def test_a_complete_clean_run_still_exits_zero(script_text: str, tmp_path: Path) -> None:
    """Positive control for the pin above: the non-zero exit must be caused by
    an ``unknown`` row and nothing else. Every stage present and above the gate
    is the one shape that still earns exit 0, so the new guard cannot simply
    make stages mode always fail."""
    table = _heredoc(script_text, "cosine_table.py", "TABLE")
    rc, out = _run_table(
        table, tmp_path, {"1": CLEAN, "2": CLEAN, "3": CLEAN, "4": CLEAN, "5": CLEAN}
    )
    assert "unknown" not in out
    assert "no stage below the 0.999 gate" in out
    assert rc == 0, f"a fully measured clean run must exit 0, got {rc}:\n{out}"


def test_a_located_first_failure_still_exits_zero(script_text: str, tmp_path: Path) -> None:
    """The other side of the guard, and the one easy to break by
    over-correcting. Naming the broken stage IS this mode succeeding -- that is
    what the package asks the owner to post -- so it must NOT share an exit
    status with "a leg never ran". The owner's single scarce maui run has to be
    able to tell 'found it' from 'found nothing to find' from 'found nothing'."""
    table = _heredoc(script_text, "cosine_table.py", "TABLE")
    rc, out = _run_table(
        table, tmp_path, {"1": CLEAN, "2": CLEAN, "3": BROKEN, "4": CLEAN, "5": CLEAN}
    )
    assert "the first stage under the gate is 3" in out, f"fault not located:\n{out}"
    assert rc == 0, f"a located failure is a successful diagnostic and must exit 0, got {rc}"


def test_a_crop_order_mismatch_counts_as_unknown(script_text: str, tmp_path: Path) -> None:
    """The second path to ``unknown`` (the table's other ``continue``) must trip
    the same guard: a stage that measured a DIFFERENT crop set than stage 1 has
    not measured anything comparable, and it already printed ``unknown`` at
    exit 0."""
    table = _heredoc(script_text, "cosine_table.py", "TABLE")
    run = tmp_path / "run"
    run.mkdir()
    (run / "stage-1.json").write_text(
        json.dumps({"names": ["a.jpg", "b.jpg"], "vectors": [CLEAN, CLEAN]})
    )
    (run / "stage-2.json").write_text(
        json.dumps({"names": ["b.jpg", "a.jpg"], "vectors": [CLEAN, CLEAN]})
    )
    script = tmp_path / "cosine_table.py"
    script.write_text(table)
    done = subprocess.run(  # real: the shipped table IS the test  # noqa: S603 - fixed argv
        [sys.executable, "-I", str(script), str(run)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "crop order differs from stage 1" in done.stdout
    assert done.returncode != 0, (
        f"an incomparable stage exited {done.returncode} -- it is unknown, so it must fail"
    )


def test_the_stages_arm_carries_the_table_verdict_to_the_exit(script_text: str) -> None:
    """The table's exit code only means anything if it reaches the script's
    final ``exit "${rc:-0}"``. Captured directly it would abort under ``set -e``
    BEFORE the after-snapshot and ``gpu-after-test.txt`` are written -- and
    ``|| true``, the other obvious shorthand, would throw the verdict away,
    which is the bug being fixed. So the step captures it into ``rc`` the way
    the parity arm already does, and this pins that the capture is inside
    ``run_stages``.

    Read through ``_code``: the window is anchored on the FIRST mention of
    ``cosine_table.py``, so an explanatory comment about a nearby guard that
    happens to contain ``|| true`` would otherwise land in ``tail`` and read as
    a swallowed verdict -- a false red for code that is correct."""
    script_text = _code(script_text)
    stages = script_text[script_text.index("run_stages() {") :]
    stages = stages[: stages.index("\n}\n")]
    at = stages.index("cosine_table.py")
    tail = stages[at:]
    assert re.search(r"^  rc=\$\?$", tail, re.M), (
        "the table's exit code must be captured into rc so it survives to the "
        "final exit; a bare call would abort under set -e before teardown"
    )
    assert "|| true" not in tail, "swallowing the table's status is the bug itself"


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


# ---------------------------------------------------------------------------
# Ruling 180: stage independence, a plan timeout the exporter honours, and a
# witness that distinguishes "the build is slow" from "the GPU is contended".
# ---------------------------------------------------------------------------


def test_the_stage_probe_runs_after_fp32_and_before_fp16(script_text: str) -> None:
    """The ruling-180 cure, and the exact failure the owner's maui run showed.

    ``run_stages`` compiles FP32, copies its plan, compiles FP16, copies that,
    THEN probes stages 3 and 4 -- under ``set -euo pipefail``. When the FP16
    compile timed out at 600 s the whole function aborted on that line, so the
    FP32 plan -- already built, 130.9 s, a good plan -- was NEVER probed. That
    is precisely the question ruling 157 exists to answer ("separates 'the plan
    is wrong' from 'FP16 is not enough'"), lost to shell ordering rather than to
    a model defect. The probe is already fault-tolerant (a stage that raises
    leaves its JSON absent and the table reports ``unknown``, never a false
    green); the bug lives one frame up, in the shell.

    So: an FP32 probe must sit between the two compiles, not after both. The
    stages arm still compiles BOTH precisions (the existing
    test_stages_mode_still_compiles_both_precisions is the control that this
    reordering does not drop the FP16 leg) -- what moves is stage 3's probe.

    Read the FUNCTION body: the stages arm only calls ``run_stages``, so an
    assertion against the arm would pass on the call and never see the order.
    """
    body = _fn_body(script_text, "run_stages")
    fp32 = body.index("compile_plan fp32")
    fp16 = body.index("compile_plan fp16")
    assert fp32 < fp16, "stages mode must still build FP32 first (ruling 159)"

    probe_calls = [m.start() for m in re.finditer(r"stage_probe\.py\s+\S*work\s+\S", body)]
    assert probe_calls, "run_stages lost its stage probe entirely"
    # A probe whose stage list covers "3" must run in the window between the two
    # compiles. Match the actual argv (``... /work 3`` or ``... /work 3,4``), not
    # the substring "3", which the copy targets (model-fp32.plan) also contain.
    window_probes = [
        p
        for p in probe_calls
        if fp32 < p < fp16 and re.search(r"/work\s+3(?:,4)?\b", body[p : p + 80])
    ]
    assert window_probes, (
        "stage 3 is probed only AFTER the FP16 compile, so an FP16 timeout still "
        "loses the FP32 measurement (the ruling-180 defect, unfixed)"
    )


def test_a_failed_stage_build_leaves_the_other_stage_measured(script_text: str) -> None:
    """Ruling 180 item 1, second clause: "a failed build leaves that stage
    ``unknown`` instead of ending the run."

    The runner runs under ``set -euo pipefail`` (pinned for the whole script by
    test_runner_syntax_is_valid's ``bash -n``, and the mode dispatch relies on
    it elsewhere), which is exactly why the FP16 timeout killed the run -- an
    unguarded ``compile_plan`` aborts the function on a non-zero exit. Each
    stage's build therefore needs its own ``|| true``-style containment so a
    failed compile leaves its plan absent and the cosine table prints
    ``unknown`` for that stage while the other precision still gets probed.

    Positive form (not just "``|| true`` appears somewhere", which the existing
    probe calls already satisfy): both ``compile_plan`` invocations inside
    run_stages are contained, AND each plan copy is chained to its OWN build's
    success (``compile_plan fpX && cp ... || true``). The AND-chain is not
    decoration -- it is what keeps this cure from creating a worse bug. Both
    compiles write the same cache path (``/out/reid/1/model.plan``), so a copy
    taken after an UNSUCCESSFUL build can only capture the other precision. The
    shape it actually guards: a build refused before it starts leaves the path
    holding FP32's bytes (``export_reid.py`` deliberately does not unlink there,
    because the path may be a plan a live gateway is serving), and an
    unconditional ``cp`` would copy those FP32 bytes into ``model-fp16.plan``
    and have stage 4 measure FP32 while reporting
    it as FP16 -- the wrong-plan swap
    test_stage_plan_never_falls_back_to_the_cache_plan exists to prevent,
    re-entering through the copy instead of the fallback. Containment with a
    conditional copy instead leaves the missing precision's file absent, its
    stage refuses (by that pin), and the cosine table prints ``unknown``:
    ruling 180's exact required state.
    """
    body = _fn_body(_code(script_text), "run_stages")
    lines = body.splitlines()

    compile_lines = [ln for ln in lines if "compile_plan " in ln]
    assert len(compile_lines) == 2, (
        f"expected the two stage compiles (fp32, fp16), found {len(compile_lines)}"
    )
    for ln in compile_lines:
        assert "&& cp " in ln and "|| true" in ln, (
            f"stage build is not contained-and-conditional: {ln!r} — an unguarded "
            "compile_plan aborts run_stages under set -euo pipefail (how stage 3 "
            "was lost on maui), and an un-chained cp after a contained failure "
            "copies the PREVIOUS precision's bytes"
        )
    for prec in ("model-fp32.plan", "model-fp16.plan"):
        assert any(prec in ln for ln in compile_lines), (
            f"{prec} is not copied on the same line as its own compile, so the "
            "copy is not conditional on that build succeeding"
        )


def test_each_plan_build_logs_wall_time_and_compute_apps(script_text: str) -> None:
    """Ruling 180 item 3: log wall time and ``nvidia-smi
    --query-compute-apps=pid,process_name,used_memory --format=csv`` into $RUN
    before each plan build.

    The owner's run recorded "GPU 0 at 100% throughout" -- which distinguishes a
    slow build from a *contended* GPU only if the other tenants' processes are
    captured at that moment. `gpu-before.txt` is a one-shot snapshot of memory
    taken before the build even starts and names no PID, so it cannot answer
    "was someone else on this GPU during the 600 s?". The per-build witness
    closes that.

    Pinned where it must live (inside ``compile_plan``, the single wrapper both
    modes use, so the parity arm gets it too) and on the exact query string,
    because a ``--query-gpu`` memory line is already there and would make a lazy
    fix look satisfied: the required flag is ``--query-compute-apps`` with
    ``process_name``, which no other line in the runner emits.
    """
    body = _fn_body(script_text, "compile_plan")
    assert "--query-compute-apps=pid,process_name,used_memory" in body, (
        "compile_plan must snapshot compute apps (PID + name + memory) around "
        "each build; --query-gpu memory alone cannot name a co-tenant (ruling 180)"
    )
    assert "--format=csv" in body, "keep the query machine-readable like the other snapshots"
    # It is logged INTO the run directory, not just printed to the build log.
    assert re.search(r'\$RUN/[^"]*compute-apps', body) or re.search(
        r'> *"\$RUN/[^"]*compute-apps', body
    ), "the compute-apps snapshot belongs in $RUN, where the operator can read it after the run"
    # Wall time: the timing must be captured (date/SECONDS/timestamp), not inferred
    # from trtexec's own output, which a timed-out build never gets to print.
    assert re.search(r"\bdate\b|SECONDS|time (?:-\+)?%|ts=", body), (
        "compile_plan must stamp wall time around the build; a build killed by the "
        "timeout prints no duration of its own (ruling 180 item 3)"
    )


def test_a_dead_gateway_cannot_stop_the_table_from_printing(script_text: str) -> None:
    """Ruling 180's required state -- "a failed build leaves that stage
    ``unknown`` instead of ending the run" -- has a third leg the first two pins
    miss, and it is the one the owner's rerun will actually hit.

    Stage 5 serves ``$RUN/cache/reid/1/model.plan``, the path BOTH compiles
    write. When the FP16 build dies it unlinks its own half-written engine
    (``export_reid.py:828``), and the FP32 build overwrote that same path first
    -- so the cache holds NO plan. ``start_gateway`` then polls
    ``models.reid`` for 300 s, never sees it healthy, and ``return 1``s. In
    stages mode that call is BARE, inside ``run_stages``, under ``set -euo
    pipefail`` -- so it aborts the function two lines before
    ``cosine_table.py``. The result is the maui failure reproduced by a
    different line: stage 3's JSON sits on disk and the owner gets no printed
    table and no ``RESULT`` line again.

    So the containment ruling 180 asks for has to cover the gateway leg too.
    ``start_gateway || true`` is the honest shape, not a suppression: stage 5's
    own HTTP call is already ``|| true`` and a stage with no vectors prints
    ``unknown``, which makes the table exit 2 -- an incomplete diagnostic still
    cannot post as a clean run, which is what finding 3 was for. Serving the
    FP32 plan instead would be the wrong-plan swap
    test_stage_plan_never_falls_back_to_the_cache_plan refuses, in the reporting
    layer rather than the probe.

    Two-sided on purpose: the parity arm's calls stay BARE (ruling 159's
    fail-fast -- parity has nothing to report if the gateway is down, and a
    blanket guard there would turn a hard failure into a silent one), and the
    table must sit AFTER the gateway leg in the body, since a guard placed
    below the print would fix nothing.
    """
    code = _code(script_text)
    body = _fn_body(code, "run_stages")
    gw = [ln for ln in body.splitlines() if "start_gateway" in ln]
    assert gw, "run_stages lost its gateway leg entirely"
    assert all("|| true" in ln for ln in gw), (
        f"stages-mode gateway leg is bare: {gw} — when the FP16 build fails the "
        "cache has no plan, start_gateway returns 1, and set -e aborts run_stages "
        "before cosine_table.py, so stage 3 is measured and never printed (the "
        "ruling-180 defect, relocated rather than fixed)"
    )
    table = body.index("cosine_table.py")
    assert table > body.index("start_gateway"), (
        "the cosine table must be printed after the gateway leg so a contained "
        "gateway failure still reaches it"
    )
    parity = _arm(code, "parity")
    bare = [ln for ln in parity.splitlines() if "start_gateway" in ln]
    assert bare and all("|| true" not in ln for ln in bare), (
        "the parity arm's gateway calls must stay fatal (ruling 159) — guarding "
        "them here would hide a bring-up failure behind a green-looking run"
    )


def test_the_runner_exposes_a_plan_timeout_with_the_600_default(script_text: str) -> None:
    """Ruling 180 item 2, shell side: ``--plan-timeout`` is an accepted argument
    whose DEFAULT stays 600 (the owner ruled "the time limit stays tight on
    purpose -- the same FP16 command built in 137.7 s on 10-13"), and whose
    value is actually forwarded to the exporter, not just parsed.

    Three separate failure modes, three assertions: a flag that parses into a
    variable but is never passed into ``compile_plan``'s container; a variable
    whose default drifted off 600 (silently widening the bound the owner wants
    tight); and a flag that reaches the podman argv but not the ``--plan-timeout``
    argument export_reid reads (see the exporter-side pins for the Python hops).
    """
    assert re.search(r"--plan-timeout\)", script_text), (
        "--plan-timeout is not an accepted argument (the arg parser rejects it)"
    )
    default = re.search(r'^PLAN_TIMEOUT="?([0-9]+)"?$', script_text, re.M)
    assert default is not None, "PLAN_TIMEOUT is not initialized at top level"
    assert default.group(1) == "600", (
        f"--plan-timeout default drifted to {default.group(1)}s; ruling 180 keeps 600"
    )
    body = _fn_body(script_text, "compile_plan")
    assert "--plan-timeout" in body and "$PLAN_TIMEOUT" in body, (
        "compile_plan builds the container argv without forwarding --plan-timeout "
        "$PLAN_TIMEOUT, so the flag exists and does nothing on the run that needs it"
    )


# ---------------------------------------------------------------------------
# [r312a] (ruling 312): the Triton image as a parameter, the layer-compare
# mode, and the onnxruntime-backend GPU probe. CPU-only pins on the same
# machine-readable surfaces the pins above use: the runner's own argv parse,
# its embedded programs (extracted by _heredoc, executed where they are
# stdlib-only), and the bodies of the functions the modes dispatch to.
# ---------------------------------------------------------------------------


def test_the_runner_accepts_a_triton_image_and_threads_it_to_the_build(script_text: str) -> None:
    """[r312a] box 2: "The runner takes the Triton image as a parameter."
    [r312b] made the base image an ARG (``TRITON_IMAGE``,
    ai/gateway/Dockerfile:1) so a venue can pin it by digest without a fork;
    the runner reaches that ARG with ``--build-arg`` on the ONE build line.

    Default stays EMPTY, not a restated tag: the Dockerfile's own default
    (`26.09-py3`) is the single place the current release lives, and a runner
    default that restates it goes stale exactly when the image moves — the
    drift the version-consistency gate exists for. Empty means the flag is
    OMITTED (``${TRITON_IMAGE:+...}``), so today's behaviour is unchanged and
    the two operator runs pass the image explicitly (26.01-py3, then the
    latest supported release).

    The build line is pinned inside STEP 1's own statement, not the whole
    file: the module has exactly one ``podman build`` and a second one would
    be a different image contract."""
    assert "--triton-image)" in script_text, (
        "--triton-image is not an accepted argument (the arg parser rejects it)"
    )
    init = re.search(r'^TRITON_IMAGE="\$\{REID_TIER_TRITON_IMAGE:-\}"$', script_text, re.M)
    assert init is not None, (
        "TRITON_IMAGE must default to empty via REID_TIER_TRITON_IMAGE — a "
        "restated tag here goes stale when the Dockerfile's own default moves"
    )
    build = script_text[script_text.index("podman build") :]
    build = build[: build.index("\n")]
    assert '--build-arg TRITON_IMAGE="$TRITON_IMAGE"' in build, (
        "the build never threads the image parameter through: the operator's "
        "26.01-py3 run would silently build the Dockerfile's default release"
    )
    assert "${TRITON_IMAGE:+" in build, (
        "an empty --triton-image must OMIT the build-arg, not pass an empty "
        "value that overrides the Dockerfile's own default"
    )


def test_layercompare_mode_is_accepted_and_dispatched(script_text: str) -> None:
    """[r312a] box 1: the runner "gains a layer-compare mode". Three surfaces:
    the --mode validator accepts it, the case dispatch has its arm, and the
    arm runs the stages sequence first (box 2: on the latest release the run
    produces "the stage table and the layer compare" — the layer compare is a
    superset, not a replacement, or the second operator run would lose the
    stage table the Done-when quotes)."""
    assert (
        "--mode is parity or stages" not in script_text
        or re.search(r"layercompare", script_text[script_text.index("--mode is") :][:200])
        or _code(script_text).count("layercompare") >= 1
    ), "mode validator never mentions layercompare"
    validator = [ln for ln in _code(script_text).splitlines() if "--mode is" in ln]
    assert validator and any("layercompare" in ln for ln in validator), (
        "the --mode validation line refuses layercompare: the operator's run "
        "dies at argument validation before any measurement"
    )
    arm = _arm(script_text, "layercompare")
    # The arm routes to run_layercompare; the stages sequence lives in that
    # function (the runner's structure: every mode's full sequence is its one
    # mode function -- run_parity, run_stages, run_layercompare). Follow the
    # route and read the sequence there: a pin that read only the arm would
    # pin a call-graph shape, not the behaviour.
    assert "run_layercompare" in arm, "the layercompare arm never dispatches"
    seq_body = _fn_body(_code(script_text), "run_layercompare")
    assert "run_stages" in seq_body, (
        "the layercompare sequence must run the stages sequence (the stage "
        "table is part of box 2's second run), not only the layer compare"
    )


def _lc_body(script_text: str) -> str:
    """Body of ``run_layercompare()``, the layer-compare mode's own block."""
    return _fn_body(script_text, "run_layercompare")


def test_layercompare_never_rewrites_the_cache_onnx(script_text: str) -> None:
    """[r312a] box 1 runs the DECOMPOSED onnx ("Polygraphy runs the decomposed
    ONNX") but the decomposer rewrites its target IN PLACE (scripts/
    decompose_instance_norm.py ``tmp.replace(model)``). The cache's model.onnx
    is the artifact the stage table's stage 2 measures and the one the two
    operator runs must share: rewrite it inside the layer-compare and stage 2
    of the SAME run measures a different graph than 188.17/188.18 did, and the
    run's own stage rows stop being comparable to the history they quote. So
    the compare must stage its own COPY under the run dir and decompose that.

    Read through _code: the module's docs name model.onnx in prose, so a raw
    substring needle would satisfy itself on a comment."""
    body = _lc_body(_code(script_text))
    assert "layercompare/" in body and "cp " in body, (
        "run_layercompare must copy the export into its own directory "
        "(layercompare/) before the decomposer rewrites it — the module's "
        "surgery is in-place, and the cache ONNX is what the stage table "
        "measures"
    )
    mounts = [spec for _, spec in _bind_mounts(body)]
    # The decomposer's own podman line, read statement-first: the invocation
    # that names the module is the one whose mounts this pin audits.
    dec_line = next(ln for ln in body.splitlines() if "decompose_instance_norm" in ln)
    dec_block = body[body.index(dec_line) - 400 : body.index(dec_line)]
    dec_mounts = [spec for _, spec in _bind_mounts(dec_block)]
    assert dec_mounts, "the decomposer call carries no bind mount: nothing was staged"
    for spec in dec_mounts:
        if spec.endswith(":ro"):
            continue  # a read-only mount cannot receive the rewrite
        assert "layercompare" in spec, (
            f"the decomposer mounts {spec} writable: the in-place rewrite would "
            "land on the cache ONNX the stage table measures (comparability loss)"
        )


def test_layercompare_uses_the_repo_decomposer_not_a_reimplementation(script_text: str) -> None:
    """The decompose rewrite's exit codes (0/30/31/32), its aliasing guards and
    its faithfulness gate live in scripts/decompose_instance_norm.py and are
    already CI-pinned there. A layer-compare arm that reimplements the rewrite
    would ship a second, unpinned decomposer into the very measurement that
    must inherit the first one's guarantees — so the runner must invoke the
    module (python3 -m or by path) and branch on ITS exit code: 0 continues,
    30/31/32 stop the compare (a graph that moved its own function, refused
    structurally, or still needs its sidecar has no faithful layer table to
    print), and the refusing numbers must not be folded into a success."""
    body = _lc_body(_code(script_text))
    assert "decompose_instance_norm" in body, (
        "run_layercompare never invokes scripts/decompose_instance_norm.py: "
        "the decomposition the box-1 text assumes would be reimplemented here"
    )
    assert re.search(r"decompose.*\|\| true|decompose.*rc=|rc=\$\?\n.*decompose", body) or (
        "|| rc=$?" in body or re.search(r"decompose[^\n]*\n\s*rc=", body)
    ), "the decomposer's exit code is neither captured nor branched on"
    # The mapped refusals stop the compare: folded into success, a graph whose
    # rewrite moved its own function would print a layer table nobody can trust.
    for code in ("30", "31", "32"):
        assert re.search(rf"rc -eq {code}|\b{code}\b", body), (
            f"decompose's exit {code} is not named: the refusing codes must stop "
            "the compare, not be read as a faithful decomposition"
        )


def test_the_layer_compare_marks_every_layer_and_prints_the_first_diverging_one(
    script_text: str,
) -> None:
    """[r312a] box 1's deliverable, verbatim-shaped: "with every layer's output
    marked, on the same 36 crops, and prints the first layer under 0.999 cosine
    with its op type and name."

    Polygraphy is named in the box text but exists NOWHERE in the image (the
    gateway installs onnx/onnxscript/onnxruntime-gpu/torch; Dockerfile:32-46)
    or the repo — only this box names it — and the probe container runs
    --network none, so pip cannot fetch it at run time. The marked-layer
    compare is therefore implemented from what the image has: the same onnx
    graph rewrite every layer's output tensor as a graph output (the marking
    decompose_instance_norm.py already proves feasible in-repo), run under ORT
    CPU vs the TensorRT plan via the engine's per-tensor debug API. The
    substitution is named in the PR body for the UR-89 review to judge.

    The program is CPU-only HERE (this test), like cosine_table.py: its
    PARSING/REPORTING half runs on plain python3 against fixture layer JSONs,
    so the pin executes the shipped code."""
    probe = _heredoc(script_text, "layer_compare.py", "LAYERCMP")
    # The marking: the program walks the ONNX graph and adds intermediate
    # tensors as outputs (clear_output + graph outputs), not a fixed list.
    assert "clear_output" in probe or "graph.output" in probe, (
        "the layer compare never marks intermediate outputs: 'every layer's "
        "output marked' is the box-1 deliverable"
    )
    # Same 36 crops: the batch is built from the run's crops dir, the same
    # sort/suffix order the stage probe uses — the cosine table's
    # crop-order guard depends on it.
    assert 'RUN / "crops"' in probe or 'run / "crops"' in probe, (
        "the layer compare must build its batch from the run's own crops "
        "(same crops as the stage table) — the box names 'the same 36 crops'"
    )
    # Word-boundary on the op type: 'INCONCLUSIVE' contains the substring
    # 'IN', so a bare-substring negative would fire on the report's own
    # wording. The op type is a whole token.
    assert "InstanceNormalization" in probe or not re.search(r"\bIN\b", probe), (
        "the marked graph is the DECOMPOSED one (box 1: 'runs the decomposed "
        "ONNX'); the program must not re-measure the raw IN graph"
    )
    # The deliverable print: first layer under the gate, WITH op type and name.
    gate = re.search(r"GATE\s*=\s*0\.999", probe)
    assert gate, "the layer compare's gate is not the ruling-68 0.999"
    tail = probe[probe.index("GATE") :]
    assert "op_type" in tail and re.search(r"first|FIRST", tail), (
        "the report must name the FIRST layer under 0.999 with its op type "
        "and name (box 1's exact deliverable)"
    )


def _run_layer_report(report_src: str, tmp_path: Path, rows: list[dict]) -> tuple[int, str]:
    """Run the shipped layer-compare report over synthetic per-layer cosine
    rows and return (rc, output). The rows are what the in-image measure half
    emits; the report half — the box-1 deliverable — is the part that must be
    CPU-testable, exactly as cosine_table.py is."""
    run = tmp_path / "run"
    run.mkdir(exist_ok=True)  # two calls per test: broken rows, then clean
    (run / "layers.json").write_text(json.dumps(rows))
    script = tmp_path / "layer_report.py"
    script.write_text(report_src)
    done = subprocess.run(  # real: the shipped report IS the test  # noqa: S603 - fixed argv
        [sys.executable, "-I", str(script), str(run)],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


def test_the_layer_report_executes_and_names_first_diverging_layer(
    script_text: str, tmp_path: Path
) -> None:
    """Positive execution control for the report half: given measured rows with
    one layer under the gate, the shipped report exits 0 (naming a divergence
    IS this mode succeeding, same shape as a located stage failure) and prints
    that layer's index, op type and name. Given all layers at or above the
    gate, it prints the clean reading — the OTHER Done-when outcome ('reading
    every plan stage at or above 0.999' at layer granularity)."""
    probe = _heredoc(script_text, "layer_compare.py", "LAYERCMP")
    assert 'if __name__ == "__main__"' in probe or "__main__" in probe, (
        "the report half is not an executable entry point"
    )
    rows = [
        {"index": i, "name": f"n{i}", "op_type": "Conv", "min_cos": 0.9999, "mean_cos": 0.99995}
        for i in range(3)
    ]
    broken = dict(rows[1], min_cos=0.987, op_type="ReduceMean", name="mean_in1_1")
    rc, out = _run_layer_report(probe, tmp_path, [*rows[:1], broken, *rows[2:]])
    assert str(1) in out and ("ReduceMean" in out or "mean_in1_1" in out), (
        f"the report did not name the first diverging layer with its op/name:\n{out}"
    )
    assert rc == 0, f"naming a divergence is a successful diagnostic, got rc {rc}:\n{out}"
    clean = [
        {"index": i, "name": f"n{i}", "op_type": "Conv", "min_cos": 0.9999, "mean_cos": 0.99995}
        for i in range(4)
    ]
    rc2, out2 = _run_layer_report(probe, tmp_path, clean)
    assert rc2 == 0 and "ReduceMean" not in out2, f"clean rows misreported:\n{out2}"


def test_the_layer_compare_runs_only_after_the_fp32_plan_is_measured(script_text: str) -> None:
    """Ordering: the layer compare measures the FP32 plan (box 1), which exists
    only after run_stages' STEP S3a copied model-fp32.plan. The compare must
    sit AFTER that copy in the layercompare arm — before it, the compare would
    refuse (stage_plan's own no-fallback refusal, now at layer granularity) or
    silently measure nothing."""
    body = _lc_body(_code(script_text))
    fp32 = body.index("model-fp32.plan")
    lc = body.index("layer_compare.py")
    assert fp32 < lc, "the layer compare runs before the FP32 plan it measures exists"


def _marking_half_src(probe: str) -> str:
    """The shipped measure()'s MARKING half, verbatim: from ``graph =
    model.graph`` (the clear-output + re-add walk) through the full
    ``onnx.save(marked, ...)`` (the end anchor is the measure half's ORT load,
    the line after the save). A closed fragment: its only free names are
    ``model``, ``LC`` and ``onnx``, the locals the executor binds. The slice
    keeps the function's own indentation and is dedented before compile so
    `compile` sees statements, not an IndentationError."""
    from textwrap import dedent

    return dedent(
        probe[
            probe.index("    graph = model.graph") : probe.index("    sess = ort.InferenceSession")
        ]
    )


def _exec_marking_half(probe: str, tmp_path: Path, model: object) -> Path:
    """Execute the marking half against a caller-built ONNX model -- the
    shipped code runs, not a reimplementation. Returns the path of the
    ``marked.onnx`` the fragment itself saves into ``LC``."""
    src = _marking_half_src(probe)
    ns: dict[str, object] = {
        "model": model,
        "LC": tmp_path,
        "onnx": pytest.importorskip("onnx"),
    }
    exec(compile(src, "<marking-half>", "exec"), ns)  # noqa: S102 nosemgrep: dangerous-eval - the shipped code IS the test
    marked_path = tmp_path / "marked.onnx"
    assert marked_path.is_file(), "the marking half never wrote marked.onnx"
    return marked_path


def _TINY_MODEL() -> object:
    """A small real ONNX graph: x -> Conv(x, W1) -> Conv(c1, W2) -> y. Its
    exporter populates value_info for the intermediate tensor c1, the shape the
    marking walk needs typed."""
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper, numpy_helper

    def _conv(name: str, x: str, w: str, y: str):
        return helper.make_node("Conv", [x, w], [y], name=name)

    graph = helper.make_graph(
        [_conv("conv1", "x", "W1", "c1"), _conv("conv2", "c1", "W2", "y")],
        "tiny-reid",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3, 8, 8])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 2, 8, 8])],
        [
            numpy_helper.from_array(np.ones((2, 3, 3, 3), dtype=np.float32), "W1"),
            numpy_helper.from_array(np.ones((2, 2, 3, 3), dtype=np.float32), "W2"),
        ],
        value_info=[
            helper.make_tensor_value_info("c1", TensorProto.FLOAT, [1, 2, 8, 8]),
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 9
    onnx.checker.check_model(model)
    return model


def test_the_marking_half_types_every_output_and_ort_loads_it(
    script_text: str, tmp_path: Path
) -> None:
    """The pre-fix bug: the marking walk appended ValueInfoProtos carrying a
    NAME and NO TYPE -- onnx.checker rejects the graph ("Field 'type' of
    'value_info' is required but missing"), so the marked measure would die in
    the image at operator time, inside a '|| true'-contained leg (the layer
    report would print INCONCLUSIVE forever, no one knows why). The pin
    EXECUTES the shipped marking half against a small real graph: every marked
    output must come out FULLY typed (copied from the exporter's own
    value_info, shape inference as the fallback), and the saved marked graph
    must load in ORT CPU with all its outputs -- the load the measure half
    immediately performs."""
    onnx = pytest.importorskip("onnx")
    ort = pytest.importorskip("onnxruntime")
    probe = _heredoc(script_text, "layer_compare.py", "LAYERCMP")
    marked_path = _exec_marking_half(probe, tmp_path, _TINY_MODEL())
    marked = onnx.load(str(marked_path))
    onnx.checker.check_model(marked)  # the pre-fix graph fails exactly here
    marked_names = [o.name for o in marked.graph.output if o.name != "y"]
    assert marked_names, "nothing was marked"
    for o in marked.graph.output:
        assert o.HasField("type") and o.type.tensor_type.elem_type != 0, (
            f"output {o.name!r} carries no type -- the graph onnx.checker "
            "rejects (the pre-fix bug, unfixed)"
        )
    sess = ort.InferenceSession(str(marked_path), providers=["CPUExecutionProvider"])
    got = {o.name for o in sess.get_outputs()}
    assert {"y", *marked_names} <= got, (
        f"the marked graph must load with ALL its outputs; ORT offered {got}"
    )


def test_the_marking_half_refuses_an_untypeable_tensor(script_text: str, tmp_path: Path) -> None:
    """The negative arm: a tensor neither value_info nor shape inference can
    type must fail the measure LOUDLY (SystemExit naming the tensor), not ship
    a nameless-typed output that dies later in ORT with an unattributable
    error. A custom-domain op gives it honestly: the exporter of a graph with
    an op outside the standard domain records no value_info for its output and
    onnx's own infer_shapes cannot type what it does not know -- exactly the
    untypeable tensor a future exporter change could leave behind."""
    onnx = pytest.importorskip("onnx")
    probe = _heredoc(script_text, "layer_compare.py", "LAYERCMP")
    try:
        _exec_marking_half(probe, tmp_path, _TINY_MODEL_CUSTOM_OP())
    except SystemExit as exc:
        assert "no type" in str(exc), f"refused for the wrong reason: {exc}"
        assert "c2" in str(exc), f"the refusal must name the untypeable tensor: {exc}"
    else:
        raise AssertionError(
            "the marking half typed an untypeable tensor -- the loud failure "
            "(finding 5's refusal) is unfixed"
        )


def _TINY_MODEL_CUSTOM_OP() -> object:
    """A graph with an op outside the standard domain: its output carries no
    value_info (the exporter cannot know the shape of an op it does not
    define) and onnx.shape_inference types nothing for an unknown domain --
    the marking walk's two type sources both come up empty."""
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper

    graph = helper.make_graph(
        [
            helper.make_node("MyOp", ["x2"], ["c2"], domain="com.test"),
            helper.make_node("Identity", ["c2"], ["y2"]),
        ],
        "tiny-custom-op",
        [helper.make_tensor_value_info("x2", TensorProto.FLOAT, [1, 3])],
        [helper.make_tensor_value_info("y2", TensorProto.FLOAT, [1, 3])],
        [],
        value_info=[],
    )
    model = helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", 17), helper.make_opsetid("com.test", 1)],
    )
    model.ir_version = 9
    return model


def test_the_ort_probe_is_a_dedicated_container_on_its_own_repo(script_text: str) -> None:
    """[r312a] box 2: "it adds a stage serving the ONNX through Triton's
    onnxruntime backend on the GPU (CUDA execution provider), as a probe
    only."

    Why a dedicated container: the served repository is baked into the image
    and entrypoint.sh §0c only links cache dirs whose REPO config already
    exists, while §0d's residency prune MOVES every non-set model to
    .retired (GATEWAY_MODEL_SET=vlm) — an ORT-backend reid cannot appear in
    the served repository without editing ai/triton (cell A's files, UR-9) or
    re-pruning the served footprint. A probe needs none of that: its own
    model-repository directory under $RUN, its own tritonserver invocation.

    "as a probe only" is pinned as its negative too: the probe writes no
    config into the served cache/repository and its model name is its own
    (reid-ort), so nothing can collide with the served reid."""
    body = _lc_body(_code(script_text))
    assert "reid-ort" in body, "the probe model must carry its own name, not collide with reid"
    assert "--model-repository" in body, "the probe never points tritonserver at a repository"
    assert "$RUN" in body, "the probe's repository must live under the run directory"
    for tok in ("entrypoint.sh", "GATEWAY_MODEL_SET"):
        assert tok not in body, (
            f"the probe must not reuse the gateway entrypoint ({tok}): §0d's "
            "residency prune and §0c's link precondition belong to the served "
            "repository, not a probe"
        )
    mounts = _bind_mounts(body)
    assert any("/models/repository" in spec for _, spec in mounts), (
        "no probe container mounts anything that could rewrite the SERVED "
        "repository — 'as a probe only' means the served footprint is untouched"
    )


def test_the_ort_probe_declares_the_cuda_execution_provider(script_text: str) -> None:
    """The box names the mechanism: Triton's onnxruntime backend ON THE GPU
    "(CUDA execution provider)". yolo26/config.pbtxt:14 is the in-repo
    precedent for backend "onnxruntime"; the probe's config must declare the
    same backend and KIND_GPU, and the ONNX it serves must be the
    layer-compare's decomposed one — the raw export's InstanceNormalization
    nodes are the graph ORT's builder chokes on in the first place."""
    body = _lc_body(_code(script_text))
    cfg = body[body.index("config.pbtxt") :]
    cfg = cfg[: cfg.index("\n", cfg.index("backend"))]
    assert 'backend: "onnxruntime"' in cfg, (
        "the probe config is not the onnxruntime backend — the box's whole "
        "point is serving the ONNX through Triton's ORT backend"
    )
    assert "KIND_GPU" in body, "the probe must run on the GPU (KIND_GPU), not CPU"
    assert "decomp" in body or "layercompare" in body, (
        "the probe must serve the DECOMPOSED onnx (the layer-compare's own "
        "copy), not the raw export"
    )


def test_the_ort_probe_fetches_embeddings_and_the_stage_table_reads_them(script_text: str) -> None:
    """A stage that serves and is never read is decoration; the box says "adds
    a STAGE" — a measured leg. The probe runs its own container whose HTTP
    port is NOT published to the host (the same topology as the served
    Triton's 8000), so the embeddings are fetched from the HOST (podman exec,
    where podman lives) over the same crop set, and the cosine table's stage
    list gains that leg. The fetch is dispatched by run_stages when the
    layercompare arm armed the probe (stage6-armed), so the pin reads the
    dispatch, not just the arm."""
    fetch = _heredoc(script_text, "stage6_host.py", "PY6")
    # The fetch's argv is a list of separate literals -- ["podman", "exec", ...]
    # -- so the joined phrase never appears; anchor on the argv elements as
    # code (the morphology a prose mention cannot fake).
    assert '"podman"' in fetch and '"exec"' in fetch and "-i" in fetch, (
        "the probe's port is not published to the host; the embeddings must be "
        "fetched from inside the container (podman exec) -- host-side, where "
        "podman lives"
    )
    body = _fn_body(_code(script_text), "run_stages")
    assert "stage6_host.py" in body, (
        "run_stages never dispatches the stage-6 fetch: the probe would serve "
        "embeddings nothing measures"
    )
    table = _heredoc(script_text, "cosine_table.py", "TABLE")
    assert '"6"' in table or "'6'" in table, (
        "the cosine table never reads the ORT probe's stage leg: the probe "
        "would serve embeddings nothing measures"
    )


def test_the_ort_probe_fetch_program_parses_and_serves_what_it_reads(script_text: str) -> None:
    """The stage-6 fetch runs HOST-side (write_stage6_host -> stage6_host.py):
    the stage-probe container has no podman inside it (--network none) and the
    probe's port is not published, so only the runner process can `podman exec`
    into the probe. The fetch's inner infer program is a STRING literal in that
    host file (python -c), so a fetch whose inner text has a syntax error, a
    missing import or a non-JSON-shaped request body would be invisible to every
    committed check and die only at operator time, inside the '|| true'-contained
    leg (stage 6 then reads unknown forever, no one knows why). So the pin:

    - parses the HOST program (it must be real python, not prose),
    - parses the `inner` string, and keeps it PURE: the probe container mounts
      ONLY the model repo, so its rows arrive on stdin and its embeddings leave
      on stdout -- no /work path reference (that file simply is not in there),
    - keeps the HOST program stdlib-only (it runs `python3 -I` on the GPU host,
      like stage 5 and the table: no numpy guarantee there),
    - and pins the rows' PROVENANCE: batch.json (names + FLAT row-major rows) is
      written by the SAME in-image batch build that writes batch.npy, so the
      fetch's crops/order/transform cannot drift from what the decomposer's
      faithfulness gate ate."""
    probe = _heredoc(script_text, "stage_probe.py", "PROBE")
    ast.parse(probe)  # the probe itself is real python
    assert "stage_ort_probe" not in probe, (
        "the in-container fetch is gone: the stage-probe container cannot exec "
        "into the probe (no podman, --network none) -- the fetch is host-side"
    )
    fetch = _heredoc(script_text, "stage6_host.py", "PY6")
    ast.parse(fetch)  # the host fetch program is real python
    imports = {
        n.names[0].name.split(".")[0] if isinstance(n, ast.Import) else n.module.split(".")[0]
        for n in ast.walk(ast.parse(fetch))
        if isinstance(n, ast.Import | ast.ImportFrom)
    }
    assert imports <= {"json", "subprocess", "sys"}, (
        f"stage6_host.py must be stdlib-only (it runs python3 -I on the GPU "
        f"host), found imports: {sorted(imports)}"
    )
    strings = {
        t.id: n.value.value
        for n in ast.walk(ast.parse(fetch))
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    inner = strings["inner"]
    ast.parse(inner)  # the fetch program itself is real python
    assert "/work" not in inner, (
        "the exec'd program reads/writes /work paths, but the probe container "
        "mounts only the model repository -- the files are not inside it"
    )
    assert "sys.stdin" in inner and "sys.stdout" in inner, (
        "the exec'd fetch must take its rows from stdin and write its "
        "embeddings to stdout: the container has no run-dir mount to read "
        "or write files through"
    )
    # The rows' provenance and shape: batch.json carries FLAT row-major rows
    # (Triton's HTTP infer protocol), written by the SAME batch build that
    # writes batch.npy.
    assert "batch.json" in fetch, (
        "the fetch must read the batch the in-image build wrote (batch.json), "
        "not re-derive it host-side (the host has no numpy)"
    )
    batch_prog = re.search(r"BATCH_PROG='(.*?)'", script_text, re.S)
    assert batch_prog, "the layercompare batch program is missing"
    assert ".reshape(-1).tolist()" in batch_prog.group(
        1
    ) or ".flatten().tolist()" in batch_prog.group(1), (
        "batch.json's rows must be FLAT row-major lists: a (3,256,128) row "
        "through .tolist() nests, and float()/Triton's JSON infer reject that shape"
    )
    assert "batch.json" in batch_prog.group(1) and "batch.npy" in batch_prog.group(1), (
        "batch.json must be written by the SAME program that writes batch.npy, "
        "or the fetch's crops/order can drift from the measured batch"
    )
    assert "podman" in fetch and "exec" in fetch, (
        "the host fetch reaches the probe with podman exec -- that is WHY it must run host-side"
    )


def test_the_probe_prelude_executes_and_builders_resolve(
    script_text: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The committed test that would have caught blocking 1: the probe died at
    IMPORT time (BUILDERS referenced stage_ort_probe defined below the dict),
    so every invocation raised before a single stage ran -- and no committed
    test EXECUTED the probe, which is why CI stayed green over it. The pins
    above are AST-parse-only, and ast.parse cannot see a NameError. Pin the
    module level for real: with sys.argv stubbed to a tmp run dir holding one
    tiny crop, everything before the STAGES loop executes -- the crop scan,
    the batch build, every def, and the BUILDERS dict's construction, where
    the forward reference lived. The loop itself stays out by seam honesty:
    stage 1/2 need torch and TensorRT engines (GPU legs), which CI cannot run
    truthfully."""
    np = pytest.importorskip("numpy")

    from PIL import Image

    probe = _heredoc(script_text, "stage_probe.py", "PROBE")
    tree = ast.parse(probe)
    prelude = ast.Module(body=[n for n in tree.body if not isinstance(n, ast.For)], type_ignores=[])
    src = ast.unparse(prelude)

    crops = tmp_path / "crops"
    crops.mkdir()
    # An 8x16 RGB PNG of mid-gray: the smallest image PIL reads that the
    # (3,256,128) resize accepts.
    img = Image.new("RGB", (8, 16), (128, 128, 128))
    img.save(crops / "crop-0001.png")
    assert (crops / "crop-0001.png").is_file() and np is not None

    monkeypatch.setattr(sys, "argv", ["stage_probe.py", str(tmp_path), "1,2"])
    ns: dict[str, object] = {"__name__": "stage_probe"}
    exec(compile(src, "<probe-prelude>", "exec"), ns)  # noqa: S102 nosemgrep: dangerous-eval - the shipped probe IS the test
    builders = ns["BUILDERS"]
    assert sorted(builders) == ["1", "2", "3", "4"], (
        f"BUILDERS must resolve to the four stage keys without a forward "
        f"reference (blocking 1's NameError lived here); got {sorted(builders)}"
    )
    assert (tmp_path / "crops" / "crop-0001.png").exists()


def test_the_ort_probe_stays_contained_and_never_blocks_the_table(script_text: str) -> None:
    """The probe is box 2's LAST clause, "as a probe only" — it must not be a
    hard dependency of the run the way the parity arm's gateway is. The
    ruling-180 shape applies one frame up: a probe container that fails to
    come up must leave its stage unknown (the table exits 2 — an incomplete
    diagnostic cannot post clean) rather than abort the layercompare arm under
    set -e before the layer report prints. The stage-6 leg that reads the
    probe is the HOST fetch dispatch (|| true-contained) and the layer report
    sits after it. And the probe container is REAPED at teardown like every
    other container the run owns (its own --rm only fires when the CONTAINER
    exits; a run killed between launch and teardown would otherwise leak it
    and fail the run with a confusing diff)."""
    body = _lc_body(_code(script_text))
    # The probe's own container lines (its name is on every podman line that
    # touches it) and the stage-6 readiness/teardown lines: each must carry
    # its own containment. The container LAUNCH is -d || true; the readiness
    # poll and the rm are inside the (not ready) branch, which returns 0; the
    # stage-6 leg itself is the host fetch call in run_stages, already
    # '|| true'-shaped (pinned below).
    lines = [ln for ln in body.splitlines() if "ortprobe" in ln and "podman" in ln]
    probe_lines = [ln for ln in body.splitlines() if "stage6-armed" in ln]
    # Containment is per STATEMENT, not per line: a multi-line podman
    # invocation carries '|| true' on its last line, and the exec poll sits
    # inside the readiness branch whose failure path returns 0 with the rm
    # itself contained. So group the physical lines into statements: a line
    # ending in \\ continues the previous one; a continuation chain is
    # contained iff its LAST line is.
    stmts: list[str] = []
    for ln in lines:
        if stmts and stmts[-1].rstrip().endswith("\\"):
            stmts[-1] = stmts[-1].rstrip() + " " + ln
        else:
            stmts.append(ln)
    bare = [s for s in stmts if "|| true" not in s and "podman exec" not in s]
    assert stmts and not bare, (
        f"every podman statement naming the probe must be contained; bare: {bare}"
    )
    assert probe_lines, "the stage-6 leg was never armed"
    # The host-side fetch dispatch carries its own containment too: a failed
    # fetch must leave stage-6.json absent (the table reads unknown) rather
    # than abort the arm before the layer report.
    fetch_lines = [
        ln
        for ln in _fn_body(_code(script_text), "run_stages").splitlines()
        if "stage6_host.py" in ln
    ]
    assert fetch_lines and fetch_lines[-1].rstrip().endswith("|| true"), (
        f"the stage-6 fetch dispatch is not contained: {fetch_lines}"
    )
    # The probe container is reaped at teardown alongside the gateway, not
    # only on the never-ready branch (finding 4).
    cleanup = _fn_body(script_text, "cleanup")
    assert "${CTR}-ortprobe" in cleanup and "rm -f" in cleanup, (
        "cleanup() never reaps the ORT-probe container: a run killed after the "
        "probe launches would leak it (its --rm only fires at container exit)"
    )
    report = body.index("layer_compare.py")
    for ln in lines + probe_lines:
        assert body.index(ln.strip()) < report, (
            f"{ln.strip()!r} sits after the layer report — the probe must not "
            "delay the box-1 deliverable"
        )
