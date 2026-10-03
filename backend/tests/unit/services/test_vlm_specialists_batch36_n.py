# TARGET-MODULE: backend.services.vlm_specialists
"""Battery N — campaign #12 RUN 2 (batch-36): closes the 13 survivors run 1
left open on ``backend/services/vlm_specialists.py``.

Run 1 (battery M) took the module 441/777 -> 904/930 and left exactly:

* 12 BIRTH survivors — keys the battery's own coverage growth brought under
  mutation (new x__default_gallery_match fn, later x__collect_face_texts
  slots, later x__collect_plate_text / x__collect_reid_text slots). These are
  TEST GAPS, not equivalents: the new code paths were never exercised.
* 1 stale-era KILL LOSS — ``x__person_crops__mutmut_55`` (the unreadable-frame
  ``continue`` -> ``break``), killed by a SHIPPED test in an older bank era and
  re-verified GREEN by this run against the current suite (campaign #9's
  two-run precedent: the honest fix is a second battery, never a floor bend).

Harness-compatible by design (batch-30 single-process sweep): module-level
sync ``test_*()`` only, no fixtures, coroutines via ``asyncio.run``; seam
swaps restore in ``finally``.

Honesty ledger — dispositions registered EQUIVALENT at authoring: NONE. All
13 open keys are KILLABLE by construction (break-twins need a survivor AFTER
the skip site; the gallery belt and the plate image flow need identity
asserts; the reid leg_failed detail sites need the exact log list). A sweep
GREEN here is a test gap, not an equivalence.

Helpers are copied from battery M (same batch, same seams) so the two files
stay independently runnable; M keeps owning the rest of the module.
"""

import asyncio
import logging
import sys
import types

import backend.services.vlm_specialists as vs

#: default phrase a degraded line takes (pinned against the shipped module)
DEFAULT_PHRASE = f"{vs.UNAVAILABLE}: specialist did not run"

_MISSING = object()


class _Box:
    """Attribute namespace for seam payloads."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _module_stub(mods):
    """Set attrs on modules; fake a module that is not imported yet.

    ``mods`` maps dotted-module -> {attr: value}. Returns a callable that
    restores sys.modules/attrs exactly (every seam vlm_specialists imports
    lives INSIDE the functions, so a call-time attribute swap reaches the
    trampoline render worlds too).
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


class FaceErr(Exception):
    pass


def _pil_stub2(open_raises=()):
    def open_frame(path):
        if path in open_raises:
            raise OSError(f"cannot read {path}")

        frame = _Box(path=path, size=(200, 100), mode="L", convert_calls=[])

        def load():
            return None

        def convert(mode):
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


class _Crop:
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


def _faithful_validator(bbox, width, height):
    x1, y1, x2, y2 = bbox
    cx1, cy1 = max(0.0, x1), max(0.0, y1)
    cx2, cy2 = min(float(width), x2), min(float(height), y2)
    if cx2 <= cx1 or cy2 <= cy1:
        return _Box(is_valid=False, clamped_bbox=None)
    return _Box(is_valid=True, clamped_bbox=(cx1, cy1, cx2, cy2))


def _bbox_stub():
    return {"backend.services.bbox_validation": {"validate_and_clamp_bbox": _faithful_validator}}


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

    def passes_quality_gate(*, face_px, score, min_px, min_score):
        return face_px >= min_px and score >= min_score

    return (
        {
            "backend.services.face_recognizer_loader": {
                "detect_faces": detect_faces,
                "align_face_crop": align_face_crop,
                "extract_face_embedding": extract_face_embedding,
                "get_face_leg_handles": get_handles,
                "FaceRecognizerError": FaceErr,
                "passes_quality_gate": passes_quality_gate,
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


async def _no_gallery(*_args):
    raise AssertionError("gallery must not be consulted")


# ---------------------------------------------------------------------------
# run-2 target 1/5: the unreadable-frame skip must SKIP, not STOP
# (_person_crops m55 — the stale-era kill this run re-earns)
# ---------------------------------------------------------------------------


def test_person_crops_unreadable_frame_does_not_end_scan():
    # m55 (continue -> break at the OSError skip): the discriminating shape
    # is an UNREADABLE detection BEFORE a readable one — battery M only held
    # the unreadable case AFTER the keepers, so break read identical there.
    stubs = {**_pil_stub2(open_raises=("bad",)), **_bbox_stub()}
    restore = _module_stub(stubs)
    try:
        # "bad" MUST be among the picks: outside them it is dropped by the
        # selector filter BEFORE the try/except OSError — the skip site the
        # break twin mutates never runs (battery M's gap, exactly).
        out = vs._person_crops(
            [_person_dict(path="bad"), _person_dict(det_id=9, path="f1")], {"bad", "f1"}
        )
        assert [(c.source, det_id) for c, det_id in out] == [("f1", "9")]
        # and the full-order matrix again with the bad one FIRST of several
        out2 = vs._person_crops(
            [
                _person_dict(path="bad"),
                _person_dict(det_id=1, path="f1"),
                _person_dict(path="bad"),
                _person_dict(det_id=2, path="f1"),
            ],
            {"bad", "f1"},
        )
        assert [det_id for _, det_id in out2] == ["1", "2"]
    finally:
        restore()


# ---------------------------------------------------------------------------
# run-2 target 2/5: the three face-leg break twins (m35 OSError skip,
# m59 detect-failure skip, m91 embedding-failure skip)
# ---------------------------------------------------------------------------


def test_face_leg_unreadable_frame_does_not_end_scan():
    # m35: "bad" BEFORE the readable frame — under break the leg answers
    # frames_unreadable instead of scoring the frame it could read.
    seen = []
    stubs, calls = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}),
        [[_face()]],
    )
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(open_raises=("bad",)), **stubs})
    try:
        out = _collect_face(["bad", "f1"])
        assert [(o.kind, getattr(o, "code", None)) for o in out] == [("unknown", None)]
        assert calls["detect"] == [("det-s", "f1")]  # only the readable frame scanned
        assert seen == []  # a skipped frame is not an unavailable event
    finally:
        restore()


