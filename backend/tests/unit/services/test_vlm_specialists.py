"""Unit tests for the rev-6 VLM specialist stage (Task 3b, F11 ruling).

The specialist stage runs face / plate / re-ID over the batch's key frames and
emits ONE short text per specialist into AssessInput.specialist_outputs —
production fills them, replay reads them from the stored snapshot (ruling 4:
the snapshot is their only carrier; the VLM never originates them).

What these tests pin, per the owner's ruling (2026-09-26):

* Condition 3 — FOUR face outcomes, not two: match / unknown / not_identifiable
  / unavailable. classify_face_outcome is the pure decision; the hard rule is
  that "unknown" is NEVER emitted for a crop failing the config quality gate
  (an S2 false-positive driver — "unknown" pushes the VLM toward alarm).
  The gate's threshold comes from config (face_min_quality), never a constant.
* Condition 2 — one embedding space: the stage reads model_id off the loaded
  recognizer; gallery vectors carry a different id ⇒ "unavailable (re-enroll)",
  never a score (the matcher-level half is the FaceEmbedding.model_id pin).
* Condition 1 degradation — a missing model, an ImportError, or any specialist
  exception yields the text "unavailable", never a raise: the specialist stage
  feeds the verdict and must never block it (spec §6).
* Text shape: one short line per specialist, numbers real ("2 people",
  similarity percent), no bytes, no paths (spec §6 privacy). The gate comes
  from config (face_min_size_px + face_scrfd_threshold), never a constant.

Re-ID honesty: the entity store (household PersonEmbedding) is CLIP-768-space
(reid_service.generate_embedding); the resident Triton reid model emits
OSNet-512. A cross-space cosine would be noise, so until that ledgered gap is
closed, match_against_person_embeddings returns "seen_before unknown" plus the
raw vector — a score here would be a lie.
"""

from __future__ import annotations

import pytest

import backend.services.vlm_specialists as vs
from backend.core.config import Settings

UNAVAILABLE = "unavailable"


GATE = {"min_px": 40, "min_score": 0.6}


def _classify(face_px, scrfd_score, match):
    return vs.classify_face_outcome(face_px=face_px, scrfd_score=scrfd_score, match=match, **GATE)


class TestFourFaceOutcomes:
    """classify_face_outcome: F12's four outcomes as a pure function. The
    gate is size + SCRFD score (both config-fed by the caller); a crop that
    fails it is never `unknown`."""

    def test_known_face_yields_name_and_score(self) -> None:
        outcome = _classify(80, 0.9, {"matched": True, "person_name": "Dad", "similarity": 0.91})
        assert outcome.kind == "match"
        assert outcome.person_name == "Dad"
        assert outcome.similarity == 0.91

    def test_good_crop_no_match_yields_unknown(self) -> None:
        outcome = _classify(80, 0.9, {"matched": False, "person_name": None, "similarity": 0.2})
        assert outcome.kind == "unknown"

    def test_quality_gate_failure_is_not_identifiable_NEVER_unknown(self) -> None:
        """The hard rule (S2 driver): the owner's tiny/night face — a crop
        under the gate must not read "unknown" even though it also has no
        match. 'unknown' pushes the VLM toward alarm."""
        outcome = _classify(18, 0.3, {"matched": False, "person_name": None, "similarity": 0.1})
        assert outcome.kind == "not_identifiable"

    def test_gate_is_inclusive_at_both_edges(self) -> None:
        outcome = _classify(40, 0.6, {"matched": False, "person_name": None, "similarity": 0.1})
        assert outcome.kind == "unknown"
        outcome = _classify(39, 0.9, {"matched": False, "person_name": None, "similarity": 0.1})
        assert outcome.kind == "not_identifiable"
        outcome = _classify(80, 0.59, {"matched": False, "person_name": None, "similarity": 0.1})
        assert outcome.kind == "not_identifiable"

    def test_unavailable_is_a_class_not_a_score(self) -> None:
        outcome = vs.FaceUnavailable(reason="weights absent")
        assert outcome.kind == "unavailable"
        assert "weights" in outcome.reason


