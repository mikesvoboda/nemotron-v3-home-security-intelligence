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

Re-ID honesty (updated by the full swap, ledger item 20): the store and the
probe now share the ONE OSNet-AIN x1.0 space, so the leg computes real
similarities. The honesty moved down a level — a gallery row is scored only
under its own model_id (compare_person_vectors), and a sentinel/foreign
gallery says "unavailable (re-enroll)", never a number.
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


class TestReIDLegRealSpace:
    """Slice C (ledger item 20): the leg is REAL now. Crops come from the
    detections whose frame the selector picked, the probe is the resident
    OSNet handle, and compare_person_vectors owns the one-space rule. These
    pins fake only the weights (the tier posture everywhere else)."""

    BELT = "osnet-ain-x1-0@osnet_ain_x1_0_msmt17@8a07e8da3894"

    @staticmethod
    def _wire_osnet(monkeypatch, handle, extract):
        import backend.services.osnet_loader as ol

        monkeypatch.setattr(ol, "get_reid_handle", lambda: handle)
        monkeypatch.setattr(ol, "extract_person_embedding", extract)

    @staticmethod
    def _handle(model_id=BELT):
        return {"model": None, "transform": None, "model_id": model_id}

    @staticmethod
    def _probe_vector():
        """THE probe vector — one fixed draw both the fake extractor and the
        gallery rows are built from, so cosine relations are exact, not
        luck."""
        v = np.random.default_rng(42).random(512).astype(np.float32)
        return v / np.linalg.norm(v)

    @staticmethod
    def _extract(model_dict, image, detection_id=None):  # noqa: ARG004
        async def _run():
            from backend.services.osnet_loader import PersonEmbeddingResult

            return PersonEmbeddingResult(
                embedding=TestReIDLegRealSpace._probe_vector(),
                detection_id=detection_id,
                model_id=model_dict.get("model_id"),
            )

        return _run()

    @staticmethod
    def _person_det(frame_path, det_id=7):
        return {
            "id": det_id,
            "object_type": "person",
            "file_path": frame_path,
            "bbox_x": 10,
            "bbox_y": 10,
            "bbox_width": 40,
            "bbox_height": 60,
        }

    @staticmethod
    async def _rows(rows):
        async def gallery(session):
            return rows

        return gallery

    async def test_match_names_and_percent(self, monkeypatch, face_frame) -> None:
        """Same belt, close vector -> the existing match grammar with the
        REAL similarity."""
        p = self._probe_vector()
        close = p + np.random.default_rng(7).normal(0, 0.02, 512).astype(np.float32)
        close = close / np.linalg.norm(close)
        rows = [(1, "Dad", close, self.BELT)]
        self._wire_osnet(monkeypatch, self._handle(), self._extract)
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[self._person_det(face_frame)],
            settings=Settings(),
            session=object(),
            gallery=await self._rows(rows),
        )
        assert "matches household member Dad" in text
        assert "% match" in text
        _assert_prompt_line(text)

    async def test_comparable_gallery_no_one_over_threshold(self, monkeypatch, face_frame) -> None:
        # A genuinely distant gallery row: zero-mean draw (the probe is all-
        # positive, so cosine lands near 0) — far under the 0.7 OSNet-space
        # threshold. The leg ran; this is a real observation the VLM may
        # act on.
        q = np.random.default_rng(11).normal(0.0, 1.0, 512).astype(np.float32)
        far = q / np.linalg.norm(q)
        assert abs(float(self._probe_vector() @ far)) < 0.3
        rows = [(1, "Dad", far, self.BELT)]
        self._wire_osnet(monkeypatch, self._handle(), self._extract)
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[self._person_det(face_frame)],
            settings=Settings(),
            session=object(),
            gallery=await self._rows(rows),
        )
        assert text == "no known-person re-ID matches"

    async def test_sentinel_gallery_is_re_enroll_NEVER_a_score(
        self, monkeypatch, face_frame
    ) -> None:
        from backend.core.vector_provenance import LEGACY_MODEL_ID

        rows = [(1, "Dad", self._probe_vector(), LEGACY_MODEL_ID)]
        self._wire_osnet(monkeypatch, self._handle(), self._extract)
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[self._person_det(face_frame)],
            settings=Settings(),
            session=object(),
            gallery=await self._rows(rows),
        )
        assert text == "unavailable (re-enroll)"
        assert "%" not in text  # never a score

    async def test_empty_gallery_is_no_gallery_not_no_matches(
        self, monkeypatch, face_frame
    ) -> None:
        """ "No matches" claims an observation; an unenrolled household has
        never been observed — "a stranger is outside" would be the lie."""
        self._wire_osnet(monkeypatch, self._handle(), self._extract)
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[self._person_det(face_frame)],
            settings=Settings(),
            session=object(),
            gallery=await self._rows([]),
        )
        assert text.lower().startswith(UNAVAILABLE)
        assert "no known-person" not in text
        _assert_prompt_line(text)

    async def test_handleless_probe_is_re_enroll(self, monkeypatch, face_frame) -> None:
        """A probe whose weights never named themselves cannot vouch for ANY
        row — beltless handle AND beltless extraction result (the handle's
        id still wins when it has one, so both halves must be mute here)."""

        async def _beltless_extract(model_dict, image, detection_id=None):
            from backend.services.osnet_loader import PersonEmbeddingResult

            return PersonEmbeddingResult(
                embedding=self._probe_vector(), detection_id=detection_id, model_id=None
            )

        rows = [(1, "Dad", self._probe_vector(), self.BELT)]
        self._wire_osnet(monkeypatch, self._handle(model_id=None), _beltless_extract)
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[self._person_det(face_frame)],
            settings=Settings(),
            session=object(),
            gallery=await self._rows(rows),
        )
        assert text == "unavailable (re-enroll)"
        assert "%" not in text

    async def test_weights_absent_is_default_phrase(self, monkeypatch, face_frame) -> None:
        import backend.services.osnet_loader as ol

        monkeypatch.setattr(ol, "get_reid_handle", lambda: None)
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[self._person_det(face_frame)],
            settings=Settings(),
            session=object(),
        )
        assert text == "unavailable: specialist did not run"
        # the zoo name is operator detail — log half, never the prompt
        assert "osnet" not in text.lower()
        _assert_prompt_line(text)

    async def test_no_person_crop_among_picks_is_no_frames_not_no_matches(
        self, monkeypatch, face_frame
    ) -> None:
        self._wire_osnet(monkeypatch, self._handle(), self._extract)
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[],
            settings=Settings(),
            session=object(),
        )
        assert text.lower().startswith(UNAVAILABLE)
        assert "no known-person" not in text

    async def test_non_person_detections_are_not_probed(self, monkeypatch, face_frame) -> None:
        self._wire_osnet(monkeypatch, self._handle(), self._extract)
        det = self._person_det(face_frame) | {"object_type": "car"}
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[det],
            settings=Settings(),
            session=object(),
        )
        assert text.lower().startswith(UNAVAILABLE)

    async def test_frame_outside_the_picks_is_not_probed(self, monkeypatch, face_frame) -> None:
        """The line describes exactly the frames the VLM sees (selector
        doctrine, same as the face leg)."""
        self._wire_osnet(monkeypatch, self._handle(), self._extract)
        text = await vs.collect_reid_text(
            frame_paths=["/some/other/frame.jpg"],
            detections=[self._person_det(face_frame)],
            settings=Settings(),
            session=object(),
        )
        assert text.lower().startswith(UNAVAILABLE)

    async def test_extraction_failure_never_raises(self, monkeypatch, face_frame) -> None:
        async def _boom(model_dict, image, detection_id=None):
            raise RuntimeError("CUDA blew up")

        rows = [(1, "Dad", self._probe_vector(), self.BELT)]
        self._wire_osnet(monkeypatch, self._handle(), _boom)
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[self._person_det(face_frame)],
            settings=Settings(),
            session=object(),
            gallery=await self._rows(rows),
        )
        # every crop failed — the leg did not observe anything (logged, then
        # the default phrase; "no matches" would be an invented observation)
        assert text.lower().startswith(UNAVAILABLE)
        assert "no known-person" not in text

    async def test_no_session_is_unavailable_not_no_matches(self, monkeypatch, face_frame) -> None:
        """Without the DB the gallery cannot answer — 'no matches' would
        claim nobody the household knows is present."""
        self._wire_osnet(monkeypatch, self._handle(), self._extract)
        text = await vs.collect_reid_text(
            frame_paths=[face_frame],
            detections=[self._person_det(face_frame)],
            settings=Settings(),
            session=None,
        )
        assert text.lower().startswith(UNAVAILABLE)
        assert "no known-person" not in text


