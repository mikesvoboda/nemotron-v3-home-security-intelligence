"""CPU-only re-ID export fidelity: exported ONNX must reproduce PyTorch to 0.999.

Ruling 157 (owner) orders a check that runs in CI with no GPU. The one seam it
closes is the one that shipped broken: ``export_to_onnx`` wrote an ONNX graph and
``validate_onnx`` — the export's own proof — compared it against the very model it
was exported from, and when onnx/onnxruntime were absent it returned True with a
WARNING instead of measuring anything. O2.4 shipped ``reid/1/model.onnx`` at
cosine min 0.230 against the served reference while the export step had reported
PASS, because the only numeric proof on CI had skipped.

What this is NOT: it is not the torchreid-port check (that is
``test_export_reid.py``, against ``osnet_ain_x1_0`` key-for-key) and it is not the
TensorRT-plan or gateway check (the owner's ``scripts/reid_parity_check.py`` on the
GPU host). This file proves exactly ONE hop the others never execute on CI:
PyTorch -> ONNX file -> onnxruntime CPU, on real crops, cosine per crop. It is the
hop whose ``ImportError`` branch is the false comfort ruling 157 exists to close,
so it is the one that must run in CI, not be reported from the export.

Why the inputs are real crops and not noise: ``validate_onnx`` feeds
``np.random.randn`` — white noise carries no layout, so a CHW/NCHW transpose or a
normalisation slip is invisible in it (it passed at 1.000 on a mis-ported graph).
A real person crop has a face at the top and a body below; a flipped axis moves
the embedding, so the 0.999 gate can actually fail. The crops are the committed
camera fixtures, read with the served preprocessing so the input tensor matches
what ``/enrich-lt/person-reid`` builds — otherwise the test would measure an
export of a graph the gateway never serves.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# These three are hard imports, deliberately NOT importorskip. importorskip is the
# exact shape that hid the fault: an absent dependency reads as "0 tests failed"
# while the check that was meant to fail never executed. Here a missing dependency
# is a collection ERROR naming the package — the loud outcome ruling 157 asks for.
# All three are now in the ``dev`` extra (uv.lock pins them): ``onnx`` and
# ``onnxscript`` because torch 2.14's exporter hard-fails without them (dynamo
# raises ``No module named 'onnxscript'``; ``dynamo=False`` raises ``Module onnx is
# not installed!``), and ``onnxruntime`` because ``validate_onnx`` needs it to
# measure anything. The gateway image ships the same three
# (ai/gateway/Dockerfile:30-32).
import onnx
import onnxruntime as ort
import onnxscript
import pytest
import torch

from ai.gateway.export import export_reid

# The committed camera fixtures already in the repo — no synthetic crop (a crop
# this file invented could not fail the check it is meant to prove, the same trap
# as a hand-written junit row), and no host-only ~/o24-crops (this is the CPU test;
# it has to run on a runner with no model zoo and no GPU).
CROPS_DIR = Path(__file__).resolve().parents[3] / "backend/tests/fixtures/images/pipeline_test"
FIXED_CROPS = (
    "test_person_house_front.jpg",
    "test_person_walking_dog.jpg",
    "test_person_porch_1.jpg",
)

# Ruling 68's parity gate, unchanged — this is the same 0.999 the owner's GPU run
# is held to, applied one hop earlier so a graph fault is caught on CI before a
# plan is ever compiled from the ONNX.
PARITY_GATE = 0.999

# A real ONNX export of OSNet-AIN through torch 2.14's dynamo path costs ~9 s
# uncontended on a CPU runner (measured: build 0.05s, export 8.92s, validate 0.69s
# = 9.7s on this host). The 5 s tier default would kill it mid-export, and the kill
# would look like a hang, not a slow-but-passing check. 60 s is this repo's own
# model-load budget (pyproject.toml:601 e2e; the sibling test_export_reid.py uses
# the same explicit per-file timeout). This file is collected by the ai-tests job
# (`pytest ai/gateway`), which uploads NO test-results-* artifact, so it is outside
# the Test Performance Audit's duration corpus and the 4.0 s unit budget never
# reaches it — the timeout marker is the whole admission, nothing else moves.
pytestmark = pytest.mark.timeout(60)


def _served_tensor(path: Path) -> np.ndarray:
    """The crop as ``/enrich-lt/person-reid`` preprocesses it: 128x256 bilinear,
    /255, ImageNet norm, CHW, batch-of-1.

    Copied from ``adapters/enrichment_light.py:225`` rather than reimplemented:
    PIL's bicubic (its default) moves pixels up to 0.7 after normalisation and the
    gateway comment names that as a parity-breaker, so the resampling filter is
    load-bearing and must match the served path exactly.
    """
    from PIL import Image

    arr = np.asarray(
        Image.open(path).convert("RGB").resize((128, 256), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    arr = arr / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    return arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(
        np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8),
    )


@pytest.fixture(scope="module")
def seeded_model() -> torch.nn.Module:
    """OSNet-AIN x1.0 at a fixed random init.

    Ruling 157: "seeded randomly-initialised OSNet-AIN if the checkpoint is
    absent." The CPU runner has no model zoo, so the checkpoint branch cannot run
    there. That is sound because this hop is *graph* fidelity — does the ONNX
    reproduce the PyTorch graph — which holds identically at random weights; the
    checkpoint's real vectors are the GPU parity run's job. ``manual_seed`` makes
    the weights the test's, not the host's, so the cosine is reproducible.
    """
    torch.manual_seed(1234)
    return export_reid.create_osnet_ain_x1_0().eval()


class TestOnnxExportFidelity:
    def test_exported_onnx_matches_pytorch_on_real_crops(
        self, seeded_model: torch.nn.Module, tmp_path: Path
    ) -> None:
        crops = [(CROPS_DIR / n) for n in FIXED_CROPS]
        missing = [str(p) for p in crops if not p.exists()]
        assert not missing, f"committed re-ID crop fixture absent: {missing}"

        tensors = [_served_tensor(p) for p in crops]

        onnx_path = tmp_path / "model.onnx"
        export_reid.export_to_onnx(seeded_model, str(onnx_path))
        assert onnx_path.exists() and onnx_path.stat().st_size > 0

        # Structure first: a graph onnx.checker rejects is a worse failure than a
        # low cosine and should say so rather than surface as a numeric miss.
        onnx.checker.check_model(onnx.load(str(onnx_path)))

        # CPUExecutionProvider explicitly. The GPU image ships onnxruntime-gpu, so
        # an implicit provider list would ride CUDA whenever a GPU is merely
        # visible, and ruling 106 closed the CUDA EP on Blackwell — the export's
        # own check must not become the failure it exists to catch.
        session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name

        # Non-vacuity BEFORE the gate: a constant or all-zero embedding gives cosine
        # 1.0 with everything, so "every crop >= 0.999" would pass on a network that
        # outputs the same vector for every image. Prove the crops are distinguishable
        # in PyTorch first; then the ONNX agreement is agreement about a real signal.
        with torch.inference_mode():
            pt_vecs = [seeded_model(torch.from_numpy(t)).numpy()[0] for t in tensors]
        assert all(np.abs(v).sum() > 0 for v in pt_vecs), "a crop embedded to all-zero"
        assert not np.allclose(pt_vecs[0], pt_vecs[1]), "two distinct crops embedded identically"
        assert all(v.shape == (export_reid.EMBEDDING_DIM,) for v in pt_vecs)

        sims: list[float] = []
        for t in tensors:
            onnx_out = session.run(None, {input_name: t})[0][0]
            with torch.inference_mode():
                pt_out = seeded_model(torch.from_numpy(t)).numpy()[0]
            assert onnx_out.shape == pt_out.shape
            sims.append(_cosine(pt_out, onnx_out))

        # The gate itself, per crop. min, not mean — ruling 68 is a floor.
        assert min(sims) >= PARITY_GATE, (
            f"exported ONNX diverges from PyTorch: per-crop cosine "
            f"{[round(s, 6) for s in sims]}, min {min(sims):.6f} < {PARITY_GATE}"
        )

    def test_the_validation_helper_no_longer_returns_true_when_deps_are_present(
        self, seeded_model: torch.nn.Module, tmp_path: Path
    ) -> None:
        """The regression that shipped O2.4 was ``validate_onnx`` returning True on a
        file it could not read, because onnx/onnxruntime were absent and the
        ImportError branch answered True. With the deps pinned in the lock this
        session proves the branch that ran was the skip: a real export validates
        True on its own merits, and the SAME helper on a nonexistent path must
        RAISE rather than answer True. That asymmetry is the whole false comfort —
        if this ever goes back to returning True for garbage, the pin goes red.
        """
        real = tmp_path / "ok.onnx"
        export_reid.export_to_onnx(seeded_model, str(real))
        assert export_reid.validate_onnx(seeded_model, str(real)) is True

        # The exact exception measured on this host with the deps present: onnx.load
        # raises FileNotFoundError for the missing file. Pinned rather than
        # `pytest.raises(Exception)` so the assertion cannot be satisfied by an
        # unrelated error escaping, and so no suppression comment is needed.
        with pytest.raises(FileNotFoundError):
            result = export_reid.validate_onnx(seeded_model, str(tmp_path / "nope.onnx"))
            raise AssertionError(
                f"validate_onnx answered {result!r} for a file that does not exist "
                "— the absent-dep ImportError branch is back"
            )
