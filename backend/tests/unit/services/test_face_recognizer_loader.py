"""Unit tests for the face-leg loaders (Task 3b, F12 ruling).

The face leg loads EXACTLY two ONNX files from InsightFace buffalo_l -
SCRFD-10G-KPS (`scrfd_10g_bnkps.onnx`, boxes + 5 landmarks) and the ArcFace
embedder (`w600k_r50.onnx`) - with onnxruntime on CPU, never via the
insightface package's FaceAnalysis (all five pack models on GPU is where the
old "~1.5 GB VRAM" figure came from). Both files are pinned by SHA-256 in
models.yml; the loader enforces the pin and reports UNAVAILABLE on any miss
(F12: absent weights mean unavailable; here "wrong bytes" is the same answer
as "no bytes").

The loader stays interface-first (F11 condition 1): aligned 112x112 crop in,
L2-normalized 512-d out; these tests run against deterministic fakes, so no
weights and no onnxruntime install are required in CI. The real-bytes proof is
a separate, weights-gated integration file (test_face_recognizer_live.py).

What the fakes prove that a mock wouldn't: the loader's OWN normalization
(session returns x37.0, the unit vector still comes out), its OWN 512-d guard
(F11 ruling 2: one embedding space - wrong dim fails loud), its OWN distance
decoding and NMS for SCRFD (fake per-stride maps with a hand-placed anchor),
and the ArcFace 5-point alignment (a pure similarity transform maps the eyes
onto the template).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
from PIL import Image

import backend.services.face_recognizer_loader as frl

SCRFD_SHA = "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91"
W600K_SHA = "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43"


class FakeEmbedSession:
    """onnxruntime-session stand-in for the embedder: outputs are a pure
    function of the input bytes (no RNG), shaped like w600k_r50 (single
    float32 1xD output node) - and deliberately NOT unit length, so the
    loader's own L2 step is what the test measures."""

    def __init__(self, out_dim: int = 512):
        self.out_dim = out_dim
        self.calls = 0

    def get_inputs(self):
        return [type("I", (), {"name": "input.1", "shape": [None, 3, 112, 112]})()]

    def run(self, _out, feeds):
        self.calls += 1
        arr = np.asarray(next(iter(feeds.values())), dtype=np.float32)
        flat = arr.reshape(-1)
        buckets = np.array([b.mean() for b in np.array_split(flat, self.out_dim)])
        mixing = np.linspace(-1.0, 1.0, self.out_dim * self.out_dim, dtype=np.float32)
        mixing = mixing.reshape(self.out_dim, self.out_dim)
        proj = np.tanh(buckets @ mixing.T)
        raw = proj * 37.0  # real sessions do NOT normalize
        return [raw.reshape(1, self.out_dim)]


def write_weights(root: Path, name: str, content: bytes = b"fake-weight-bytes") -> Path:
    weights = root / name
    weights.write_bytes(content)
    return weights


