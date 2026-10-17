"""[osb-r252] pins for ``scripts/decompose_instance_norm.py`` (owner ruling 252).

Ruling 252's Done-when is "a CPU-only CI test pinning it", and this is that test: a fixture ONNX
graph with three ``InstanceNormalization`` nodes, the rewrite applied to it, and the ORIGINAL versus
DECOMPOSED graphs compared through onnxruntime on CPU. No GPU, no network, no operator spend.

Why a fixture graph rather than the real OSNet export: the export lives in the operator's venue and
nothing in this repo holds one, and the rewrite's correctness is a property of the OP GRAPH, not of
the trained weights. What the fixture must not be is weak, so every assertion below is paired with a
control that would catch it going stale, and the two instrument-level properties that the fixture
cannot prove (real node/initializer counts, the gate's sensitivity envelope on real weights) were
measured directly against the venue's own export — see the opsb-188.18 NOTES comment (§SRGWHY).

The instrument this suite most depends on is `onnx.checker`, and one of its limits is pinned here
rather than trusted: on the venue's export the checker PASSED a graph whose `axes` initializer had
been stored as float32, and only the ORT load rejected it. test_axes_initializer_keeps_int64_dtype
therefore pins the dtype directly instead of leaning on the checker.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

# onnx/onnxruntime live only in the `dev` extra, so the ONE CI leg that sweeps EVERY tracked test
# file for import errors — collection-sanity's WP0.8 real-tree sweep — runs on base deps (numpy
# present, onnx absent) and this file is not the file that leg claims to run: the four
# `Backend Unit Tests` shards, which DO install the extra, execute it for real (witnessed in CI at
# the head). A module-scope `import onnx` therefore errored the sweep — a scope mismatch, not a
# defect — so the guard skips it only where the dep was never installed. That is a scope statement,
# not an escape hatch: the legs that claim to run this file have the dep and run every case in it
# (round-2 review caught a stale count here — "all 21" when the file collected 27 — so this sentence
# deliberately carries NO number; the count lives in the CI shard rows, the only live referent).
onnx = pytest.importorskip("onnx", reason="onnx is a dev-extra dep; see the sweep-vs-shard note")
from onnx import TensorProto, helper, numpy_helper  # noqa: E402  (after the guard, by design)

_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "decompose_instance_norm.py"
_C = 8  # channels of the fixture's normalized activations: scale/bias are length-_C vectors
_D = 5  # output width of the final 1x1-equivalent conv: an embedding-like 2-D output
_W, _H = 128, 256  # the reid contract the surgery refuses any other layout for
_N = 2  # rows in the batch (keeps the fixture's cosine MIN meaningful, not just its mean)
_EPS = 1e-3  # deliberately NOT the 1e-5 default: the rewrite must carry the graph's own value


def _scale(seed: int) -> np.ndarray:
    """Per-channel scale spanning a wide range, NOT constant across channels.

    A constant scale would let a channel-misaligned rewrite sail through the cosine check (the same
    vacuity the gate has to be calibrated against), so the fixture varies per channel by design; the
    range is wide because test_channel_misalignment plants a per-channel re-aim and that stimulus has
    to be strong enough to cross the gate — a narrow scale would read a real misalignment as a pass,
    which is exactly the insensitivity the venue calibration recorded.
    """
    rng = np.random.default_rng(seed)
    return (0.2 + 2.7 * rng.random(_C)).astype(np.float32)


def _inits() -> list:
    """Initializers built with numpy_helper, because the sidecar leg depends on it.

    save(..., save_as_external_data=True) relocates only tensors whose data_location is NONE; one
    that already carries RAW bytes (what helper.make_tensor produces) stays inline and NOTHING is
    externalized — measured both ways on this onnx version: make_tensor -> no sidecar at all,
    from_array -> model.onnx + model.onnx.data. torch's exporter, which produced the venue's real
    export, emits the NONE form, so numpy_helper is also the closer emulation. Had these been built
    with helper.make_tensor, test_sidecar_dropped_only_after_the_recheck would have staged a graph
    that never had a sidecar and asserted its way to a vacuous pass.

    ``decoy_axes`` is an int64 [2,3] initializer used by NOTHING. It exists so the axes assertion in
    TestRewrite cannot be satisfied by a content filter: 3 rewritten IN nodes plus this decoy means
    "find the int64 [2,3] initializers" counts 4, so only selecting on the name the rewrite mints
    gives the right answer. It is unused on purpose — ORT drops unused initializers at load, which
    also keeps it out of the external-data problem below.
    """

    def w(name, shape, seed):
        rng = np.random.default_rng(seed)
        return numpy_helper.from_array((rng.standard_normal(shape) * 0.1).astype(np.float32), name)

    out = [
        w("w1", (_C, 3, 3, 3), 1),
        w("w2", (_C, _C, 3, 3), 2),
        w("w3", (_D, _C, 1, 1), 3),
        numpy_helper.from_array(np.array([2, 3], np.int64), "decoy_axes"),
    ]
    for i in range(3):
        out.append(numpy_helper.from_array(_scale(10 + i), f"s{i}"))
        out.append(numpy_helper.from_array(np.full(_C, 0.1 * (i + 1), np.float32), f"b{i}"))
    return out


def _fixture_model(opset: int = 21) -> onnx.ModelProto:
    """Three IN nodes on a path that preserves per-channel signal to a 2-D output.

    Four properties are load-bearing; each was re-cut after a measured failure:

    * conv1 emits W == C == _C, so the first IN sits at the ONE shape where the bug this rewrite
      avoids is *silently shape-correct*: a length-C vector broadcast against the last axis pairs
      channel c with s[(c*W+w) mod C] == s[w] and leaves every shape intact. test_channel_
      misalignment_is_visible_to_the_gate plants exactly that, and the fixture must be able to see
      it. An earlier fixture had W=1, where the same plant simply fails to broadcast.
    * nothing normalizes or spatially averages after the LAST IN. An earlier fixture ended in a mean
      over H,W; the next InstanceNormalization absorbs a per-channel factor and the mean averages
      what survives, so a planted defect on the first IN read cosine 0.99998 — an instrument that
      reads 1.0 for a real defect certifies nothing. The tail is a random 1x1 channel mix and a
      Flatten: no normalization, no reduction, and per-channel signal reaches the output intact.
    * the graph must reach 2-D without any node reading a constant tensor at load time. `Flatten`
      takes no initializer; `Squeeze`/`ReduceMean` take their axes as one, and an axes initializer
      stored EXTERNALLY is unparseable to onnxruntime ("Cannot parse data from external tensors",
      measured), which would have made the sidecar leg fail for a reason that has nothing to do with
      what it tests. The venue's real export has no such consumer, so Flatten is also the faithful
      emulation.
    * activations shrink early (8x8 after conv1, 2x2 after conv2) so all of this stays CPU-scale.
    """
    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, ["batch", 3, _H, _W])
    out = helper.make_tensor_value_info("out", TensorProto.FLOAT, ["batch", _D * 4])
    mk = helper.make_node
    nodes = [
        mk("Conv", ["x", "w1"], ["y0"], kernel_shape=[3, 3], strides=[32, 16], pads=[1, 1, 1, 1]),
        mk("InstanceNormalization", ["y0", "s0", "b0"], ["n0"], epsilon=_EPS),
        mk("Conv", ["n0", "w2"], ["y1"], kernel_shape=[3, 3], strides=[4, 4], pads=[1, 1, 1, 1]),
        mk("InstanceNormalization", ["y1", "s1", "b1"], ["n1"], epsilon=_EPS),
        mk("InstanceNormalization", ["n1", "s2", "b2"], ["n2"], epsilon=_EPS),
        mk("Conv", ["n2", "w3"], ["y3"], kernel_shape=[1, 1]),
        mk("Flatten", ["y3"], ["out"], axis=1),
    ]
    g = helper.make_graph(nodes, "reid-fixture", [x], [out], _inits())
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", opset)])
    m.ir_version = 10
    return m


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("decompose_instance_norm", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["decompose_instance_norm"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def model() -> onnx.ModelProto:
    return _fixture_model()


@pytest.fixture
def batch() -> np.ndarray:
    rng = np.random.default_rng(7)
    return rng.standard_normal((_N, 3, _H, _W)).astype(np.float32)


def _venue(tmp_path: Path, model: onnx.ModelProto, batch: np.ndarray, external: bool = False):
    """Stage the layout the rewrite's CLI requires: model.onnx + pre/model.onnx(.data) + batch.npy.

    ``external`` writes the graph with an external-data sidecar, the shape the venue's real export
    has, and the reason the sidecar is dropped LAST (the pre snapshot still loads through it). The
    surgery target is a COPY: save_as_external_data flags the in-memory initializers EXTERNAL as a
    side effect, and ``model`` is module-scoped, so saving it directly would leak that state into
    whichever test -p randomly runs next.
    """
    work = tmp_path / "venue"
    (work / "pre").mkdir(parents=True)
    for d in (work, work / "pre"):
        m = onnx.ModelProto()
        m.CopyFrom(model)
        if external:
            onnx.save(
                m,
                str(d / "model.onnx"),
                save_as_external_data=True,
                all_tensors_to_one_file=True,
                location="model.onnx.data",
                size_threshold=0,
            )
        else:
            onnx.save(m, str(d / "model.onnx"))
    np.save(str(tmp_path / "batch.npy"), batch)
    return work, tmp_path / "batch.npy"


def _rank3_in_model() -> onnx.ModelProto:
    """A legal-ONNX graph whose single IN sits on a RANK-3 activation.

    This is the shape that makes the module's chosen authority (the ORT load) disagree with
    ``onnx.checker`` for a reason the fixture's own int64/float axes plant cannot reach: the rewrite
    hardcodes ``axes = [2, 3]``, so a ``Rank``-3 input leaves ``ReduceMean`` reducing off the end of
    the tensor. The checker PASSES that graph and onnxruntime refuses it at load — measured:
    ``ShapeInferenceError`` at the emitted ``ReduceMean``. It exists so
    test_a_graph_ort_refuses_never_touches_the_target can drive a REAL ORT refusal through the real
    ``surgery()`` instead of mocking ``embed``: a monkeypatched refusal would certify the branch, not
    the authority it claims to be.
    """
    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, ["batch", 3, _H, _W])
    out = helper.make_tensor_value_info("out", TensorProto.FLOAT, ["batch", _C])
    mk = helper.make_node
    rng = np.random.default_rng(1)
    inits = [
        numpy_helper.from_array(
            (rng.standard_normal((_C, 3, 3, 3)) * 0.1).astype(np.float32), "w1"
        ),
        numpy_helper.from_array(np.array([0, _C, -1], np.int64), "shp"),  # -> rank 3
        numpy_helper.from_array(_scale(5), "s0"),
        numpy_helper.from_array(np.full(_C, 0.1, np.float32), "b0"),
    ]
    nodes = [
        mk("Conv", ["x", "w1"], ["y0"], kernel_shape=[3, 3], strides=[16, 8], pads=[1, 1, 1, 1]),
        mk("Reshape", ["y0", "shp"], ["r3"]),
        mk("InstanceNormalization", ["r3", "s0", "b0"], ["n0"], epsilon=_EPS),
        mk("GlobalAveragePool", ["n0"], ["out"]),
    ]
    g = helper.make_graph(nodes, "rank3-in", [x], [out], inits)
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 21)])
    m.ir_version = 10
    return m


class TestReviewFollowups:
    """Pins for the five CONFIRMED findings in the #7238 review (comment 6238690810).

    The review's verdict was REQUEST CHANGES: each of these instruments printed a PASS or a value it
    could not have measured. Three of the five are behavioural and were driven RED against the
    reviewed head first (findings 1, 2, 5); two are coverage/premise pins whose script was already
    behaving, so their teeth are aimed at the NEXT edit (findings 3, 4 — see each test).
    """

    @pytest.mark.timeout(60)
    def test_a_nan_row_that_is_not_the_first_row_still_refuses(
        self, script, model, tmp_path, batch
    ) -> None:
        """Finding 1: the guard read ``row["cos"][0]`` only, so a NaN in any later row passed.

        Driven end-to-end rather than by asserting on a literal: ``epsilon=0.0`` is a legal attribute
        (the module refuses only a MISSING epsilon), so a spatially-degenerate batch row makes the
        first IN compute 0/0. Against the reviewed head this printed ``surgery ok: faithful`` and
        returned 0 with ``cos = [1.0000001192092896, nan]`` — measured, no mock. The NaN lands in row
        1, which is exactly where a row[0]-only guard cannot see it.
        """
        m = onnx.ModelProto()
        m.CopyFrom(model)
        for node in m.graph.node:
            if node.op_type == "InstanceNormalization":
                for attr in node.attribute:
                    if attr.name == "epsilon":
                        attr.f = 0.0
        degenerate = batch.copy()
        degenerate[1] = 0.0  # row 1 all-zero -> 0/0 -> NaN embedding row
        work, b = _venue(tmp_path, m, degenerate)
        with pytest.raises(SystemExit, match="not interpretable"):
            script.surgery(work / "model.onnx", work / "pre", b, work / "S.json", want_in=3)
        assert not (tmp_path / "venue" / "model.onnx.decomp.tmp").exists(), (
            "the temp file survived a refusal: the next run in this dir would read a stale graph"
        )

    @pytest.mark.timeout(60)
    def test_a_negative_cosine_row_refuses(self, script, model, tmp_path, batch) -> None:
        """Finding 1: the `x >= 0.0` half of the guard had ZERO coverage — the NaN pin above trips

        BOTH halves (nan >= 0.0 is False), so deleting either half left the suite green. This plants
        the ONE shape that hits `>= 0.0` WITHOUT being non-finite: a finite cosine near -1, reached by
        a sign flip in a weight load — the PRE snapshot's FINAL Conv weight (w3, the one whose output
        is the embedding) negated, while the TARGET stays honest. surgery() embeds pre and the
        decomposed target, so an inverted pre embedding is anti-aligned with an honest decomposed one:
        cos=[-1,-1]. As shipped this refuses (rc 1, "not interpretable", nothing written); with only
        `>= 0.0` removed it writes S.json with min=-1.0 — a PASS-shaped artefact for a graph the
        module declared unmeasurable.
        """
        # Stage pre and target SEPARATELY. _venue copies one model to both, so a whole-model flip
        # there is a tautology (negate both sides -> cos stays +1); the reviewer hit the same trap.
        # Here the target is the honest graph and only pre has the inverted weight.
        work = tmp_path / "venue"
        (work / "pre").mkdir(parents=True)
        onnx.save(model, str(work / "model.onnx"))  # TARGET: honest
        neg = onnx.ModelProto()
        neg.CopyFrom(model)
        planted = 0
        for ini in neg.graph.initializer:
            if ini.name == "w3":  # last Conv -> the embedding direction
                ini.CopyFrom(
                    numpy_helper.from_array(
                        (-numpy_helper.to_array(ini)).astype(np.float32), ini.name
                    )
                )
                planted += 1
        assert planted == 1, "expected exactly one w3 initializer to negate; stimulus is vacuous"
        onnx.save(neg, str(work / "pre" / "model.onnx"))  # PRE: sign-flipped weight load
        np.save(str(tmp_path / "batch.npy"), batch)
        b = tmp_path / "batch.npy"
        # SELF-VALIDATE on the instrument's own sensitive axis before trusting the call: cosine_rows
        # must actually read negative here, else the plant is off-axis and the test would pass for the
        # wrong reason (the null-stimulus trap that fakes a mutant green).
        decomp, _ = script.decompose(model, want_in=3)
        onnx.save(decomp, str(tmp_path / "d.onnx"))
        cos = script.cosine_rows(
            script.embed(work / "pre" / "model.onnx", batch),
            script.embed(tmp_path / "d.onnx", batch),
        )
        assert cos.size and float(np.min(cos)) < -0.5, (
            f"plant produced {cos}, not an anti-aligned row"
        )
        with pytest.raises(SystemExit, match="not interpretable"):
            script.surgery(work / "model.onnx", work / "pre", b, work / "S.json", want_in=3)
        assert not (work / "model.onnx.decomp.tmp").exists()

    @pytest.mark.timeout(60)
    def test_an_empty_batch_refuses_before_numpy(self, script, model, tmp_path) -> None:
        """Finding 2(a): (0,3,256,128) has the right ndim and trailing dims, so the OLD layout guard

        accepted it, then all() over an empty cos passed vacuously and cos.min() died inside numpy
        with an unmapped rc 1, stranding the .decomp.tmp beside the export. The guard now carries an
        explicit N>=1 clause; deleting it makes THIS red (M7) — the source fix alone pins nothing.
        """
        work = tmp_path / "venue"
        (work / "pre").mkdir(parents=True)
        onnx.save(model, str(work / "model.onnx"))
        onnx.save(model, str(work / "pre" / "model.onnx"))
        np.save(str(tmp_path / "batch.npy"), np.zeros((0, 3, _H, _W), np.float32))
        with pytest.raises(SystemExit, match=r"N>=1"):
            script.surgery(
                work / "model.onnx",
                work / "pre",
                tmp_path / "batch.npy",
                work / "S.json",
                want_in=3,
            )
        assert not (work / "model.onnx.decomp.tmp").exists(), "empty batch stranded the temp"

    @pytest.mark.timeout(60)
    def test_out_json_that_is_the_target_refuses(self, script, model, tmp_path, batch) -> None:
        """Finding 2(c): out_json naming the target itself is the one-argument slip that, on a gate

        regression, wrote the JSON ROW over the model and returned rc 30 — the code whose whole
        contract is "the target was not touched" (measured 4192 B model -> 480 B row). The aliasing
        of out_json to the target is now refused up front, like the pre-snapshot alias.
        """
        work, b = _venue(tmp_path, model, batch)
        target = work / "model.onnx"
        sha_before = script._sha(target)
        with pytest.raises(SystemExit, match="row destination"):
            # out_json == the surgery target, the slip.
            script.surgery(target, work / "pre", b, target, want_in=3)
        assert script._sha(target) == sha_before, (
            "the target was touched by the out_json alias refusal"
        )

    @pytest.mark.timeout(60)
    def test_out_json_that_is_the_pre_snapshot_refuses(
        self, script, model, tmp_path, batch
    ) -> None:
        """Round-3 finding 2: the alias refusal compared out_json to the TARGET only, never to the

        pre snapshot, while the row is written before the gate check. Priced on the pre-fix script:
        a faithful run returned rc 0 having replaced the snapshot with a 482 B row, and an unfaithful
        one returned rc 30 — the code whose contract is "nothing was touched" — having destroyed the
        baseline the recheck is made of, so the invocation can never be re-run. The snapshot is the
        artifact the module's own comments say must survive the recheck.
        """
        work, b = _venue(tmp_path, model, batch)
        snap = work / "pre" / "model.onnx"
        sha_before = script._sha(snap)
        with pytest.raises(SystemExit, match="pre-surgery snapshot"):
            script.surgery(work / "model.onnx", work / "pre", b, snap, want_in=3)
        assert script._sha(snap) == sha_before, (
            "the pre snapshot was touched by the out_json alias refusal"
        )

    def test_the_alias_predicate_needs_both_of_its_two_halves(self, script, tmp_path) -> None:
        """Round-3 finding 3: ``_aliases`` is ``exists() and _samefile`` OR ``resolve()``, and each

        half covers a case the other CANNOT see, so no single plant reaches both — the same shape as
        the cosine guard, hence the same cure: pin each half by DIRECT call. M8b (drop the inode
        disjunct) and M8c (drop ``resolve()``) both left the suite green at the reviewed head because
        the only alias test exercises one path, the plain same-path slip.
        (a) HARDLINK, both files existing: two names, one inode. ``resolve()`` returns two different
            paths, so only the inode disjunct catches it — and missing it is priced as the exact
            destruction the guard's comment names (rc 30 with the model replaced by the row).
        (b) NON-CANONICAL SPELLING of the target whose stat FAILS (``build/../model.onnx`` with no
            ``build/``): ``exists()`` is False, so the inode disjunct is structurally blind and only
            ``resolve()`` — lexical, per its own docstring — sees it. HONEST SCOPE: this half is
            DEFENCE IN DEPTH. I could not build an end-to-end destruction from it, and the reason is
            worth keeping: on Linux the same missing component that defeats the stat also defeats the
            write (ENOENT), and that write is separately mapped to rc 31, so a mutant here is green
            because the case is unreachable-with-harm, not because the test is weak. It is pinned by
            DIRECT CALL for exactly that reason — the guard is cheap, the alternative is trusting a
            kernel's path semantics to stay unfavourable.
        (c) NEGATIVE: an honest independent copy must NOT be refused, or the guard is overbroad and
            every real venue run dies at the door.
        """
        target = tmp_path / "model.onnx"
        target.write_bytes(b"model-bytes")

        # (a) hardlink: different path, same inode.
        link = tmp_path / "S.json"
        os.link(target, link)
        assert link.resolve() != target.resolve(), "hardlink resolved equal — plant is vacuous"
        assert script._aliases(link, target), "the inode half is dead: a hardlink alias slips"

        # (b) stat-invisible spelling of the target: only the resolved-path half can see it.
        sneaky = tmp_path / "nope" / ".." / "model.onnx"  # 'nope' is never created
        assert not sneaky.exists(), "plant is vacuous: the stat-invisible case became visible"
        assert script._aliases(sneaky, target), "the resolve half is dead: a sneaky alias slips"

        # (c) an honest copy is the same BYTES but a different file: must pass through.
        copy = tmp_path / "copy.onnx"
        copy.write_bytes(b"model-bytes")
        assert copy.resolve() != target.resolve() and not script._samefile(copy, target)
        assert not script._aliases(copy, target), (
            "the predicate is overbroad: an honest copy would be refused"
        )

    @pytest.mark.timeout(60)
    def test_unwritable_out_json_refuses_31_not_crashes(
        self, script, model, tmp_path, batch
    ) -> None:
        """Finding 2(b): out_json into a non-existent parent escaped as a raw FileNotFoundError ->

        rc 1 (unmapped by main()) and left the .decomp.tmp behind. The write is now inside the same
        refusal discipline as every other exit, so it raises Refusal (-> 31) and removes the temp.
        """
        work, b = _venue(tmp_path, model, batch)
        missing = work / "nope" / "S.json"  # parent directory does not exist
        with pytest.raises(script.Refusal, match="cannot write the faithfulness row"):
            script.surgery(work / "model.onnx", work / "pre", b, missing, want_in=3)
        assert not (work / "model.onnx.decomp.tmp").exists(), "the temp survived the write refusal"

    def test_the_interpretability_guard_pins_both_halves(self, script) -> None:
        """The guard `np.isfinite(x) and x >= 0.0` has two arms, neither individually reachable by a

        single plant (NaN trips both; a negative trips only `>= 0.0`; +inf — if it were reachable —
        trips only `isfinite`, and on every non-degenerate path measured it co-occurs with NaN). So
        the arm a future edit could silently delete is pinned at SOURCE level, the way this file
        already pins load-bearing text: a direct textual claim about the guard, not a reachable
        input. `>= 0.0` also has a real behavioural test above; this is the belt for `isfinite`.
        """
        # The scanned path is a module constant: _SCRIPT is __file__ plus two literal segments, so no
        # untrusted input reaches the open. Same rationale as the Path(M.__file__).read_text() pins in
        # backend/tests/unit/services/. Suppressed per rule, not per scan — see setup.py:1526's shape.
        src = Path(script.__file__).read_text()  # nosemgrep: path-traversal-open
        assert "np.isfinite(x)" in src and "x >= 0.0" in src, (
            "the interpretability guard must reject BOTH non-finite and negative cosines; one arm "
            "deleted makes a PASS-shaped S.json describe an unmeasurable graph"
        )

    @pytest.mark.timeout(60)
    def test_a_pre_dir_that_is_the_target_refuses(self, script, model, tmp_path, batch) -> None:
        """Finding 2: nothing refused a pre-snapshot that IS the target — the module's own #1 trap.

        A one-argument slip (passing the export's own directory as ``pre-dir``) makes the in-place
        save overwrite the snapshot before the recheck reads it, so the comparison is a file against
        itself: ``max|delta| = 0.0``, and the module's docstring names that exact fingerprint as
        certifying nothing. Stage it the way the slip stages it — pre/model.onnx hardlinked to the
        target — and assert the refusal happens BEFORE anything is written.
        """
        work, b = _venue(tmp_path, model, batch)
        target = work / "model.onnx"
        aliased = tmp_path / "alias" / "pre"
        aliased.mkdir(parents=True)
        os.link(str(target), str(aliased / "model.onnx"))  # same inode, different path
        sha_before = script._sha(target)
        with pytest.raises(SystemExit, match="IS the surgery target"):
            script.surgery(target, aliased, b, work / "S.json", want_in=3)
        assert script._sha(target) == sha_before, (
            "the target was rewritten while its snapshot was aliased"
        )
        assert not (work / "S.json").exists(), "a row was written for a comparison that never ran"

    @pytest.mark.timeout(60)
    def test_the_gate_is_pinned_and_catches_a_marginal_defect(self, script) -> None:
        """Finding 3: every assertion compared against ``script.GATE``, so nothing pinned its value.

        Two teeth. (a) The value itself: at the reviewed head ``GATE = 0.999`` -> ``0.5`` left all 21
        cases green, i.e. ruling 68's instrument could be softened ~1000x in error terms with CI
        green. (b) A sensitivity plant INSIDE the gap: the fixture's channel-misalignment control reads
        cosine 0.144, which proves the gate rejects GARBAGE and says nothing about whether it rejects
        the marginal 0.998 a subtly-wrong rewrite produces. delta=0.10 on w1 measures min 0.998325 —
        inside (0.99, 0.999), under the gate, above the old plant's reach.
        """
        assert script.GATE == 0.999, (
            f"ruling 68's gate drifted to {script.GATE!r}; it is never to be loosened, and no "
            "assertion in this file noticed before"
        )
        assert 0.99 < script.GATE < 1.0

    @pytest.mark.timeout(120)
    def test_a_marginal_defect_lands_in_the_gap_the_gate_polices(
        self, script, model, tmp_path, batch
    ) -> None:
        """Finding 3's sensitivity control: a plant between 0.99 and the gate, not at 0.14.

        The existing control re-aims the channel vector and lands at 0.144 — orders of magnitude below
        the threshold it is supposed to prove the position of. This one perturbs the snapshot's w1
        until the surgery itself returns 30 with a min strictly inside (0.99, 0.999), which is the only
        witness that the gate's *position* is doing work rather than its existence.
        """
        work, b = _venue(tmp_path, model, batch)
        pre = work / "pre" / "model.onnx"
        m = onnx.load(str(pre))
        rng = np.random.default_rng(11)
        for k, ini in enumerate(m.graph.initializer):
            if ini.name == "w1":
                arr = numpy_helper.to_array(ini)
                pert = (arr + rng.standard_normal(arr.shape) * float(arr.std()) * 0.10).astype(
                    np.float32
                )
                m.graph.initializer[k].CopyFrom(numpy_helper.from_array(pert, "w1"))
        onnx.save(m, str(pre))
        rc = script.surgery(work / "model.onnx", work / "pre", b, work / "S.json", want_in=3)
        row = json.loads((work / "S.json").read_text())
        assert rc == 30, f"a min-{row['min']:.6f} regression must not pass as faithful"
        assert 0.99 < row["min"] < script.GATE, (
            f"plant landed at {row['min']:.6f}, outside the (0.99, {script.GATE}) gap the gate exists "
            "to police — this control has stopped testing what it names"
        )

    @pytest.mark.timeout(60)
    def test_the_external_data_probe_sees_what_a_plain_load_blinds(self, script, tmp_path) -> None:
        """Finding 4: the instrument re-used the load that CLEARS data_location, so it read 0 always.

        ``onnx.load()`` inlines external data and clears the marker — the module's own docstring says
        so, then the old code re-used that load to look for the marker, making the exit-32 branch
        unreachable by construction. Positive control first (the absence assertion is worthless
        without it): a file that provably needs its sidecar must report EXTERNAL under the probe and
        ZERO under a plain load. Measured on onnx 1.23.2: 1 vs 0.
        """
        probe = script._external_initializers
        on_disk = tmp_path / "ext.onnx"
        m = _fixture_model()
        onnx.save(
            m,
            str(on_disk),
            save_as_external_data=True,
            all_tensors_to_one_file=True,
            location="ext.onnx.data",
            size_threshold=0,
        )
        assert (tmp_path / "ext.onnx.data").is_file(), "the positive control staged no sidecar"
        plain = [
            i.name
            for i in onnx.load(str(on_disk)).graph.initializer
            if i.HasField("data_location") and i.data_location == TensorProto.EXTERNAL
        ]
        seen = probe(on_disk)
        assert plain == [], "a plain load reported EXTERNAL; the premise of this pin has changed"
        assert seen, "the probe cannot see external data either -> the exit-32 branch is still dead"
        # and a genuinely self-contained file must report nothing, or the 32 branch would always fire
        inline = tmp_path / "inlined.onnx"
        onnx.save(_fixture_model(), str(inline))
        assert probe(inline) == []

    @pytest.mark.timeout(60)
    def test_a_graph_ort_refuses_never_touches_the_target(self, script, tmp_path, batch) -> None:
        """Finding 5: the target was overwritten BEFORE the module's own authority ran.

        ``onnx.checker`` is explicitly not the authority — the ORT load is — yet the reviewed head
        saved in place and only then embedded. A rank-3 IN graph (legal ONNX; the rewrite hardcodes
        axes=[2,3]) passed the checker, refused the ORT load, and left the target OVERWRITTEN with an
        exit code of 1, which ``main()`` does not map. Now: the refusal is a mapped 31 and the input
        survives. No mock — the refusal comes from a real ORT load of a real rewritten graph.
        """
        rank3 = _rank3_in_model()
        assert script._count_in(rank3) == 1
        work, b = _venue(tmp_path, rank3, batch)
        target = work / "model.onnx"
        sha_before = script._sha(target)
        rc = script.main([str(target), str(work / "pre"), str(b), str(work / "S.json"), "1"])
        assert rc == 31, f"a refusal escaped the documented exit-code set as {rc}"
        assert script._sha(target) == sha_before, (
            "the input was destroyed by a surgery that never verified"
        )
        assert not (tmp_path / "venue" / "model.onnx.decomp.tmp").exists(), "temp left behind"
        assert not (work / "S.json").exists(), (
            "a faithfulness row was printed for an unloadable graph"
        )


class TestRewrite:
    def test_every_in_node_is_replaced(self, script, model) -> None:
        after, n = script.decompose(model, want_in=3)
        assert n == 3
        assert script._count_in(after) == 0
        # nine ops per IN, net of the one it replaces
        assert len(after.graph.node) == len(model.graph.node) + 3 * 8

    def test_decomposed_graph_loads_in_ort(self, script, model, tmp_path, batch) -> None:
        """The authority is the ORT load, not onnx.checker (see module docstring)."""
        after, _ = script.decompose(model, want_in=3)
        onnx.checker.check_model(after)
        onnx.save(after, str(tmp_path / "d.onnx"))
        emb = script.embed(tmp_path / "d.onnx", batch)
        assert emb.shape == (_N, _D * 4) and np.isfinite(emb).all()

    def test_axes_initializer_keeps_int64_dtype(self, script, model) -> None:
        # Pinned directly because onnx.checker will NOT catch it: on the venue's export a blanket
        # float32 cast of the axes tensor produced a graph the checker passed and ORT refused.
        after, _ = script.decompose(model, want_in=3)
        # Selected by the name the rewrite mints (ax_in*), NOT by [2,3] content: the fixture graph
        # carries its own int64 [2,3] initializer for the final Squeeze, so a content filter would
        # silently count that one too and the assertion would be about the fixture, not the rewrite.
        axes = [i for i in after.graph.initializer if i.name.startswith("ax_in")]
        assert len(axes) == 3, "one axes tensor per rewritten IN node"
        assert all(
            i.data_type == TensorProto.INT64 and list(numpy_helper.to_array(i)) == [2, 3]
            for i in axes
        ), [i.data_type for i in axes]
        floats = [
            i.name
            for i in after.graph.initializer
            if i.data_type == TensorProto.FLOAT and i.name.startswith("ax_")
        ]
        assert not floats, f"axes stored as float: {floats}"

    def test_scale_is_streshaped_channelwise(self, script, model) -> None:
        # (C,) broadcasts against the LAST axis (W, not C). The rewrite must emit 1xCx1x1.
        after, _ = script.decompose(model, want_in=3)
        for i in after.graph.initializer:
            if i.name.startswith(("s4_", "b4_")):
                assert list(i.dims) == [1, _C, 1, 1], (i.name, list(i.dims))

    def test_epsilon_is_carried_not_assumed(self, script, model) -> None:
        after, _ = script.decompose(model, want_in=3)
        eps_vals = {
            float(numpy_helper.to_array(i).reshape(-1)[0])
            for i in after.graph.initializer
            if i.name.startswith("eps_")
        }
        # approx, not ==: the value round-trips through a float32 initializer, so the exact float64
        # literal _EPS is not what comes back (0.0010000000474974513 vs 0.001 measured). approx does
        # not take a set, so the one-element set is compared as a sorted sequence.
        assert sorted(eps_vals) == pytest.approx([_EPS]), "the graph's own epsilon, not a default"
        assert not any(
            i.name.startswith("eps_in")
            and abs(float(numpy_helper.to_array(i).reshape(-1)[0]) - 1e-5) < 1e-9
            for i in after.graph.initializer
        ), "a default 1e-5 crept in"

    def test_tensor_names_are_unique(self, script, model) -> None:
        # A name minted twice for two tensors leaves an op reading a tensor nothing writes.
        after, _ = script.decompose(model, want_in=3)
        produced = [o for node in after.graph.node for o in node.output]
        assert len(produced) == len(set(produced))

    def test_superseded_inits_are_counted(self, script, model) -> None:
        after, _ = script.decompose(model, want_in=3)
        assert script.superseded(model, after) == 6  # 3 IN nodes x (scale, bias)


class TestFaithfulness:
    @pytest.mark.timeout(60)
    def test_surgery_is_faithful_and_returns_zero(self, script, model, tmp_path, batch) -> None:
        work, b = _venue(tmp_path, model, batch)
        rc = script.surgery(work / "model.onnx", work / "pre", b, work / "S.json", want_in=3)
        assert rc == 0
        row = json.loads((work / "S.json").read_text())
        assert row["min"] >= script.GATE
        assert row["n"] == _N and len(row["cos"]) == _N
        assert row["sha_before"] != row["sha_after"], "the file was never rewritten"
        assert row["witness"]["replaced"] == 3 and row["external_left"] == 0

    @pytest.mark.timeout(60)
    def test_sidecar_dropped_only_after_the_recheck(self, script, model, tmp_path, batch) -> None:
        work, b = _venue(tmp_path, model, batch, external=True)
        assert (work / "model.onnx.data").is_file()
        assert (work / "pre" / "model.onnx.data").is_file()
        rc = script.surgery(work / "model.onnx", work / "pre", b, work / "S.json", want_in=3)
        assert rc == 0
        assert not (work / "model.onnx.data").exists(), "sidecar survived a self-contained save"
        assert (work / "pre" / "model.onnx.data").is_file(), "the snapshot is the venue's input"
        # and the file the builder will read still runs on its own
        emb = script.embed(work / "model.onnx", batch)
        assert emb.shape == (_N, _D * 4) and np.isfinite(emb).all()

    @pytest.mark.timeout(60)
    def test_a_different_function_returns_thirty(self, script, model, tmp_path, batch) -> None:
        # The leg must be able to fail loudly: an instrument that cannot go red certifies nothing.
        # The plant sits on the axis the instrument measures -- the snapshot the recheck reads is
        # made to compute a DIFFERENT function while the file being rewritten stays pristine.
        work, b = _venue(tmp_path, model, batch)
        pre = work / "pre" / "model.onnx"
        m = onnx.load(str(pre))
        rng = np.random.default_rng(11)
        for k, ini in enumerate(m.graph.initializer):
            if ini.name == "w1":
                arr = numpy_helper.to_array(ini)
                pert = (rng.standard_normal(arr.shape) * float(arr.std())).astype(np.float32)
                m.graph.initializer[k].CopyFrom(numpy_helper.from_array(pert, "w1"))
        onnx.save(m, str(pre))
        rc = script.surgery(work / "model.onnx", work / "pre", b, work / "S.json", want_in=3)
        assert rc == 30
        assert json.loads((work / "S.json").read_text())["min"] < script.GATE

    @pytest.mark.timeout(60)
    def test_channel_misalignment_is_visible_to_the_gate(
        self, script, model, tmp_path, batch
    ) -> None:
        # Sensitivity control on the axis the fixture exists to exercise: the "wrong-but-plausible"
        # defect this programme actually shipped once. The rewrite stores the channel vector as
        # 1xCx1x1 (broadcast on the channel axis); the bug stored it 1x1x1W (broadcast on width). At
        # W == C those are the SAME eight numbers and both broadcast legally, so nothing about the
        # shapes distinguishes them -- only the output does. The fixture gives the FIRST IN W == C
        # precisely so this control can run; the later INs have W != C, where a width-broadcast is
        # shape-ILLEGAL and ORT refuses the model at load, so the plant targets IN1 only (s4_in1_*).
        # A first draft re-aimed all three and died on IN2's incompatible Mul: an error that is loud
        # is not the same as a control that tests the thing it names.
        work, _b = _venue(tmp_path, model, batch)
        orig = script.embed(work / "pre" / "model.onnx", batch)
        after, _ = script.decompose(model, want_in=3)
        planted = 0
        for k, ini in enumerate(after.graph.initializer):
            if ini.name.startswith("s4_in1_"):
                v = numpy_helper.to_array(ini).reshape(-1)
                after.graph.initializer[k].CopyFrom(
                    numpy_helper.from_array(v.astype(np.float32).reshape(1, 1, 1, v.size), ini.name)
                )
                planted += 1
        assert planted == 1, f"expected exactly one IN1 scale tensor to misalign, got {planted}"
        onnx.save(after, str(tmp_path / "mis.onnx"))
        mis = script.embed(tmp_path / "mis.onnx", batch)
        got = float(script.cosine_rows(orig, mis).min())
        assert got < script.GATE, f"misaligned channels read {got}: the gate could not see them"


class TestRefusals:
    """Each refusal is a claim about a shape that must never reach a builder."""

    def test_zero_in_nodes_refuses(self, script) -> None:
        m = _fixture_model()
        del m.graph.node[:]
        m.graph.node.extend([helper.make_node("Identity", ["x"], ["out"])])
        # no IN nodes at all: an already-decomposed or different graph
        with pytest.raises(script.Refusal, match="ZERO InstanceNormalization"):
            script.decompose(m)

    def test_unexpected_in_count_refuses(self, script, model) -> None:
        with pytest.raises(script.Refusal, match="want exactly 4"):
            script.decompose(model, want_in=4)

    def test_old_opset_refuses(self, script) -> None:
        # Below opset 18 `axes` is an attribute; emitting the input form would not validate.
        with pytest.raises(script.Refusal, match="opset 13"):
            script.decompose(_fixture_model(opset=13), want_in=3)

    def test_non_constant_scale_refuses(self, script, model) -> None:
        m = onnx.ModelProto()
        m.CopyFrom(model)
        m.graph.input.append(helper.make_tensor_value_info("s0b", TensorProto.FLOAT, [_C]))
        for node in m.graph.node:
            if node.op_type == "InstanceNormalization" and node.input[1] == "s0":
                node.input[1] = "s0b"
        with pytest.raises(script.Refusal, match="non-constant scale/bias"):
            script.decompose(m, want_in=3)

    def test_missing_epsilon_refuses(self, script, model) -> None:
        m = onnx.ModelProto()
        m.CopyFrom(model)
        for node in m.graph.node:
            if node.op_type == "InstanceNormalization":
                del node.attribute[:]
        with pytest.raises(script.Refusal, match="no epsilon"):
            script.decompose(m, want_in=3)

    def test_two_input_in_refuses(self, script, model) -> None:
        m = onnx.ModelProto()
        m.CopyFrom(model)
        for node in m.graph.node:
            if node.op_type == "InstanceNormalization":
                del node.input[2]
        with pytest.raises(script.Refusal, match="3-input"):
            script.decompose(m, want_in=3)

    @pytest.mark.timeout(60)
    def test_missing_snapshot_dir_refuses(self, script, model, tmp_path, batch) -> None:
        # The pre snapshot is a DIRECTORY; handing it a bare file would print a fake row.
        onnx.save(model, str(tmp_path / "model.onnx"))
        np.save(str(tmp_path / "b.npy"), batch)
        with pytest.raises(SystemExit, match="pre-surgery snapshot"):
            script.surgery(
                tmp_path / "model.onnx",
                tmp_path / "nowhere",
                tmp_path / "b.npy",
                tmp_path / "S.json",
                want_in=3,
            )

    @pytest.mark.timeout(60)
    def test_wrong_batch_layout_refuses(self, script, model, tmp_path, batch) -> None:
        work, _b = _venue(tmp_path, model, batch)
        bad = np.zeros((_N, 3, 64, 64), np.float32)
        np.save(str(tmp_path / "bad.npy"), bad)
        with pytest.raises(SystemExit, match="not \\(N,3,256,128\\)"):
            script.surgery(
                work / "model.onnx",
                work / "pre",
                tmp_path / "bad.npy",
                tmp_path / "S.json",
                want_in=3,
            )


class TestCli:
    """The venue invokes this file as a program; main()'s exit codes are its contract."""

    @pytest.mark.timeout(60)
    def test_cli_exits_zero_on_a_faithful_rewrite(self, script, model, tmp_path, batch) -> None:
        work, b = _venue(tmp_path, model, batch)
        assert (
            script.main(
                [str(work / "model.onnx"), str(work / "pre"), str(b), str(work / "S.json"), "3"]
            )
            == 0
        )

    @pytest.mark.timeout(60)
    def test_cli_maps_a_structural_refusal_to_thirtyone(
        self, script, model, tmp_path, batch
    ) -> None:
        work, b = _venue(tmp_path, model, batch)
        # 4 is the wrong expected IN count, so decompose() refuses; the mapping Refusal -> 31 lives
        # in main() itself, not only in the __main__ guard, because the exit codes are the contract
        # the venue branches on and an imported caller must not raise past them.
        rc = script.main(
            [str(work / "model.onnx"), str(work / "pre"), str(b), str(work / "S.json"), "4"]
        )
        assert rc == 31