class TestReIDLegGrammar:
    """reid_text's arms, pinned directly (the eval corpus builds them)."""

    def test_matches_none_is_re_enroll_line(self) -> None:
        assert vs.reid_text(None, None) == "unavailable (re-enroll)"

    def test_unavailable_reason_is_clean_line(self) -> None:
        line = vs.reid_text(None, "some internal reason")
        assert line == "unavailable: specialist did not run"

    def test_empty_matches_is_the_real_no_match_line(self) -> None:
        assert vs.reid_text([], None) == "no known-person re-ID matches"


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
        # The prompt line says only that the leg did not run. WHY it didn't
        # (the F12 call, the ledger row behind it) is operator context, not a
        # hint the VLM can act on — so it must NOT appear here; the
        # `not_included` counter label is what carries it.
        assert out["threat"].startswith(UNAVAILABLE)
        _assert_prompt_line(out["threat"])
        assert "f12" not in out["threat"].lower()
        assert "ledger" not in out["threat"].lower()


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


# ---------------------------------------------------------------------------
# Prompt hygiene (owner ruling 2026-09-26): specialist_outputs is VLM PROMPT
# text, not a diagnostics channel. An unavailable line tells the model that a
# specialist did not run — nothing else. The WHY (which weights, which space,
# which exception, which path) belongs to logs, metrics and the ledger.
# ---------------------------------------------------------------------------

