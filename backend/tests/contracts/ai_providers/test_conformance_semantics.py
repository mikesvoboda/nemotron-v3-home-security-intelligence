"""WP8.3 S1-S9 - the semantic trap table, one cluster per bullet.

NINE BULLETS, NINE CLASSES, NINE GRIP NOTES (plan:946-955), retargeted onto
the shipped post-R8-S3 surface: 9 operations and the two adapters the
gateway actually mounts (/yolo26, /enrich-lt). Every bullet still has a test
whose name starts with its own id, so the plan table is still checkable
against this file by name. What a bullet no longer has is split two ways, and
the split is the record:

  * RETARGETED - the trap still lives somewhere, so the test now drives the
    surviving text: S1's positional triple moved onto the COCO table and the
    named-field model that survived in ai/yolo26/pose_estimation.py; S4, S5
    and S6 ride the surviving prompt and confidence surfaces; S7 is untouched
    (the band divergence was never a provider property); S9's envelope pin now
    sweeps the whole registry, each op against the artifact that really states
    its root keys (the golden where a response model exists, the marker's
    x-deployed-keys where one does not).
  * TOMBSTONED - the subject is gone and the hazard is written out in full in
    the def's docstring, asserted ABSENT (op id not in the registry, module
    not importable, file not on disk), plus a non-vacuity block. House style,
    copied from test_conformance_geometry.py's G2/G3/G7 tombstones. Dead
    subjects are never skipped or xfailed.

The R8 S3 rulings that decided the split (docs/vss-integration/ledger):
ruling 1 retires Florence whole, ruling 4 sweeps ai/florence, ai/clip,
ai/enrichment and ai/enrichment-light off disk, ruling 5 retires CLIP as a
consequence of the Triton prune; the keep set is yolo26 / reid / threat. So
the pose, action-classify, composite-enrich, Florence-prompt and
embedding-space traps lost their providers: /pose-analyze is a real 404 (G9
pins it), the registry has 9 operations and none of them takes a frames list
or returns an action distribution, and neither surviving adapter runs an
ensemble.

The same discipline transfers to this file's own surface: nothing here is
hand-listed from memory. The gateway mount table is read out of
ai/gateway/main.py (imports paired with include_router calls, the shape
main.py uses), the per-slot op sets come from operations_for_slot(), the
not-wired census from client_methods == [], the confidence-emitting set from
the schemas and goldens, and the multi-frame set from the request schemas'
multipart key lists. A hand-listed table is exactly what rotted here once
already.

Nothing in this file touches network/GPU/weights: adapters run with their
Triton client patched to a canned tensor (the seam doctrine: the stub sits
below the HTTP boundary, the response is the production serializer), the fake
runs over ASGITransport, and every corpus read is scoped by
_source_corpus() - a whole-tree AST walk is a budget breach (WP1.3).
"""

from __future__ import annotations

import ast
import base64
import inspect
import json
import re
from collections.abc import AsyncIterator, Iterator
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from typing import Any, get_origin, get_type_hints
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from backend.ai_contract import OPERATION_IDS, OPERATIONS
from backend.ai_contract.fake.app import create_fake_app
from backend.ai_contract.provider import (
    PROVIDER_SLOT,
    ProviderId,
    operations_for_slot,
    register_provider,
    registered_providers,
)
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[4]
ADAPTER_DIR = REPO_ROOT / "ai/gateway/adapters"
GATEWAY_MAIN_SRC = REPO_ROOT / "ai/gateway/main.py"
POSE_EST_SRC = REPO_ROOT / "ai/yolo26/pose_estimation.py"
SEVERITY_TS_SRC = REPO_ROOT / "frontend/src/utils/severityCalculator.ts"
CONFIDENCE_TS_SRC = REPO_ROOT / "frontend/src/utils/confidence.ts"
GOLDEN_DIR = REPO_ROOT / "backend/tests/contracts/ai_providers/golden/payloads"
SCHEMA_DIR = REPO_ROOT / "backend/ai_contract/schemas"
SUITE_DIR = REPO_ROOT / "backend/tests/contracts/ai_providers"
# The five sibling files this cluster's tombstones cite BY NAME: a tombstone
# that hands its own hazard to a sibling has to be able to notice when the
# sibling stops owning it, so the citation is a path read, not a memory.
SIBLING_MODULES = {
    "ops": SUITE_DIR / "test_conformance_ops.py",
    "geometry": SUITE_DIR / "test_conformance_geometry.py",
    "numeric": SUITE_DIR / "test_conformance_numeric.py",
    "clientconf": SUITE_DIR / "test_client_conformance.py",
    "vlm": SUITE_DIR / "test_conformance_vlm.py",
}
# The frozen verbatim copy of the deleted analyzer's think-tag plumbing
# (R8 S2): the behavior claim is pinned against the same code that made it
# true, and its header records both historical cite sets.
RETIRED_ANALYZER_SRC = SUITE_DIR / "retired_providers.py"

# The nine operations, read from the generated registry.
OP_IDS = set(OPERATION_IDS)
assert len(OP_IDS) == 9, f"expected 9 operations, got {sorted(OP_IDS)}"

# The COCO-17 body-keypoint table, in canonical order (pose_estimation.py
# KEYPOINT_NAMES is the same list; s1a pins the DB comment against it).
COCO_17 = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]


def _source_corpus(*roots: str) -> Iterator[Path]:
    """Ship-adjacent .py files, with the two walking hazards carved out:
    __pycache__ (duplicate/stale trees) and /tests/ - the retired
    services' OWN test suites still sit on disk and import the deleted
    modules as prose-shaped fixture paths, so a corpus that includes them
    reports the dead surface as live (measured: the only surviving
    "pose-analyze" spellings in ai/ are in ai/yolo26/tests/).
    """
    for root in roots:
        for path in (REPO_ROOT / root).rglob("*.py"):
            parts = path.relative_to(REPO_ROOT).parts
            if "__pycache__" in parts or "tests" in parts:
                continue
            yield path


# The gateway's real mount table, derived from main.py the way the gateway
# itself states it: the "from ai.gateway.adapters.X import router as Y" lines
# paired with the "app.include_router(Y, prefix=\"/Z\")" lines. The old
# hand-listed five-entry table is what made this module's gateway fixture
# raise ModuleNotFoundError on a swept adapter - a fixture that cannot build
# the app reports neither pass nor fail, which is the worst of the three
# states. Deriving it means a third mount moves these tests with it instead
# of breaking them.
_IMPORT_ALIAS_RE = re.compile(r"from (ai\.gateway\.adapters\.\w+) import router as (\w+)")
_MOUNT_RE = re.compile(r"app\.include_router\((\w+),\s*prefix=\"([^\"]+)\"")


def _production_mounts() -> tuple[tuple[str, str], ...]:
    src = GATEWAY_MAIN_SRC.read_text(encoding="utf-8")
    alias_to_module = {alias: module for module, alias in _IMPORT_ALIAS_RE.findall(src)}
    assert alias_to_module, f"{GATEWAY_MAIN_SRC.name} no longer imports adapter routers"
    mounts = [(alias_to_module[alias], prefix) for alias, prefix in _MOUNT_RE.findall(src)]
    assert mounts, f"{GATEWAY_MAIN_SRC.name} no longer include_router()s anything"
    return tuple(mounts)


GATEWAY_MOUNTS = _production_mounts()
GATEWAY_MODULES = {module for module, _prefix in GATEWAY_MOUNTS}
# One patch target per mounted module: a Triton-backed adapter whose client
# is NOT stubbed would hit a real gRPC port inside a contract test. Derived,
# so a mounted adapter cannot escape the stub.
GATEWAY_PATCH_TARGETS = tuple(f"{module}.get_triton_client" for module in sorted(GATEWAY_MODULES))
assert {"ai.gateway.adapters.yolo26", "ai.gateway.adapters.enrichment_light"} == GATEWAY_MODULES, (
    f"gateway modules drifted from the shipped pair: {sorted(GATEWAY_MODULES)}"
)


# The registry's Operation record has NO handler field (id/method/path/
# availability/client_methods/evidence), so the op -> handler join is made the
# way FastAPI makes it: full path = mount prefix + route path, method match,
# function object read out of the mounted router. Derived, because a hand
# map of op id to function name is the same class of rot as the hand mount
# table above - it names things that a router edit silently renames.
def _route_handlers() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for module_name, prefix in GATEWAY_MOUNTS:
        for route in import_module(module_name).router.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None:
                continue
            methods = set(getattr(route, "methods", set()) or set())
            for op_id, op in OPERATIONS.items():
                if op.path == f"{prefix}{route.path}" and op.method in methods:
                    out[op_id] = endpoint
    return out


ROUTE_HANDLERS = _route_handlers()


def _multipart_ops() -> set[str]:
    """Ops whose REQUEST schema is the multipart marker: the generator emits a
    top-level ``contentEncoding: binary`` for UploadFile routes, so the marker
    is the schema's own shape and not a property list.

    A MISSING request schema is not an error here: the golden generator emits
    a request artifact only when a request schema exists
    (scripts/gen-ai-contract.py), and the enrich-lt ops share one request
    model the generator does not walk. Their absence from this set is the
    correct answer - and a bare ``read_text()`` would turn that legitimate
    absence into a collection ERROR, the worst of the three states and the
    exact failure this module's mount table was just rebuilt to avoid.
    """
    result: set[str] = set()
    for op_id in OP_IDS:
        path = SCHEMA_DIR / f"{op_id}.request.json"
        if not path.exists():
            continue
        if "binary" in json.loads(path.read_text(encoding="utf-8")).get("contentEncoding", ""):
            result.add(op_id)
    return result


MULTI_IMAGE_OPS = _multipart_ops()
assert {"yolo26_detect", "yolo26_detect_batch", "yolo26_segment"} == MULTI_IMAGE_OPS, (
    f"multipart ops drifted from the measured census: {sorted(MULTI_IMAGE_OPS)}"
)


def _upload_keys(op_id: str) -> list[str]:
    """The route's upload parameter NAME(S), read out of the mounted
    handler's own signature: /yolo26/detect takes ``file``,
    /yolo26/detect/batch takes ``files``. The wrong key is a 422 from FastAPI
    before any adapter code runs, so a hand-listed key rots the moment a
    router renames its parameter - and a parameter rename is exactly what a
    router edit does.
    """
    sig = inspect.signature(ROUTE_HANDLERS[op_id])
    return [name for name, param in sig.parameters.items() if "UploadFile" in str(param.annotation)]


# A route that accepts SEVERAL images annotates its upload parameter as a
# collection of UploadFile (/yolo26/detect/batch: ``files: list[UploadFile]``)
# while a single-image route names one (``file: UploadFile``). Both have
# exactly one upload parameter, so the arity test below reads the annotation,
# not the parameter count.
MULTI_UPLOAD_OPS = {
    op_id
    for op_id in MULTI_IMAGE_OPS
    if any(
        "list[" in str(param.annotation) or "Sequence" in str(param.annotation)
        for name, param in inspect.signature(ROUTE_HANDLERS[op_id]).parameters.items()
        if "UploadFile" in str(param.annotation)
    )
}
assert {"yolo26_detect_batch"} == MULTI_UPLOAD_OPS, (
    f"multi-upload routes drifted from the measured census: {sorted(MULTI_UPLOAD_OPS)}"
)


def _json_body_for(op_id: str) -> dict[str, Any]:
    """A legal JSON body for a mounted JSON route, built from that route's
    OWN pydantic request model. The two enrich-lt ops have no request schema
    in the contract (they share one request model the generator does not
    walk) - which is precisely why the body is read off the model rather than
    hand-listed: an added required field would otherwise make these drives a
    422, and a 422 reads as "the provider refused" instead of "the test sent
    the wrong thing".
    """
    fn = ROUTE_HANDLERS[op_id]
    model = next(
        (
            hint
            for name, hint in get_type_hints(fn).items()
            if name != "return" and isinstance(hint, type) and issubclass(hint, BaseModel)
        ),
        None,
    )
    assert model is not None, f"{op_id} takes no pydantic body model; re-derive this drive"
    body: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue
        origin = get_origin(field.annotation) or field.annotation
        if origin is str:
            body[name] = _png_b64()  # every required string on this surface IS an image
        elif origin is int:
            body[name] = 1
        elif origin is float:
            body[name] = 1.0
        elif origin is bool:
            body[name] = False
        elif origin is list:
            body[name] = []
        else:  # pragma: no cover - a new required type is handled, never guessed
            raise AssertionError(f"{model.__name__}.{name}: unhandled required {origin!r}")
    assert body, f"{model.__name__} declares no required field; this drive would send an empty body"
    return body


def _gateway_kwargs(op_id: str) -> dict[str, Any]:
    """Transport kwargs for driving one registry op against the mounted
    gateway app, derived per op: multipart routes get one real PNG per
    declared upload key (TWO for the batch route, since the per-file fan-out
    is what s8b drives), JSON routes get a body built from their own model.
    """
    if op_id in MULTI_IMAGE_OPS:
        n = 2 if op_id in MULTI_UPLOAD_OPS else 1
        return {
            "files": [
                (key, ("frame.png", _png_bytes(), "image/png"))
                for key in _upload_keys(op_id)
                for _ in range(n)
            ]
        }
    return {"json": _json_body_for(op_id)}


def _png_bytes() -> bytes:
    import zlib

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return len(data).to_bytes(4, "big") + tag + data + zlib.crc32(tag + data).to_bytes(4, "big")

    ihdr = (256).to_bytes(4, "big") + (256).to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    raw = b"".join(b"\x00" + bytes(256 * 3) for _ in range(256))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )


def _png_b64() -> str:
    return base64.b64encode(_png_bytes()).decode("ascii")


