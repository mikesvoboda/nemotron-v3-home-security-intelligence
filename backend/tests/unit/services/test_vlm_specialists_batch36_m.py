# TARGET-MODULE: backend.services.vlm_specialists
"""Battery M — campaign #12 of the ladder (batch-36): kill-real coverage for
``backend/services/vlm_specialists.py`` (336 survivors at 56.76% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, so every seam swap restores in ``finally``.

Honesty ledger — dispositions registered EQUIVALENT at authoring (the sweep
must show GREEN on exactly these unless the sweep proves otherwise; anything
else GREEN is a test gap):

* ``x__collect_face_texts__mutmut_31`` (``readable = False`` -> ``None``):
  the pre-loop initializer is only consumed by ``not readable`` truthiness —
  both falsy. (The in-loop ``= True`` -> ``None`` variant is NOT an
  equivalent — readable frames then read frames_unreadable; the sweep kills
  it, correctly.)
* ``x__collect_face_texts__mutmut_87`` (``match = None`` -> ``""``): ``match``
  is only read behind ``if session is not None`` (immediately rebound) or
  behind the ``if match and ...`` truthiness guard; both carriers falsy, no
  identity read.
* ``x__collect_reid_text__mutmut_66`` (``outcome_seen = None`` -> ``""``):
  the only consumer is ``is PersonMatchOutcome.NO_GALLERY`` and both sentinels
  are non-members; when the loop ran, ``probed > 0`` forces a real
  assignment before the read (``probed == 0`` returns first).
* ``x__collect_reid_text__mutmut_86/_87/_88`` (``probed = 1`` / ``-= 1`` /
  ``+= 2``): ``probed`` is only consumed by ``if probed == 0``; every
  non-zero variant behaves identically on the whole domain.
* ``x__bbox_crop__mutmut_61`` (``not is_valid or clamped is None`` -> ``and``):
  ``validate_and_clamp_bbox`` PAIRS its outputs — every invalid result
  carries ``clamped_bbox=None`` and every valid one a real box (verified in
  bbox_validation.py source, all five return arms) — so the discriminating
  arm (valid + None, or invalid + box) is empty on the callee's domain.
* ``x_plate_text__mutmut_30`` (``getattr(match, "matched", None)``): falsy
  default in a truthiness slot — an absent attr reads falsy under either
  default, a present one never consults it.
* ``x_collect_specialist_outputs__mutmut_34/_36`` (gather
  ``return_exceptions=None`` / kw dropped): the parameter default IS False
  and gather only truth-tests it.
* ``x_collect_specialist_outputs__mutmut_41/_44/_45`` (zip ``strict=None`` /
  dropped / ``False``): tasks and results are built in lockstep from the
  same dict — lengths can never differ, and every length-equal zip is
  identical under any falsy strict.
"""

import asyncio
import logging
import sys
import types

import backend.services.vlm_specialists as vs

#: default phrase a degraded line takes (never retype the module's literal:
#: these are pinned against the shipped module below)
DEFAULT_PHRASE = f"{vs.UNAVAILABLE}: specialist did not run"
RE_ENROLL_PHRASE = f"{vs.UNAVAILABLE} (re-enroll)"

_MISSING = object()