#: Strings that must never reach the prompt: model/library names, wire or
#: file identifiers, and project vocabulary the model cannot act on. The
#: point of the list is the CLASS of leak, not a specific word — an
#: exception message interpolated into a line brings paths and package
#: names, and a "the store is CLIP-768 space, the probe is OSNet-512"
#: sentence brings engineering context the model cannot act on.
BANNED_IN_PROMPT = (
    "clip",
    "osnet",
    "triton",
    "onnx",
    "scrfd",
    "w600k",
    "arcface",
    "insightface",
    "model_zoo",
    "reid_service",
    "vlm_specialists",
    "personembedding",
    "fast_alpr",
    "fast-alpr",
    "ledger",
    "rev 7",
    "follow-up",
    "face-recognizer@",
    "/",
    "\\",
    ".py",
    "768",
    "512",
)

#: One short line. The owner's example is "reid: unavailable" — a sentence
#: with a causal clause is already too long for prompt text.
MAX_PROMPT_LINE = 48


def _assert_prompt_line(text: str) -> None:
    """One short, model-facing line: no internal names, no paths, no prose."""
    assert text.strip() == text, "a prompt line must not carry padding/newlines"
    assert "\n" not in text
    assert len(text) <= MAX_PROMPT_LINE, f"prompt line too long for the VLM: {text!r}"
    low = text.lower()
    leaked = [token for token in BANNED_IN_PROMPT if token in low]
    assert not leaked, f"internal names leaked into prompt text {text!r}: {leaked}"