class TestFaceText:
    def test_match_text_names_the_person(self) -> None:
        text = vs.face_text([vs.FaceOutcome(kind="match", person_name="Dad", similarity=0.91)])
        assert "Dad" in text
        assert "91%" in text

    def test_counts_stay_out_of_unknown_when_gate_failed(self) -> None:
        """'1 unknown face' built from a night/tiny crop is exactly the S2
        false-positive driver — the counts line must say '2 face(s) not
        identifiable' instead."""
        faces = [
            vs.FaceOutcome(kind="not_identifiable"),
            vs.FaceOutcome(kind="not_identifiable"),
        ]
        text = vs.face_text(faces)
        assert "unknown" not in text.lower()
        assert "2" in text

    def test_mixed_census(self) -> None:
        faces = [
            vs.FaceOutcome(kind="match", person_name="Mom", similarity=0.88),
            vs.FaceOutcome(kind="unknown"),
            vs.FaceOutcome(kind="not_identifiable"),
        ]
        text = vs.face_text(faces)
        assert "Mom" in text
        assert "1 unknown" in text
        assert "not identifiable" in text

    def test_unavailable_never_writes_unknown(self) -> None:
        text = vs.face_text([vs.FaceUnavailable(reason="face-recognizer weights absent")])
        assert text.lower().startswith(UNAVAILABLE)
        assert "unknown" not in text.lower()

    def test_no_faces_is_not_unavailable(self) -> None:
        """Zero faces detected is a REAL observation (the camera saw no one),
        distinct from the specialist not having run."""
        assert vs.face_text([]) == "0 faces detected"


class TestQualityGateComesFromConfig:
    """F12 Task 3b: the gate is a MINIMUM FACE SIZE plus the SCRFD SCORE,
    both from config (AdaFace/CR-FIQA are ledgered later items, not built)."""

    def test_face_gate_settings_exist_with_defaults(self) -> None:
        settings = Settings()
        assert settings.face_min_size_px == 40  # a 40-px crop is borderline-identifiable
        assert settings.face_scrfd_threshold == 0.6

    def test_face_gate_settings_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FACE_MIN_SIZE_PX", "64")
        monkeypatch.setenv("FACE_SCRFD_THRESHOLD", "0.8")
        fresh = Settings()
        assert fresh.face_min_size_px == 64
        assert fresh.face_scrfd_threshold == 0.8

    def test_face_match_threshold_setting_exists(self) -> None:
        settings = Settings()
        assert settings.face_match_threshold == 0.68  # DEFAULT_MATCH_THRESHOLD precedent

    def test_gate_passes_on_size_AND_score(self) -> None:
        """Both knobs feed passes_quality_gate; each alone is enough to fail
        (a big face the detector barely believes, or a confident tiny face —
        the night/tiny case the owner names)."""
        assert vs.passes_quality_gate(face_px=80, score=0.9, min_px=40, min_score=0.6)
        assert not vs.passes_quality_gate(face_px=30, score=0.9, min_px=40, min_score=0.6)
        assert not vs.passes_quality_gate(face_px=80, score=0.4, min_px=40, min_score=0.6)


class TestGracefulAbsence:
    """Every collect_* helper degrades to UNAVAILABLE, never raises."""

    async def test_face_specialist_unavailable_without_any_inputs(self) -> None:
        text = await vs.collect_face_text(frame_paths=[], session=None, settings=Settings())
        assert text.lower().startswith(UNAVAILABLE)

    async def test_plate_specialist_unavailable_without_package(self, monkeypatch) -> None:
        # fast_alpr absent here (the [alpr] extra is not installed in the
        # sandbox venv) — the loader import guard must answer, not raise.
        text = await vs.collect_plate_text(frame_paths=[])
        assert text.lower().startswith(UNAVAILABLE)

    async def test_reid_specialist_honest_without_embedding_source(self) -> None:
        text = vs.reid_text(matches=None, unavailable_reason="no crop available")
        assert text.lower().startswith(UNAVAILABLE)

    async def test_collect_all_degrades_every_key_present(self) -> None:
        """Keys always exist (faces/plates/person_reid) so the prompt shows
        the gap per specialist instead of a silently missing line."""
        out = await vs.collect_specialist_outputs(
            key_frame_paths=[], detections=[], session=None, settings=Settings()
        )
        assert set(out) >= {"faces", "plates", "person_reid"}
        assert all(v.strip() for v in out.values())


# ---------------------------------------------------------------------------
# The F12 wiring: fake model-zoo handles stand in for the loaded face leg
# ---------------------------------------------------------------------------

import numpy as np  # noqa: E402  (below the pure tests that need no array lib)


