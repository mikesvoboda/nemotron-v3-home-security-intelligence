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

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = PROJECT_ROOT / "scripts" / "uplevel" / "reid_real_tier.sh"


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
    ``run_stages``."""
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
    compiles write the same cache path (``/out/reid/1/model.plan``), so when the
    FP16 build fails, the cache still holds the FP32 plan's bytes; an
    unconditional ``cp`` after a contained-but-failed build would copy FP32
    bytes into ``model-fp16.plan`` and have stage 4 measure FP32 while reporting
    it as FP16 -- the wrong-plan swap
    test_stage_plan_never_falls_back_to_the_cache_plan exists to prevent,
    re-entering through the copy instead of the fallback. Containment with a
    conditional copy instead leaves the missing precision's file absent, its
    stage refuses (by that pin), and the cosine table prints ``unknown``:
    ruling 180's exact required state.
    """
    body = _fn_body(script_text, "run_stages")
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