def test_face_leg_detect_failure_does_not_end_scan():
    # m59: two readable frames with the detector raising -> TWO
    # detection_failed outcomes; break yields one (the scan died at the first).
    seen = []
    stubs, calls = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}),
        [],
        detect_raises=FaceErr("det blew up"),
    )
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs})
    try:
        out = _collect_face(["f1", "f2"])
        assert [(o.kind, o.code) for o in out] == [
            ("unavailable", "detection_failed"),
            ("unavailable", "detection_failed"),
        ]
        assert all("det blew up" in o.reason for o in out)
        assert calls["detect"] == [("det-s", "f1"), ("det-s", "f2")]
    finally:
        restore()


def test_face_leg_embedding_failure_does_not_end_face_loop():
    # m91: two landmarked faces on one frame, embedding raising on both ->
    # TWO embedding_failed outcomes; break stops after the first face.
    seen = []
    stubs, calls = _face_stub(
        ({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}),
        [[_face(), _face(bbox=(60.0, 10.0, 160.0, 100.0))]],
        extract_raises=FaceErr("embed blew up"),
    )
    restore = _module_stub({**_metrics_stub(seen), **_pil_stub2(), **stubs})
    try:
        out = _collect_face(["f1"])
        assert [(o.kind, o.code) for o in out] == [
            ("unavailable", "embedding_failed"),
            ("unavailable", "embedding_failed"),
        ]
        assert all("embed blew up" in o.reason for o in out)
        # both probes used the SAME rec-handle session (identity read)
        assert [sess for sess, _crop in calls["extract"]] == ["rec-s", "rec-s"]
    finally:
        restore()


# ---------------------------------------------------------------------------
# run-2 target 3/5: _default_gallery_match probe-belt wiring
# (m1 default None -> ""; m12 handles[1].get("model_id") or "" -> or "XXXX")
# ---------------------------------------------------------------------------


def _gal_stub(handles, match_impl):
    return {
        "backend.services.face_recognizer_loader": {"get_face_leg_handles": lambda: handles},
        "backend.services.face_recognition_service": {
            "get_face_recognition_service": lambda: _Box(match_face=match_impl)
        },
    }


def test_default_gallery_match_belt_and_passthrough():
    calls = []

    async def match_face(session, vector, *, threshold, model_id):
        calls.append((session, vector, threshold, model_id))
        return {"matched": True, "person_name": "Ann"}

    restore = _module_stub(
        _gal_stub(({"session": "det-s"}, {"session": "rec-s", "model_id": "arc-x"}), match_face)
    )
    try:
        out = asyncio.run(vs._default_gallery_match(SESSION, [0.5], 0.35))
        assert out == {"matched": True, "person_name": "Ann"}
        # the belt is the handle's model_id, verbatim (m12: "XXXX" would
        # forward the literal; m1: the mutated default leaks "" when handles
        # are gone — see the second scenario)
        assert calls == [(SESSION, [0.5], 0.35, "arc-x")]
    finally:
        restore()

    # handles gone mid-call (unload race): the belt stays None — NOT ""
    calls.clear()
    restore = _module_stub(_gal_stub(None, match_face))
    try:
        out = asyncio.run(vs._default_gallery_match(SESSION, [0.5], 0.35))
        assert calls == [(SESSION, [0.5], 0.35, None)]
        assert out["matched"] is True
    finally:
        restore()

    # handle present but UNNAMED (empty model_id): the belt normalizes the
    # falsy id to None — the sentinel, never "" and never "XXXX"
    calls.clear()
    restore = _module_stub(
        _gal_stub(({"session": "det-s"}, {"session": "rec-s", "model_id": ""}), match_face)
    )
    try:
        asyncio.run(vs._default_gallery_match(SESSION, [0.5], 0.35))
        assert calls == [(SESSION, [0.5], 0.35, None)]
    finally:
        restore()