# Canned Triton tensors: one SHAPE per mounted model, because the two mounted
# post-processors read OPPOSITE layouts (measured, not assumed):
#
#   * yolo26 reads ANCHOR-MAJOR rows [x, y, w, h, score, class_id], so a
#     (1, 5, 6) row set is one detection at score 0.9.
#   * the threat reader transposes whenever rows < cols and then slices
#     ``preds[:, 4:]`` as the class block, so its legal shape is (1, 8, N) with
#     N > 8: four box rows plus four class-score rows, anchors down the LAST
#     axis. The yolo tensor is NOT legal there - its class block slices to zero
#     columns and np.argmax raises "attempt to get argmax of an empty
#     sequence", which /enrich-lt/threat-detect turns into a 400. That is the
#     layout divergence s6c states in prose, and it is why the tensor is chosen
#     by model name instead of shared.
GATEWAY_CANNED_ROWS = np.array([[[10.0, 20.0, 110.0, 60.0, 0.9, 0]]], dtype=np.float32)
# Only anchor 0 scores above the adapter's 0.25 threshold, so the threat drive
# emits exactly one row: enough for the row-level range checks below, few
# enough to read in a failure message.
_THREAT_ANCHORS = 12
_threat_boxes = np.tile(
    np.array([[100.0], [100.0], [40.0], [80.0]], dtype=np.float32),
    (1, _THREAT_ANCHORS),
)
_threat_scores = np.zeros((4, _THREAT_ANCHORS), dtype=np.float32)
_threat_scores[0, 0] = 0.9
GATEWAY_THREAT_ROWS = np.vstack((_threat_boxes, _threat_scores))[np.newaxis, :, :]
assert GATEWAY_THREAT_ROWS.shape == (1, 8, _THREAT_ANCHORS), GATEWAY_THREAT_ROWS.shape
ENRICH_LT_EMBEDDING = np.zeros((1, 512), dtype=np.float32)


def _fake_triton() -> AsyncMock:
    """Canned Triton client for the mounted adapters (one tensor for every
    model name, image-shaped outputs where the adapter wants an image)."""
    triton = AsyncMock()
    triton.is_model_ready.return_value = True
    # Spelled out rather than left to AsyncMock's auto-attribute: /yolo26/segment
    # awaits this and iterates metadata["outputs"], and a bare AsyncMock hands it
    # a MagicMock - which raises inside the adapter's try/except and leaks an
    # un-awaited coroutine warning into every segment drive.
    triton.get_model_metadata.return_value = {"outputs": [{"name": "output0"}]}
    triton.infer.side_effect = lambda **kw: _canned_for(kw.get("model_name"), kw.get("outputs"))
    return triton


def _canned_for(model_name: Any, outputs: Any) -> dict[str, Any]:
    names = list(outputs or [])
    out: dict[str, Any] = {}
    for name in names:
        if model_name == "reid":
            out[name] = ENRICH_LT_EMBEDDING
        elif model_name == "threat":
            out[name] = GATEWAY_THREAT_ROWS
        else:
            out[name] = GATEWAY_CANNED_ROWS
    if not names:
        return {"output0": GATEWAY_CANNED_ROWS}
    return out


@pytest.fixture
def fake_app() -> FastAPI:
    return create_fake_app()


@pytest.fixture
async def fake_client(fake_app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=fake_app), base_url="http://fake") as client:
        yield client


@pytest.fixture
def gateway_app() -> FastAPI:
    """A FRESH app mounting exactly what production mounts (GATEWAY_MOUNTS):
    FastAPI router state is per-instance, so an app here must never be shared
    with production's module-level object (the doctrine geometry G9 states).
    """
    app = FastAPI(title="S-emantics gateway app (contract suite)")
    for module, prefix in GATEWAY_MOUNTS:
        router = import_module(module).router
        app.include_router(router, prefix=prefix)
    return app


@pytest.fixture
async def gateway_client(gateway_app: FastAPI) -> AsyncIterator[AsyncClient]:
    # Every Triton seam in the MOUNTED set is patched to the canned tensor:
    # the entry point is production adapter code, and the only fake thing
    # below the HTTP boundary is the gRPC call. The targets are derived from
    # main.py, so a newly mounted Triton-backed adapter cannot slip a real
    # socket into the contract tier - which is what a hand-listed pair of
    # patch() calls would have failed to guarantee on its third mount.
    with ExitStack() as stack:
        for target in GATEWAY_PATCH_TARGETS:
            stack.enter_context(patch(target, return_value=_fake_triton()))
        async with AsyncClient(
            transport=ASGITransport(app=gateway_app), base_url="http://gateway"
        ) as client:
            yield client


# --- S1: pose keypoints are POSITIONAL triples -----------------------------


class TestS1PoseKeypointsArePositional:
    """THE GATEWAY POSE LEG IS RETIRED; THE TRIPLE SURVIVES, AND SO DOES THE
    ONE UNCONSTRAINED COLUMN THAT HOLDS IT.

    s1b/s1d below carry the retired fake/gateway legs in full. s1a and s1c
    now retarget onto the surviving spellings of the same positional triple:
    the DB comment, the API schema's arity-blind list, and the 17x3 ndarray
    reader that still ships and still consumes triples positionally.
    """

    def test_s1a_db_column_comment_declares_the_triple_with_conf_last(self) -> None:
        from backend.models.enrichment import PoseResult

        col = PoseResult.__table__.columns["keypoints"]
        comment = col.comment or ""
        # The comment is the ONLY thing telling a consumer how to read this
        # JSONB blob; no schema, no validator, no fixture.
        assert "[[x, y, conf], ...]" in comment, (
            f"pose_results.keypoints comment no longer names the triple with "
            f"conf LAST; a consumer that infers the shape reads it wrong: {comment!r}"
        )
        assert "17 COCO keypoints" in comment, (
            f"pose_results.keypoints comment lost its 17-COCO arity claim: {comment!r}"
        )

    def test_s1b_pose_provider_and_route_are_retired(self) -> None:
        """TOMBSTONE: THE POSE PROVIDER, ITS FAKE LEG AND ITS CLIENT WERE ALL
        SWEPT, AND THE WIRE ARTIFACT THAT COULD CARRY THE ARITY SLIP NO LONGER
        EXISTS.

        This def used to POST a 17-row STGCN tensor to the fake at
        ``/enrich-lt/pose-analyze`` and assert that the items of ``keypoints``
        came back NAMED. Three hazards lived behind that:

          (a) ARITY SLIPS QUIETLY. The fake walks a response schema's
              ``items`` list positionally, and the pose schema declared FOUR
              item properties (x / y / confidence / label). A consumer reading
              triples [x, y, conf] off the gateway would have read the wrong
              slot for conf - and a four-property item and a three-property
              item are both valid against an arity-blind
              ``list[list[float]]``. Nothing on the wire could detect the
              slip, which is why it was pinned from schema text.
          (b) LABEL-FREE ROWS WERE THE GATEWAY TRUTH AND THE FAKE CONTRADICTED
              IT: the legacy adapter built pose rows as {x, y, confidence}
              with NO label while the fake's schema walk handed every consumer
              a label, so a consumer that trusted the fake crashed on the
              deployed provider's first pose row.
          (c) A CLIENT THAT SWALLOWED ITS OWN ERROR SHAPE: the retired
              enrichment client decoded the keypoint list out of the data
              envelope BEFORE checking the envelope's success flag, so a
              failed response became an empty list, the "person present"
              test became False, and the route answered 200 "no person" - a
              silent data-loss verdict off a transport error.

        Retired by R8 S3 rulings 3/4/5 (the Triton repository keeps only
        yolo26 / reid / threat) plus R8 S2's enrichment-tier client deletion.
        Two of the three halves have named surviving owners:

          (b) LABEL-FREE: no pose op is in the registry, and the only
              label-bearing keypoint spelling that ships is the Pydantic
              ``Keypoint`` in ai/yolo26/pose_estimation.py, which carries
              ``name`` as an EXPLICIT field - asserted by test_s1c below, so
              the label-bearing form can no longer be faked by a schema walk.
          (c) CLIENT ABSENCE:
              test_client_conformance.py's ``test_retired_client_modules_are_
              unimportable`` owns the import-level proof for the deleted
              client modules, including the enrichment one.

        Half (a) has NO surviving owner and cannot retarget: the schemas it
        was read out of are gone with the ops, and the shape that remains is
        the DB-side blob plus the ai/yolo26 producer, both of which are
        positionally pinned in s1a/s1c. If a pose op comes back, the arity
        pin must be re-derived from ITS response schema before any consumer
        trusts the blob - that is what this record is for.
        """
        # (i) The op ids are gone from the registry.
        assert "enrich_lt_pose_analyze" not in OP_IDS
        assert "enrichment_pose_analyze" not in OP_IDS
        assert not any("pose" in op_id for op_id in OP_IDS), (
            f"a pose-shaped op returned ({sorted(o for o in OP_IDS if 'pose' in o)}); "
            "the arity half above has a subject again and must be re-derived"
        )
        # (ii) No pose schema artifact survives either: the tombstone would be
        # asserting against a schema file that no generation pass writes.
        assert not list(SCHEMA_DIR.glob("*pose*")), (
            f"a pose schema came back: {sorted(p.name for p in SCHEMA_DIR.glob('*pose*'))}"
        )
        # (iii) No mounted adapter can serve a pose route: the mounted pair is
        # pinned at module import, and no adapter file defines a pose path.
        assert {module.rsplit(".", 1)[1] for module in GATEWAY_MODULES} == {
            "yolo26",
            "enrichment_light",
        }
        # LIVE form only: the retired route names appear in the surviving
        # adapters' docstrings as prose about the prune, so a bare substring
        # search would read the retirement record as a resurrection.
        for py in ADAPTER_DIR.glob("*.py"):
            assert 'router.post("/pose-analyze"' not in py.read_text(encoding="utf-8"), (
                f"{py.name} mounts a pose route again while no pose op exists"
            )
        # (iv) The retired serving directories stayed swept (ruling 4) and the
        # client is unimportable, asserted the safe way - an import that must
        # fail, never a file read against a staged-deleted path.
        for dead_dir in ("ai/enrichment", "ai/enrichment-light"):
            assert not (REPO_ROOT / dead_dir).exists(), f"{dead_dir} came back on disk"
        with pytest.raises(ModuleNotFoundError):
            import_module("backend.services.enrichment_client")
        # NON-VACUITY: the absences above are read against live artifacts.
        assert len(list(SCHEMA_DIR.glob("*.response.json"))) == len(OP_IDS), (
            "the schema corpus and the registry disagree; 'no pose schema' proves nothing"
        )
        assert {
            "enrich_lt_person_reid",
            "enrich_lt_threat_detect",
            "yolo26_detect",
        } <= OP_IDS, "the keep set left the registry; this tombstone lost its contrast"
        sibling = SIBLING_MODULES["clientconf"].read_text(encoding="utf-8")
        assert "def test_retired_client_modules_are_unimportable" in sibling, (
            "the client-side half of this hazard is no longer owned by the "
            "sibling this tombstone cites - re-home it before trusting (iv)"
        )

    def test_s1c_conf_is_read_positionally_and_the_named_model_names_it(self) -> None:
        """THE TRIPLE, RETARGETED: the surviving reader unpacks conf from a
        fixed slot and the surviving model names it - two spellings of one
        contract, both asserted.

        s1c used to compare the gateway adapter's positional row unpack
        against the fake's 4-property item schema. Both sides are gone with
        the pose provider, but the triple is still consumed positionally by
        code that ships: pose_estimation.py reads ``(x, y, conf)`` out of a
        fixed (17, 3) row and indexes a 17-name table by POSITION, and its
        Pydantic model gives every slot a name. A COCO reindex (a name
        inserted at 3, say) reddens the index assertion and passes the
        table-equality one; the two together are what makes an unlabelled
        positional blob safe.
        """
        pose_src = POSE_EST_SRC.read_text(encoding="utf-8")
        # (i) The COCO table survives, in canonical order, at 17.
        tree = ast.parse(pose_src)
        names = None
        model_fields: dict[str, list[str]] = {}
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "KEYPOINT_NAMES" and isinstance(node.value, ast.List):
                    names = [str(elt.value) for elt in node.value.elts]
            if isinstance(node, ast.ClassDef):
                model_fields[node.name] = [
                    sub.target.id
                    for sub in node.body
                    if isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name)
                ]
        assert names == COCO_17, (
            f"KEYPOINT_NAMES drifted from the canonical COCO-17 table: {names!r}"
        )
        # (ii) KEYPOINT_INDICES is derived from that table and nowhere else
        # (a comprehension over KEYPOINT_NAMES, evaluated at import): a
        # hand-edited lookup that shifted one table and not the other is the
        # exact way a positional triple silently changes meaning. Read from
        # the live module, not from text.
        from ai.yolo26.pose_estimation import KEYPOINT_INDICES as LIVE_INDICES

        assert {name: i for i, name in enumerate(COCO_17)} == LIVE_INDICES, (
            f"KEYPOINT_INDICES diverged from the COCO order: {LIVE_INDICES!r}"
        )
        # (iii) The readers unpack the triple positionally, conf LAST, and the
        # formatter resolves a NAME by index - the hazard s1c was written for.
        assert "x, y, conf = keypoints[idx]" in pose_src, (
            "pose_estimation.py no longer unpacks the triple positionally; the "
            "arity assumption this pin exists for moved and must be re-homed"
        )
        assert "if conf < min_conf:" in pose_src, (
            "the triple's third slot is no longer read as a visibility/confidence "
            "gate - the conf-last convention lost its only reader"
        )
        assert "person_keypoints[i, 0]" in pose_src and "person_keypoints[i, 2]" in pose_src, (
            "pose_estimation.py no longer maps fixed slots 0/1/2 onto x/y/confidence"
        )
        assert "name=KEYPOINT_NAMES[i]" in pose_src, (
            "pose_estimation.py no longer resolves a keypoint's NAME by index; "
            "an unlabelled positional blob just lost its only labeller"
        )
        # (iv) The surviving Pydantic spellings: the NAMED model has one field
        # per slot (a label-bearing row is allowed to be label-bearing), and
        # the PUBLIC API schema stays arity-blind - the gap s1b/a pinned.
        assert model_fields["Keypoint"] == ["name", "x", "y", "confidence"], (
            f"Keypoint's field set changed: {model_fields.get('Keypoint')}"
        )
        from backend.api.schemas.enrichment import PoseEnrichment

        field = PoseEnrichment.model_fields["keypoints"]
        assert "list" in str(field.annotation), (
            f"PoseEnrichment.keypoints is no longer an untyped list: {field.annotation}"
        )
        assert "name" not in str(field.annotation), (
            "PoseEnrichment.keypoints gained a name in its annotation while the "
            "DB comment still promises a positional triple"
        )
        # (v) The DB column is still an unconstrained JSONB: the reason the
        # comment (s1a) is the only defence.
        from backend.models.enrichment import PoseResult
        from sqlalchemy.dialects.postgresql import JSONB

        col = PoseResult.__table__.columns["keypoints"]
        assert isinstance(col.type, JSONB), (
            f"pose_results.keypoints is no longer raw JSONB: {col.type!r}"
        )
        # CHECK constraints ONLY, and read off each constraint's own sqltext.
        # str(table.constraints) was the first attempt and is unusable: a
        # ForeignKey's repr prints its parent table, so the column list - and
        # the keypoints COMMENT TEXT - leaks into it and the substring probe
        # reports a constraint that does not exist.
        from sqlalchemy.schema import CheckConstraint

        constraints = list(PoseResult.__table__.constraints)
        checks = [c for c in constraints if isinstance(c, CheckConstraint)]
        others = [c for c in constraints if not isinstance(c, CheckConstraint)]
        assert others, (
            "pose_results exposes no non-CHECK constraints; the constraint scan "
            "below would be searching an empty set"
        )
        assert not any("keypoints" in str(c.sqltext) for c in checks), (
            "a CHECK constraint now covers pose_results.keypoints - the "
            "comment-only-shape hazard moved into a constraint; this pin's "
            "premise needs a rewrite"
        )

    def test_s1d_pose_fault_knobs_survive_without_a_pose_operation(self) -> None:
        """TOMBSTONE: THE POSE FAULT LEG IS GONE; THE FAULT GRAMMAR IS NOT.

        This def used to drive ``X-Fake-Fault: schema-invalid`` into the fake
        at ``/enrich-lt/pose-analyze`` and assert the response lost the
        ``keypoints`` root key while still parsing as JSON. The point was that
        the fake could REPRODUCE a schema-invalid 2xx - spec S5's
        unparseable-verdict branch, the branch where the client must trust
        neither the status code nor the parser. The fake's three fault knobs
        (timeout / schema-invalid / 5xx) were built for that ladder, and
        R8 S3 deleted the only op they had been driven against: the knobs
        would have become decoration.

        The knob grammar still has to be proven non-vacuous, so this def
        asserts the retirement (no pose op, no pose route) AND drives the
        identical three faults against a surviving op, ``vlm_assess``, here -
        retargeting, not just recording. Sibling: the ladder's full three-way
        circuit/DEGRADED treatment lives in
        backend/tests/contracts/ai_providers/test_conformance_vlm.py's
        ``TestFakeFaultKnobs``; the byte-identity arm of the doctrine lives
        in test_conformance_geometry.py's G7.
        """
        assert "enrich_lt_pose_analyze" not in OP_IDS, (
            "pose is back in the registry; the ladder below must be re-derived"
        )
        import asyncio

        from backend.ai_contract.fake.app import FAULT_HEADER, PROFILE_HEADER

        app = create_fake_app()
        op = OPERATIONS["vlm_assess"]
        body = {"image_paths": ["a.png"], "prompt": "what is in the frame?"}

        async def _drive(fault: str | None) -> tuple[int, bytes, float]:
            import time

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://fake") as client:
                headers = {PROFILE_HEADER: "security"}
                if fault:
                    headers[FAULT_HEADER] = fault
                start = time.monotonic()
                r = await client.request(op.method, op.path, json=body, headers=headers)
                return r.status_code, r.content, time.monotonic() - start

        ok_code, ok_body, ok_secs = asyncio.run(_drive(None))
        five_code, _, _ = asyncio.run(_drive("5xx"))
        bad_code, bad_body, _ = asyncio.run(_drive("schema-invalid"))
        to_code, _, to_secs = asyncio.run(_drive("timeout:0.05"))
        # Healthy baseline first: without this the three below are vacuous.
        assert ok_code == 200
        ok_json = json.loads(ok_body)
        assert ok_json, "the healthy baseline response has no JSON body"
        assert five_code == 503, f"5xx fault did not become a 503: {five_code}"
        assert bad_code == 200 and bad_body, f"schema-invalid fault misbehaved: {bad_code}"
        parsed = json.loads(bad_body)  # parses as JSON...
        assert any(v is None for v in parsed.values()) or parsed != ok_json, (
            "the schema-invalid body is indistinguishable from the healthy one; "
            "the client's unparseable-verdict branch just went untestable"
        )
        assert to_secs >= 0.05, f"timeout fault did not stall: {to_secs:.3f}s"