class _FakeDetector:
    """SCRFD stand-in (the face_recognizer_loader tests own the decode math;
    this fake's only job is a deterministic detection at the REAL flat
    anchor-major layout for ANY input size): one face centered at
    (row 10, col 10) x stride 8, box 240 px (passes the default gate), score
    0.99, landmarks present."""

    box_dist = (10.0, 10.0, 20.0, 20.0)  # x stride 8 -> 240 px face

    def get_inputs(self):
        return [type("I", (), {"name": "input.1"})()]

    def run(self, _out, feeds):
        blob = np.asarray(next(iter(feeds.values())), dtype=np.float32)
        h_in, w_in = blob.shape[2], blob.shape[3]
        outs = [[], [], []]
        for level, stride in enumerate((8, 16, 32)):
            h, w = h_in // stride, w_in // stride
            n = h * w * 2
            s = np.zeros((n, 1), np.float32)
            b = np.zeros((n, 4), np.float32)
            k = np.zeros((n, 10), np.float32)
            if stride == 8:
                row, col = min(10, h - 1), min(10, w - 1)
                idx = (row * w + col) * 2
                s[idx, 0] = 0.99
                b[idx] = self.box_dist
                k[idx, :] = np.tile(np.float32([0.5, 0.5]), 5)
            outs[0].append(s)
            outs[1].append(b)
            outs[2].append(k)
        return outs[0] + outs[1] + outs[2]


class _TinyDetector(_FakeDetector):
    box_dist = (1.0, 1.0, 2.0, 2.0)  # -> 24 px: the night/tiny crop F12 names


class _FakeEmbed:
    """Embedder stand-in: output is a deterministic pure function of the
    input bytes (same crop bytes -> same vector), like w600k_r50's shape."""

    def get_inputs(self):
        return [type("I", (), {"name": "input.1"})()]

    def run(self, _out, feeds):
        arr = np.asarray(next(iter(feeds.values())), dtype=np.float32).reshape(-1)
        buckets = np.array([b.mean() for b in np.array_split(arr, 512)])
        mixing = np.linspace(-1.0, 1.0, 512 * 512, dtype=np.float32).reshape(512, 512)
        return [(np.tanh(buckets @ mixing.T) * 37.0).reshape(1, 512)]


class _FakeManager:
    """ModelManager stand-in: the private-dict shape the production
    consumers already read (the same pattern enrichment uses)."""

    def __init__(self, det=None, rec_id="face-recognizer@w600k_r50@4c06341c33c2"):
        loaded = {}
        if det is not None:
            loaded["face-detector-scrfd"] = {
                "session": det,
                "input_name": "input.1",
                "model_id": "face-detector-scrfd@scrfd_10g_bnkps@5838f7fe0536",
            }
            loaded["face-recognizer"] = {
                "session": _FakeEmbed(),
                "input_name": "input.1",
                "model_id": rec_id,
                "embedding_dim": 512,
            }
        self._loaded_models = loaded


@pytest.fixture
def face_frame(tmp_path):
    """A real PNG at a real path — the leg opens files exactly like
    production does with Detection.file_path."""
    from PIL import Image

    rng = np.random.default_rng(11)
    path = tmp_path / "frame-0001.jpg"
    Image.fromarray(rng.integers(0, 255, (480, 640, 3), dtype=np.uint8), "RGB").save(path)
    return str(path)


def _wire_manager(monkeypatch, manager):
    import backend.services.model_zoo as mz

    monkeypatch.setattr(mz, "get_model_manager", lambda: manager)


async def _fake_gallery(match):
    async def gallery(session, vector, threshold):
        return match

    return gallery


class TestFaceLegEndToEnd:
    """collect_face_text over a REAL file through fake sessions: the leg's
    own steps (open -> detect -> align -> embed -> classify -> text) all run;
    only the weights are faked."""

    async def test_big_face_good_score_no_match_is_unknown(self, monkeypatch, face_frame) -> None:
        _wire_manager(monkeypatch, _FakeManager(det=_FakeDetector()))
        text = await vs.collect_face_text(
            frame_paths=[face_frame], settings=Settings(), session=None
        )
        assert "1 unknown face" in text

    async def test_tiny_face_is_not_identifiable_NEVER_unknown(
        self, monkeypatch, face_frame
    ) -> None:
        """The F12 synthetic-case rule at the LEG level (not just the pure
        classifier): a 24-px crop — the owner's night scenario — must render
        'not identifiable'; 'unknown' is the word that drives S2."""
        _wire_manager(monkeypatch, _FakeManager(det=_TinyDetector()))
        text = await vs.collect_face_text(
            frame_paths=[face_frame], settings=Settings(), session=None
        )
        assert "not identifiable" in text
        assert "unknown" not in text.lower()

    async def test_match_names_the_person_with_percent(self, monkeypatch, face_frame) -> None:
        _wire_manager(monkeypatch, _FakeManager(det=_FakeDetector()))
        gallery = await _fake_gallery({"matched": True, "person_name": "Dad", "similarity": 0.91})
        text = await vs.collect_face_text(
            frame_paths=[face_frame],
            settings=Settings(),
            gallery=gallery,
            session=object(),  # any non-None: the fake gallery ignores it
        )
        assert "Dad" in text
        assert "91%" in text

    async def test_text_carries_no_paths_or_bytes(self, monkeypatch, face_frame) -> None:
        """Privacy (spec §6): frame paths and raw vectors never reach the
        prompt line, even the degraded ones."""
        _wire_manager(monkeypatch, _FakeManager(det=_FakeDetector()))
        text = await vs.collect_face_text(
            frame_paths=[face_frame], settings=Settings(), session=None
        )
        assert "/" not in text
        assert face_frame not in text

    async def test_missing_model_reads_unavailable_not_zero_faces(
        self, monkeypatch, face_frame
    ) -> None:
        """Weights absent (the sandbox/deploy truth) is "unavailable" — never
        "0 faces detected", which the VLM could read as an observation."""
        _wire_manager(monkeypatch, _FakeManager(det=None))
        text = await vs.collect_face_text(
            frame_paths=[face_frame], settings=Settings(), session=None
        )
        assert text.lower().startswith(UNAVAILABLE)
        assert "0 faces" not in text