@pytest.fixture
def crop() -> Image.Image:
    rng = np.random.default_rng(7)  # fixed seed: the fake's determinism is the point
    arr = rng.integers(0, 255, (112, 112, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


# ---------------------------------------------------------------------------
# models.yml: F12 names the two files and pins them; nothing license-related
# ---------------------------------------------------------------------------


class TestCatalogRows:
    @pytest.fixture(scope="class")
    def catalog(self) -> dict:
        import yaml

        data = yaml.safe_load((Path(__file__).resolve().parents[4] / "models.yml").read_text())
        return {m["name"]: m for m in data["models"]}

    def test_two_face_rows(self, catalog) -> None:
        assert {"face-detector-scrfd", "face-recognizer"} <= set(catalog)

    def test_rows_name_the_two_buffalo_files(self, catalog) -> None:
        assert catalog["face-detector-scrfd"]["runtime_file"] == "scrfd_10g_bnkps.onnx"
        assert catalog["face-recognizer"]["runtime_file"] == "w600k_r50.onnx"

    def test_rows_pinned_by_sha256(self, catalog) -> None:
        assert catalog["face-detector-scrfd"]["sha256"] == SCRFD_SHA
        assert catalog["face-recognizer"]["sha256"] == W600K_SHA

    def test_cpu_only_out_of_vram_budget(self, catalog) -> None:
        assert catalog["face-detector-scrfd"]["vram_mb"] == 0
        assert catalog["face-recognizer"]["vram_mb"] == 0
        assert catalog["face-recognizer"]["category"] == "embedding"
        assert catalog["face-detector-scrfd"]["category"] == "detection"

    def test_rows_enabled_now(self, catalog) -> None:
        """F12: the pick landed - these rows are live catalog entries, not
        placeholders. Absence of the WEIGHTS at deploy time is what degrades
        to unavailable (loader), not a disabled catalog row."""
        assert catalog["face-detector-scrfd"]["enabled"] is True
        assert catalog["face-recognizer"]["enabled"] is True

    def test_no_license_framing_left(self, catalog) -> None:
        """F12 ruling 2: licenses are not a selection criterion - the
        interim license_status field is gone and no face row talks about
        licensing."""
        for row in (catalog["face-detector-scrfd"], catalog["face-recognizer"]):
            assert "license_status" not in row
            assert "license" not in row["description"].lower()


# ---------------------------------------------------------------------------
# Embedding interface (F11 condition 1): crop in, unit 512-d out
# ---------------------------------------------------------------------------


class TestExtractFaceEmbedding:
    def test_returns_l2_normalized_512d(self, crop: Image.Image) -> None:
        session = FakeEmbedSession()
        vec = frl.extract_face_embedding(session, crop)
        assert len(vec) == frl.FACE_EMBEDDING_DIM == 512
        assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-4

    def test_deterministic_for_the_same_crop(self, crop: Image.Image) -> None:
        session = FakeEmbedSession()
        a = frl.extract_face_embedding(session, crop)
        b = frl.extract_face_embedding(session, crop)
        assert a == b  # same bytes in, same vector out - no RNG anywhere

    def test_rejects_wrong_dimension_output(self, crop: Image.Image) -> None:
        """The gallery speaks 512-d; weights that emit anything else are a
        different space and must fail loud, never normalize and pass."""
        session = FakeEmbedSession(out_dim=256)
        with pytest.raises(frl.FaceRecognizerError, match="512"):
            frl.extract_face_embedding(session, crop)

    def test_preprocess_is_neg_one_to_one_chw(self, crop: Image.Image) -> None:
        blob = frl.preprocess_face_crop(crop)
        assert blob.shape == (1, 3, 112, 112)
        assert blob.dtype == np.float32
        assert blob.min() >= -1.0001 and blob.max() <= 1.0001


# ---------------------------------------------------------------------------
# Loading: weights absent OR hash mismatch -> unavailable (F12)
# ---------------------------------------------------------------------------


class _FakeOrtModule:
    """sys.modules stand-in for onnxruntime (the sandbox/CI truth: the [face]
    extra is optional). InferenceSession records the exact path+providers."""

    last: ClassVar[dict] = {}

    class InferenceSession:
        def __init__(self, path, providers=None):
            _FakeOrtModule.last = {"path": str(path), "providers": providers}
            self._s = FakeEmbedSession()

        def get_inputs(self):
            return self._s.get_inputs()

        def run(self, o, f):
            return self._s.run(o, f)


@pytest.fixture
def fake_ort(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "onnxruntime", _FakeOrtModule)
    _FakeOrtModule.last = {}
    return _FakeOrtModule


class TestLoadFaceRecognizer:
    async def test_missing_weights_raises_unavailable(self, tmp_path: Path) -> None:
        with pytest.raises(frl.FaceRecognizerUnavailable):
            await frl.load_face_recognizer(str(tmp_path / "nothing-here" / "w600k_r50.onnx"))

    async def test_hash_mismatch_raises_unavailable(self, tmp_path: Path, fake_ort) -> None:
        """Wrong bytes are as unavailable as no bytes: a mirror that shipped a
        different build must not run and silently fork the gallery space."""
        weights = write_weights(tmp_path, "w600k_r50.onnx", b"someone-elses-build")
        with pytest.raises(frl.FaceRecognizerUnavailable, match="sha256"):
            await frl.load_face_recognizer(str(weights), expected_sha256=W600K_SHA)

    async def test_hash_match_loads_cpu_provider(self, tmp_path: Path, fake_ort) -> None:
        content = b"exact-bytes"
        weights = write_weights(tmp_path, "w600k_r50.onnx", content)
        model = await frl.load_face_recognizer(
            str(weights), expected_sha256=hashlib.sha256(content).hexdigest()
        )
        assert model["session"] is not None
        assert fake_ort.last["providers"] == ["CPUExecutionProvider"]  # CPU by ruling
        assert fake_ort.last["path"].endswith("w600k_r50.onnx")

    async def test_model_id_carries_file_and_hash(self, tmp_path: Path, fake_ort) -> None:
        """F11 ruling 2: model_id identifies the embedding space, so it must
        change when the weights bytes change - filename AND content hash ride
        it, which is what makes the matcher's re-enroll rule enforceable."""
        content = b"exact-bytes"
        weights = write_weights(tmp_path, "w600k_r50.onnx", content)
        sha = hashlib.sha256(content).hexdigest()
        model = await frl.load_face_recognizer(str(weights), expected_sha256=sha)
        assert model["model_id"] == f"face-recognizer@w600k_r50@{sha[:12]}"

    async def test_model_id_without_pin_still_carries_file(self, tmp_path: Path, fake_ort) -> None:
        weights = write_weights(tmp_path, "w600k_r50.onnx")
        model = await frl.load_face_recognizer(str(weights))
        assert model["model_id"] == "face-recognizer@w600k_r50"

    async def test_import_error_becomes_unavailable(self, tmp_path: Path, monkeypatch) -> None:
        """onnxruntime absent (the sandbox/CI truth) is the ruling's
        'unavailable,' not an ImportError escaping into a batch."""
        weights = write_weights(tmp_path, "w600k_r50.onnx")
        import builtins

        real_import = builtins.__import__

        def no_onnx(name, *a, **k):
            if name == "onnxruntime":
                raise ImportError("no onnxruntime")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", no_onnx)
        with pytest.raises(frl.FaceRecognizerUnavailable):
            await frl.load_face_recognizer(str(weights))


# ---------------------------------------------------------------------------
# SCRFD detection (F12): distance-decoded boxes + 5 landmarks, threshold, NMS
# ---------------------------------------------------------------------------


class FakeScrfdSession:
    """Hand-placed single detection for a 64x64 input, in the REAL buffalo
    scrfd output layout: per stride, flat anchor-major (N_anchors, C) arrays
    (verified against scrfd_10g_bnkps.onnx: stride 8 at 640 gives (12800, 1)
    scores / (12800, 4) dbox / (12800, 10) dkps; anchors per cell = 2, row
    order = (row, col, anchor)).

    At 64x64: stride 8 -> 8x8 cells x 2 anchors = 128 rows. The anchor at
    (row 2, col 3, anchor 0) -> center (x, y) = (24, 16). Raw distances
    (1, 1, 2, 2) x stride 8 -> box (16, 8, 40, 32). Anchor 1 of the SAME cell
    carries the same box (IoU 1.0) so the NMS pin has real work.
    """

    def get_inputs(self):
        return [type("I", (), {"name": "input.1", "shape": [1, 3, "?", "?"]})()]

    @staticmethod
    def _flat_map(n_rows: int, channels: int) -> np.ndarray:
        return np.zeros((n_rows, channels), np.float32)

    def run(self, _out, feeds):
        blob = np.asarray(next(iter(feeds.values())), dtype=np.float32)
        h_in, w_in = blob.shape[2], blob.shape[3]
        outs_s, outs_b, outs_k = [], [], []
        for stride in (8, 16, 32):
            h, w = h_in // stride, w_in // stride
            n = h * w * 2
            outs_s.append(self._flat_map(n, 1))
            outs_b.append(self._flat_map(n, 4))
            outs_k.append(self._flat_map(n, 10))
        if (h_in, w_in) != (64, 64):
            return outs_s + outs_b + outs_k
        # Row order matches the reference anchor grid: stack([centers]*2,
        # axis=1).reshape(-1, 2) interleaves per CELL -> index =
        # (row * W + col) * 2 + anchor, with W = 8 at stride 8.
        row, col = 2, 3
        primary = (row * 8 + col) * 2 + 0
        duplicate = (row * 8 + col) * 2 + 1
        outs_s[0][primary, 0] = 0.99
        outs_s[0][duplicate, 0] = 0.90
        outs_b[0][primary] = np.float32([1.0, 1.0, 2.0, 2.0])
        outs_b[0][duplicate] = np.float32([1.0, 1.0, 2.0, 2.0])
        outs_k[0][primary, :] = np.tile(np.float32([0.5, 0.5]), 5)
        outs_k[0][duplicate, :] = np.tile(np.float32([0.5, 0.5]), 5)
        return outs_s + outs_b + outs_k  # scores(3), dboxes(3), dkps(3)


def _image(w: int, h: int) -> Image.Image:
    rng = np.random.default_rng(3)
    return Image.fromarray(rng.integers(0, 255, (h, w, 3), dtype=np.uint8), "RGB")


class TestDetectFaces:
    def test_decodes_distance_and_landmarks(self) -> None:
        faces = frl.detect_faces(FakeScrfdSession(), _image(64, 64), input_size=(64, 64))
        assert len(faces) == 1
        face = faces[0]
        assert face.bbox == pytest.approx((16, 8, 40, 32), abs=1.0)
        assert face.score == pytest.approx(0.99)
        assert face.landmarks is not None and face.landmarks.shape == (5, 2)
        assert face.landmarks[0] == pytest.approx((28, 20), abs=1.0)

    def test_nms_collapses_the_duplicate_anchor(self) -> None:
        """Without NMS the two same-cell anchors above would both cross the
        threshold and one face would report twice."""
        faces = frl.detect_faces(FakeScrfdSession(), _image(64, 64), input_size=(64, 64))
        assert len(faces) == 1

    def test_threshold_filters_low_scores(self) -> None:
        faces = frl.detect_faces(
            FakeScrfdSession(), _image(64, 64), input_size=(64, 64), threshold=0.95
        )
        # 0.90 duplicate already gone; 0.99 is the only survivor either way -
        # raise the bar and NOTHING survives:
        faces_high = frl.detect_faces(
            FakeScrfdSession(), _image(64, 64), input_size=(64, 64), threshold=0.995
        )
        assert len(faces_high) == 0
        assert len(faces) == 1


# ---------------------------------------------------------------------------
# Alignment: ArcFace 5-point template (F12), numpy reference transform
# ---------------------------------------------------------------------------


class TestAlignFaceCrop:
    """A real SCRFD landmark set on a real face is approximately consistent
    with the ArcFace template under ONE similarity transform — so the honest
    test is: synthesize landmarks by transforming the template (scale,
    rotate, translate a known amount), then the fit must map them back."""

    @staticmethod
    def _face_landmarks(scale: float, deg: float, tx: float, ty: float) -> np.ndarray:
        theta = np.deg2rad(deg)
        rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        tmpl = np.asarray(frl.ARCFACE_TEMPLATE, dtype=np.float32)
        return (scale * (tmpl @ rot.T) + np.array([tx, ty], dtype=np.float32)).astype(np.float32)

    def test_maps_landmarks_onto_the_template(self) -> None:
        landmarks = self._face_landmarks(scale=2.5, deg=10.0, tx=40.0, ty=60.0)
        img = np.zeros((400, 400, 3), np.uint8)
        crop = frl.align_face_crop(img, landmarks)
        assert crop.size == (112, 112)
        t = frl.alignment_transform(landmarks)
        for i in range(5):
            assert t.apply(landmarks[i]) == pytest.approx(frl.ARCFACE_TEMPLATE[i], abs=1.0)

    def test_transform_is_a_similarity_transform(self) -> None:
        """Scale + rotation + translation only: the eye-distance in the fit
        must equal the template's eye-distance (the alignment's whole job)."""
        landmarks = self._face_landmarks(scale=1.7, deg=-25.0, tx=10.0, ty=5.0)
        t = frl.alignment_transform(landmarks)
        p0 = t.apply(landmarks[0])
        p1 = t.apply(landmarks[1])
        tmpl_dist = float(
            np.linalg.norm(
                np.asarray(frl.ARCFACE_TEMPLATE[0]) - np.asarray(frl.ARCFACE_TEMPLATE[1])
            )
        )
        assert float(np.linalg.norm(np.asarray(p1) - np.asarray(p0))) == pytest.approx(
            tmpl_dist, abs=0.5
        )

    def test_align_warp_moves_a_marked_eye(self) -> None:
        """The crop's pixel content must follow the transform: paint a black
        eye at the left-landmark position on a white image and check the
        aligned crop goes dark at the template's left eye (min, not mean: the
        painted blob is smaller than the template-space patch at scale > 1)."""
        landmarks = self._face_landmarks(scale=2.0, deg=0.0, tx=30.0, ty=30.0)
        img = np.full((300, 300, 3), 255, np.uint8)
        lx, ly = round(float(landmarks[0][0])), round(float(landmarks[0][1]))
        img[ly - 2 : ly + 3, lx - 2 : lx + 3] = 0
        crop = np.asarray(frl.align_face_crop(img, landmarks))
        tx, ty = round(frl.ARCFACE_TEMPLATE[0][0]), round(frl.ARCFACE_TEMPLATE[0][1])
        patch = crop[ty - 3 : ty + 4, tx - 3 : tx + 4]
        assert patch.min() < 64  # the eye landed on the template's eye
        # ...and NOT elsewhere: the nose template point (no paint there) stays white.
        nx, ny = round(frl.ARCFACE_TEMPLATE[2][0]), round(frl.ARCFACE_TEMPLATE[2][1])
        assert crop[ny - 2 : ny + 3, nx - 2 : nx + 3].mean() > 200


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------


class TestLoaderRegistered:
    def test_both_face_loaders_in_the_map(self) -> None:
        from backend.services.model_zoo import _LOADER_MAP

        assert _LOADER_MAP["face-recognizer"] is frl.load_face_recognizer
        assert _LOADER_MAP["face-detector-scrfd"] is frl.load_face_detector