# ---------------------------------------------------------------------------
# S2 — the embedding-space tag: written, read, and now the only space there is.
# ---------------------------------------------------------------------------
class TestS2EmbeddingSpaceTag:
    """S2's finding was: the {"vector","model","dimension"} tag is written and
    never read, so a cosine across two embedding spaces "reported plausible
    numbers with zero error raised".

    CLOSED by the re-ID full swap (owner ruling, ledger item 20; F11 "one
    embedding space, model id on every stored vector"). s2a/s2b are the CLOSE
    side and stay as written: they assert the tag HAS production readers and
    that the writer refuses an unnamed producer. s2c tombstones the second
    space, which R8 S3 ruling 5 removed along with CLIP.
    """

    def test_s2a_the_tag_has_readers_and_guards_every_comparison(self) -> None:
        """Post-swap: the corpus scan that once found ZERO readers must find
        the guard's readers - the entity repository's provenance filter (a
        foreign-space row is SKIPPED, never scored) and hybrid storage's
        belt-copy (a PostgreSQL match carries its model_id downstream). Same
        scan recipe as the original, and the same exclusion (test trees are
        not production consumers); the assertion is inverted with the
        contract. A pin here going back to zero readers would mean the belt
        became decorative again.
        """
        readers = []
        for path in _source_corpus("backend", "ai", "scripts"):
            rel = path.relative_to(REPO_ROOT)
            text = path.read_text(encoding="utf-8", errors="replace")
            if rel == Path("backend/models/entity.py"):
                assert "def get_embedding_model(" in text  # the def itself
                continue
            if "get_embedding_model" in text:
                readers.append(str(rel))
        assert set(readers) >= {
            "backend/repositories/entity_repository.py",
            "backend/services/hybrid_entity_storage.py",
        }, f"the belt lost its readers again: {readers}"

        # And the reader is a GUARD, not decoration: the repository refuses a
        # foreign-space row, and a probe that names no space at all.
        from backend.models.entity import Entity
        from backend.repositories.entity_repository import EntityRepository

        def _row(model: str | None) -> Entity:
            e = Entity(entity_type="person", trust_status="unknown")
            e.embedding_vector = {"vector": [0.1] * 4, "model": model, "dimension": 4}
            return e

        keep = EntityRepository._provenance_matches
        assert keep(_row("osnet-ain-x1-0@w@aaaaaaaaaaaa"), "osnet-ain-x1-0@w@aaaaaaaaaaaa")
        assert not keep(_row("clip"), "osnet-ain-x1-0@w@aaaaaaaaaaaa")
        assert not keep(_row("osnet-ain-x1-0@w@aaaaaaaaaaaa"), None)

    def test_s2b_the_writer_refuses_an_unnamed_producer(self) -> None:
        """Pre-swap, set_embedding(..., model="siglip-2") recorded the tag and
        validated NOTHING, and the default was the LITERAL "clip" - so a write
        that never named its producer mislabeled the bytes (provenance
        backwards). Post-swap the producer is REQUIRED: an omitted or
        explicitly-None model refuses loudly, and a named one is stored and
        readable verbatim.
        """
        from backend.models.entity import Entity

        with pytest.raises(ValueError, match="model"):
            Entity(entity_type="person").set_embedding([0.1] * 4)
        with pytest.raises(ValueError, match="model"):
            Entity(entity_type="person").set_embedding([0.1] * 4, model=None)

        ent = Entity(entity_type="person")
        ent.set_embedding([0.1] * 4, model="osnet-ain-x1-0@w@aaaaaaaaaaaa")
        assert ent.embedding_vector["model"] == "osnet-ain-x1-0@w@aaaaaaaaaaaa"
        assert ent.get_embedding_model() == "osnet-ain-x1-0@w@aaaaaaaaaaaa"
        assert ent.embedding_vector["dimension"] == 4
        storage = (REPO_ROOT / "backend/services/hybrid_entity_storage.py").read_text(
            encoding="utf-8"
        )
        assert "entity.get_embedding_vector()" in storage
        assert "get_embedding_model" in storage

    def test_s2c_the_second_embedding_space_is_gone_from_the_surface(self) -> None:
        """TOMBSTONE: THE TWO-SPACE COSINE HAD NO READER; THE SECOND SPACE HAS
        NO PROVIDER.

        s2c drove ``/clip/embed`` (768-dim CLIP space) and
        ``/enrich-lt/person-reid`` (512-dim re-ID space) off ONE fake app and
        asserted both came back unit-norm: two competing dimensionalities,
        cosine-ready, with the s2a tag never consulted. The hazard was the
        silent-success failure mode - a downstream cosine between a CLIP-space
        and an OSNet-space vector "reports plausible numbers with zero error
        raised", because unit norm is indistinguishable across spaces and
        nothing on the wire names one.

        R8 S3 ruling 5 deleted the CLIP provider (a Triton-prune consequence:
        FULL_MODEL_SET keeps yolo26/reid/threat, so clip/clip_text cannot
        boot anywhere), which removes the second space rather than adding a
        discriminator to the first. What remains of the claim is the
        SINGULARITY, and the numeric cluster owns it under its own name -
        ``TestN5MultiSlotTombstone.test_the_second_embedding_slot_is_gone_and_
        the_ratchet_owns_it`` plus ``test_the_surviving_slot_is_the_one_every_
        column_names``. What is pinned HERE, in this file's own words, is the
        provider-side absence the fake could no longer express: there is no
        embedding op to drive except the re-ID one.
        """
        embedding_ops = {
            op_id
            for op_id in OP_IDS
            if "embedding"
            in json.loads((SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8")).get(
                "properties", {}
            )
        }
        assert embedding_ops == {"enrich_lt_person_reid"}, (
            f"a second embedding-producing op is back ({sorted(embedding_ops)}); the "
            "two-space cosine hazard is live again and must be re-driven, not tombstoned"
        )
        assert "clip_embed" not in OP_IDS and "clip_similarity" not in OP_IDS
        for dead in ("clip", "clip_text"):
            with pytest.raises(ModuleNotFoundError):
                import_module(f"ai.gateway.adapters.{dead}")
        assert not (REPO_ROOT / "ai/clip").exists(), "ai/clip came back on disk"
        # NON-VACUITY: the surviving space is real and driven, so the
        # singleton set above is a comparison against a live provider and not
        # against an empty registry.
        sibling = SIBLING_MODULES["numeric"].read_text(encoding="utf-8")
        assert "class TestN5MultiSlotTombstone" in sibling, (
            "the numeric cluster no longer owns the multi-slot tombstone this "
            "record cites - re-home the claim before trusting the absence"
        )


# ---------------------------------------------------------------------------
# S3 — prompt strings are passed through verbatim: the provider never
#      interprets them (plan 965-967).
# ---------------------------------------------------------------------------
class TestS3FlorenceControlTokenPrompts:
    """S3's finding was that Florence-2 control tokens ("<CAPTION>",
    "<OD>", ...) are literal wire content: the client sends the token string,
    the adapter hands the SAME bytes to Triton, and nothing between the two
    rejects a provider that answers a control token by echoing it back.

    Florence is retired whole (ruling 1), so the token half of the property
    has no subject. The MECHANISM the token made visible - prompt text is
    passthrough, never validated or templated - is alive on the llama.cpp
    lane, which is what s3a retargets onto. The fake half is a property of
    the fake and is retargeted too.
    """

    def test_s3a_prompt_text_is_passthrough_on_the_surviving_completion_lane(
        self,
    ) -> None:
        """RETARGETED, and stronger than the leg it replaces: both ends of the
        passthrough, plus the schema arm that makes "no validation" a fact
        rather than a reading.

        The retired leg read ``"prompt": prompt,`` out of FlorenceClient and
        the ``Field(default="<CAPTION>")`` out of the Florence adapter. The
        surviving spelling is the llama.cpp completion lane: a shipped caller
        builds a payload whose prompt key is a bare variable, the registry's
        request schema declares ``prompt`` as a plain ``string`` with no
        ``pattern``/``enum``/``format``, and the adapter-side model is the
        same passthrough. A schema that constrained the prompt would be the
        end of the hazard; a schema that does not is the hazard, so the
        absence is the assertion.

        The control-token spellings themselves (``prompt.strip("<>").split
        (">")[0]`` and the ``Field(default="<CAPTION>")`` default) are
        asserted ABSENT below, in the same def - a re-home that reintroduced
        a token parser would land next to a pin that notices.
        """
        # (1) The shipped caller's payload assembles prompt verbatim. The
        # corpus is scoped: a whole-tree AST sweep is a WP1.3 breach.
        hits: list[str] = []
        for path in _source_corpus("backend/services", "backend/api"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if '"prompt": prompt' in text or '"prompt": prompt_text' in text:
                hits.append(str(path.relative_to(REPO_ROOT)))
        assert hits, (
            "no shipped caller passes a prompt through to /completion any more - "
            "the passthrough property has moved, re-home this pin"
        )
        # (2) The contract does not constrain it.
        schema = json.loads((SCHEMA_DIR / "llm_completion.request.json").read_text("utf-8"))
        prompt_prop = schema["properties"]["prompt"]
        assert prompt_prop["type"] == "string", prompt_prop
        for discriminator in ("pattern", "enum", "format", "minLength"):
            assert discriminator not in prompt_prop, (
                f"llm_completion.request.json now constrains prompt with {discriminator}; "
                "the provider-side string is no longer blind, so S3's property "
                "changed shape and must be re-derived, not left asserting this"
            )
        # (3) The dead control-token interpretations stay dead. Prose names
        # them; this reads LIVE source text for them.
        for module in sorted(GATEWAY_MODULES):
            src = import_module(module).__file__
            assert src is not None
            adapter_text = Path(src).read_text(encoding="utf-8")
            assert 'default="<CAPTION>"' not in adapter_text
            assert 'split(">")' not in adapter_text
        assert not (REPO_ROOT / "backend/services/florence_client.py").exists()
        assert not (REPO_ROOT / "ai/gateway/adapters/florence.py").exists()
        with pytest.raises(ModuleNotFoundError):
            import_module("ai.gateway.adapters.florence")
        for florence_op in (
            "florence_extract",
            "florence_detect",
            "florence_ocr",
            "florence_batch_extract",
        ):
            assert florence_op not in OP_IDS, f"{florence_op} came back"

    async def test_s3b_the_gateway_no_longer_hosts_a_prompt_echoing_route(
        self, gateway_client: AsyncClient
    ) -> None:
        """TOMBSTONE + RETARGET: the Florence echo leg is gone; the surviving
        prompt route is served by a DIFFERENT provider, and the pair of facts
        is the honest record.

        This def used to POST ``/florence/extract`` with ``prompt:
        "<CAPTION>"``, with a mock "VLM" that echoed the token back as the
        caption, and assert the adapter returned ``prompt_used == "<CAPTION>"``
        and the echoed caption verbatim. That was the hazard made executable:
        a consumer asking a question got the question back, and NOTHING
        between the adapter and the response model noticed, because the
        adapter's own contract is "pass the prompt to Triton, return whatever
        comes back". CHARACTERIZATION, not endorsement.

        R8 S3 ruling 1 deleted the adapter, the client, the serving dir and
        the Triton model dir. The surviving prompt-bearing route is
        ``/completion`` - and it is NOT on the gateway: the registry's
        gateway column is False for both LLM ops, and the mounted app answers
        404. Pinning that here keeps the record executable: the shape that
        used to echo is no longer reachable through the app this suite builds.
        """
        r = await gateway_client.post("/florence/extract", json={"image": _png_b64()})
        assert r.status_code == 404, f"/florence/extract served again: {r.status_code}"
        r = await gateway_client.post("/completion", json={"prompt": "<CAPTION>"})
        assert r.status_code == 404, f"/completion mounted on the gateway again: {r.status_code}"
        assert OPERATIONS["llm_completion"].availability["gateway"] is False, (
            "the registry claims the completion lane for the gateway while the "
            "mounted app says 404 - one of the two is lying"
        )
        # NON-VACUITY: the app is live and its REAL routes answer.
        healthy = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        assert healthy.status_code == 200, healthy.text
        assert isinstance(json.loads(healthy.content)["detections"], list), (
            "the mounted app's real route stopped emitting a detection list - the "
            "two 404s above would be asserting against a dead app"
        )

    def test_s3c_the_fake_is_prompt_blind_by_construction(self) -> None:
        """RETARGETED (was: the Florence fake contrast): the fake's
        payload-blindness is a property of the fake, not of Florence, and it
        survives op retirement with the fake intact.

        The doctrine (fake/app.py: the body is parsed ONLY for echo fields)
        means fake-side conformance can NEVER observe a prompt-semantics
        failure: two requests that differ in prompt text get byte-identical
        responses, because the generator is seeded by
        ``sha256(op_id | path | profile)`` and not by the body. The retired
        leg proved that with ``prompt_used != "<CAPTION>"`` on
        ``/florence/extract``. Both LLM ops are still fake-served, so the
        identical claim is driven against ``/completion`` and
        ``/v1/chat/completions`` here - and asserted as the LIMIT it is: a
        green fake row on these ops certifies envelope and shape, never
        prompt handling, which is why s3a is mandatory for the bullet.

        ``vlm_assess`` is the CONTRAST arm and the non-vacuity: it is a fake
        op whose body IS read (the generator keys its verdict on
        ``image_paths``), so the byte-identity asserted below cannot be a
        generator artifact that makes every response a constant.
        """
        import asyncio

        async def _drive() -> tuple[bytes, bytes, bytes, bytes, bytes, bytes]:
            app = create_fake_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fake"
            ) as client:
                c1 = await client.post("/completion", json={"prompt": "<CAPTION>", "n_predict": 1})
                c2 = await client.post(
                    "/completion",
                    json={"prompt": "what is in the frame? count the people", "n_predict": 32},
                )
                h1 = await client.post(
                    "/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "<CAPTION>"}]},
                )
                h2 = await client.post(
                    "/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "totally different ask"}]},
                )
                v1 = await client.post("/vlm/chat/completions", json={"image_paths": ["a.png"]})
                v2 = await client.post(
                    "/vlm/chat/completions", json={"image_paths": ["a.png", "b.png"]}
                )
            return c1.content, c2.content, h1.content, h2.content, v1.content, v2.content

        c1, c2, h1, h2, v1, v2 = asyncio.run(_drive())
        assert c1 == c2, (
            "the fake started keying /completion on the prompt body; the "
            "payload-blindness claim below is no longer true of the shipped fake"
        )
        assert h1 == h2, "the fake started keying /v1/chat/completions on the messages body"
        assert json.loads(c1), "the blind responses are not even valid JSON"
        assert v1 != v2, (
            "the fake went CONSTANT on every body: the equality above is now "
            "vacuous and the generator's payload-blindness broke"
        )
        # And the blind lane never produced a control token: what the retired
        # leg asserted, expressed on the surviving ops.
        assert "<" not in json.loads(c1)["content"]
        assert "<" not in json.loads(h1)["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# S4 — caption language is an unwritten contract: the frontend classifies
#      summaries by ENGLISH keyword matching (plan 969-970).
# ---------------------------------------------------------------------------
class TestS4CaptionLanguageKeywordContract:
    def test_s4a_the_english_keyword_tables_are_the_real_list(self) -> None:
        """PLAN CITE CORRECTION (2026-09-19): the plan cites
        severityCalculator.ts:56 ("the keyword list"); the list is THREE
        tables - CRITICAL_KEYWORDS, HIGH_KEYWORDS, LOW_KEYWORDS - and the
        plan's seven quoted terms are a cross-level sample of them. Matching
        is case-insensitive SUBSTRING: a NON-ENGLISH caption matches NOTHING
        and falls through silently, so a caption-language change on the
        surviving completion lane (a multilingual VLM) hits none of these
        tables while the UI defaults downward with no error raised.

        The fake cannot be pinned on this: its captions are generated strings
        ("caption_NNN") that already violate the contract today, so a fake-
        side assertion would be a permanent red against shipped behavior. The
        tables are what is pinned; the fake-caption violation is recorded in
        the ledger. TS read as TEXT, never imported.
        """
        ts = SEVERITY_TS_SRC.read_text(encoding="utf-8")

        def _kw_list(name: str) -> list[str]:
            m = re.search(rf"const {name} = \[([^\]]*)\]", ts, re.DOTALL)
            assert m, name
            return re.findall(r"'([^']+)'", m.group(1))

        crit = _kw_list("CRITICAL_KEYWORDS")
        high = _kw_list("HIGH_KEYWORDS")
        low = _kw_list("LOW_KEYWORDS")
        assert {"intruder", "breach", "weapon"} <= set(crit)
        assert {"loitering", "trespassing"} <= set(high)
        assert {"routine", "delivery"} <= set(low)
        assert crit == ["critical", "emergency", "intruder", "breach", "weapon", "threat"]
        assert high == [
            "high-risk",
            "suspicious",
            "masked",
            "obscured face",
            "loitering",
            "trespassing",
        ]
        assert low == ["routine", "normal", "expected", "delivery"]
        assert (
            re.search(
                r"const MEDIUM_KEYWORDS = \['unusual', 'unexpected', "
                r"'unfamiliar', 'monitoring'\]",
                ts,
            )
            is not None
        )
        # substring (not word-boundary) matching is part of the contract:
        assert re.search(r"lowerContent\.includes\(keyword\.toLowerCase\(\)\)", ts) is not None
        # NON-VACUITY: the three tables parsed to non-empty, mutually
        # disjoint sets (a failed regex would have raised above, but an empty
        # table would not have).
        assert crit and high and low
        assert not (set(crit) & set(high)) and not (set(high) & set(low))


# ---------------------------------------------------------------------------
# S5 — think-tag stripping by regex; unclosed tag = "no reasoning" and the
#      RAW text passes through as the JSON payload (plan 972-974).
# ---------------------------------------------------------------------------
class TestS5ThinkTagStripping:
    """The strip site is the frozen verbatim copy of the deleted analyzer
    (backend/tests/contracts/ai_providers/retired_providers.py): R8 S2 deleted
    nemotron_analyzer.py with the legacy tier, and the copy's header records
    both historical cite sets. The behavior claim is pinned against the same
    code that made it true, and the surviving consumer is the VLM/risk lane,
    which still receives raw completion text (s3a's lane)."""

    def test_s5a_the_strip_regex_is_dotted_dotall_think_only(self) -> None:
        src = RETIRED_ANALYZER_SRC.read_text(encoding="utf-8")
        assert 're.compile(r"<think>.*?</think>", re.DOTALL)' in src
        assert 're.compile(r"<think>(.*?)</think>", re.DOTALL)' in src
        assert "reasoning_content" not in src  # no OpenAI reasoning channel
        assert "<reasoning>" not in src  # no generic reasoning tag handling

    def test_s5b_unclosed_think_passes_raw_text_as_the_payload(self) -> None:
        """Closed think -> (reasoning, clean JSON); an UNCLOSED think yields
        the "no reasoning" verdict and the RAW text as the payload - the
        plan's claim verbatim; a foreign CoT channel is INVISIBLE to the
        regex and also passes through unchanged. The downstream brace-scan
        then treats the first brace inside leaked CoT as the payload boundary.
        """
        from backend.tests.contracts.ai_providers.retired_providers import (
            extract_reasoning_and_response,
        )

        closed = '<think>Analyzing the scene...</think>{"risk_score": 25}'
        reasoning, response = extract_reasoning_and_response(closed)
        assert reasoning == "Analyzing the scene..."
        assert response == '{"risk_score": 25}'
        unclosed = '<think>unclosed reasoning {"risk": 1}'
        reasoning2, response2 = extract_reasoning_and_response(unclosed)
        assert reasoning2 == ""  # the "no reasoning" verdict
        assert response2 == unclosed  # raw text passed through AS the payload
        other = '<reasoning>CoT here</reasoning>{"risk": 1}'
        reasoning3, response3 = extract_reasoning_and_response(other)
        assert reasoning3 == ""
        assert response3 == other  # foreign CoT channel invisible to the regex

    def test_s5c_second_consumer_repeats_the_same_regex(self) -> None:
        """Two strip sites, one regex object - pin so a partial fix (one site
        patched for a new tag) cannot pass unnoticed."""
        src = RETIRED_ANALYZER_SRC.read_text(encoding="utf-8")
        hits = [m.start() for m in re.finditer(r"_THINK_PATTERN\.sub\(", src)]
        assert len(hits) == 2, hits


# ---------------------------------------------------------------------------
# S6 — frontend/src/utils/confidence.ts THROWS outside [0,1]: a percentage
#      provider crashes the detection UI instead of degrading (plan 976-977).
# ---------------------------------------------------------------------------
class TestS6ConfidenceRangeThrow:
    """s6a is the throw itself, unchanged. s6b is RETARGETED and stronger: the
    op set it sweeps is derived from the artifacts (schema text + the bare-dict
    ``x-deployed-keys`` marker), not from a probe-enumerated list of five
    enrichment ops that no longer exist. s6c is RETARGETED onto every mounted
    route rather than one, so both clamp regimes are driven."""

    def test_s6a_the_throw_is_pinned_in_the_ts_text(self) -> None:
        """The guard condition and the two in-range category cuts. The throw
        is the whole property: a provider that emitted 92.5 for "92.5%" would
        not render a wrong number, it would RAISE inside the component.
        """
        ts = CONFIDENCE_TS_SRC.read_text(encoding="utf-8")
        assert "if (confidence < 0 || confidence > 1) {" in ts
        assert "throw new Error('Confidence score must be between 0.0 and 1.0');" in ts
        assert "if (confidence < 0.7) return 'low';" in ts
        assert "if (confidence < 0.85) return 'medium';" in ts

    def test_s6b_every_provider_emittable_confidence_lives_in_the_unit_interval(
        self,
    ) -> None:
        """RETARGETED + strengthened. The UI throw survives only if every
        provider keeps confidence in [0,1], so the sweep must cover EVERY op
        that can emit one and MISS NONE - which is why the set is derived from
        two artifact sources instead of a hand list:

          (a) ops whose RESPONSE SCHEMA names a confidence field (measured:
              enrich_lt_threat_detect - the lane that carries
              threats_detected[].confidence AND max_confidence);
          (b) ops whose response schema is the BARE-DICT marker with
              ``x-deployed-keys`` (measured: the whole yolo26 family - their
              detections[].confidence is invisible to a schema walk because no
              pydantic response model exists, which is exactly how the old
              probe-enumerated list came to omit them).

        The retired five (pet/vehicle/action/clothing/demographics classify)
        are gone with their ops; a new op that emits confidence in either
        spelling joins this sweep automatically, and an op that drops its
        confidence field leaves it - so the census assertion below is the
        non-vacuity, and the drive is real HTTP against the fake.
        """
        import asyncio

        schema_named = {
            op_id
            for op_id in OP_IDS
            if re.search(
                r'"(max_)?confidence"\s*:',
                (SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8"),
            )
        }
        bare_dict = {
            op_id
            for op_id in OP_IDS
            if "x-deployed-keys"
            in (SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8")
        }
        conf_ops = schema_named | bare_dict
        assert conf_ops == {
            "enrich_lt_threat_detect",
            "yolo26_detect",
            "yolo26_detect_batch",
            "yolo26_segment",
        }, f"the confidence-emitting census changed shape: {sorted(conf_ops)}"
        assert schema_named and bare_dict, (
            "one of the two spellings vanished; the derivation is now a single "
            "source and can no longer catch a confidence field moving between them"
        )

        def _fake_kwargs(op_id: str) -> dict[str, Any]:
            """The drive body the fake accepts: multipart for an upload route,
            the committed example where one exists, otherwise a neutral image
            body - the enrich-lt pair has NO request golden, by design of the
            generator, and the fake ignores bodies except for echo fields.
            """
            op = OPERATIONS[op_id]
            if op_id in MULTI_IMAGE_OPS:
                return {"files": [("file", ("frame.png", _png_bytes(), "image/png"))]}
            example = GOLDEN_DIR / f"{op_id}.request.example.json"
            if example.exists():
                return {"json": json.loads(example.read_text(encoding="utf-8"))}
            return {"json": {"image": _png_b64()}}

        def _walk(node: Any, key: str = "") -> list[float]:
            found: list[float] = []
            if isinstance(node, dict):
                for k, v in node.items():
                    found += _walk(v, k)
            elif isinstance(node, list):
                for item in node:
                    found += _walk(item, key)
            elif isinstance(node, int | float) and key in ("confidence", "max_confidence"):
                found.append(float(node))
            return found

        async def _sweep() -> tuple[list[str], int]:
            app = create_fake_app()
            offenders: list[str] = []
            seen = 0
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fake"
            ) as client:
                for op_id in sorted(conf_ops):
                    op = OPERATIONS[op_id]
                    kwargs = _fake_kwargs(op_id)
                    r = await client.request(op.method, op.path, **kwargs)
                    assert r.status_code == 200, (op_id, r.status_code, r.text)
                    values = _walk(r.json())
                    seen += len(values)
                    offenders += [f"{op_id}: {v}" for v in values if not 0.0 <= v <= 1.0]
            return offenders, seen

        offenders, seen = asyncio.run(_sweep())
        assert seen >= 6, (
            f"the sweep only found {seen} confidence values across {len(conf_ops)} ops - "
            "the fake stopped emitting what the schemas promise, so a clean sweep "
            "below would be vacuous"
        )
        assert offenders == [], f"percent-leak would CRASH confidence.ts: {offenders}"

    async def test_s6c_both_clamp_regimes_are_driven_and_both_stay_in_range(
        self, gateway_client: AsyncClient
    ) -> None:
        """RETARGETED (was: one yolo route), and it now states the asymmetry
        the shipped code actually has instead of assuming one policy:

          * yolo26 CLAMPS: ``score = max(0.0, min(1.0, score))`` in the post-NMS
            reader and the same idiom in the pre-NMS reader - two clamp sites.
          * the enrich-lt lane does NOT clamp. ``_postprocess_threat`` filters
            on the threshold and rounds, and ``max_confidence`` is a plain
            ``max(...)`` over those rounded values. An out-of-band tensor score
            (a raw logit of 1.7, say) would therefore reach the wire on the
            light lane and be clamped on the yolo lane. Geometry's G7 drives
            exactly that out-of-band value against the real socket; what is
            pinned HERE is the asymmetry as shipped TEXT plus the in-range
            result of driving every mounted route with an in-band tensor.

        Driving every mounted route (not one) is also what exercises this
        cluster's derived mount table end to end.
        """
        yolo_src = (ADAPTER_DIR / "yolo26.py").read_text(encoding="utf-8")
        light_src = (ADAPTER_DIR / "enrichment_light.py").read_text(encoding="utf-8")
        assert yolo_src.count("max(0.0, min(1.0") == 2, (
            "the yolo lane's clamp count changed; the asymmetry below is no longer "
            "the two-reader shape this pin describes"
        )
        assert "max(0.0, min(1.0" not in light_src, (
            "the enrich-lt lane gained a clamp: the G7 out-of-band divergence is "
            "closed and both this pin and geometry's G7 need rewriting together"
        )

        emitted = 0
        for op_id in sorted(MULTI_IMAGE_OPS):
            r = await gateway_client.post(OPERATIONS[op_id].path, **_gateway_kwargs(op_id))
            assert r.status_code == 200, (op_id, r.text)
            body = r.json()
            # The batch route nests one result per upload; the other two are
            # flat. Both spellings come from x-deployed-keys, read below.
            deployed = json.loads(
                (SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8")
            )["x-deployed-keys"]
            assert set(body) == set(deployed), (op_id, sorted(body), sorted(deployed))
            rows = (
                [item for res in body["results"] for item in res["detections"]]
                if "results" in body
                else body["detections"]
            )
            values = [float(d["confidence"]) for d in rows]
            emitted += len(values)
            assert all(0.0 <= v <= 1.0 for v in values), (op_id, values)
        assert emitted >= 3, f"the yolo drives emitted {emitted} confidences; vacuous"

        r = await gateway_client.post(
            OPERATIONS["enrich_lt_threat_detect"].path,
            **_gateway_kwargs("enrich_lt_threat_detect"),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) == {"threats_detected", "is_threat", "max_confidence", "inference_time_ms"}
        assert body["threats_detected"], (
            "the threat drive emitted no rows; the check below is vacuous"
        )
        row_values = [float(d["confidence"]) for d in body["threats_detected"]]
        assert all(0.0 <= v <= 1.0 for v in row_values), row_values
        assert 0.0 <= float(body["max_confidence"]) <= 1.0, body["max_confidence"]


# ---------------------------------------------------------------------------
# S7 — FOUR divergent risk-band tables for one 0-100 score (plan 979-982).
#      Untouched by R8 S3: the divergence was never a provider property, it is
#      four tables in three languages that no retirement can reach.
# ---------------------------------------------------------------------------
class TestS7RiskBandTablesDiverge:
    def test_s7a_backend_three_tables_agree_at_29_59_84(self) -> None:
        """Backend trio, runtime-VERIFIED: llm_response.py 29/59/84
        (infer_risk_level_from_score), severity.py risk_score_to_severity and
        event.py Event.computed_risk_level all read the settings defaults
        29/59/84. THREE code tables, TWO numbers - the FOUR-way divergence
        completes only at s7b. Needs ENVIRONMENT != production."""
        from backend.api.schemas.llm_response import (
            DEFAULT_HIGH_MAX,
            DEFAULT_LOW_MAX,
            DEFAULT_MEDIUM_MAX,
            infer_risk_level_from_score,
        )
        from backend.models.event import Event
        from backend.services.severity import Severity, SeverityService

        assert (DEFAULT_LOW_MAX, DEFAULT_MEDIUM_MAX, DEFAULT_HIGH_MAX) == (29, 59, 84)
        assert infer_risk_level_from_score(29).value == "low"
        assert infer_risk_level_from_score(30).value == "medium"
        assert infer_risk_level_from_score(84).value == "high"
        assert infer_risk_level_from_score(85).value == "critical"

        svc = SeverityService()
        assert svc.get_thresholds() == {"low_max": 29, "medium_max": 59, "high_max": 84}
        assert svc.risk_score_to_severity(82) is Severity.HIGH
        assert svc.risk_score_to_severity(30) is Severity.MEDIUM
        assert svc.risk_score_to_severity(29) is Severity.LOW

        event = Event()
        event.risk_score = 82
        assert event.computed_risk_level == "high"
        event.risk_score = 29
        assert event.computed_risk_level == "low"

    def test_s7b_the_frontend_table_is_a_different_partition(self) -> None:
        """Fourth table (frontend): SEVERITY_THRESHOLDS {CRITICAL: 80, HIGH: 60,
        MEDIUM: 40, LOW: 20}. Backend 82=high (s7a, runtime), frontend
        82=critical - the plan's exact split. PARKED RULING: unifying the
        tables (serve thresholds from the API, or re-tune the TS) rewrites this
        characterization, it does not delete it. The frontend side is COMPUTED
        FROM THE PARSED TABLE, never hardcoded twice.
        """
        ts = SEVERITY_TS_SRC.read_text(encoding="utf-8")
        m = re.search(r"const SEVERITY_THRESHOLDS = \{(.*?)\} as const;", ts, re.DOTALL)
        assert m, "SEVERITY_THRESHOLDS is no longer the literal this pin reads"
        thresholds = {k: int(v) for k, v in re.findall(r"(\w+):\s*(\d+)", m.group(1))}
        assert thresholds == {"CRITICAL": 80, "HIGH": 60, "MEDIUM": 40, "LOW": 20}, thresholds
        assert "if (score >= SEVERITY_THRESHOLDS.CRITICAL) return 'critical';" in ts

        from backend.api.schemas.llm_response import infer_risk_level_from_score

        backend_82 = infer_risk_level_from_score(82).value  # 'high'
        frontend_82 = next(
            (
                level.lower()
                for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
                if thresholds[level] <= 82
            ),
            "clear",
        )
        # THE divergence, as an assertion (both sides shipped-correct; the
        # split is the finding): an 82 score is high in the DB and critical in
        # the UI at the same instant.
        assert backend_82 == "high"
        assert frontend_82 == "critical"
        assert backend_82 != frontend_82, (
            "the tables converged: this characterization is stale, update it "
            "(and the parked ruling) rather than deleting the pin"
        )

    def test_s7c_risk_score_int_strictness_layers_are_out_of_scope_here(self) -> None:
        """Cross-reference guard for the adjacent numeric-cluster bullet: the
        band tables classify a float happily (their guards are comparisons)
        while the DB bounds the domain with a CHECK. Pinning that the band
        tables are NOT int-domain tests, so a numeric-side change cannot be
        mistaken for a band-table change.
        """
        from backend.api.schemas.llm_response import infer_risk_level_from_score

        assert infer_risk_level_from_score(82.5).value == "high"  # no int guard


# ---------------------------------------------------------------------------
# S8 — the only MULTI-FRAME operation (plan 984-985). R8 S3 retired the op;
#      the surviving multi-IMAGE set is a different kind, and the difference
#      is the record.
# ---------------------------------------------------------------------------
class TestS8ActionClassifyMultiFrame:
    """Bullet S8 was ``enrichment_action_classify``: the one op whose list
    field was a TEMPORAL frame SEQUENCE, driven through a two-stage Triton
    pipeline (pose per frame, then one action call over the resampled
    skeleton). s8a/s8b below carry that hazard in full; s8c retargets the
    half that survived the op - payload-blindness is a property of the fake,
    and it now has a surviving multi-image op to be blind to.
    """

    def test_s8a_frame_sequence_is_gone_and_multi_image_is_not_a_substitute(self) -> None:
        """TOMBSTONE: THE ONLY TEMPORAL-SEQUENCE OP AND ITS PROVIDER ARE GONE,
        AND THE SURVIVING MULTI-IMAGE OPS ARE NOT A DROP-IN REPLACEMENT.

        What the retired legs established, kept because the hazards are
        general:

          * THE STATUS-CODE PAIR, corrected against live code: an EMPTY frames
            list was a handler-level **400** ("Frames list cannot be empty"),
            while a MISSING or wrongly-typed frames field was a pydantic
            **422**. The two cases read the same in a workflow prompt and are
            different defects - a client that retries on 422 and a client that
            retries on 400 are not the same client.
          * FAN-OUT COUNT: N frames meant N pose calls in REQUEST ORDER and
            then exactly ONE action call. A driver that mocked one flat Triton
            output could never see a collapsed loop or a reordered batch, and
            the adapter's own skeleton assembly is order-sensitive, so a
            frame-sequence op whose consumer assumes list order is a
            silent-corruption hazard.
          * MULTI-IMAGE != MULTI-FRAME: an op that carries several images in
            one request is not an op that carries one temporal sequence, and
            the difference is a wire-shape fact (a repeated upload part vs a
            list field), not a naming preference.

        The provider module that held the frames model, the 400/422 pair and
        the two-stage pipeline was swept by ruling 4, so there is no text left
        to retarget the first two halves onto - the precedent is the S2b
        V3 tombstone, not a skip. The third half is retargeted in s8c: the
        derived multi-image set below IS driven, and it is driven as an
        unordered SET. The multi-image class itself is owned, with a name, by
        this suite's ops module - ``TestMultiImageOps`` derives membership,
        pins the multipart 422, the per-file fan-out count and per-item error
        isolation - and the op-id absence is ratcheted by
        ``TestO1ActionClassifyTombstone``.
        """
        assert "enrichment_action_classify" not in OP_IDS
        assert not (REPO_ROOT / "ai/gateway/adapters/enrichment.py").exists()
        assert {"yolo26_detect", "yolo26_detect_batch", "yolo26_segment"} == MULTI_IMAGE_OPS, (
            f"the multi-image class changed: {sorted(MULTI_IMAGE_OPS)}"
        )
        # No surviving op takes a list field that could BE a frame sequence:
        # the yolo family is multipart (repeated parts, no JSON body) and
        # vlm_assess's image_paths is an unordered path list with maxItems 4.
        list_ops: set[str] = set()
        for op_id in OP_IDS:
            req = SCHEMA_DIR / f"{op_id}.request.json"
            if not req.exists():
                continue
            props = json.loads(req.read_text(encoding="utf-8")).get("properties", {}) or {}
            list_ops |= {
                op_id
                for name, prop in props.items()
                if prop.get("type") == "array" and "image" in name.lower()
            }
        assert list_ops == {"vlm_assess"}, (
            f"a second list-of-images request field appeared: {sorted(list_ops)}; the "
            "sequence-vs-set distinction above needs a new subject"
        )
        vlm_paths = json.loads((SCHEMA_DIR / "vlm_assess.request.json").read_text(encoding="utf-8"))
        assert vlm_paths["properties"]["image_paths"]["maxItems"] == 4, (
            "vlm_assess.image_paths lost its maxItems bound; it can no longer be "
            "distinguished from an unbounded sequence"
        )
        # NON-VACUITY: the class the tombstone hands off is alive and driven.
        sibling = SIBLING_MODULES["ops"].read_text(encoding="utf-8")
        assert "class TestMultiImageOps" in sibling and "class TestO1ActionClassifyTombstone" in (
            sibling
        ), "the ops module no longer owns the multi-image class or the op-id ratchet"

    async def test_s8b_the_frame_count_contract_has_no_surviving_route(
        self, gateway_client: AsyncClient
    ) -> None:
        """TOMBSTONE + RETARGET onto the closest surviving shape.

        This def drove FOUR frames through ``/enrichment/action-classify`` and
        asserted the Triton call log was exactly ``[pose, pose, pose, pose,
        stgcn_action]``: the temporal sequence arrived whole, in request
        order, and collapsed into one downstream call. A loop that ran once
        per REQUEST instead of once per frame, or a reorder, was visible in
        that log and invisible in the response body.

        The route is gone (ruling 4). What survives is a per-file fan-out on a
        DIFFERENT axis: ``/yolo26/detect/batch`` takes N uploads and runs ONE
        Triton infer per upload, then returns a per-item list. So the
        "the count arrives whole" property is re-driven here as an IMAGE
        COUNT, against the mounted app with the Triton seam recorded by model
        name - and the record asserts the fan-out is per FILE, which is the
        same class of claim (a batch route that silently serves only the
        first member is the defect this leg existed for). What cannot be
        re-driven is the ORDER-SENSITIVITY of a temporal sequence, because no
        surviving route has a sequence; that half stays a hazard in this
        docstring, and ``TestMultiImageOps`` in the ops module is its named
        successor for shape and error isolation.
        """
        seen: list[str] = []

        async def _record(**kw: Any) -> dict[str, Any]:
            seen.append(str(kw.get("model_name")))
            return _canned_for(kw.get("model_name"), kw.get("outputs"))

        triton = _fake_triton()
        triton.infer = AsyncMock(side_effect=_record)
        with patch("ai.gateway.adapters.yolo26.get_triton_client", return_value=triton):
            r = await gateway_client.post(
                "/yolo26/detect/batch", files=_gateway_kwargs("yolo26_detect_batch")["files"]
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(_gateway_kwargs("yolo26_detect_batch")["files"]) == 2, (
            "the batch drive stopped sending two files; the fan-out count below is vacuous"
        )
        assert body["batch_size"] == 2, body
        assert len(body["results"]) == 2, body
        assert seen == ["yolo26", "yolo26"], (
            f"the batch route's Triton fan-out is no longer one call per file: {seen}"
        )
        # The retired sequence route stays gone, on the same app:
        r = await gateway_client.post("/enrichment/action-classify", json={"frames": []})
        assert r.status_code == 404, f"/enrichment/action-classify served again: {r.status_code}"

    def test_s8c_a_payload_blind_fake_cannot_certify_a_sequence_provider(self) -> None:
        """RETARGETED (was: the action-classify frame-count invariance).

        The fake parses request bodies ONLY for echo fields, so NOTHING about
        a request's list ever reaches the response as an echo - the retired op
        got no list back at all, so a frame-count regression was invisible
        there by construction and the gateway leg was mandatory for the bullet.
        ``vlm_assess`` is the surviving op with a list field, and the measured
        shape of its payload-friendliness (2026-09-30) is NOT the retired op's
        shape. It has three parts, and this def drives all three against the
        fake because stating the claim exactly is what keeps it honest:

          (1) NO ECHO AT ALL. ``image_paths`` is not in the response schema's
              property set, so the list never comes back - the retired op's
              condition survives verbatim.
          (2) SEED-BY-IDENTITY, NOT BY SHAPE. ``vlm_assess`` alone re-draws its
              verdict from ``"|".join(image_paths)``; growing the list from one
              path to four MOVES the seed, so the bodies are not byte-identical
              the way they were on the retired op. But the seed is a join over
              the strings: a list is reduced to one flat token sequence, which
              means structure is lost - measured here, not asserted softly: one
              path containing the separator joins to the same seed as two paths
              split at it.
          (3) THE ENVELOPE IS STILL FIXED. Root keys and the ``criteria``
              length are a function of the schema walk only, so no request can
              change the shape the client parses.

        So: byte-deterministic and replay-stable, but blind to LIST STRUCTURE
        rather than to the payload as a whole. That is weaker than the retired
        op's blindness, and it is why the gateway leg (s8b, which counts Triton
        calls per file) stays mandatory rather than decorative: only the call
        log can see a fan-out that ran once per REQUEST.
        """
        import asyncio

        schema_keys = set(
            json.loads((SCHEMA_DIR / "vlm_assess.response.json").read_text(encoding="utf-8"))[
                "properties"
            ]
        )
        # (1) No echo: the request's list field is not a response field.
        assert "image_paths" not in schema_keys, (
            "vlm_assess's response grew an image_paths echo; the retired op's "
            "no-echo condition no longer holds and the derivation below changes"
        )

        async def _drive() -> dict[str, bytes]:
            app = create_fake_app()
            bodies = {
                "one_a": {"image_paths": ["a.png"]},
                "one_a_replay": {"image_paths": ["a.png"]},
                "four_abcd": {"image_paths": ["a.png", "b.png", "c.png", "d.png"]},
                "absent": {"prompt": "what is in the frame?"},
                "empty": {"image_paths": []},
                "join_a_b": {"image_paths": ["a|b"]},
                "split_ab": {"image_paths": ["a", "b"]},
                "one_a_extras": {"image_paths": ["a.png"], "junk": [1, 2, 3]},
            }
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fake"
            ) as client:
                out: dict[str, bytes] = {}
                for label, body in bodies.items():
                    r = await client.post(OPERATIONS["vlm_assess"].path, json=body)
                    assert r.status_code == 200, (label, r.status_code, r.text)
                    out[label] = r.content
            return out

        got = asyncio.run(_drive())
        # (2a) Replay stability: the determinism the fake exists for.
        assert got["one_a"] == got["one_a_replay"], "the fake lost replay byte-identity"
        # (2b) NOT arity-blind, and the docstring says so plainly: four paths
        # and one path differ. The retired op's byte-identity is gone.
        assert got["one_a"] != got["four_abcd"], (
            "vlm_assess's verdict stopped keying on the joined paths: the "
            "image-hash seed in fake/generators.py moved and this record is stale"
        )
        # (2c) Structure-blind, which is the claim that survives: the join is a
        # lossy reduction, so one path carrying the separator is indistinguishable
        # from two paths split at it. A real sequence provider would not be.
        assert got["join_a_b"] == got["split_ab"], (
            "the fake's seed stopped being a flat join of the path strings: a "
            "sequence STRUCTURE is visible in the fake's output now, which is the "
            "property this pin exists to prove absent - re-derive the record"
        )
        # (2d) An empty list and an absent field collapse to the same seed, so
        # "no frames" is indistinguishable from "field omitted".
        assert got["absent"] == got["empty"], (
            "the fake distinguishes an empty list from an absent field; the "
            "payload-blindness record needs this arm re-stated"
        )
        # (2e) Unrecognized request fields cannot reach the wire either.
        assert got["one_a"] == got["one_a_extras"], (
            "the fake started reading a request field it was not specced on"
        )
        # (3) The envelope is fixed however the seed moves: same root keys, same
        # criteria length, whatever the list held.
        shapes = {
            (tuple(sorted(json.loads(raw))), len(json.loads(raw)["criteria"]))
            for raw in got.values()
        }
        assert len(shapes) == 1, f"the fake's envelope moved with the payload: {shapes}"
        (root_keys, criteria_len) = shapes.pop()
        assert set(root_keys) == schema_keys, (sorted(root_keys), sorted(schema_keys))
        assert criteria_len >= 1, "the fake's criteria list is empty; shape check vacuous"


# ---------------------------------------------------------------------------
# S9 — the composite call whose response was a FREE-FORM map, and the
#      envelope-vs-fanout split it carried (plan 987-988).
# ---------------------------------------------------------------------------
class TestS9CompositeEnrich:
    """Two of this bullet's three legs had one subject: the composite
    ``/enrichment/enrich`` route. s9a and s9b tombstone it and re-drive what
    survived; s9c is RETARGETED - the envelope claim was never composite-
    specific, it is "the fake's body has the same ROOT KEYS as the committed
    golden", and every op has a golden.
    """

    def test_s9a_free_form_map_is_gone_and_bare_dict_remains(self) -> None:
        """TOMBSTONE: THE FREE-FORM RESPONSE MAP LEFT THE CONTRACT; THE BARE
        DICTS THAT STAYED CANNOT CATCH A KEY-SET REGRESSION EITHER.

        The composite's response field was ``enrichments`` with
        ``additionalProperties: true`` - a snapshot of a free-form map cannot
        fail, so EVERY wrong-key body validated green and the only
        load-bearing assertion in the whole cluster was the KEY SET per
        detection_type (person -> {clothing, demographics}, vehicle ->
        {vehicle}, pet -> {pet}, anything else -> {}). Two more hazards rode
        the same route:

          * ECHO-vs-GENERATED divergence, pinned per side and jointly: the
            gateway ECHOED the request's detection_type; the fake GENERATED one
            ("detection_type_NNN" from its string walker) and returned a
            free-form map with no per-type fan-out. A test that asserted only
            one side let a client that reads the echo break silently when the
            same client was pointed at the fake.
          * A DOCSTRING FALSEHOOD pinned as behavior: the handler advertised a
            depth branch it never implemented (unknown types got an empty
            map), characterized so that a "fix" which ADDED the branch
            reddened the suite instead of silently changing the contract.

        Ruling 4 deleted the adapter, so the free-form map has no text left to
        retarget onto and the ratchet in ``TestO2CompositeEnrichTombstone``
        (ops module) owns the op id. What DID survive is the weaker shape one
        level down - the yolo family still returns a bare ``dict[str, Any]``,
        so their schemas are the BareDictResponse marker and validation
        against them cannot fail either. The pin below is that marker census:
        the ops module's ``TestMultiImageOps`` asserts those key sets by
        driving the routes, and if the marker vanished from all three this
        record would be pointing at nothing.
        """
        assert "enrichment_enrich" not in OP_IDS
        assert not (REPO_ROOT / "ai/gateway/adapters/enrichment.py").exists()

        # The census is the ROOT-LEVEL marker the generator emits
        # (title=BareDictResponse + x-deployed-keys), not "the string
        # additionalProperties appears somewhere": ``enrich_lt_threat_detect``
        # carries the word too, on the ITEM schema of threats_detected, and it
        # has a real pydantic model and a real golden. Sloppy matching would
        # file it under the bare-dict family and the key-set argument below
        # would then be about an op that has no key set to lose.
        def _root_marker(op_id: str) -> bool:
            schema = json.loads((SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8"))
            return schema.get("title") == "BareDictResponse" and "x-deployed-keys" in schema

        bare = {op_id for op_id in OP_IDS if _root_marker(op_id)}
        assert bare == MULTI_IMAGE_OPS, (
            f"the bare-dict census changed: {sorted(bare)} - the key-set argument "
            "below and in the ops module needs re-deriving"
        )
        # NON-VACUITY, both directions: the marker set is neither everything
        # (a generator that stopped emitting response models) nor empty, and
        # the two spellings of the hazard stay distinguishable.
        assert 0 < len(bare) < len(OP_IDS), (sorted(bare), len(OP_IDS))
        item_free = {
            op_id
            for op_id in OP_IDS
            if not _root_marker(op_id)
            and '"additionalProperties": true'
            in (SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8")
        }
        assert item_free == {"enrich_lt_threat_detect"}, (
            f"the free-form ITEM hazard moved: {sorted(item_free)} - the vocabulary "
            "cluster's V3 pin needs the same re-derivation"
        )
        # The free-form marker is not worn by any surviving RESPONSE schema:
        # enrich-lt's threats_detected items are additionalProperties objects,
        # which is the same hazard in miniature and stays owned by the
        # vocabulary cluster (its V3 pins threat rows carry no name key).
        sibling = SIBLING_MODULES["ops"].read_text(encoding="utf-8")
        assert "class TestO2CompositeEnrichTombstone" in sibling, (
            "the ops module no longer owns the composite op-id ratchet"
        )
        vocab = (SUITE_DIR / "test_conformance_vocabulary.py").read_text(encoding="utf-8")
        assert "def test_V3_threat_rows_carry_no_canonical_name_at_all" in vocab, (
            "the free-form-item hazard lost the only surviving pin that named it"
        )

    async def test_s9b_no_surviving_route_gathers_two_models(
        self, gateway_client: AsyncClient
    ) -> None:
        """TOMBSTONE: THE COMPOSITE GATHER AND ITS INDEPENDENT-DEGRADATION
        CONTRACT ARE GONE.

        One POST to ``/enrichment/enrich`` gathered TWO specialist inferences
        concurrently with per-task exception capture, so one sub-model failure
        degraded one branch of the response instead of failing the call, and
        the drive asserted both branches arrived from a single round trip.
        (It also had to patch the adapter's weight loader to None - the
        adapter's OWN documented degradation path - to stay hermetic, which is
        why the envelope rather than the zero-shot math is what that drive
        certified.) Three properties lived there: single-round-trip
        aggregation, concurrent execution, and independent failure of a
        branch.

        Ruling 4 swept the provider, and the mounted surface has no peer: the
        census below reads every mounted handler and finds exactly ONE Triton
        model name per route and no gather anywhere, so "one call, several
        specialists, degrading independently" has no subject. No amount of
        re-driving a single-model route substitutes for it; the honest form is
        this absence, with the per-handler model-name census as the mechanism
        that notices if a composite ever comes back.
        """
        per_route: dict[str, int] = {}
        gather_sites = 0
        for op_id in sorted(OP_IDS):
            if op_id not in {o for o in OP_IDS if OPERATIONS[o].availability["gateway"]}:
                continue
            body = inspect.getsource(ROUTE_HANDLERS[op_id])
            per_route[op_id] = len(re.findall(r"model_name=", body))
            gather_sites += body.count("gather(")
        assert per_route and all(n == 1 for n in per_route.values()), (
            f"a gateway route now reaches more than one Triton model per call: {per_route} - "
            "the composite fan-out has a subject again and this tombstone must be re-driven"
        )
        assert gather_sites == 0, (
            f"the mounted adapters gained concurrent fan-out ({gather_sites} gather sites): "
            "independent branch degradation is testable again, here or in the ops module"
        )

        # The residency bound, derived TWICE and never from a literal: once
        # from each adapter's own /health payload, once from the model names its
        # routes actually CALL under a recording Triton client. The two
        # derivations must agree - which is the load-bearing part: a route that
        # quietly reached a second model would show up as a called-not-advertised
        # name, and that is exactly the composite this tombstone says is gone.
        def _health_models(payload: dict[str, Any]) -> set[str]:
            """Model names a health payload declares, from ITS OWN shape: the
            light adapter reports a per-model dict, the yolo adapter a single
            model. Any other shape raises rather than returning an empty set.
            """
            if "models" in payload:
                return set(payload["models"])
            if "model" in payload:
                return {payload["model"]}
            raise AssertionError(f"unrecognized /health shape: {sorted(payload)}")

        called: set[str] = set()

        async def _record(**kw: Any) -> dict[str, Any]:
            called.add(str(kw.get("model_name")))
            return _canned_for(kw.get("model_name"), kw.get("outputs"))

        mounted_prefixes = {prefix for _m, prefix in GATEWAY_MOUNTS}
        routes = sorted(
            {
                (op_id, op.path)
                for op_id, op in OPERATIONS.items()
                if op.method == "POST"
                and any(op.path.startswith(f"{prefix}/") for prefix in mounted_prefixes)
            }
        )
        # 5 registry POST ops on the two prefixes (3 yolo + 2 enrich-lt).
        assert len(routes) == 5, f"the mounted POST census changed: {routes}"
        with ExitStack() as stack:
            for target in GATEWAY_PATCH_TARGETS:
                recorder = _fake_triton()
                recorder.infer = AsyncMock(side_effect=_record)
                stack.enter_context(patch(target, return_value=recorder))
            for op_id, path in routes:
                r = await gateway_client.post(path, **_gateway_kwargs(op_id))
                assert r.status_code == 200, (op_id, path, r.text)
            advertised: set[str] = set()
            for prefix in sorted(mounted_prefixes):
                r = await gateway_client.get(f"{prefix}/health")
                assert r.status_code == 200, (prefix, r.text)
                advertised |= _health_models(r.json())
        assert advertised and called, (sorted(advertised), sorted(called))
        assert called == advertised, (
            f"routes call {sorted(called)} but health advertises {sorted(advertised)}: "
            "a route reaching a model its adapter does not declare is a composite "
            "coming back, and this tombstone must be re-driven"
        )
        assert len(called) == 3, (
            f"the residency set moved to {sorted(called)}; one Triton model per route is "
            "the bound this tombstone rests on"
        )
        r = await gateway_client.post("/enrichment/enrich", json={"image": _png_b64()})
        assert r.status_code == 404, f"/enrichment/enrich served again: {r.status_code}"

    def test_s9c_the_fake_envelope_matches_the_committed_golden_for_every_op(
        self,
    ) -> None:
        """RETARGETED and widened: the fake-vs-golden ROOT-KEY sweep, over the
        whole registry instead of the one composite op.

        s9c used to compare the fake's ``/enrichment/enrich`` body against
        that op's committed golden and call it a pair with s9b's fan-out: the
        fake certifies the ENVELOPE, the gateway certifies the AGGREGATION,
        and fake-only conformance would miss a composite that never
        aggregates. That claim does not need the composite - it needs an op,
        so it is swept across the whole registry.

        The sweep compares each fake body against the artifact that ACTUALLY
        states that op's root keys, which is two different artifacts, and
        pretending otherwise is how this def first went red:

          * MODELLED ops (a pydantic response model exists): the committed
            golden is the key set, and the pin asserts golden == the schema's
            own property set so "the golden" cannot silently mean "an empty
            dict someone committed".
          * BARE-DICT ops (``-> dict[str, Any]``, no model): their golden is
            honestly ``{}`` - the generator snapshot-walked nothing - so key-set
            equality against it would demand the fake emit NOTHING. Their
            committed key statement is ``x-deployed-keys``, the WP7.4 field the
            generator writes from the adapter's own return dict.

        ``llm_slots`` is the second carve-out and it is stated, not hidden: its
        golden is a JSON STRING (the generator walked an ``Any`` slot list and
        emitted the binary-marker body), so key-set equality is not a
        meaningful claim there and the drive asserts only that it parses. The
        three-way census below makes the sweep non-vacuous in every direction:
        five golden-backed ops, three marker-backed ops, one string op, and the
        three families are disjoint and jointly the whole registry.
        """
        import asyncio

        golden_obj: set[str] = set()
        string_ops: set[str] = set()
        marker_ops: set[str] = set()
        golden_backed: dict[str, set[str]] = {}
        for op_id in OP_IDS:
            golden = json.loads((GOLDEN_DIR / f"{op_id}.response.example.json").read_text("utf-8"))
            schema = json.loads((SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8"))
            if not isinstance(golden, dict):
                string_ops.add(op_id)
                continue
            if schema.get("title") == "BareDictResponse":
                marker_ops.add(op_id)
                golden_backed[op_id] = set(schema["x-deployed-keys"])
                assert not golden, (
                    f"{op_id} carries the bare-dict marker AND a non-empty golden "
                    f"{sorted(golden)}: two sources now state its key set"
                )
                continue
            golden_obj.add(op_id)
            golden_backed[op_id] = set(golden)
            # The golden is only a proxy for the contract if it IS the schema.
            assert set(golden) == set(schema["properties"]), (
                op_id,
                sorted(set(golden) ^ set(schema["properties"])),
            )
        assert string_ops == {"llm_slots"}, f"the string-golden carve-out moved: {string_ops}"
        assert golden_obj == {
            "enrich_lt_person_reid",
            "enrich_lt_threat_detect",
            "llm_chat_completion",
            "llm_completion",
            "vlm_assess",
        }, f"the golden-backed family changed: {sorted(golden_obj)}"
        assert marker_ops == MULTI_IMAGE_OPS, (
            f"the marker-backed family changed: {sorted(marker_ops)}"
        )
        assert golden_obj and marker_ops and string_ops
        assert not (golden_obj & marker_ops) and not (marker_ops & string_ops)
        assert golden_obj | marker_ops | string_ops == OP_IDS, "a registry op joined no family"

        def _fake_kwargs(op_id: str) -> dict[str, Any]:
            op = OPERATIONS[op_id]
            if op.method == "GET":
                return {}
            example = GOLDEN_DIR / f"{op_id}.request.example.json"
            if example.exists():
                payload = json.loads(example.read_text(encoding="utf-8"))
                if isinstance(payload, str):
                    return {"files": [("file", ("frame.png", _png_bytes(), "image/png"))]}
                return {"json": payload}
            # No request golden at all (the enrich-lt pair): the fake reads
            # bodies only for echo fields, so a neutral image body is legal.
            return {"json": {"image": _png_b64()}}

        async def _sweep() -> dict[str, tuple[set[str], set[str]]]:
            app = create_fake_app()
            out: dict[str, tuple[set[str], set[str]]] = {}
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fake"
            ) as client:
                for op_id in sorted(golden_obj | marker_ops):
                    op = OPERATIONS[op_id]
                    r = await client.request(op.method, op.path, **_fake_kwargs(op_id))
                    assert r.status_code == 200, (op_id, r.status_code, r.text)
                    body = r.json()
                    assert isinstance(body, dict), (
                        f"{op_id}: the contract's golden is an object, the fake answered "
                        f"{type(body).__name__}"
                    )
                    out[op_id] = (set(body), golden_backed[op_id])
                # The carve-out still gets driven: it must PARSE.
                op = OPERATIONS[next(iter(string_ops))]
                r = await client.request(op.method, op.path, **_fake_kwargs(next(iter(string_ops))))
                assert r.status_code == 200, (op.id, r.status_code, r.text)
                json.loads(r.content)
            return out

        compared = asyncio.run(_sweep())
        assert set(compared) == golden_obj | marker_ops, (
            f"the sweep skipped ops (compared {sorted(compared)})"
        )
        for op_id, (emitted, expected) in compared.items():
            assert emitted == expected, (
                f"{op_id}: fake root keys {sorted(emitted)} != committed key set "
                f"{sorted(expected)} - fake-side conformance is validating a surface "
                "the contract does not ship"
            )


# ---------------------------------------------------------------------------
# Matrix guards - the semantics-relevant ops against every provider's
# availability column. NEVER invoke a registered callable for
# per_model_http / llamacpp_llm / gateway_light (network / live client).
#
# Both tables below are DERIVED. The hand-listed _SEMANTICS_OPS and the
# hand-copied SIBLING_SENTINELS are what rotted here: they named eleven ops
# and three not-wired sets, and R8 S3 retired eight of the ops without
# touching this file. The semantics rows are now "any op with a semantic trap
# in this cluster", read off the artifacts; the not-wired census is read off
# the registry's own client_methods field and cross-checked against the call
# objects.
# ---------------------------------------------------------------------------
def _confidence_sites(src: str) -> int:
    """How many times a source spells a ``confidence`` response key."""
    return len(re.findall(r'"(?:max_)?confidence"\s*:', src))


def _semantics_ops() -> set[str]:
    """Every live op that carries one of this file's nine semantic traps, read
    from the artifacts rather than from a list someone maintained:

      * a confidence value in its RESPONSE schema text (S6) - which covers
        both spellings, the declared ``max_confidence`` field and the
        ``confidence`` key of a free-form item;
      * a bare-dict ``x-deployed-keys`` response (S6/S9: the key sets are
        invisible to a schema walk, so a drive is the only check);
      * an ``embedding`` field (S2: dimension/space confusion);
      * a ``prompt`` field in its REQUEST schema (S3/S4: passthrough text);
      * a multipart request (S8: multi-image fan-out);
      * a JSON-object golden (S9: the envelope claim).

    ``llm_slots`` is the one op with no semantic trap and no golden object - it
    is deliberately OUT, and the census below is the non-vacuity.
    """
    hits: set[str] = set()
    for op_id in OP_IDS:
        resp_text = (SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8")
        if _confidence_sites(resp_text) or '"x-deployed-keys"' in resp_text:
            hits.add(op_id)
        props = (
            json.loads(resp_text).get("properties", {}) or {}
            if json.loads(resp_text).get("type") == "object"
            else {}
        )
        if "embedding" in props or "prompt" in props:
            hits.add(op_id)
        req = SCHEMA_DIR / f"{op_id}.request.json"
        # Absence is the correct answer for the enrich-lt pair (they share one
        # request model the generator does not walk), so it is skipped rather
        # than opened -- a bare read_text() here would be a collection ERROR.
        req_text = req.read_text(encoding="utf-8") if req.exists() else ""
        if "binary" in req_text:
            hits.add(op_id)
        req_props = (json.loads(req_text).get("properties", {}) or {}) if req_text else {}
        if "prompt" in req_props:
            hits.add(op_id)
        golden = json.loads((GOLDEN_DIR / f"{op_id}.response.example.json").read_text("utf-8"))
        if isinstance(golden, dict):
            hits.add(op_id)
    return hits


SEMANTICS_OPS = _semantics_ops()
assert set(OP_IDS) - {"llm_slots"} == SEMANTICS_OPS, (
    f"the semantics-row census changed: {sorted(SEMANTICS_OPS)}"
)
assert (
    len(
        {
            op
            for op in SEMANTICS_OPS
            if _confidence_sites((SCHEMA_DIR / f"{op}.response.json").read_text("utf-8"))
        }
    )
    >= 1
)
# llm_slots is out, and that exclusion has to be provably a decision rather
# than a derivation accident: it has a golden, a route and a provider.
assert "llm_slots" in OP_IDS and OPERATIONS["llm_slots"].availability["fake"] is True


def _provider_ops(pid: ProviderId) -> dict[str, Any]:
    """Registered callables for a provider, registering the FAKE on demand
    (fake is deliberately not registered at import - ai_contract/providers.py;
    the accepted in-test pattern is the ops module's)."""
    if pid is ProviderId.FAKE:
        from backend.ai_contract.fake import fake_provider_ops

        return register_provider(
            ProviderId.FAKE, fake_provider_ops(), OPERATIONS, deployed=True
        ).operations()
    return registered_providers()[pid.value].operations()


# Registry's OWN record of the third matrix state: an op declared for a slot
# with no bound client method gets the shared NOT-WIRED sentinel instead of a
# callable. NOT a hand list - a field read.
NOT_WIRED_OPS = {op_id for op_id, op in OPERATIONS.items() if not op.client_methods}
assert len(NOT_WIRED_OPS) == 7, f"the not-wired census changed: {sorted(NOT_WIRED_OPS)}"
_NOT_WIRED_QUALNAME = "_not_wired"

# Which factory builds each provider's callables, read out of ``_register_all``'s
# own AST. This is the fact that decides what the third matrix state MEANS for a
# provider: a REGISTRY-BOUND provider (factory ``_bound_or_reject``) resolves
# ``client_methods`` and therefore hands back the NOT-WIRED sentinel exactly
# where the registry says ``client_methods == []``; an AUTHORED provider writes
# its own callable per op, so ``client_methods`` says nothing about it and its
# sentinel set is empty by construction regardless of what the registry column
# says. The trap this removes: ``llamacpp_llm`` registers llm_completion and
# llm_chat_completion - both registry-not-wired - with LIVE payload passthrough,
# so ``registered sentinels == ops & NOT_WIRED_OPS`` is simply the wrong oracle
# for it. Hard-coding which providers are bound would have frozen that as a list
# of names; hard-coding the EXPECTED QUALNAME of each authored callable (the
# first attempt here) froze the same fact one level deeper.
_PROVIDER_FACTORY_FN = "_register_all"
_BOUND_FACTORY = "_bound_or_reject"


def _provider_factories() -> dict[ProviderId, str]:
    src = (REPO_ROOT / "backend/ai_contract/providers.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    module_fns = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == _PROVIDER_FACTORY_FN
    )

    def pids_of(node: ast.AST) -> set[ProviderId]:
        return {
            ProviderId[attr]
            for attr in (
                a.attr
                for a in ast.walk(node)
                if isinstance(a, ast.Attribute)
                and isinstance(a.value, ast.Name)
                and a.value.id == "ProviderId"
            )
            if attr in ProviderId.__members__
        }

    def factories_of(node: ast.AST) -> set[str]:
        return {
            n.id
            for n in ast.walk(node)
            if isinstance(n, ast.Name) and n.id in module_fns and n.id != _PROVIDER_FACTORY_FN
        }

    found: dict[ProviderId, str] = {}

    def record(pids: set[ProviderId], node: ast.AST) -> None:
        names = factories_of(node)
        assert names, f"a registration site names no factory from providers.py: {ast.dump(node)}"
        assert len(names) == 1, f"a registration site mixes factories: {sorted(names)}"
        (name,) = names
        for pid in pids:
            assert pid not in found, f"{pid.value} is registered twice by {_PROVIDER_FACTORY_FN}()"
            found[pid] = name

    for node in ast.walk(fn):
        if isinstance(node, ast.For):
            pids = pids_of(node.iter)
            if pids:
                record(pids, node)
        elif (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "register_provider"
            and len(node.args) >= 2
        ):
            pids = pids_of(node.args[0])
            if pids:
                record(pids, node.args[1])

    # FAKE is the one provider _register_all does NOT own (ai_contract/providers.py
    # keeps it out of the import-time registration); its authored-ness is derived
    # from ITS OWN source below rather than assumed.
    from backend.ai_contract.fake import fake_provider_ops

    assert _BOUND_FACTORY not in inspect.getsource(fake_provider_ops), (
        "the fake started resolving client_methods itself: the registry-bound/authored "
        "split below no longer covers it"
    )
    assert set(found) == set(ProviderId) - {ProviderId.FAKE}, (
        f"_register_all() no longer registers every non-fake provider: {sorted(found)}"
    )
    assert ProviderId.FAKE not in found, "the fake is registered at import after all"
    found[ProviderId.FAKE] = "authored-by-fake_provider_ops"
    assert any(name == _BOUND_FACTORY for name in found.values()) and any(
        name != _BOUND_FACTORY for name in found.values()
    ), f"the bound/authored split collapsed: {found}"
    return found


PROVIDER_FACTORIES = _provider_factories()
REGISTRY_BOUND_PROVIDERS = {
    pid for pid, name in PROVIDER_FACTORIES.items() if name == _BOUND_FACTORY
}
assert REGISTRY_BOUND_PROVIDERS and set(ProviderId) > REGISTRY_BOUND_PROVIDERS

# Union-slot SUBSET providers -> their required set. llamacpp's is EVIDENCE
# -derived exactly the way its registration is (per_model_server True AND
# ai/nemotron in evidence); the pin below is that the derivation still yields
# the measured pair, which is what keeps the equality guard from becoming a
# tautology against the provider's own expression.
_LLAMACPP_REQUIRED = {
    op_id
    for op_id, op in OPERATIONS.items()
    if op.availability.get("per_model_server", False) and "ai/nemotron" in op.evidence
}
SUBSET_REQUIRED: dict[ProviderId, set[str]] = {
    ProviderId.LLAMACPP_LLM: _LLAMACPP_REQUIRED,
    ProviderId.OPENAI_VLM: {"vlm_assess"},
    ProviderId.RTVI_VLM: {"vlm_assess"},
}
assert {"llm_completion", "llm_chat_completion"} == _LLAMACPP_REQUIRED, (
    f"the evidence-derived llama.cpp set moved: {sorted(_LLAMACPP_REQUIRED)}"
)
assert all(
    required < set(operations_for_slot("per_model_server", OPERATIONS))
    for required in SUBSET_REQUIRED.values()
), "a SUBSET provider's required set stopped being a strict subset of the union column"


def _sibling_sentinel_sets() -> dict[ProviderId, set[str]]:
    """The ops module's three NOT-WIRED literals, read by AST (the sibling
    owns them; a hand copy here is the drift this rewrite exists to remove).

    Only the three shapes those literals actually use are evaluated - set
    literal, name, ``|``, ``set(name)`` - and anything else raises, so a
    sibling rewrite into a comprehension fails LOUD instead of reading as an
    empty set.
    """
    wanted = {
        "SENTINELS_GATEWAY": ProviderId.GATEWAY,
        "SENTINELS_LIGHT": ProviderId.GATEWAY_LIGHT,
        "SENTINELS_PER_MODEL": ProviderId.PER_MODEL_HTTP,
    }
    src = SIBLING_MODULES["ops"].read_text(encoding="utf-8")
    # Every module-level assignment is collected, not just the three wanted
    # names: SENTINELS_GATEWAY is spelled `_ENRICH_LT_UNBOUND | {...}`, so a
    # reader that only knew the three targets fails on the helper name.
    assigns: dict[str, ast.expr] = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigns[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                assigns[node.target.id] = node.value

    def _eval(node: ast.expr) -> set[str]:
        if isinstance(node, ast.Set):
            return {ast.literal_eval(elt) for elt in node.elts}
        if isinstance(node, ast.Name):
            return _eval(assigns[node.id])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return _eval(node.left) | _eval(node.right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "set":
            (arg,) = node.args
            return _eval(arg)
        raise AssertionError(f"unsupported set-expression shape: {ast.dump(node)}")

    missing = set(wanted) - set(assigns)
    assert not missing, f"the ops module renamed a sentinel literal: {sorted(missing)}"
    return {wanted[name]: _eval(assigns[name]) for name in wanted}


class TestSemanticsMatrixGuards:
    @pytest.mark.parametrize("pid", list(ProviderId), ids=lambda p: p.value)
    def test_semops_registered_set_matches_the_availability_column(self, pid) -> None:
        """Presence/absence is a green guard, never a skip (plan procedure).
        For the three never-invoked providers this IS the semantics coverage:
        the registered set equals the slot column, and the SUBSET providers
        equal their own evidence-declared required set inside the union
        column. The per-provider semantics-row expectations are spelled out
        for the two single-app providers so a column edit that drops e.g. a
        yolo op from the gateway fails LOUD, not quietly.
        """
        ops = set(_provider_ops(pid))
        assert ops, f"{pid.value} registered nothing"
        if pid in SUBSET_REQUIRED:
            assert ops == SUBSET_REQUIRED[pid], pid
            return
        column = set(operations_for_slot(PROVIDER_SLOT[pid], OPERATIONS))
        assert ops == column, (pid, sorted(ops ^ column))
        present = ops & SEMANTICS_OPS
        assert present, f"{pid.value} serves no semantics row at all"
        if pid is ProviderId.GATEWAY:
            assert {"yolo26_detect", "yolo26_segment", "enrich_lt_threat_detect"} <= present
        elif pid is ProviderId.GATEWAY_LIGHT:
            assert present == {"enrich_lt_person_reid", "enrich_lt_threat_detect"}, present
        elif pid is ProviderId.PER_MODEL_HTTP:
            assert {"yolo26_detect", "vlm_assess", "llm_completion"} <= present, present
        elif pid is ProviderId.FAKE:
            assert present == SEMANTICS_OPS, present
            assert ops == set(OPERATIONS), "the fake stopped covering the whole spec column"

    @pytest.mark.parametrize("pid", list(ProviderId), ids=lambda p: p.value)
    def test_semops_not_wired_state_is_the_registry_census_and_the_siblings_set(self, pid) -> None:
        """The third matrix state (declared, not wired), pinned from three
        independent directions at once: the registry's ``client_methods``
        field, the call object that was actually registered, and the ops
        module's own literal. A wiring change has to move all three or this
        reddens - which is the cross-module coupling the hand-copied
        SIBLING_SENTINELS table used to fake.
        """
        ops = _provider_ops(pid)
        sentinels = {op_id for op_id, fn in ops.items() if _NOT_WIRED_QUALNAME in fn.__qualname__}
        if pid in REGISTRY_BOUND_PROVIDERS:
            # The registry's client_methods field IS the oracle here.
            assert sentinels == set(ops) & NOT_WIRED_OPS, (
                pid,
                sorted(sentinels ^ (set(ops) & NOT_WIRED_OPS)),
            )
            sibling_sets = _sibling_sentinel_sets()
            if pid in sibling_sets:
                # The ops module's literal is a THIRD opinion, only for the three
                # providers it has a row for. The two SUBSET providers that share
                # the per-model-server column (openai_vlm, rtvi_vlm) register one
                # bound op and no sentinel at all, so the enrich-lt non-vacuity
                # below is about the three full-column providers, not them.
                assert sentinels == sibling_sets[pid] & set(ops), (
                    pid,
                    sorted(sentinels ^ (sibling_sets[pid] & set(ops))),
                )
                assert "enrich_lt_person_reid" in sentinels, (
                    "the enrich-lt pair left the not-wired state: the semantics rows "
                    "lost their only third-state example"
                )
                return
            assert not (set(ops) & NOT_WIRED_OPS) or pid is ProviderId.PER_MODEL_HTTP, (
                pid,
                sorted(set(ops) & NOT_WIRED_OPS),
            )
            return
        # An AUTHORED provider: every callable comes from a factory named at its
        # registration site (derived above, not hand-listed), so no registered
        # callable may be a placeholder no matter what the registry column says.
        factory = PROVIDER_FACTORIES[pid]
        qualnames = {fn.__qualname__ for fn in ops.values()}
        assert sentinels == set(), (pid, sorted(sentinels))
        assert ops, pid
        if factory == "authored-by-fake_provider_ops":
            assert all(q.startswith("fake_provider_ops.") for q in qualnames), qualnames
        else:
            assert all(q.startswith(f"{factory}.") for q in qualnames), (factory, qualnames)
            # NON-VACUITY of the split: an authored provider whose ops ARE
            # registry-not-wired is the case the naive oracle got wrong. If no
            # authored provider ever overlaps that census, bound-vs-authored is
            # decoration and this pin should be deleted rather than kept.
            if pid is not ProviderId.FAKE and set(ops) & NOT_WIRED_OPS:
                assert set(ops) <= NOT_WIRED_OPS, (pid, sorted(set(ops) - NOT_WIRED_OPS))

    def test_semops_plan_bullets_all_mapped(self) -> None:
        """MEASURE meta-guard: bullets S1-S9 each still own a test in THIS
        file and no skip/xfail/deselect text ever appears - a bullet dropped
        in review turns this RED, which is the point. Self-scan via
        ``__file__``: the path is this module's own, no user input.
        """
        text = Path(__file__).read_text(encoding="utf-8")  # nosemgrep: path-traversal-open
        defs = [
            ln.strip().split("(")[0] for ln in text.splitlines() if ln.strip().startswith("def ")
        ]
        for bullet in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9"):
            prefix = f"def test_s{bullet[1].lower()}"
            hits = [d for d in defs if d.startswith(prefix)]
            assert hits, f"bullet {bullet} lost its test"
        # NON-VACUITY, per def rather than per bullet: a tombstone that kept
        # its name but lost its assertions would satisfy the name scan above,
        # so every test in this module must assert at its own top level. A
        # helper's assert does not count for its enclosing test.
        tree = ast.parse(text)
        bare = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name.startswith("test_")
            and not any(isinstance(child, ast.Assert) for child in node.body)
        ]
        assert bare == [], f"tests with no top-level assert: {bare}"
        # Forbidden MECHANISMS - needles assembled at runtime so this guard's
        # own literals cannot self-match the scan it runs (the header names
        # the rule in prose; this rules out CALLS):
        forbidden = [
            "pytest" + "." + tail
            for tail in ("skip(", "skip.if", "skipif", "mark.xfail", "importorskip")
        ] + ["--" + "deselect"]
        for needle in forbidden:
            assert needle not in text, needle