# ---------------------------------------------------------------------------
# run-2 target 4/5: the plate leg's image flow (m10 image=None,
# m11 np.asarray(None), m13 Image.open(None), m19 run_fast_alpr(alpr, None))
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


def _np_recording(dtype_seen):
    sentinel = object()

    def asarray(arr, dtype=None):
        box = _Box(arr=arr, dtype=dtype)
        dtype_seen.append(box)
        return box

    return {"numpy": {"asarray": asarray, "float32": sentinel}}, sentinel


def test_collect_plate_text_image_identity_reaches_alpr():
    # the image object that reaches run_fast_alpr must be exactly
    # np.asarray(Image.open(path).convert("RGB")) — path, convert mode, and
    # array identity are all pinned (kills None-array, open(None), and the
    # dropped-image polarity).
    calls = {"load": [], "run": []}
    arr_seen = []
    match_calls = []

    async def fake_match(plate_texts):
        match_calls.append(list(plate_texts))
        return []

    plan = [[_Box(text="ABC123")]]
    stubs_n, _ = _np_recording(arr_seen)
    restore = _module_stub(
        {
            **_metrics_stub([]),
            **_pil_stub2(),
            **_alpr_stub(plan, calls),
            **stubs_n,
            "backend.services.vlm_specialists": {"_match_plate_vehicles": fake_match},
        }
    )
    try:
        out = asyncio.run(vs.collect_plate_text(frame_paths=["f1"]))
        assert out == "ABC123 - not a household plate"
        assert match_calls == [["ABC123"]]
        assert calls["run"][0][0].alpr == "ALPR"
        assert len(arr_seen) == 1
        # np.asarray got the CONVERTED frame object, and the alpr call got
        # exactly that array back (one identity chain, no None in the middle)
        arr_box = arr_seen[0]
        converted = arr_box.arr
        assert converted.source == "f1" and converted.converted and converted.mode == "RGB"
        assert calls["run"][0][1] is arr_seen[0]
    finally:
        restore()


def test_collect_plate_text_unreadable_frame_skipped_not_fatal():
    # the plate leg's own OSError skip: "bad" before "f1" contributes no
    # image, but the readable frame still runs the ALPR.
    calls = {"load": [], "run": []}
    arr_seen = []

    async def fake_match(plate_texts):
        return []

    plan = [[_Box(text="XYZ")]]  # indexed per run_fast_alpr CALL: only f2 is readable
    stubs_n, _ = _np_recording(arr_seen)
    restore = _module_stub(
        {
            **_metrics_stub([]),
            **_pil_stub2(open_raises=("bad",)),
            **_alpr_stub(plan, calls),
            **stubs_n,
            "backend.services.vlm_specialists": {"_match_plate_vehicles": fake_match},
        }
    )
    try:
        out = asyncio.run(vs.collect_plate_text(frame_paths=["bad", "f2"]))
        assert out == "XYZ - not a household plate"
        assert [getattr(a.arr, "source", None) for a in arr_seen] == ["f2"]
        assert len(calls["run"]) == 1
    finally:
        restore()


# ---------------------------------------------------------------------------
# run-2 target 5/5: the collect_reid_text stage's leg_failed DETAIL sites
# (m20 detail=None, m23 kwarg dropped, m28 detail=str(None))
# ---------------------------------------------------------------------------


def test_collect_reid_text_leg_failed_detail_exact_log():
    # the wrapper's degradation logs the human-readable WHY with exact extra;
    # the three detail mutants all erase or falsify that detail
    seen = []
    records, undo_log = _logs()

    async def explode(**kw):
        raise ValueError("reid inner blew")

    restore = _module_stub(
        {
            **_metrics_stub(seen),
            "backend.services.vlm_specialists": {"_collect_reid_text": explode},
        }
    )
    try:
        out = asyncio.run(vs.collect_reid_text(frame_paths=["f1"]))
        assert out == DEFAULT_PHRASE
        assert seen == [("person_reid", "leg_failed")]
        assert _log_sig(records) == [
            ("WARNING", "person_reid specialist failed", (_MISSING,) * 4, (ValueError,)),
            (
                "WARNING",
                "specialist unavailable",
                ("person_reid", "leg_failed", "reid inner blew", _MISSING),
                None,
            ),
        ]
    finally:
        undo_log()
        restore()