class TestPromptHygiene:
    """Every unavailable output is a single short line with no internal
    names — and the reason it was withheld still reaches the log and a
    metric, so dropping it from the prompt costs no operator visibility."""

    async def test_face_weights_absent_is_a_clean_line(self, monkeypatch, face_frame) -> None:
        """A resident-manager read with NOTHING loaded = the F12 deploy
        without the two ONNX files: the leg cannot run."""
        _wire_manager(monkeypatch, _FakeManager())  # empty _loaded_models
        text = await vs.collect_face_text(
            frame_paths=[face_frame], settings=Settings(), session=None
        )
        assert text.lower().startswith(UNAVAILABLE)
        _assert_prompt_line(text)

    async def test_plate_leg_real_absent_extra_is_a_clean_line(self) -> None:
        """The sandbox/CI truth, unprefaked: the [alpr] extra is not
        installed, so the leg dies on the loader's error, whose message
        names a package and a pip index hint. That message used to be
        interpolated straight into the prompt line."""
        text = await vs.collect_plate_text(frame_paths=[])
        assert text.lower().startswith(UNAVAILABLE)
        _assert_prompt_line(text)

    async def test_reid_unavailable_is_a_clean_line(self) -> None:
        text = await vs.collect_reid_text()
        assert text.lower().startswith(UNAVAILABLE)
        _assert_prompt_line(text)

    async def test_threat_slot_is_a_clean_line(self) -> None:
        text = await vs.collect_threat_text(frame_paths=[])
        assert text.lower().startswith(UNAVAILABLE)
        _assert_prompt_line(text)

    async def test_stage_belt_line_is_clean(self, monkeypatch) -> None:
        async def boom(**_kwargs):
            raise RuntimeError("Traceback (most recent call last): /backend/services/x.py")

        monkeypatch.setattr(vs, "collect_face_text", boom)
        monkeypatch.setattr(vs, "collect_plate_text", boom)
        monkeypatch.setattr(vs, "collect_reid_text", boom)
        out = await vs.collect_specialist_outputs(
            key_frame_paths=[], settings=Settings(), session=None
        )
        for value in out.values():
            assert value.lower().startswith(UNAVAILABLE)
            _assert_prompt_line(value)

    async def test_reason_still_reaches_the_log(self, monkeypatch, face_frame) -> None:
        """What the prompt loses, the operator keeps: the withheld reason is
        logged, so a degraded specialist is still diagnosable."""
        logged: list[tuple[str, dict]] = []

        class _SpyLogger:
            def warning(self, msg, **kw):
                logged.append((msg, kw))

            def info(self, msg, **kw):
                logged.append((msg, kw))

            def debug(self, msg, **kw):
                logged.append((msg, kw))

        monkeypatch.setattr(vs, "logger", _SpyLogger())
        _wire_manager(monkeypatch, _FakeManager())
        text = await vs.collect_face_text(
            frame_paths=[face_frame], settings=Settings(), session=None
        )
        _assert_prompt_line(text)
        assert logged, "the withheld reason must reach the log"
        blob = " ".join([m for m, _ in logged] + [str(k) for _, k in logged]).lower()
        assert "onnx" in blob or "weights" in blob or "install" in blob

    async def test_unavailable_increments_a_metric(self, monkeypatch, face_frame) -> None:
        """The other half of "put the reason in logs/metrics": a labelled
        counter, so a persistent degradation alerts without log-reading."""
        from backend.core.metrics import SPECIALIST_UNAVAILABLE_TOTAL

        def value():
            return SPECIALIST_UNAVAILABLE_TOTAL.labels(
                specialist="faces", reason="weights_absent"
            )._value.get()

        before = value()
        _wire_manager(monkeypatch, _FakeManager())
        await vs.collect_face_text(frame_paths=[face_frame], settings=Settings(), session=None)
        assert value() == before + 1

    async def test_space_mismatch_keeps_the_ruling_phrase_without_ids(
        self, monkeypatch, face_frame
    ) -> None:
        """F11 ruling 2's vocabulary ("unavailable (re-enroll)") survives —
        it is model-facing — but the model IDS behind it do not."""
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
        assert "re-enroll" in text
        assert "face-recognizer@" not in text
        assert "DEADBEEF" not in text
        _assert_prompt_line(text)
