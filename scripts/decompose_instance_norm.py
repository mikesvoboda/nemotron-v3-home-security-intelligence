#!/usr/bin/env python3
"""Rewrite ``InstanceNormalization`` out of a REID ONNX graph, in place, and prove it faithful.

[osb-r252] (owner ruling 252) — the O2.4 TensorRT path reads a graph whose ``InstanceNormalization``
nodes the builder cannot lower; the fix is to decompose them to elementwise + reduction ops BEFORE a
plan is compiled. This module performs that rewrite on the venue's OWN fresh export and MEASURES the
result against the original graph with onnxruntime on CPU, so a broken rewrite is caught here rather
than at a builder leg. The operator-side runbook lives in the opsb-188.18 NOTES comment (§SRGWHY);
the CPU-only CI test that pins this module is backend/tests/unit/scripts/
test_decompose_instance_norm.py (ruling 252's Done-when: "a CPU-only CI test pinning it").

Three properties this rewrite is obliged to carry, each one a trap this programme already fell into:

  * TWO FILES, TWO SESSIONS. Faithfulness compares the pre-surgery graph against the post-surgery
    graph, both run through onnxruntime on CPU over the SAME batch the downstream stage consumes. A
    file compared against itself scores 1.0 by construction and certifies nothing — the vacuity
    shape that burned r157 twice.
  * THE PRE SNAPSHOT IS A DIRECTORY, NOT A FILE. Its initializers carry the external-data key
    ``model.onnx.data`` resolved relative to the model file, so the snapshot is staged as
    ``<pre-dir>/model.onnx`` + ``<pre-dir>/model.onnx.data``. Renaming it makes the pre graph
    unloadable FOR THE WRONG REASON and fakes the very row this rewrite exists to print.
  * THE SIDECAR IS DROPPED LAST. ``onnx.load()`` INLINES external data, which is why the rewrite's
    own EXTERNAL refusal never fires on the export and why the saved file is self-contained — but
    the PRE graph still loads THROUGH its sidecar, and the recheck reads PRE. Unlinking the sidecar
    during the rewrite therefore destroys the instrument that catches a broken surgery (measured:
    ``External data path validation failed for initializer: conv1.conv.weight``). So the drop
    happens AFTER the recheck row, and only once the saved model proves it needs nothing.

The batch arrives as already-transformed bytes: nothing here opens a crop file. Exit codes and the
CLI contract are documented on ``main``.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper

GATE = 0.999                       # ruling 68, the same gate the plan table is judged by
MIN_OPSET_AXES_INPUT = 18          # ReduceMean takes `axes` as an INPUT from opset 18 on


class Refusal(RuntimeError):
    """Refusal, not a fallback. A half-rewritten graph must never reach a builder."""


def _opset(model) -> int:
    std = [o for o in model.opset_import if not o.domain or o.domain == "ai.onnx"]
    if len(std) != 1:
        raise Refusal(f"expected exactly one ai.onnx opset import, got {len(std)}")
    return std[0].version


def _count_in(model) -> int:
    return sum(1 for n in model.graph.node if n.op_type == "InstanceNormalization")


def decompose(model, want_in: int | None = None):
    """IN -> ReduceMean/Sub/Mul/ReduceMean/Add/Sqrt/Div/Mul/Add, channel-aligned by 1xCx1x1 shapes.

    Returns ``(new_model, n_replaced)``. Axes-as-input, per the opset guard: emitting the input form
    below opset 18 would produce a model the checker rejects, so that case refuses rather than
    guessing a spelling. ``want_in`` (when given) is an expected InstanceNormalization count that the
    graph must match exactly — the venue passes the export's own number so a graph that is not the
    one the readings are comparable to refuses loudly instead of measuring the wrong thing.
    """
    opset = _opset(model)
    if opset < MIN_OPSET_AXES_INPUT:
        raise Refusal(f"opset {opset} < {MIN_OPSET_AXES_INPUT}: ReduceMean's axes must be an "
                      "attribute there and the input form emitted here would not validate")
    n_in = _count_in(model)
    if n_in == 0:
        raise Refusal("ZERO InstanceNormalization nodes in the graph. This rewrite exists to replace "
                      "them; an already-decomposed or different model reached it. Refusing rather "
                      "than measuring the wrong graph.")
    if want_in is not None and n_in != want_in:
        raise Refusal(f"{n_in} InstanceNormalization nodes, want exactly {want_in}: the graph is not "
                      "the one the recorded readings are comparable to. Refused.")
    g = model.graph
    inits = {i.name: i for i in g.initializer}
    n = 0
    k = 0

    def uniq(p):
        nonlocal k
        k += 1
        return f"{p}_in{n}_{k}"

    def const(name, arr, dtype=np.float32):
        # DTYPE IS A PARAMETER, NOT A DEFAULT. A blanket float32 cast here silently stored the
        # int64 `axes` tensor as float; onnx.checker PASSED that graph and onnxruntime rejected it
        # ("Type 'tensor(float)' of input parameter (ax_in1_3) of operator (ReduceMean)"). So the
        # checker this module calls is not sufficient authority for a graph a builder will accept --
        # the ORT load is, which is exactly why the recheck row runs before any save is trusted.
        return numpy_helper.from_array(np.asarray(arr, dtype=dtype), name)

    new_nodes, new_inits = [], list(g.initializer)
    for node in g.node:
        if node.op_type != "InstanceNormalization":
            new_nodes.append(node)
            continue
        if len(node.input) != 3:
            raise Refusal(f"IN node {node.name!r} has {len(node.input)} inputs, want the 3-input "
                          "affine form (X, scale, B) and nothing else")
        n += 1
        # SPEC ORDER, not intuition: InstanceNormalization's inputs are (input, scale, B). The first
        # draft unpacked them as (scale, B, input) and the refusal below fired on the REAL export --
        # the guard doing its job (input 0 is an activation, so it is never an initializer) rather
        # than silently compiling a graph that multiplies the wrong tensors.
        x, s_name, b_name = node.input
        eps = next((float(a.f) for a in node.attribute if a.name == "epsilon"), None)
        if eps is None:
            raise Refusal(f"IN node {node.name!r} carries no epsilon attribute; this rewrite carries "
                          "the graph's own value into the Add and will not assume one")
        s_init, b_init = inits.get(s_name), inits.get(b_name)
        if s_init is None or b_init is None:
            raise Refusal(f"IN node {node.name!r} has non-constant scale/bias; the channel-aligned "
                          "rewrite needs the initializer bytes to reshape them")
        s = numpy_helper.to_array(s_init).astype(np.float32).reshape(-1)
        b = numpy_helper.to_array(b_init).astype(np.float32).reshape(-1)
        if s.shape != b.shape:
            raise Refusal(f"IN node {node.name!r}: scale {s.shape} != bias {b.shape}")
        c_ch = int(s.shape[0])
        # (C,) broadcasts against the LAST axis under ONNX rules -- W, not C. The scalars must be
        # reshaped to 1xCx1x1 or channel c is multiplied by s[(c*W + w) mod C]: a wrong-but-plausible
        # vector that reads as a pass to anything numerics-blind.
        s4, b4 = uniq("s4"), uniq("b4")
        new_inits.append(const(s4, s.reshape(1, c_ch, 1, 1)))
        new_inits.append(const(b4, b.reshape(1, c_ch, 1, 1)))
        # ONE axes tensor, reused by both reductions. Each name is minted exactly once and every
        # consumer reads THAT name -- an early draft called uniq("var") twice, minting two different
        # tensors and leaving Sqrt reading a name nothing writes. ORT rejects an undefined input, so
        # the mistake was loud rather than silent, but the rule is the point: a unique-name generator
        # must never be called in two places that mean the same tensor.
        ax = uniq("ax")
        new_inits.append(const(ax, [2, 3], np.int64))                   # H,W of NCHW
        eps_i = uniq("eps")
        new_inits.append(const(eps_i, np.float32(eps)))   # 0-D, the form the design module measured
        m1, m2 = uniq("mean1"), uniq("mean2")   # mean over H,W, then mean of squares
        v0, v1 = uniq("diff"), uniq("sq")
        var, sd = uniq("var"), uniq("std")
        sc, mul = uniq("scaled"), uniq("mul")
        mk = onnx.helper.make_node
        new_nodes += [
            mk("ReduceMean", [x, ax], [m1], keepdims=1),        # axes as INPUT: opset >= 18
            mk("Sub", [x, m1], [v0]),
            mk("Mul", [v0, v0], [v1]),
            mk("ReduceMean", [v1, ax], [m2], keepdims=1),
            mk("Add", [m2, eps_i], [var]),
            mk("Sqrt", [var], [sd]),
            mk("Div", [v0, sd], [sc]),
            mk("Mul", [sc, s4], [mul]),
            mk("Add", [mul, b4], [node.output[0]]),
        ]
    out = onnx.ModelProto()
    out.CopyFrom(model)
    del out.graph.node[:]
    out.graph.node.extend(new_nodes)
    del out.graph.initializer[:]
    out.graph.initializer.extend(new_inits)
    return out, n


def superseded(before, after) -> int:
    """Initializers the rewrite made dead: the original IN scale/bias tensors.

    onnxruntime's optimizer drops unused initializers at load, so they are harmless -- but they are
    reported, not silently shipped, because "which bytes are now dead" is exactly the kind of claim
    that goes stale when the rewrite changes its naming.
    """
    used = {i for node in after.graph.node for i in node.input}
    used |= {i.name for i in after.graph.input}
    in_sb = set()
    for node in before.graph.node:
        if node.op_type == "InstanceNormalization":
            in_sb |= {node.input[1], node.input[2]}
    dead = {i.name for i in after.graph.initializer} - used
    return len(dead & in_sb)


def embed(model_path, batch):
    import onnxruntime as ort
    # CPUExecutionProvider EXPLICIT: a production gateway image ships onnxruntime-gpu and a bare
    # session would ride CUDA, which is not the engine the parity claim is about.
    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    return np.asarray(sess.run(None, {name: batch})[0], dtype=np.float32)


def cosine_rows(a, b):
    a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    b = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return np.einsum("ij,ij->i", a, b)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _samefile(a: Path, b: Path) -> bool:
    """True when two paths are the SAME file, not merely paths that look alike.

    Identity is (st_dev, st_ino), not ``a.resolve() == b.resolve()``: a resolve-comparison misses a
    hardlink (two names, one inode — what a ``cp -l`` or a mistaken pre-dir leaves behind), while an
    inode check catches it and a symlink as well, yet still lets an honest copy (different inode)
    through. FileNotFoundError-safe: a missing path is simply ``not the same file``.
    """
    try:
        sa, sb = a.stat(), b.stat()
    except OSError:
        return False
    return sa.st_dev == sb.st_dev and sa.st_ino == sb.st_ino


def _external_initializers(path) -> list:
    """Names of initializers the saved file still needs from a sidecar.

    Loaded with ``load_external_data=False`` ON PURPOSE. ``onnx.load()`` INLINES external data and
    clears ``data_location`` — the module's own opening insight — so a plain load reports ZERO
    EXTERNAL initializers for every file and this instrument would read 0 by construction. Only the
    non-inlining load can see what the saved model actually references, which is the difference
    between a measurement and a tautology.

    Scope, stated exactly: this makes the INSTRUMENT able to see external data; it does not make exit
    32 a routine outcome. ``onnx.save`` writes the graph self-contained, so on the plain-save path the
    honest answer is 0 and the sidecar is genuinely droppable (measured: a fixture saved with
    ``save_as_external_data`` reports EXTERNAL under this probe, the same graph saved plainly reports
    nothing). 32 stays the documented code for a save path that externalizes — reserved, not dead.
    """
    m = onnx.load(str(path), load_external_data=False)
    return [i.name for i in m.graph.initializer
            if i.HasField("data_location") and i.data_location == onnx.TensorProto.EXTERNAL]


def surgery(model_path, predir, batch, out_json, want_in: int = 5) -> int:
    """Rewrite ``model_path`` in place and write the faithfulness row to ``out_json``.

    ``predir`` holds the pre-surgery snapshot (``model.onnx`` + ``model.onnx.data``); ``batch`` is a
    loaded ``(N,3,256,128)`` array or a path to one. Returns the exit code main() maps: 0 faithful,
    30 faithfulness moved below the gate, 31 structural refusal, 32 sidecar still needed after a
    self-contained save.
    """
    model = Path(model_path)
    pre = Path(predir) / "model.onnx"
    if not pre.is_file():
        raise SystemExit(f"no pre-surgery snapshot at {pre} (the layout is a DIRECTORY: model.onnx + "
                         "model.onnx.data) - cannot print a faithful row")
    if _samefile(pre, model):
        raise SystemExit(
            f"pre-surgery snapshot {pre} IS the surgery target {model} (same inode). The module's own "
            "opening rule: a file compared against itself scores 1.0 by construction and certifies "
            "nothing — a pre-dir that is the export's own directory turns the recheck into that "
            "tautology AND the in-place save overwrites the snapshot before it is read. Stage the "
            "snapshot in a separate directory before re-running.")
    # out_json gets the SAME aliasing refusal the pre-snapshot got, for the same reason and one worse:
    # the row is written BEFORE the gate check, so if the destination resolves to the target, a gate
    # regression returns rc 30 — the code whose whole contract is "the target was not touched" — with
    # the target REPLACED BY THE ROW (measured at 9caefef26: 4192 B model -> 480 B JSON, rc 30). The
    # one-argument slip (row path = model path) must be refused here, before anything is written.
    # _samefile needs both files to exist; the destination usually does not yet, so resolve() is the
    # identity for the not-yet-created case and _samefile the stronger one when it does.
    outj = Path(out_json)
    if (outj.exists() and _samefile(outj, model)) or outj.resolve() == model.resolve():
        raise SystemExit(
            f"row destination {outj} IS the surgery target {model} - the faithfulness row would "
            "overwrite the export it describes, and on a gate regression it does exactly that under "
            "rc 30, the code that promises the target survived. Point out_json at a separate file.")
    batch = np.load(str(batch)) if isinstance(batch, (str, Path)) else np.asarray(batch)
    # shape[0] < 1 is its own clause because the tuple test below cannot see it: (0,3,256,128) has the
    # right ndim and the right trailing dims, so a ZERO-ROW batch passes the guard whose stated job is
    # "refuse a layout this rewrite has not witnessed" — and then dies inside numpy at cos.min() with a
    # ValueError main() does not map (raw rc 1), stranding the .decomp.tmp beside the export. An empty
    # batch is precisely a layout that has not been witnessed: there is nothing in it to witness.
    if batch.ndim != 4 or batch.shape[1:] != (3, 256, 128) or batch.shape[0] < 1:
        raise SystemExit(f"batch {batch.shape} is not (N,3,256,128) with N>=1 - refusing to feed the "
                         "graphs a layout this rewrite has not witnessed")

    sha_before, size_before = _sha(model), model.stat().st_size
    before = onnx.load(str(model))
    nodes_before = len(before.graph.node)

    after, n = decompose(before, want_in=want_in)
    if _count_in(after) != 0:
        raise SystemExit(f"{_count_in(after)} IN nodes survived the rewrite")
    onnx.checker.check_model(after)
    # VERIFY-BEFORE-MOVE. The ORT load is this module's chosen authority (docstring: the checker
    # passed a graph ORT refused), yet the old sequence saved IN PLACE first and only then embedded —
    # so an ORT-refusable graph (a rank-3 IN input: legal ONNX, but the rewrite hardcodes axes=[2,3])
    # crashed with a raw rc 1 that main() does not map, AFTER it had already destroyed the input.
    # Save to a sibling temp path, let the recheck embed THAT, and only once it is faithful move it
    # over the target. A failure now leaves the original model.onnx intact and maps to a real code.
    tmp = model.with_name(model.name + ".decomp.tmp")
    onnx.save(after, str(tmp))
    decomp = onnx.load(str(tmp))                    # in-memory graph: witness counts, before ORT runs
    ext = _external_initializers(tmp)

    # ---- the recheck row, BEFORE the target is overwritten and BEFORE the sidecar is touched ----
    # embed() of the decomposed temp is this module's CHOSEN AUTHORITY (the docstring: the checker
    # passed a graph ORT refused). It runs here, before any move, so a graph ORT will not load — a
    # rank-3 IN input, say — is caught as a refusal that leaves the original model.onnx untouched, and
    # NOT as a raw crash after the target is already gone. The exception class is picked by its module,
    # not its name: ORT raises Fail / InvalidGraph / InvalidArgument, all under this module, with no
    # shared base, so a single-name catch would let the float-axes (InvalidGraph) case slip past.
    try:
        a = embed(pre, batch)                        # ORIGINAL graph, its sidecar still beside it
        b = embed(tmp, batch)                        # DECOMPOSED graph, the bytes the builder sees
    except Exception as exc:                         # noqa: BLE001 - module-filtered, not blanket
        tmp.unlink(missing_ok=True)
        if type(exc).__module__ != "onnxruntime.capi.onnxruntime_pybind11_state":
            raise                                    # not an ORT load error: do not mislabel it 31
        raise Refusal(f"the decomposed graph loaded by onnx.checker is REFUSED by onnxruntime at load "
                      f"({type(exc).__name__}: {exc}). The checker is not the authority; the ORT load "
                      "is. The original model.onnx was left untouched (nothing was moved into place).")
    cos = cosine_rows(a, b)
    if not all(bool(np.isfinite(x)) and x >= 0.0 for x in cos):
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"cosine row is not interpretable: {[float(x) for x in cos]} contains a "
                         "non-finite or negative value. A degenerate embedding row (0/0) reads as a "
                         "PASS to a row[0]-only guard; nothing may be built from an unmeasured graph.")
    # the row describes the DECOMPOSED file, which is tmp until the faithful move renames it onto the
    # target; sha_after/size_after must therefore be measured on tmp, not on model (still pristine).
    row = {
        "n": int(cos.size), "min": float(cos.min()), "mean": float(cos.mean()),
        "max_abs_delta": float(np.abs(a - b).max()),
        "witness": {"replaced": n, "nodes_before": nodes_before,
                    "nodes_after": len(decomp.graph.node), "ir_version": decomp.ir_version,
                    "opset": _opset(decomp), "superseded_inits": superseded(before, decomp)},
        "sha_before": sha_before, "sha_after": _sha(tmp),
        "size_before": size_before, "size_after": tmp.stat().st_size,
        "external_left": len(ext), "gate": GATE, "cos": [float(x) for x in cos],
    }
    # The row write is inside the SAME refusal discipline as every other exit: an unwritable
    # destination (a parent directory that does not exist is the ordinary slip) used to escape as a raw
    # FileNotFoundError -> rc 1, which main() does not map, and it left the .decomp.tmp beside the
    # export. A venue that branches on the documented 0/30/31/32 set cannot tell "the graph is wrong"
    # from "the module crashed writing a file", and the tmp is valid decomposed ONNX named like a
    # leftover — ~9.4 MB on the real export — that a `*.onnx*` plan glob would pick up.
    try:
        outj.write_text(json.dumps(row))
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise Refusal(f"cannot write the faithfulness row to {outj} ({exc}). The original model.onnx "
                      "was left untouched and the decomposed temp was removed.") from exc

    w = row["witness"]
    print(f"  surgery: replaced {w['replaced']} IN · nodes {w['nodes_before']}→{w['nodes_after']}"
          f" · ir {w['ir_version']} · opset {w['opset']} · superseded initializers {w['superseded_inits']}")
    print(f"  model.onnx {size_before} B sha {sha_before[:12]}… → {row['size_after']} B sha "
          f"{row['sha_after'][:12]}… · external initializers left: {len(ext)}")
    print(f"  recheck (ORIGINAL vs DECOMPOSED, ORT CPU, {row['n']} rows): min {row['min']:.8f} "
          f"mean {row['mean']:.8f} max|Δ| {row['max_abs_delta']:.3e}  gate {GATE}")
    if row["min"] < GATE:
        tmp.unlink(missing_ok=True)                  # unfaithful: the target stays pristine
        print(f"  THE SURGERY BROKE FAITHFULNESS at min {row['min']:.8f} < {GATE}. The plans must NOT "
              "be built from this graph; nothing downstream may be read.")
        return 30

    # ---- the graph is faithful and ORT-loadable: only NOW does the target change ----------------
    os.replace(str(tmp), str(model))                 # atomic: the plans are built from THIS file
    # ---- the sidecar, dropped LAST and only if the moved file proves it needs nothing ------------
    # tmp and model share a directory, so the decomposed model's own sidecar (if it has one) is named
    # after model.name and is beside it. ext==0 means the moved file references no sidecar at all.
    side = model.with_name(model.name + ".data")
    if ext:
        print(f"  sidecar KEPT: {len(ext)} external initializer(s) still referenced "
              f"({ext[0]}…). The plans still build; this is a tidiness loss, not a measurement loss.")
        return 32
    if side.exists():
        side.unlink()
        print(f"  sidecar dropped: {side.name} (the decomposed model is self-contained)")
    print("  surgery ok: faithful, checker-clean, zero IN nodes; the plan legs now read THIS graph")
    return 0


def main(argv=None) -> int:
    """CLI: decompose_instance_norm.py <model.onnx> <pre-dir> <batch-npy> <out-json> [want-in=5].

    The exit codes are mapped HERE, not only in the ``__main__`` guard: they are the contract the
    venue branches on, and a function whose docstring promises them must not raise past them just
    because it was imported instead of exec'd.

    Exit: 0 ok · 30 the rewrite moved the graph's own function (min cosine under the gate) ·
          31 the graph is not the graph this rewrite was written for (structural refusal) ·
          32 the decomposed model still needs its sidecar (refused the drop; plans unaffected).
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) not in (4, 5):
        raise SystemExit("usage: decompose_instance_norm.py <model.onnx> <pre-dir> <batch-npy> "
                         "<out-json> [want-in]")
    model, predir, batchnpy, outp = argv[:4]
    want_in = int(argv[4]) if len(argv) == 5 else 5
    try:
        return surgery(model, predir, batchnpy, outp, want_in=want_in)
    except Refusal as exc:
        print(f"REFUSED (structural): {exc}")
        return 31


if __name__ == "__main__":
    sys.exit(main())