class TestEmbeddingSpaceMismatch:
    """F11 ruling 2's stage half: a gallery whose stored vectors carry a
    different face-model id than the loaded weights yields
    "unavailable (re-enroll)" — NEVER any score or census."""

    async def test_different_gallery_id_degrades_to_re_enroll(
        self, monkeypatch, face_frame
    ) -> None:
        _wire_manager(monkeypatch, _FakeManager(det=_FakeDetector()))

        async def other_ids(session):
            return {"face-recognizer@w600k_r50@DEADBEEFdead"}

        monkeypatch.setattr(vs, "_gallery_model_ids", other_ids)
        text = await vs.collect_face_text(
            frame_paths=[face_frame],
            settings=Settings(),
            gallery=await _fake_gallery(None),
            session=object(),
        )
        assert text.lower().startswith(UNAVAILABLE)
        assert "re-enroll" in text
        assert "unknown" not in text.lower()

    async def test_matching_ids_proceed_normally(self, monkeypatch, face_frame) -> None:
        _wire_manager(monkeypatch, _FakeManager(det=_FakeDetector()))

        async def same_ids(session):
            return {"face-recognizer@w600k_r50@4c06341c33c2"}

        monkeypatch.setattr(vs, "_gallery_model_ids", same_ids)
        text = await vs.collect_face_text(
            frame_paths=[face_frame],
            settings=Settings(),
            gallery=await _fake_gallery(None),
            session=object(),
        )
        assert text == "1 unknown face(s)"

    async def test_no_model_id_column_yet_is_conservatively_open(
        self, monkeypatch, face_frame
    ) -> None:
        """FaceEmbedding.model_id ships with the enrollment migration; until
        it exists _gallery_model_ids returns set() and the leg works — pinned
        so the mismatch rule can't silently vanish with a schema change."""
        _wire_manager(monkeypatch, _FakeManager(det=_FakeDetector()))
        assert await vs._gallery_model_ids(None) == set()


class TestThreatExclusion:
    """The F12 threat call: NOT included (evidence in doc 14 §2; GATEWAY_-
    ENABLE_THREAT stays false). The key is absent by default, and the slot
    exists explicitly so a rev-7 YOLOE-26 hint has a wiring point."""

    async def test_threat_key_absent_by_default(self) -> None:
        out = await vs.collect_specialist_outputs(
            key_frame_paths=[], settings=Settings(), session=None
        )
        assert "threat" not in out
        assert set(out) == set(vs.SPECIALIST_KEYS)

    async def test_rev7_slot_renders_unavailable_when_asked(self) -> None:
        out = await vs.collect_specialist_outputs(
            key_frame_paths=[], settings=Settings(), session=None, run_threat=True
        )
        assert out["threat"].startswith(UNAVAILABLE)
        assert "not included" in out["threat"]


class TestNeverRaises:
    """The stage's last belt: even a broken leg function cannot fail the
    batch — every key still exists with a non-blank value."""

    async def test_gather_belt_holds_when_every_leg_explodes(self, monkeypatch) -> None:
        async def boom(**_kwargs):
            raise RuntimeError("a leg should never raise")

        monkeypatch.setattr(vs, "collect_face_text", boom)
        monkeypatch.setattr(vs, "collect_plate_text", boom)
        monkeypatch.setattr(vs, "collect_reid_text", boom)
        out = await vs.collect_specialist_outputs(
            key_frame_paths=[], settings=Settings(), session=None
        )
        assert set(out) >= {"faces", "plates", "person_reid"}
        assert all(UNAVAILABLE in v.lower() and v.strip() for v in out.values())