class _Box:
    """Attribute namespace for seam payloads."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _module_stub(mods):
    """Set attrs on modules; fake a module that is not imported yet.

    ``mods`` maps dotted-module -> {attr: value}. Returns a callable that
    restores sys.modules/attrs exactly (every seam the module body imports
    lives INSIDE the functions, so a call-time attribute swap reaches the
    render worlds too — the trampoline shares one module namespace).
    """
    undo = []
    for dotted, attrs in mods.items():
        mod = sys.modules.get(dotted)
        if mod is None:
            mod = types.ModuleType(dotted)
            sys.modules[dotted] = mod
            undo.append(("module", dotted, mod))
            parent, _, leaf = dotted.rpartition(".")
            if parent and parent in sys.modules and not hasattr(sys.modules[parent], leaf):
                setattr(sys.modules[parent], leaf, mod)
                undo.append(("parentattr", f"{parent}.{leaf}", mod))
        for key, val in attrs.items():
            old = getattr(mod, key, _MISSING)
            setattr(mod, key, val)
            undo.append(("attr", (mod, key), old))

    def restore():
        for kind, target, old in reversed(undo):
            if kind == "module":
                dotted, mod = target, old
                if sys.modules.get(dotted) is mod:
                    sys.modules.pop(dotted, None)
            elif kind == "parentattr":
                parent, leaf = target.rsplit(".", 1)
                holder = sys.modules.get(parent)
                if holder is not None and getattr(holder, leaf, None) is old:
                    delattr(holder, leaf)
            else:
                mod, key = target
                if old is _MISSING:
                    if hasattr(mod, key):
                        delattr(mod, key)
                else:
                    setattr(mod, key, old)

    return restore


def _logs():
    """Exact (level, message, extra, exc-class) capture on the module logger."""
    records = []

    class _Cap(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Cap()
    old_handlers = vs.logger.handlers[:]
    old_propagate = vs.logger.propagate
    old_level = vs.logger.level
    vs.logger.handlers[:] = [handler]
    vs.logger.propagate = False
    vs.logger.setLevel(logging.DEBUG)  # ambient level must not gate capture

    def restore():
        vs.logger.handlers[:] = old_handlers
        vs.logger.propagate = old_propagate
        vs.logger.setLevel(old_level)

    return records, restore


def _log_sig(records):
    out = []
    for r in records:
        extra = tuple(
            getattr(r, key, _MISSING) for key in ("specialist", "code", "detail", "det_id")
        )
        exc = None if r.exc_info is None else (r.exc_info[0],)
        out.append((r.levelname, r.getMessage(), extra, exc))
    return out


def _metrics_stub(seen):
    def _rec(spec, code):
        seen.append((spec, code))

    return {"backend.core.metrics": {"record_specialist_unavailable": _rec}}


# ---------------------------------------------------------------------------
# _unavailable_line: metric + log + phrase selection (8 keys)
# ---------------------------------------------------------------------------


def test_unavailable_line_default_and_phrase_map():
    # the phrase table is only reachable THROUGH _unavailable_line: an unknown
    # code reads the default phrase, space_mismatch reads the re-enroll phrase
    seen = []
    restore = _module_stub(_metrics_stub(seen))
    try:
        assert vs._unavailable_line("faces", "weights_absent") == DEFAULT_PHRASE
        assert seen == [("faces", "weights_absent")]
        seen.clear()
        assert vs._unavailable_line("person_reid", "space_mismatch") == RE_ENROLL_PHRASE
        assert seen == [("person_reid", "space_mismatch")]
    finally:
        restore()


def test_unavailable_line_log_only_when_detail():
    seen = []
    records, undo_log = _logs()
    restore = _module_stub(_metrics_stub(seen))
    try:
        vs._unavailable_line("plates", "leg_failed")
        assert _log_sig(records) == []  # no detail -> no log line
        vs._unavailable_line("plates", "leg_failed", detail="boom")
        got = _log_sig(records)
        assert got == [
            (
                "WARNING",
                "specialist unavailable",
                ("plates", "leg_failed", "boom", _MISSING),
                None,
            )
        ]
    finally:
        undo_log()
        restore()


# ---------------------------------------------------------------------------
# face_text (3 keys)
# ---------------------------------------------------------------------------


def test_face_text_match_percent_and_joiner():
    seen = []
    restore = _module_stub(_metrics_stub(seen))
    try:
        outcomes = [
            vs.FaceOutcome(kind="match", person_name="Ann", similarity=0.87),
            # 0.4999 separates *100 (49) from *101 (50) under int() truncation
            vs.FaceOutcome(kind="match", person_name="Di", similarity=0.4999),
            vs.FaceOutcome(kind="match", person_name="Zero", similarity=None),
            vs.FaceOutcome(kind="unknown"),
            vs.FaceOutcome(kind="unknown"),
            vs.FaceOutcome(kind="not_identifiable"),
        ]
        assert vs.face_text(outcomes) == (
            "known person Ann (87% match); known person Di (49% match); "
            "known person Zero (0% match); "
            "2 unknown face(s); 1 face(s) not identifiable (too small or low quality)"
        )
        assert vs.face_text([]) == "0 faces detected"
        assert vs.face_text([vs.FaceUnavailable("why", code="frames_unreadable")]) == DEFAULT_PHRASE
        assert seen[-1] == ("faces", "frames_unreadable")
    finally:
        restore()


# ---------------------------------------------------------------------------
# reid_text (3 keys)
# ---------------------------------------------------------------------------


def test_reid_text_grammar():
    seen = []
    records, undo_log = _logs()
    restore = _module_stub(_metrics_stub(seen))
    try:
        assert vs.reid_text([], None) == "no known-person re-ID matches"
        assert records == []  # the empty-matches line logs nothing
        assert vs.reid_text(None, "the reason") == DEFAULT_PHRASE
        # the reason must ride the LOG as detail (None/drop mutants go silent)
        assert _log_sig(records) == [
            (
                "WARNING",
                "specialist unavailable",
                ("person_reid", "unavailable", "the reason", _MISSING),
                None,
            )
        ]
        assert vs.reid_text(None, None) == RE_ENROLL_PHRASE
        assert seen[:2] == [("person_reid", "unavailable"), ("person_reid", "space_mismatch")]
        assert vs.reid_text([_Box(member_name="Ann", similarity=0.91)], None) == (
            "matches household member Ann (91% match)"
        )
        assert vs.reid_text([_Box(person_name="Bo")], None) == "matches household member Bo"
        assert vs.reid_text([_Box(notes="x")], None) == "matches household member known person"
        assert vs.reid_text([_Box(member_name=None, person_name=None, similarity=None)], None) == (
            "matches household member known person"
        )
    finally:
        undo_log()
        restore()


def test_reid_text_nonfloat_similarity_drops_pct():
    assert vs.reid_text([_Box(member_name="Ann", similarity=0.5)], None) == (
        "matches household member Ann (50% match)"
    )


# ---------------------------------------------------------------------------
# plate_text (12 keys)
# ---------------------------------------------------------------------------


def test_plate_text_unavailable_shortcircuit():
    seen = []
    restore = _module_stub(_metrics_stub(seen))
    try:
        assert vs.plate_text(["unavailable"], []) == DEFAULT_PHRASE
        assert seen == [("plates", "leg_failed")]
    finally:
        restore()


def test_plate_text_full_grammar():
    class _Hit:
        text = "ABC123"
        matched = True
        member_name = "Dad"
        vehicle_id = "v1"

    class _MatchFalse:
        text = "FALSEY"
        matched = False

    class _NoMember:
        text = "VONLY"
        matched = True
        member_name = None
        vehicle_id = "v2"

    class _NoVeh:
        text = "GENERIC"
        matched = True
        member_name = None
        vehicle_id = None

    class _AbsentAttrs:
        text = "ABSENT"
        matched = True
        member_name = None
        vehicle_id = None

    results = [
        "ABC123",
        _Hit(),
        "GONE",
        _MatchFalse(),
        _NoMember(),
        _NoVeh(),
        _AbsentAttrs(),
        "XYZ789",
    ]
    matches = [
        _Hit(),
        _Box(matched=True),  # NO text attr: default None key (2-arg -> raise)
        _Box(text="GONE", matched=True),
        _Box(text="FALSEY", matched=False),
        _NoMember(),
        _NoVeh(),
        _Box(text="ABSENT"),  # no matched attr at all -> falsy default
    ]
    assert vs.plate_text(results, matches) == (
        "ABC123 - household vehicle (Dad); ABC123 - household vehicle (Dad); "
        "GONE - household vehicle (household); FALSEY - not a household plate; "
        "VONLY - household vehicle (v2); GENERIC - household vehicle (household); "
        "ABSENT - not a household plate; XYZ789 - not a household plate"
    )


def test_plate_text_empty_results():
    assert vs.plate_text([], []) == "0 license plates detected"


# ---------------------------------------------------------------------------
# _face_frames (8 keys)
# ---------------------------------------------------------------------------


def test_face_frames_shapes():
    assert vs._face_frames(["a", _Box(file_path="b"), _Box(other="c"), _Box(file_path="")]) == [
        "a",
        "b",
    ]
    assert vs._face_frames([]) == []


# ---------------------------------------------------------------------------
# _gallery_model_ids (4 keys)
# ---------------------------------------------------------------------------


class _SqlSession:
    """Fake AsyncSession: records the SQL it is handed, answers with rows."""

    def __init__(self, rows, raises=None):
        self.sql = []
        self.rows = rows
        self.raises = raises

    async def execute(self, clause):
        self.sql.append(str(getattr(clause, "text", clause)))
        if self.raises is not None:
            raise self.raises
        return self.rows


def test_gallery_model_ids_sql_and_rows():
    seen = []
    restore = _module_stub(_metrics_stub(seen))
    try:
        session = _SqlSession([("a",), ("b",), (None,), ("",)])
        assert asyncio.run(vs._gallery_model_ids(session)) == {"a", "b"}
        assert session.sql == ["SELECT DISTINCT model_id FROM face_embeddings"]
        broken = _SqlSession([], raises=RuntimeError("no column"))
        assert asyncio.run(vs._gallery_model_ids(broken)) == set()  # pre-migration belt
        assert asyncio.run(vs._gallery_model_ids(None)) == set()
    finally:
        restore()


# ---------------------------------------------------------------------------
# _bbox_crop (28 keys)
# ---------------------------------------------------------------------------

_BBOX_CALLS = []


def _faithful_validator(bbox, width, height):
    """Reproduces validate_and_clamp_bbox's is_valid/clamped_bbox PAIRING:
    invalid results always carry clamped_bbox None, valid ones never."""
    _BBOX_CALLS.append((bbox, width, height))
    x1, y1, x2, y2 = bbox
    cx1, cy1 = max(0.0, x1), max(0.0, y1)
    cx2, cy2 = min(float(width), x2), min(float(height), y2)
    if cx2 - cx1 < 1.0 or cy2 - cy1 < 1.0:
        return _Box(is_valid=False, clamped_bbox=None)
    return _Box(is_valid=True, clamped_bbox=(cx1, cy1, cx2, cy2))


def _bbox_stub():
    return {"backend.services.bbox_validation": {"validate_and_clamp_bbox": _faithful_validator}}


class _FrameCrop:
    def __init__(self, mode, owner):
        self.mode = mode
        self.owner = owner

    def convert(self, mode):
        self.owner.convert_calls.append(mode)
        if mode != "RGB":
            raise ValueError(f"bad convert mode {mode!r}")
        return _Box(mode="RGB")


class _Frame:
    size = (200, 100)

    def __init__(self, crop_mode="L"):
        self.crop_calls = []
        self.convert_calls = []
        self.crop_mode = crop_mode

    def crop(self, box):
        self.crop_calls.append(box)
        return _FrameCrop(self.crop_mode, self)


def test_bbox_crop_dict_det_success_and_clamp():
    _BBOX_CALLS.clear()
    restore = _module_stub(_bbox_stub())
    try:
        frame = _Frame()
        det = {
            "bbox_x": 10.0,
            "bbox_y": 20.0,
            "bbox_width": 100.0,
            "bbox_height": 40.0,
        }
        out = vs._bbox_crop(frame, det)
        assert _BBOX_CALLS == [((10.0, 20.0, 110.0, 60.0), 200, 100)]
        assert frame.crop_calls == [(10, 20, 110, 60)]
        assert frame.convert_calls == ["RGB"]  # L crop must be converted
        assert out is not None and out.mode == "RGB"

        frame2 = _Frame(crop_mode="RGB")
        det2 = {
            "bbox_x": 50.0,
            "bbox_y": 60.0,
            "bbox_width": 80.0,  # x2=130 fits, y2=150 clamps to 100
            "bbox_height": 90.0,
        }
        vs._bbox_crop(frame2, det2)
        assert frame2.crop_calls == [(50, 60, 130, 100)]
        assert frame2.convert_calls == []  # already RGB: returned as-is
        frame3 = _Frame(crop_mode="RGB")
        vs._bbox_crop(frame3, det2)
        assert frame3.convert_calls == []
        assert frame3.crop_calls == [(50, 60, 130, 100)]

        frame4 = _Frame()
        assert vs._bbox_crop(frame4, {**det, "bbox_x": 10.0, "bbox_width": -20.0}) is None
        assert frame4.crop_calls == []  # invalid pair: crop NEVER attempted
        # an EMPTY-after-clamp box (is_valid False, clamped None) must not
        # reach frame.crop — the and-mutant would call crop(None-box) instead
        frame5 = _Frame()
        assert vs._bbox_crop(frame5, {**det, "bbox_x": 300.0}) is None
        assert frame5.crop_calls == []
    finally:
        restore()


def test_bbox_crop_object_det_and_missing_attr():
    _BBOX_CALLS.clear()
    restore = _module_stub(_bbox_stub())
    try:
        frame = _Frame()
        det = _Box(bbox_x=1.5, bbox_y=2.5, bbox_width=20.0, bbox_height=30.0)
        out = vs._bbox_crop(frame, det)
        assert frame.crop_calls == [(1, 2, 21, 32)]  # int() truncation pinned
        assert out.mode == "RGB"
        # a missing attr reads None via the default -> float(None) -> None,
        # NOT an AttributeError (kills the 2-arg getattr mutants)
        sparse = _Box(bbox_x=1.0, bbox_y=2.0, bbox_width=5.0)
        assert vs._bbox_crop(frame, sparse) is None
        assert (
            vs._bbox_crop(frame, _Box(bbox_x=float("nan"), bbox_y=0, bbox_width=5, bbox_height=5))
            is None
        )
        assert (
            vs._bbox_crop(frame, _Box(bbox_x=0, bbox_y=0, bbox_width=float("inf"), bbox_height=5))
            is None
        )
    finally:
        restore()


# ---------------------------------------------------------------------------
# _person_crops (35 keys)
# ---------------------------------------------------------------------------


def _person_dict(det_id=42, path="f1", **extra):
    base = {
        "object_type": "person",
        "file_path": path,
        "id": det_id,
        "bbox_x": 10.0,
        "bbox_y": 20.0,
        "bbox_width": 100.0,
        "bbox_height": 40.0,
    }
    base.update(extra)
    return base


def _person_obj(det_id=7, path="f1", **kw):
    fields = {
        "object_type": "person",
        "file_path": path,
        "id": det_id,
        "bbox_x": 10.0,
        "bbox_y": 20.0,
        "bbox_width": 100.0,
        "bbox_height": 40.0,
    }
    fields.update(kw)
    for drop in kw.pop("without", ()):
        fields.pop(drop, None)
    return _Box(**fields)


def test_person_crops_filters_and_order():
    stubs = {**_pil_stub2(open_raises=("bad",)), **_bbox_stub()}
    restore = _module_stub(stubs)
    try:
        dets = [
            _Box(object_type="car", file_path="f1"),  # non-person -> continue
            {"object_type": "car", "file_path": "f1"},
            _person_dict(det_id=42, path="f1"),  # dict person in picks
            _person_obj(det_id=7, path="f1"),  # object person in picks
            _person_dict(path="f9"),  # outside picks -> skip
            _person_dict(path=""),  # empty path -> skip
            _person_dict(path="bad"),  # unreadable -> skip (PIL stub raises)
            _Box(object_type="person"),  # no file_path attr at all -> skip
            _Box(object_type="person", file_path=None),  # None path -> skip
            _Box(id=1),  # NO object_type attr -> skipped (not person)
        ]
        picks = {"f1"}
        out = vs._person_crops(dets, picks)
        assert [(c.source, det_id) for c, det_id in out] == [("f1", "42"), ("f1", "7")]
        assert all(c.converted and c.mode == "RGB" for c, _ in out)
        assert all(c.box == (10, 20, 110, 60) for c, _ in out)  # clamped ints
        assert vs._person_crops(None, set()) == []
        assert vs._person_crops([], {"f1"}) == []
        # empty picks accept ANY path (kills the not-path/and polarity mutants)
        loose = vs._person_crops([_person_dict(path="whatever")], set())
        assert [det_id for _, det_id in loose] == ["42"]
        # an out-of-picks person BEFORE an in-picks one must not end the scan
        ordered = vs._person_crops(
            [_person_dict(path="f9"), _person_dict(det_id=9, path="f1")], picks
        )
        assert [det_id for _, det_id in ordered] == ["9"]
        # an object without an id defaults to "" (not None, not "None", not "XXXX")
        noid = vs._person_crops([_person_obj(without=("id",))], picks)
        assert [det_id for _, det_id in noid] == [""]
    finally:
        restore()


# ---------------------------------------------------------------------------
# seam fakes (face / osnet / household / alpr legs)
# ---------------------------------------------------------------------------


class FaceErr(Exception):
    pass


class _Crop:
    """What Image.open(...).crop(box) hands to _bbox_crop: mode + convert."""

    def __init__(self, mode, source, box, frame=None):
        self.mode = mode
        self.source = source
        self.box = box
        self.frame = frame

    def convert(self, mode):
        if self.frame is not None:
            self.frame.convert_calls.append(mode)
        if mode != "RGB":
            raise ValueError(f"bad convert mode {mode!r}")
        return _Box(mode="RGB", source=self.source, box=self.box, converted=True)


def _pil_stub2(open_raises=()):
    def open_frame(path):
        if path in open_raises:
            raise OSError(f"cannot read {path}")

        frame = _Box(path=path, size=(200, 100), mode="L", convert_calls=[])

        def load():
            return None

        def convert(mode):  # frame-level convert (not used by _bbox_crop path)
            frame.convert_calls.append(mode)
            if mode != "RGB":
                raise ValueError(f"bad convert mode {mode!r}")
            return _Box(mode="RGB", source=path, converted=True)

        def crop(box):
            frame.convert_calls.append(("crop", box))
            return _Crop("L", path, box, frame=frame)

        frame.load = load
        frame.convert = convert
        frame.crop = crop
        return frame

    return {"PIL": {"Image": _Box(open=open_frame)}}


def _face_stub(handles, faces, *, detect_raises=None, extract_raises=None):
    calls = {
        "detect": [],
        "align": [],
        "extract": [],
        "handles_calls": [],
        "detect_thresholds": [],
    }

    def detect_faces(session, image, *, threshold):
        calls["detect"].append((session, getattr(image, "path", image)))
        calls["detect_thresholds"].append(threshold)
        if detect_raises is not None:
            raise detect_raises
        return list(faces.pop(0)) if faces else []

    def align_face_crop(image, landmarks):
        calls["align"].append(getattr(image, "path", image))
        return _Box(crop_of=landmarks)

    def extract_face_embedding(session, crop):
        calls["extract"].append((session, crop))
        if extract_raises is not None:
            raise extract_raises
        return [0.1, 0.2, 0.3]

    def get_handles():
        calls["handles_calls"].append(1)
        return handles

    frl = _Box(
        detect_faces=detect_faces,
        align_face_crop=align_face_crop,
        extract_face_embedding=extract_face_embedding,
        get_face_leg_handles=get_handles,
        FaceRecognizerError=FaceErr,
        passes_quality_gate=lambda *, face_px, score, min_px, min_score: (
            face_px >= min_px and score >= min_score
        ),
    )
    return (
        {
            "backend.services.face_recognizer_loader": {
                "detect_faces": detect_faces,
                "align_face_crop": align_face_crop,
                "extract_face_embedding": extract_face_embedding,
                "get_face_leg_handles": get_handles,
                "FaceRecognizerError": FaceErr,
                "passes_quality_gate": frl.passes_quality_gate,
            },
            "backend.services.face_recognition_service": {
                "get_face_recognition_service": lambda: _Box(match_face=None),
            },
        },
        calls,
    )


SETTINGS = _Box(face_min_size_px=30, face_scrfd_threshold=0.6, face_match_threshold=0.35)
SESSION = _Box(name="fake-session")


def _face(*, bbox=(40.0, 10.0, 140.0, 100.0), score=0.9, landmarks=(1, 2, 3, 4, 5)):
    return _Box(bbox=bbox, score=score, landmarks=landmarks)


def _collect_face(frame_paths, *, settings=SETTINGS, gallery=None, session=None):
    if gallery is None:
        gallery = _no_gallery
    return asyncio.run(
        vs._collect_face_texts(frame_paths, settings=settings, gallery=gallery, session=session)
    )


def _never(why):
    raise AssertionError(why)


async def _no_gallery(*_args):
    raise AssertionError("gallery must not be consulted")


def test_face_leg_no_frames_vs_weights_absent():
    # scenario S1: nothing to look at -> no_frames
    seen = []
    stubs, calls = _face_stub(({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}), [])
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs})

    def _run(paths):
        return _collect_face(paths)

    try:
        out = _run([])
        assert [(o.kind, getattr(o, "reason", None), getattr(o, "code", None)) for o in out] == [
            ("unavailable", "no key frames available", "no_frames")
        ]
        assert calls["handles_calls"] == []  # paths empty short-circuits handles
    finally:
        restore()
    # scenario S2: paths present but handles None -> weights_absent
    seen2 = []
    stubs2, calls2 = _face_stub(None, [])
    restore2 = _module_stub({**_metrics_stub(seen2), **_pil_stub2(), **stubs2})
    records, undo_log = _logs()
    try:
        out2 = _run(["f1"])
        assert [(o.kind, getattr(o, "code", None)) for o in out2] == [
            ("unavailable", "weights_absent")
        ]
        assert out2[0].reason == (
            "face weights not loaded (absent files fail the hash pin / CPU "
            "ONNX extras not installed — deploy-side, not a verdict failure)"
        )
        assert calls2["handles_calls"] == [1]
        assert records == []  # the leg itself logs nothing
    finally:
        undo_log()
        restore2()


def test_face_leg_frames_unreadable_and_zero_faces():
    seen = []
    stubs, calls = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}), [[]]
    )
    restore = _module_stub(
        {**_metrics_stub(seen), **_pil_stub2(open_raises=("bad1", "bad2")), **stubs}
    )
    try:
        out = _collect_face(["bad1", "bad2"])
        assert [(o.kind, o.reason, o.code) for o in out] == [
            ("unavailable", "no key frame readable", "frames_unreadable")
        ]
        assert calls["detect"] == []
        # readable frame with zero faces is a REAL observation: outcomes []
        ok = _collect_face(["f1"])
        assert ok == []
    finally:
        restore()


def test_face_leg_detect_and_embedding_failures():
    seen = []
    stubs, calls = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}),
        [[_face()]],
        detect_raises=FaceErr("det blew up"),
    )
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs})
    try:
        out = _collect_face(["f1"])
        assert [(o.kind, o.code) for o in out] == [("unavailable", "detection_failed")]
        assert "det blew up" in out[0].reason
    finally:
        restore()
    stubs2, _ = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}),
        [[_face()]],
        extract_raises=FaceErr("embed blew up"),
    )
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs2})
    try:
        out = _collect_face(["f1"])
        assert [(o.kind, o.code) for o in out] == [("unavailable", "embedding_failed")]
        assert "embed blew up" in out[0].reason
    finally:
        restore()


def test_face_leg_landmarks_none_and_gate_and_match():
    seen = []
    # face 1: landmarks None -> not_identifiable (no embedding call)
    # face 2: gate-failing crop WITH a match dict -> STILL not_identifiable
    #   (the F11 ruling-3 ordering rule)
    # face 3: gate-passing + matched dict -> match outcome with name+score
    # face 4: gate-passing + no match -> unknown
    stubs, calls = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}),
        [
            [
                _face(landmarks=None),
                _face(bbox=(40.0, 10.0, 52.0, 22.0), score=0.9),  # 12px < 30 min_px
                _face(),
                _face(bbox=(10.0, 10.0, 90.0, 90.0), score=0.7),
                # x-dim gate-fail face: min(25,50)=25 fails; min(x2+x1,50)=45
                # would pass (kills the m85 first-operand + mutant)
                _face(bbox=(10.0, 10.0, 35.0, 60.0), score=0.9),
                # y-dim gate-fail face: min(100,22)=22 fails; min(100,y2+y1)=42
                # would pass (kills the m86 second-operand + mutant)
                _face(bbox=(100.0, 10.0, 200.0, 32.0), score=0.9),
            ]
        ],
    )
    # the gallery is queried by every LANDMARKED face in scan order (faces
    # 2..6; the landmarks-None face never embeds/queries), so the None answer
    # for the gate-passing no-match face sits at query index 2
    _HIT = {"matched": True, "person_name": "Ann", "similarity": 0.88}
    answers = [_HIT, _HIT, None, _HIT, _HIT]
    n = {"i": 0}

    async def gallery(session, vector, threshold):
        gallery.calls.append((session, vector, threshold))
        ans = answers[n["i"]]
        n["i"] += 1
        return ans

    gallery.calls = []
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs})
    try:
        out = _collect_face(["f1"], gallery=gallery, session=SESSION)
        kinds = [o.kind for o in out]
        assert kinds == [
            "not_identifiable",
            "not_identifiable",
            "match",
            "unknown",
            "not_identifiable",
            "not_identifiable",
        ]
        m = out[2]
        assert m.person_name == "Ann" and m.similarity == 0.88
        # EVERY landmarked face queries the gallery (the gate is applied in
        # classify AFTER the query); the landmarks-None one never embedded
        assert gallery.calls == [(SESSION, [0.1, 0.2, 0.3], 0.35)] * 5
        assert len(answers) == 5
        # detector got the settings threshold and the det handle's session
        assert calls["detect_thresholds"] == [0.6]
        assert calls["detect"] == [("det-s", "f1")]
    finally:
        restore()


def test_face_leg_gallery_exception_and_unavailable_answer():
    seen = []

    async def boom(session, vector, threshold):
        raise RuntimeError("db down")

    async def honest(session, vector, threshold):
        return {"unavailable": True}

    # ONE fresh face stub per scenario: the stub's face plan is consumed
    # (popped) by each detect call, so a shared stub would read "0 faces"
    stubs, _ = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}), [[_face()]]
    )
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs})
    try:
        out = _collect_face(["f1"], gallery=boom, session=SESSION)
        assert [(o.kind, o.code) for o in out] == [("unavailable", "gallery_query_failed")]
        assert "db down" in out[0].reason
    finally:
        restore()
    stubs, _ = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}), [[_face()]]
    )
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs})
    try:
        out2 = _collect_face(["f1"], gallery=honest, session=SESSION)
        assert [(o.kind, o.code) for o in out2] == [("unavailable", "space_mismatch")]
        assert "['arc-x']" in out2[0].reason and "(re-enroll needed)" in out2[0].reason
    finally:
        restore()


def test_face_leg_space_mismatch_vs_inert_gallery_ids():
    seen = []

    async def nomatch(session, vector, threshold):
        return None

    def _run_with(session):
        # fresh face stub per scenario (face plans are consumed per call)
        stubs, _ = _face_stub(
            ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}),
            [[_face()]],
        )
        restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs})
        try:
            return _collect_face(["f1"], gallery=nomatch, session=session)
        finally:
            restore()

    # gallery carries a DIFFERENT id -> whole-line space_mismatch
    out = _run_with(_SqlSession([("other-id",)]))
    assert [(o.kind, o.code) for o in out] == [("unavailable", "space_mismatch")]
    # FULL reason equality: the XX/UPPER fragment mutants must not hide
    # behind a substring read (fragment-count-asserts trap)
    assert out[0].reason == (
        "gallery embeddings carry a different face-model id "
        "['other-id'] than the loaded weights ['arc-x']"
    )
    # same id -> the check stays inert, the unknown outcome survives
    out2 = _run_with(_SqlSession([("arc-x",)]))
    assert [o.kind for o in out2] == ["unknown"]
    # empty id set (pre-migration DB / NULL rows) -> also inert
    out3 = _run_with(_SqlSession([(None,)]))
    assert [o.kind for o in out3] == ["unknown"]

    class Bad(_SqlSession):
        async def execute(self, clause):
            raise RuntimeError("table missing")

    # the id read is belted INSIDE _gallery_model_ids, so a raise reads as
    # "gallery carries no ids" — the conservative, inert direction
    out4 = _run_with(Bad([]))
    assert [o.kind for o in out4] == ["unknown"]


def test_face_leg_recognizer_probe_id_default():
    # rec handle WITHOUT model_id: probe_ids gets str("") == "" (kills the
    # "XXXX" default mutant: sorted probe ids render ['XXXX'] there)
    seen = []
    stubs, _ = _face_stub(({"session": "det-s"}, {"session": "rec-s"}), [[_face()]])
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs})
    try:

        async def nomatch(session, vector, threshold):
            return None

        out = _collect_face(["f1"], gallery=nomatch, session=_SqlSession([("other",)]))
        assert [(o.kind, o.code) for o in out] == [("unavailable", "space_mismatch")]
        assert "['']" in out[0].reason  # probe side is the empty string
    finally:
        restore()


# ---------------------------------------------------------------------------
# collect_face_text (stage funnel)
# ---------------------------------------------------------------------------


def test_collect_face_text_leg_failed_funnel():
    seen = []
    records, undo_log = _logs()

    def explode(*_a, **_k):
        raise RuntimeError("kaboom")

    restore = _module_stub(
        {
            **_metrics_stub(seen),
            "backend.services.vlm_specialists": {"_collect_face_texts": explode},
        }
    )
    try:
        out = asyncio.run(vs.collect_face_text(frame_paths=[], settings=SETTINGS))
        assert out == DEFAULT_PHRASE
        assert seen == [("faces", "leg_failed")]
        assert _log_sig(records) == [
            ("WARNING", "face specialist failed", (_MISSING,) * 4, (RuntimeError,))
        ]
    finally:
        undo_log()
        restore()


def test_collect_face_text_default_gallery_wiring():
    # gallery=None must bind _default_gallery_match, which reads the model id
    # from the LOADED HANDLE (belt) and hands it to the service match_face.
    seen = []
    calls = []
    stubs, _ = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}), [[_face()]]
    )

    async def match_face(session, vector, *, threshold, model_id):
        calls.append((session, vector, threshold, model_id))

    svc = _Box(match_face=match_face)
    restore = _module_stub(
        {
            **_metrics_stub(seen),
            **_pil_stub2(),
            **stubs,
            "backend.services.face_recognition_service": {
                "get_face_recognition_service": lambda: svc
            },
        }
    )
    try:
        out = asyncio.run(
            vs.collect_face_text(
                frame_paths=["f1"], settings=SETTINGS, gallery=None, session=SESSION
            )
        )
        assert out == "1 unknown face(s)"
        # _default_gallery_match read the probe belt from the LOADED HANDLE
        assert calls == [(SESSION, [0.1, 0.2, 0.3], 0.35, "arc-x")]
    finally:
        restore()


# ---------------------------------------------------------------------------
# re-ID leg (_collect_reid_text 103 keys + collect_reid_text stage)
# ---------------------------------------------------------------------------

import enum  # noqa: E402


class Outcome(enum.Enum):
    """Stand-in PersonMatchOutcome: the module imports the real enum at call
    time from backend.services.household_matcher, which this battery swaps —
    so ITS identity is whatever this test hands it."""

    MATCH = "match"
    NO_MATCH = "no_match"
    NO_GALLERY = "no_gallery"
    UNAVAILABLE_REENROLL = "reenroll"


class ExtractErr(Exception):
    pass


def _osnet_stub(handle, *, extract_plan=None):
    """handle: what get_reid_handle() returns; extract_plan: list of
    exceptions (raised in call order) or None values (succeeding)."""
    calls = {"extract": [], "get_handle": []}
    state = {"n": 0}

    def get_reid_handle():
        calls["get_handle"].append(1)
        return handle

    async def extract_person_embedding(h, image):
        calls["extract"].append((h, image))
        i = state["n"]
        state["n"] += 1
        if extract_plan is not None and i < len(extract_plan) and extract_plan[i] is not None:
            raise extract_plan[i]
        return _Box(embedding=[0.5, 0.5], model_id=None)

    return (
        {
            "backend.services.osnet_loader": {
                "get_reid_handle": get_reid_handle,
                "extract_person_embedding": extract_person_embedding,
                "OSNET_ZOO_NAME": "osnet_x1.0_ain",
            }
        },
        calls,
    )


def _np_stub(dtype_seen):
    sentinel = object()

    def asarray(arr, dtype=None):
        dtype_seen.append(dtype)
        return _Box(arr=arr, dtype=dtype)

    return {
        "numpy": {
            "asarray": asarray,
            "float32": sentinel,
        }
    }, sentinel


def _hm_stub(plan, threshold_seen, *, matcher_threshold=0.55):
    """Fake household_matcher: compare_person_vectors replays PLAN (list of
    comparison boxes) one per probe call."""
    calls = {"compare": []}
    state = {"n": 0}

    class Matcher:
        similarity_threshold = matcher_threshold

    def compare_person_vectors(probe, belt, rows, *, threshold):
        calls["compare"].append((probe, belt, rows, threshold))
        threshold_seen.append(threshold)
        i = state["n"]
        state["n"] += 1
        return plan[i] if i < len(plan) else _Box(outcome=Outcome.NO_MATCH, match=None, skipped=0)

    return (
        {
            "backend.services.household_matcher": {
                "PersonMatchOutcome": Outcome,
                "compare_person_vectors": compare_person_vectors,
                "get_household_matcher": lambda: Matcher(),
            }
        },
        calls,
    )


REID_SETTINGS = _Box(reid_similarity_threshold=0.77)
REID_HANDLE = {"session": "osnet-s", "model_id": "osnet-handle"}
_CROPS_FP = ["f1"]


def _reid_dets(*paths, det_ids=(1,)):
    return [_person_dict(path=p, id=i) for p, i in zip(paths, det_ids, strict=False)]


def _collect_reid(
    *,
    frame_paths=_CROPS_FP,
    detections=None,
    settings=REID_SETTINGS,
    session=SESSION,
    gallery=None,
):
    if detections is None:
        detections = _reid_dets("f1")
    seen = []
    dtype_seen = []
    threshold_seen = []
    gallery_calls = []

    async def _gal(sess):
        gallery_calls.append(sess)
        return ["row-a"]

    stubs_o, calls_o = _osnet_stub(REID_HANDLE, extract_plan=None)
    stubs_n, f32 = _np_stub(dtype_seen)
    stubs_h, calls_h = _hm_stub([], threshold_seen)
    extra = {
        **_metrics_stub(seen),
        **_pil_stub2(),
        **stubs_o,
        **stubs_n,
        **stubs_h,
        "backend.core.vector_provenance": {"LEGACY_MODEL_ID": "legacy-probe-id"},
        "backend.services.vlm_specialists": {},
    }
    # (the empty vlm_specialists entry is a no-op anchor; real swaps below)
    extra.pop("backend.services.vlm_specialists")
    restore = _module_stub(extra)

    ctx = _Box(
        seen=seen,
        dtype_seen=dtype_seen,
        threshold_seen=threshold_seen,
        gallery_calls=gallery_calls,
        calls_o=calls_o,
        calls_h=calls_h,
        f32=f32,
        restore=restore,
    )
    return ctx


def test_reid_no_frames_and_no_person_crops():
    records, undo_log = _logs()
    ctx = _collect_reid(frame_paths=[], detections=[], session=None, gallery=None)
    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=[], detections=[], settings=None, session=None, gallery=None
            )
        )
        assert out == DEFAULT_PHRASE
        assert ctx.seen == [("person_reid", "no_frames")]
        assert _log_sig(records) == [
            (
                "WARNING",
                "specialist unavailable",
                (
                    "person_reid",
                    "no_frames",
                    "no person detection among the selected key frames",
                    _MISSING,
                ),
                None,
            )
        ]
    finally:
        undo_log()
        ctx.restore()
    records2, undo_log2 = _logs()
    ctx2 = _collect_reid()
    try:
        # picks non-empty but NO person detection among them -> no_person_crops
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=["f1"],
                detections=[_person_dict(path="f9")],
                settings=None,
                session=None,
                gallery=None,
            )
        )
        assert out == DEFAULT_PHRASE
        assert ctx2.seen == [("person_reid", "no_person_crops")]
        assert _log_sig(records2)[0][2][:2] == ("person_reid", "no_person_crops")
    finally:
        undo_log2()
        ctx2.restore()


def test_reid_weights_absent_and_no_session():
    records, undo_log = _logs()
    stubs_o, _ = _osnet_stub(None)
    seen = []
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs_o})
    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1"),
                settings=None,
                session=None,
                gallery=None,
            )
        )
        assert out == DEFAULT_PHRASE
        assert seen == [("person_reid", "weights_absent")]
        assert _log_sig(records)[0][2] == (
            "person_reid",
            "weights_absent",
            "osnet_x1.0_ain not loaded (BACKEND_MODEL_PRELOAD / models.yml)",
            _MISSING,
        )
    finally:
        undo_log()
        restore()
    ctx = _collect_reid()
    records, undo_log = _logs()
    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1"),
                settings=None,
                session=None,
                gallery=None,
            )
        )
        assert out == DEFAULT_PHRASE
        assert ctx.seen == [("person_reid", "no_session")]
        assert _log_sig(records)[0][2] == (
            "person_reid",
            "no_session",
            "no DB session for the person gallery",
            _MISSING,
        )
    finally:
        undo_log()
        ctx.restore()


def test_reid_happy_path_belt_threshold_dtype_and_line():
    # stage entry (kills the settings-drop mutant on collect_reid_text too)
    plan = [_Box(outcome=Outcome.NO_MATCH, match=None, skipped=0)]
    records, undo_log = _logs()
    seen, dtype_seen, threshold_seen, gallery_calls = [], [], [], []
    stubs_o, calls_o = _osnet_stub(REID_HANDLE)
    stubs_n, f32 = _np_stub(dtype_seen)
    stubs_h, calls_h = _hm_stub(plan, threshold_seen)
    extra = {
        **_metrics_stub(seen),
        **_pil_stub2(),
        **stubs_o,
        **stubs_n,
        **stubs_h,
        "backend.core.vector_provenance": {"LEGACY_MODEL_ID": "legacy-probe-id"},
    }

    async def _gal(sess):
        gallery_calls.append(sess)
        return ["row-a"]

    restore = _module_stub(extra)
    try:
        out = asyncio.run(
            vs.collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1"),
                settings=REID_SETTINGS,
                session=SESSION,
                gallery=_gal,
            )
        )
        assert out == "no known-person re-ID matches"
        assert seen == [] and records == []
        assert gallery_calls == [SESSION]  # session threaded to the gallery
        assert calls_h["compare"][0][1] == "osnet-handle"  # the HANDLE belt wins
        assert calls_h["compare"][0][3] == 0.77  # settings threshold (stage-passed)
        assert dtype_seen == [f32]  # np.float32 dtype pinned
        # detector identity flows: crop source is f1
        assert calls_o["extract"][0][1].source == "f1"

        async def _gal2(sess):
            return ["row-a"]

        # settings=None falls back to the MATCHER's threshold (0.55), not the
        # settings value (kills the `is not None` polarity mutants)
        assert (
            asyncio.run(
                vs._collect_reid_text(
                    frame_paths=_CROPS_FP,
                    detections=_reid_dets("f1"),
                    settings=None,
                    session=SESSION,
                    gallery=_gal2,
                )
            )
            == "no known-person re-ID matches"
        )
        assert threshold_seen == [0.77, 0.55]
    finally:
        undo_log()
        restore()


def test_reid_belt_fallbacks_and_result_belt():
    # (a) handle WITHOUT model_id + result.model_id None -> LEGACY belt
    # (b) result.model_id set -> the RESULT belt wins over the handle's
    for handle, model_id, expect_belt in [
        ({"session": "osnet-s"}, None, "legacy-probe-id"),
        (REID_HANDLE, "res-belt", "res-belt"),
    ]:
        plan = [_Box(outcome=Outcome.NO_MATCH, match=None, skipped=0)]
        threshold_seen = []
        seen = []
        stubs_o, calls_o = _osnet_stub(handle)
        if model_id is not None:
            stubs_o["backend.services.osnet_loader"]["extract_person_embedding"] = (
                _make_model_id_extractor(model_id)
            )
        stubs_n, _ = _np_stub([])
        stubs_h, calls_h = _hm_stub(plan, threshold_seen)
        restore = _module_stub(
            {
                **_metrics_stub(seen),
                **_pil_stub2(),
                **stubs_o,
                **stubs_n,
                **stubs_h,
                "backend.core.vector_provenance": {"LEGACY_MODEL_ID": "legacy-probe-id"},
            }
        )

        async def _gal(sess):
            return ["row-a"]

        try:
            out = asyncio.run(
                vs._collect_reid_text(
                    frame_paths=_CROPS_FP,
                    detections=_reid_dets("f1"),
                    settings=REID_SETTINGS,
                    session=SESSION,
                    gallery=_gal,
                )
            )
            assert out == "no known-person re-ID matches"
            assert calls_h["compare"][0][1] == expect_belt
        finally:
            restore()


def _make_model_id_extractor(model_id):
    async def extract(h, image):
        return _Box(embedding=[0.5, 0.5], model_id=model_id)

    return extract


def test_reid_matches_best_per_member():
    # member 5 twice (0.9 then 0.4 -> keeps 90%), member 6 twice with an
    # EXACT tie (0.8 then 0.8 -> the FIRST name survives; `>=` would let the
    # later Ann2 claim the slot — this is the m114 strict-vs-loose kill),
    # member 7 once
    m_a = _Box(member_id=5, member_name="Ann", similarity=0.9)
    m_b = _Box(member_id=5, member_name="Ann", similarity=0.4)
    m_c = _Box(member_id=6, person_name="Bo", similarity=0.8)
    m_d = _Box(member_id=6, member_name="Ann2", similarity=0.8)
    m_e = _Box(member_id=7, member_name="Cy", similarity=None)
    m_f = _Box(member_id=8, member_name="Di", similarity=0.4999)  # 49 vs *101->50
    plan = [
        _Box(outcome=Outcome.MATCH, match=m_a, skipped=0),
        _Box(outcome=Outcome.MATCH, match=m_b, skipped=0),
        _Box(outcome=Outcome.MATCH, match=m_c, skipped=0),
        _Box(outcome=Outcome.MATCH, match=m_d, skipped=0),
        _Box(outcome=Outcome.MATCH, match=m_e, skipped=0),
        _Box(outcome=Outcome.MATCH, match=m_f, skipped=0),
    ]
    threshold_seen = []
    seen = []
    stubs_o, _ = _osnet_stub(REID_HANDLE)
    stubs_n, _ = _np_stub([])
    stubs_h, calls_h = _hm_stub(plan, threshold_seen)
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs_o, **stubs_n, **stubs_h})

    async def _gal(sess):
        return ["row-a"] * 3

    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets(
                    "f1", "f1", "f1", "f1", "f1", "f1", det_ids=(1, 2, 3, 4, 5, 6)
                ),
                settings=REID_SETTINGS,
                session=SESSION,
                gallery=_gal,
            )
        )
        assert out == (
            "matches household member Ann (90% match); "
            "matches household member Bo (80% match); "
            "matches household member Cy; "
            "matches household member Di (49% match)"
        )
        assert seen == []
    finally:
        restore()


def test_reid_all_extractions_failed():
    records, undo_log = _logs()
    seen = []
    stubs_o, calls_o = _osnet_stub(REID_HANDLE, extract_plan=[ExtractErr("a"), ExtractErr("b")])
    stubs_n, _ = _np_stub([])
    threshold_seen = []
    stubs_h, _ = _hm_stub([], threshold_seen)
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs_o, **stubs_n, **stubs_h})

    async def _gal(sess):
        return ["row-a", "row-b"]

    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1", "f1", det_ids=(1, 2)),
                settings=REID_SETTINGS,
                session=SESSION,
                gallery=_gal,
            )
        )
        assert out == DEFAULT_PHRASE
        assert seen == [("person_reid", "extraction_failed")]
        # the per-crop failures were EACH logged with exc_info + det_id extra
        sigs = _log_sig(records)
        assert sigs == [
            (
                "WARNING",
                "person_reid crop failed",
                (_MISSING, _MISSING, _MISSING, "1"),
                (ExtractErr,),
            ),
            (
                "WARNING",
                "person_reid crop failed",
                (_MISSING, _MISSING, _MISSING, "2"),
                (ExtractErr,),
            ),
            (
                "WARNING",
                "specialist unavailable",
                (
                    "person_reid",
                    "extraction_failed",
                    "all 2 person crop extractions failed",
                    _MISSING,
                ),
                None,
            ),
        ]
        assert threshold_seen == []  # nothing ever compared
    finally:
        undo_log()
        restore()


def test_reid_partial_crop_failure_survives():
    # first crop fails, second works -> the leg keeps working (a 'break'
    # mutant on the except arm loses the SECOND crop's match)
    m_ok = _Box(member_id=9, member_name="Zoe", similarity=0.95)
    plan = [_Box(outcome=Outcome.MATCH, match=m_ok, skipped=0)]
    seen = []
    stubs_o, _ = _osnet_stub(REID_HANDLE, extract_plan=[ExtractErr("one bad box"), None])
    stubs_n, _ = _np_stub([])
    threshold_seen = []
    stubs_h, _ = _hm_stub(plan, threshold_seen)
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs_o, **stubs_n, **stubs_h})

    async def _gal(sess):
        return ["row-a"]

    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1", "f1", det_ids=(1, 2)),
                settings=REID_SETTINGS,
                session=SESSION,
                gallery=_gal,
            )
        )
        assert out == "matches household member Zoe (95% match)"
    finally:
        restore()


def test_reid_unavailable_reenroll_short_circuits():
    # crop 1 -> NO_MATCH, crop 2 -> UNAVAILABLE_REENROLL: the refusal must
    # WIN over the earlier no-match (and a later crop must never run)
    seen = []
    records, undo_log = _logs()
    plan = [
        _Box(outcome=Outcome.NO_MATCH, match=None, skipped=0),
        _Box(outcome=Outcome.UNAVAILABLE_REENROLL, match=None, skipped=7),
    ]
    stubs_o, calls_o = _osnet_stub(REID_HANDLE)
    stubs_n, _ = _np_stub([])
    threshold_seen = []
    stubs_h, _ = _hm_stub(plan, threshold_seen)
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs_o, **stubs_n, **stubs_h})

    async def _gal(sess):
        return ["row-a", "row-b", "row-c"]

    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1", "f1", "f1", det_ids=(1, 2, 3)),
                settings=REID_SETTINGS,
                session=SESSION,
                gallery=_gal,
            )
        )
        assert out == RE_ENROLL_PHRASE
        assert seen == [("person_reid", "space_mismatch")]
        assert _log_sig(records)[0][2] == (
            "person_reid",
            "space_mismatch",
            "7 gallery rows not comparable to the probe space",
            _MISSING,
        )
        assert len(calls_o["extract"]) == 2  # returned before probing crop 3
    finally:
        undo_log()
        restore()


def test_reid_no_gallery_outcome():
    seen = []
    records, undo_log = _logs()
    plan = [_Box(outcome=Outcome.NO_GALLERY, match=None, skipped=0)]
    stubs_o, _ = _osnet_stub(REID_HANDLE)
    stubs_n, _ = _np_stub([])
    threshold_seen = []
    stubs_h, _ = _hm_stub(plan, threshold_seen)
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs_o, **stubs_n, **stubs_h})

    async def _gal(sess):
        return []

    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1"),
                settings=REID_SETTINGS,
                session=SESSION,
                gallery=_gal,
            )
        )
        assert out == DEFAULT_PHRASE
        assert seen == [("person_reid", "no_gallery")]
        assert _log_sig(records)[0][2] == (
            "person_reid",
            "no_gallery",
            "household has no stored person vectors",
            _MISSING,
        )
    finally:
        undo_log()
        restore()


def test_reid_match_with_none_member_id_gets_own_slot():
    # member_id None is a match that names nobody: it can only live under the
    # None key — key=None mutants (m109) collide two named members instead
    m1 = _Box(member_id=None, member_name="Ghost", similarity=0.9)
    m2 = _Box(member_id=5, member_name="Ann", similarity=0.8)
    plan = [
        _Box(outcome=Outcome.MATCH, match=m1, skipped=0),
        _Box(outcome=Outcome.MATCH, match=m2, skipped=0),
    ]
    seen = []
    stubs_o, _ = _osnet_stub(REID_HANDLE)
    stubs_n, _ = _np_stub([])
    threshold_seen = []
    stubs_h, _ = _hm_stub(plan, threshold_seen)
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs_o, **stubs_n, **stubs_h})

    async def _gal(sess):
        return ["row-a", "row-b"]

    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1", "f1", det_ids=(1, 2)),
                settings=REID_SETTINGS,
                session=SESSION,
                gallery=_gal,
            )
        )
        assert (
            out
            == "matches household member Ghost (90% match); matches household member Ann (80% match)"
        )
    finally:
        restore()


def test_reid_match_arm_needs_both_conditions():
    # NO_MATCH WITH a stray match object must NOT enter best_by_member
    # (the 'and'->'or' mutant m106 would render it)
    stray = _Box(member_id=5, member_name="Stray", similarity=0.99)
    plan = [_Box(outcome=Outcome.NO_MATCH, match=stray, skipped=0)]
    seen = []
    stubs_o, _ = _osnet_stub(REID_HANDLE)
    stubs_n, _ = _np_stub([])
    threshold_seen = []
    stubs_h, _ = _hm_stub(plan, threshold_seen)
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs_o, **stubs_n, **stubs_h})

    async def _gal(sess):
        return ["row-a"]

    try:
        out = asyncio.run(
            vs._collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1"),
                settings=REID_SETTINGS,
                session=SESSION,
                gallery=_gal,
            )
        )
        assert out == "no known-person re-ID matches"
    finally:
        restore()


def test_collect_reid_text_stage_never_raises():
    seen = []
    records, undo_log = _logs()

    async def explode(**kw):
        raise ValueError("inner blew")

    restore = _module_stub(
        {
            **_metrics_stub(seen),
            "backend.services.vlm_specialists": {"_collect_reid_text": explode},
        }
    )
    try:
        out = asyncio.run(vs.collect_reid_text(frame_paths=[]))
        assert out == DEFAULT_PHRASE
        assert seen == [("person_reid", "leg_failed")]
        sig = _log_sig(records)[0]
        assert sig == ("WARNING", "person_reid specialist failed", (_MISSING,) * 4, (ValueError,))
    finally:
        undo_log()
        restore()


def test_collect_reid_text_default_gallery_is_loader():
    # gallery=None binds _default_person_gallery -> load_person_gallery(session)
    seen = []
    loader_calls = []

    async def load_person_gallery(session):
        loader_calls.append(session)
        return []

    stubs_o, _ = _osnet_stub(REID_HANDLE)
    stubs_n, _ = _np_stub([])
    threshold_seen = []
    stubs_h, _ = _hm_stub([], threshold_seen)
    restore = _module_stub(
        {
            **_metrics_stub(seen),
            **_pil_stub2(),
            **stubs_o,
            **stubs_n,
            **stubs_h,
            "backend.services.household_matcher": {
                "PersonMatchOutcome": Outcome,
                "compare_person_vectors": stubs_h["backend.services.household_matcher"][
                    "compare_person_vectors"
                ],
                "get_household_matcher": stubs_h["backend.services.household_matcher"][
                    "get_household_matcher"
                ],
                "load_person_gallery": load_person_gallery,
            },
        }
    )
    try:
        out = asyncio.run(
            vs.collect_reid_text(
                frame_paths=_CROPS_FP,
                detections=_reid_dets("f1"),
                settings=REID_SETTINGS,
                session=SESSION,
            )
        )
        assert loader_calls == [SESSION]
        assert out == "no known-person re-ID matches"
    finally:
        restore()


# ---------------------------------------------------------------------------
# plate leg (collect_plate_text 18 keys) + threat (6 keys)
# ---------------------------------------------------------------------------


def _alpr_stub(plan, calls, *, load_raises=None):
    async def load_fast_alpr(path):
        calls["load"].append(path)
        if load_raises is not None:
            raise load_raises
        return _Box(alpr="ALPR")

    async def run_fast_alpr(alpr, image):
        calls["run"].append((alpr, image))
        i = len(calls["run"]) - 1
        return plan[i] if i < len(plan) else []

    return {
        "backend.services.fast_alpr_loader": {
            "load_fast_alpr": load_fast_alpr,
            "run_fast_alpr": run_fast_alpr,
        }
    }


def test_collect_plate_text_happy_path():
    calls = {"load": [], "run": []}
    match_calls = []
    plan = [[_Box(text="AAA")], ["BBB"]]

    async def fake_match(plate_texts):
        match_calls.append(list(plate_texts))
        return [_Box(text="AAA", matched=True, member_name="Dad")]

    seen = []
    np_seen = []
    stubs_n, _ = _np_stub(np_seen)
    restore = _module_stub(
        {
            **_metrics_stub(seen),
            **_pil_stub2(open_raises=("bad",)),
            **_alpr_stub(plan, calls),
            **stubs_n,
            "backend.services.vlm_specialists": {"_match_plate_vehicles": fake_match},
        }
    )
    try:
        out = asyncio.run(vs.collect_plate_text(frame_paths=["f1", "bad", "f2"]))
        assert out == "AAA - household vehicle (Dad); BBB - not a household plate"
        assert calls["load"] == [""]  # the "" load path is pinned (None/XXXX die)
        assert calls["run"][0][0].alpr == "ALPR"
        assert match_calls == [["AAA", ""]]  # bare str result -> getattr default ""
        assert seen == []
    finally:
        restore()


def test_collect_plate_text_load_first_and_empty():
    calls = {"load": [], "run": []}

    async def fake_match(plate_texts):
        raise AssertionError("must not be consulted")

    seen = []
    records, undo_log = _logs()
    restore = _module_stub(
        {
            **_metrics_stub(seen),
            **_pil_stub2(),
            **_alpr_stub([], calls),
            "backend.services.vlm_specialists": {"_match_plate_vehicles": fake_match},
        }
    )
    try:
        # no frames but the package LOADED: the leg ran, saw nothing -> real 0
        out = asyncio.run(vs.collect_plate_text(frame_paths=[]))
        assert out == "0 license plates detected"
        assert calls["load"] == [""]  # LOAD precedes the empty shortcut (pinned)
        assert calls["run"] == []
        # frames readable but zero plates across all of them
        out2 = asyncio.run(vs.collect_plate_text(frame_paths=["f1"]))
        assert out2 == "0 license plates detected"
    finally:
        undo_log()
        restore()


def test_collect_plate_text_failure_degrades_with_detail():
    calls = {"load": [], "run": []}
    seen = []
    records, undo_log = _logs()
    restore = _module_stub(
        {
            **_metrics_stub(seen),
            **_pil_stub2(),
            **_alpr_stub([], calls, load_raises=RuntimeError("plate boom")),
            "backend.services.vlm_specialists": {},
        }
    )
    try:
        out = asyncio.run(vs.collect_plate_text(frame_paths=["f1"]))
        assert out == DEFAULT_PHRASE  # "unavailable: ..." — never the raw error
        assert seen == [("plates", "leg_failed")]
        assert _log_sig(records) == [
            ("INFO", "plate specialist unavailable", (_MISSING,) * 4, (RuntimeError,)),
            (
                "WARNING",
                "specialist unavailable",
                ("plates", "leg_failed", "plate boom", _MISSING),
                None,
            ),
        ]
    finally:
        undo_log()
        restore()


def test_collect_threat_text_line():
    seen = []
    restore = _module_stub(_metrics_stub(seen))
    try:
        out = asyncio.run(vs.collect_threat_text(frame_paths=["f1"]))
        assert out == DEFAULT_PHRASE
        assert seen == [("threat", "not_included")]
    finally:
        restore()


# ---------------------------------------------------------------------------
# collect_specialist_outputs (44 keys): legs are swapped to record their call
# kwargs exactly — every dropped/None/renamed kwarg lands in the recorder.
# ---------------------------------------------------------------------------

_FACE_G = _Box(name="face-gallery-sentinel")


def _stage_legs(seen_kw, fail=None):
    async def fake_face(*, frame_paths, settings, gallery, session):
        seen_kw.append(("faces", frame_paths, settings, gallery, session))
        if fail == "faces":
            raise RuntimeError("faces leg exploded")
        return "FACES"

    async def fake_plates(*, frame_paths):
        seen_kw.append(("plates", frame_paths))
        if fail == "plates":
            raise RuntimeError("plates leg exploded")
        return "PLATES"

    async def fake_reid(*, frame_paths, detections, settings, session):
        seen_kw.append(("reid", frame_paths, detections, settings, session))
        if fail == "reid":
            raise RuntimeError("reid leg exploded")
        return "REID"

    async def fake_threat(*, frame_paths):
        seen_kw.append(("threat", frame_paths))
        return "THREAT"

    return {
        "collect_face_text": fake_face,
        "collect_plate_text": fake_plates,
        "collect_reid_text": fake_reid,
        "collect_threat_text": fake_threat,
    }


def test_collect_specialist_outputs_wiring_happy():
    seen_kw = []
    seen = []
    records, undo_log = _logs()
    restore = _module_stub(
        {
            **_metrics_stub(seen),
            "backend.services.vlm_specialists": _stage_legs(seen_kw),
        }
    )
    try:
        out = asyncio.run(
            vs.collect_specialist_outputs(
                key_frame_paths=["f1"],
                settings=SETTINGS,
                detections=[_person_dict()],
                session=SESSION,
                face_gallery=_FACE_G,
            )
        )
        assert out == {"faces": "FACES", "plates": "PLATES", "person_reid": "REID"}
        assert ("faces", ["f1"], SETTINGS, _FACE_G, SESSION) in seen_kw
        assert ("plates", ["f1"]) in seen_kw
        assert ("reid", ["f1"], [_person_dict()], SETTINGS, SESSION) in seen_kw
        assert [k for k, *_ in seen_kw if k == "threat"] == []  # F12: no threat key
        assert seen == [] and records == []
    finally:
        undo_log()
        restore()


def test_collect_specialist_outputs_default_kwargs():
    # gallery=None and session=None must be forwarded as EXACTLY those
    # (a swap/None-ing of the two kwargs lands in the recorder differently)
    seen_kw = []
    seen = []
    restore = _module_stub(
        {
            **_metrics_stub(seen),
            "backend.services.vlm_specialists": _stage_legs(seen_kw),
        }
    )
    try:
        out = asyncio.run(
            vs.collect_specialist_outputs(
                key_frame_paths=["f1"], settings=SETTINGS, detections=None
            )
        )
        assert out == {"faces": "FACES", "plates": "PLATES", "person_reid": "REID"}
        assert ("faces", ["f1"], SETTINGS, None, None) in seen_kw
        assert ("reid", ["f1"], None, SETTINGS, None) in seen_kw
    finally:
        restore()


def test_collect_specialist_outputs_threat_wiring():
    seen_kw = []
    seen = []
    restore = _module_stub(
        {
            **_metrics_stub(seen),
            "backend.services.vlm_specialists": _stage_legs(seen_kw),
        }
    )
    try:
        out = asyncio.run(
            vs.collect_specialist_outputs(
                key_frame_paths=["f1"],
                settings=SETTINGS,
                session=SESSION,
                run_threat=True,
            )
        )
        assert out == {
            "faces": "FACES",
            "plates": "PLATES",
            "person_reid": "REID",
            "threat": "THREAT",
        }
        assert ("threat", ["f1"]) in seen_kw
    finally:
        restore()


def test_collect_specialist_outputs_stage_error_floor():
    seen_kw = []
    seen = []
    records, undo_log = _logs()
    restore = _module_stub(
        {
            **_metrics_stub(seen),
            "backend.services.vlm_specialists": _stage_legs(seen_kw, fail="plates"),
        }
    )
    try:
        out = asyncio.run(
            vs.collect_specialist_outputs(
                key_frame_paths=["f1"], settings=SETTINGS, session=SESSION
            )
        )
        # every leg degrades through the SAME funnel with code stage_error
        assert out == {
            "faces": DEFAULT_PHRASE,
            "plates": DEFAULT_PHRASE,
            "person_reid": DEFAULT_PHRASE,
        }
        assert sorted(seen) == [
            ("faces", "stage_error"),
            ("person_reid", "stage_error"),
            ("plates", "stage_error"),
        ]
        assert _log_sig(records) == [
            ("WARNING", "specialist stage failed as a whole", (_MISSING,) * 4, (RuntimeError,))
        ]
    finally:
        undo_log()
        restore()
