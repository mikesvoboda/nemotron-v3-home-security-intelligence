"""Unit tests for the ONNX face-recognition embedding loader (Task 3b).

Owner ruling (F11, 2026-09-26), condition 1: the extractor is a model-zoo
loader against a fixed interface — aligned face crop in, L2-normalized
512-d vector out — running on **CPU onnxruntime**, with "weights absent
means unavailable." No specific weights are hard-wired: the license review
is still open, so this slice proves the INTERFACE with a deterministic fake
and the degradation path with real absence (no onnxruntime install needed,
no weights on disk).

What the fake proves that a mock wouldn't: the normalization is computed by
the loader (a fake session returning an unnormalized vector still yields a
unit vector), and the dimension guard rejects any candidate weights that do
not speak the gallery's 512-d space (F11 ruling 2: one embedding space end
to end).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import backend.services.face_recognizer_loader as frl


class FakeSession:
    """A deterministic onnxruntime-session stand-in: outputs are a pure
    function of the input bytes (no RNG), shaped like a real recognizer
    (single float32 output node)."""

    def __init__(self, out_dim: int = 512, normalize_side_effect: bool = False):
        self.out_dim = out_dim
        self.calls = 0
        # Real sessions do NOT normalize; the fake returns a long vector so
        # the loader's own L2 step is what the unit test measures.
        self._normalize_side_effect = normalize_side_effect

    def get_inputs(self):
        return [type("I", (), {"name": "input", "shape": [1, 3, 112, 112]})()]

    def run(self, _out, feeds):
        self.calls += 1
        arr = np.asarray(next(iter(feeds.values())), dtype=np.float32)
        # deterministic projection: hash-free, pure function of the pixels.
        # Fold the input to a length-out_dim vector of bucket means (array_split
        # so the pixel count need not divide), then a fixed mixing matrix built
        # from a linspace seed — same bytes in, same vector out.
        flat = arr.reshape(-1)
        buckets = np.array([b.mean() for b in np.array_split(flat, self.out_dim)])
        mixing = np.linspace(-1.0, 1.0, self.out_dim * self.out_dim, dtype=np.float32)
        mixing = mixing.reshape(self.out_dim, self.out_dim)
        proj = np.tanh(buckets @ mixing.T)
        raw = proj * 37.0  # deliberately NOT unit length
        return [raw.reshape(1, self.out_dim)]


@pytest.fixture
def crop() -> Image.Image:
    rng = np.random.default_rng(7)  # fixed seed: the fake's determinism is the point
    arr = rng.integers(0, 255, (112, 112, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


class TestExtractFaceEmbedding:
    def test_returns_l2_normalized_512d(self, crop: Image.Image) -> None:
        session = FakeSession()
        vec = frl.extract_face_embedding(session, crop)
        assert len(vec) == frl.FACE_EMBEDDING_DIM == 512
        assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-4

    def test_deterministic_for_the_same_crop(self, crop: Image.Image) -> None:
        session = FakeSession()
        a = frl.extract_face_embedding(session, crop)
        b = frl.extract_face_embedding(session, crop)
        assert a == b  # same bytes in, same vector out — no RNG anywhere

    def test_rejects_wrong_dimension_output(self, crop: Image.Image) -> None:
        """The gallery speaks 512-d; weights that emit anything else are a
        different space and must fail loud, never normalize and pass."""
        session = FakeSession(out_dim=256)
        with pytest.raises(frl.FaceRecognizerError, match="512"):
            frl.extract_face_embedding(session, crop)


class TestLoadFaceRecognizer:
    async def test_missing_weights_raises_unavailable(self, tmp_path: Path) -> None:
        with pytest.raises(frl.FaceRecognizerUnavailable):
            await frl.load_face_recognizer(str(tmp_path / "nothing-here"))

    async def test_empty_dir_raises_unavailable(self, tmp_path: Path) -> None:
        (tmp_path / "face-recognizer").mkdir()
        with pytest.raises(frl.FaceRecognizerUnavailable):
            await frl.load_face_recognizer(str(tmp_path / "face-recognizer"))

    async def test_model_id_carries_the_weights_file(self, tmp_path: Path, monkeypatch) -> None:
        """Ruling 2: the model id identifies the embedding space, so it must
        change when the weights pick changes — the weights filename is in it.
        onnxruntime itself is faked here (the sandbox has no onnx install)."""
        weights = tmp_path / "face-recognizer"
        weights.mkdir()
        (weights / "candidate-pick.onnx").write_bytes(b"fake-weight-bytes")

        class FakeOrt:
            class InferenceSession:
                def __init__(self, path, providers=None):
                    assert str(path).endswith("candidate-pick.onnx")
                    assert providers == ["CPUExecutionProvider"]
                    self._s = FakeSession()

                def get_inputs(self):
                    return self._s.get_inputs()

                def run(self, o, f):
                    return self._s.run(o, f)

        monkeypatch.setitem(__import__("sys").modules, "onnxruntime", FakeOrt)
        model = await frl.load_face_recognizer(str(weights))
        assert model["model_id"] == "face-recognizer@candidate-pick"
        assert model["session"] is not None

    async def test_import_error_becomes_unavailable(self, tmp_path: Path, monkeypatch) -> None:
        """onnxruntime absent (the sandbox/CI truth) is the ruling's
        "unavailable," not an ImportError escaping into a batch."""
        weights = tmp_path / "face-recognizer"
        weights.mkdir()
        (weights / "x.onnx").write_bytes(b"w")
        import builtins

        real_import = builtins.__import__

        def no_onnx(name, *a, **k):
            if name == "onnxruntime":
                raise ImportError("no onnxruntime")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", no_onnx)
        with pytest.raises(frl.FaceRecognizerUnavailable):
            await frl.load_face_recognizer(str(weights))


class TestLoaderRegistered:
    def test_face_recognizer_is_in_the_loader_map(self) -> None:
        from backend.services.model_zoo import _LOADER_MAP

        assert "face-recognizer" in _LOADER_MAP
        assert _LOADER_MAP["face-recognizer"] is frl.load_face_recognizer

    def test_models_yml_row_exists_weights_pending(self) -> None:
        """Owner condition 1: the catalog row exists as a separate choice,
        ledgered weights-pending; nothing in code hard-wires a licensee."""
        import yaml

        data = yaml.safe_load((Path(__file__).resolve().parents[4] / "models.yml").read_text())
        row = next(m for m in data["models"] if m["name"] == "face-recognizer")
        assert row["category"] == "embedding"
        assert row["vram_mb"] == 0  # CPU per the ruling — out of the VRAM budget
        assert row["required"] is False
        assert row["enabled"] is False  # until the license pick lands
        assert "license" in row["description"].lower()
