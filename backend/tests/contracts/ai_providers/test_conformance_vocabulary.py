"""WP8.3 per-property module: VOCABULARY (V1a-V5).

Part of the plan's single conformance suite (docs/superpowers/plans/
2026-09-19-swap-readiness-72h.md §WP8.3, "_Vocabulary_" block): the
property a provider swap changes first, with no enforcement anywhere
today.

R8 S3 retarget state (2026-09-29, five owner rulings). A third of the
shipped AI surface was swept by this slice, and it took the module this
file was drafted against: the gateway drove FIVE adapter routers over FIVE
``get_triton_client`` names; two adapters survive (``/yolo26``,
``/enrich-lt``), so the mount list, the patch-target list and every drive
built on them are re-derived here rather than trimmed by hand. Florence
retired whole (ruling 1) and CLIP retired as a prune consequence (ruling 5),
so:

  * RETARGETED — the VOCAB_HOMES derivation (the detections-keyed set is now
    read out of the committed schemas' ``x-deployed-keys`` instead of a hand
    list that named two dead ops), the drivable gateway legs (two-router app,
    two patch targets), V4's failure-shape property (retargeted onto the
    SINGLE-image route, which is the side that answers 503 — the batch side
    isolates per item and stays 200), V5's synthetic-name leg (retargeted
    from yolo's unreachable ``class_{id}`` fallback onto the light lane's
    reachable ``threat_{id}``), and V5's DB-write leg (the wire key that
    reaches the column is the SURVIVING ``class`` spelling, which the fake
    emits and the consumer stores).
  * TOMBSTONED — the per-provider three-names property. One concept, three
    wire spellings, was drivable on both providers because Florence's routes
    answered ``label`` while yolo answered ``class``. There is no ``label``
    responder left to drive, so that pin dies here with the hazard spelled
    out — not as a skip.

Provider driving shapes (harness-verified, do not re-litigate):
  * fake   — registered in-test; driven through its app over
             ASGITransport; X-Fake-Profile switches the vocabulary
             profile; /fake/profiles/classes exposes both tables as data.
  * gateway — the TWO surviving adapter routers mounted with production
             prefixes (ai/gateway/main.py:272-273) with both module-level
             get_triton_client names patched (template:
             ai/gateway/tests/test_adapters_yolo26.py:98-104, at the
             two-target shape R8 S3 leaves).
  * per_model_http / llamacpp_llm — MATRIX GUARD ONLY (column match +
             deployed flag). Their callables hit the network — never
             invoked.
  * registered gateway/gateway_light callables are UNBOUND client
             methods (real network if called) — this suite never calls
             registered_providers()[...].operations() callables.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
from contextlib import ExitStack, asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.ai_contract.operations import OPERATION_IDS, OPERATIONS
from backend.core.config import Settings
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = REPO_ROOT / "backend/ai_contract/schemas"

# ---------------------------------------------------------------------------
# Mirror data (the test_fake_provider.py pattern: vocabularies carried as
# DATA; AST mirror tests pin every copy against its source).
# ---------------------------------------------------------------------------

# ai/yolo26/model.py:151.
WP83_SECURITY_CLASSES = {
    "person",
    "car",
    "truck",
    "dog",
    "cat",
    "bird",
    "bicycle",
    "motorcycle",
    "bus",
}

# Server-side per-class table, ai/yolo26/model.py:173 (AST-pinned below;
# the literal here is only the expectation the pin compares against).
WP83_SERVER_THRESHOLDS = {
    "person": 0.45,
    "car": 0.70,
    "truck": 0.70,
    "bus": 0.70,
    "motorcycle": 0.65,
    "bicycle": 0.65,
    "dog": 0.55,
    "cat": 0.55,
    "bird": 0.55,
}

# Backend per-class table (the DECLARED DEFAULT), backend/core/config.py
# :1829-1843 (Settings.model_fields readout — deliberately NOT an env-
# resolved instance, so a sandbox .env cannot redden a vocabulary pin
# that is about shipped defaults).
WP83_BACKEND_THRESHOLDS = {
    "person": 0.40,
    "car": 0.50,
    "truck": 0.50,
    "bus": 0.55,
    "motorcycle": 0.50,
    "bicycle": 0.50,
    "dog": 0.45,
    "cat": 0.45,
    "bird": 0.45,
    "backpack": 0.50,
    "handbag": 0.50,
    "suitcase": 0.50,
}

# The three backend entries the native server can never let fire
# (backend/core/config.py:1829; dropped upstream by the single SECURITY
# filter in ai/yolo26/model.py:1085).
WP83_DEAD_ENTRIES = {"backpack", "handbag", "suitcase"}

# V5: the wire key the DB write reads (detector_client.py:1286
# `object_type=detection_data.get("class")`) — the spelling the SURVIVING
# surface emits on both providers. The sibling spellings this concept used
# to be pinned across are in the V3 tombstone below.
WP83_WIRE_KEY = "class"

# V4 consumer property: the key whose ABSENCE the consumer checks (and the
# ONLY thing it checks — no isinstance(list) guard exists anywhere in the
# file), and the metric that absence records.
WP83_DETECTIONS_KEY = "detections"
WP83_MALFORMED_METRIC = "malformed_response"

# V3's third, still-labeled vocabulary (enrichment_light.py:84). Derived,
# not hand-listed, by the test that uses it — this is the only place the
# name is written down, and it is written as a lookup, not a literal.
_THREAT_TABLE_SITE = REPO_ROOT / "ai/gateway/adapters/enrichment_light.py"


def _threat_classes() -> list[str]:
    """THREAT_CLASSES read out of the light adapter's source (its function-
    local literal, so `_ast_assign`'s module-level walk does not see it —
    this scans for the one AnnAssign whose value is a list of string
    constants)."""
    tree = ast.parse(_THREAT_TABLE_SITE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            names = (
                [t.id for t in node.targets if isinstance(t, ast.Name)]
                if isinstance(node, ast.Assign)
                else ([node.target.id] if isinstance(node.target, ast.Name) else [])
            )
            if "THREAT_CLASSES" in names and node.value is not None:
                value = ast.literal_eval(node.value)
                if isinstance(value, list) and all(isinstance(x, str) for x in value):
                    return value
    raise AssertionError("THREAT_CLASSES literal not found in the light adapter")


# ---------------------------------------------------------------------------
# V4 membership: the registry operations whose committed response contract
# carries a TOP-LEVEL "detections" key.
#
# DERIVED (WP4.2), not hand-listed. The hand list this replaces named four
# ops, two of them Florence, and R8 S3 took those two out of the contract —
# a literal like that does not fail loudly, it just keeps asserting a set
# that no longer means anything. The rule that generated it is still the
# rule, and it still runs:
#   * a WALKED schema carries the key in `properties` or `required`;
#   * a BARE-DICT schema (the yolo family — the route declares
#     `-> dict[str, Any]`) carries it in `x-deployed-keys`.
# Measured today: yolo26_detect + yolo26_segment. yolo26_detect_batch is
# excluded by the same rule that always excluded it — its "detections" live
# per-ITEM (x-deployed-keys ["results", ...]; adapters/yolo26.py:421-427)
# and the consumer's key check (detector_client.py:1153) reads the TOP level
# only. Per-item shape belongs to the batch/op-targets cluster
# (test_conformance_ops.py::TestMultiImageOps).
# ---------------------------------------------------------------------------


def _schema_carries_key(op_id: str, key: str) -> bool:
    path = SCHEMA_DIR / f"{op_id}.response.json"
    if not path.exists():
        return False
    schema = json.loads(path.read_text(encoding="utf-8"))
    if key in (schema.get("properties") or {}) or key in (schema.get("required") or []):
        return True
    return key in (schema.get("x-deployed-keys") or [])


def _detections_keyed_ops() -> tuple[str, ...]:
    return tuple(
        op_id for op_id in sorted(OPERATIONS) if _schema_carries_key(op_id, WP83_DETECTIONS_KEY)
    )


def _provider_vocab_column(op_id: str, slot: str) -> bool:
    return bool(OPERATIONS[op_id].availability.get(slot, False))


# ---------------------------------------------------------------------------
# V1c: the orphan census's cheap prefilter.
#
# A byte-substring test on the module name is a SOUND SUPERSET of the
# import form the census matches: `from ai.triton import X` / `import
# ai.triton` contain "ai.triton" verbatim, so the AST pass only ever runs
# over files the substring already matched — the prefilter cannot hide a
# consumer, which is the only way a filtered scan can be wrong. It exists
# because the full-tree scan is the expensive part: ledger item 49 is a
# 4.0s unit-test breach this exact census walked into, and CI measures
# roughly 2x local.
# ---------------------------------------------------------------------------
_ORPHAN_NEEDLE = "ai.triton"
_ORPHAN_ROOTS = ("backend", "ai", "scripts", "frontend")
_ORPHAN_IMPORT = re.compile(r"^\s*(from|import)\s+ai\.triton\b", re.MULTILINE)


def _production_ai_triton_consumers() -> list[str]:
    consumers: list[str] = []
    for root in _ORPHAN_ROOTS:
        tree = REPO_ROOT / root
        if not tree.is_dir():
            continue
        for path in sorted(tree.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT)
            if "__pycache__" in rel.parts:
                continue
            if rel.parts[:2] == ("ai", "triton"):
                continue  # the module itself
            if "tests" in rel.parts or rel.name.startswith("test_"):
                continue  # test pins are not production consumers
            text = path.read_text(encoding="utf-8", errors="replace")
            if _ORPHAN_NEEDLE not in text:
                continue  # sound superset prefilter — see the note above
            if _ORPHAN_IMPORT.search(text):
                consumers.append(str(rel))
    return consumers


# ---------------------------------------------------------------------------
# The gateway driving shape, DERIVED from the live production mount block.
#
# This is the piece R8 S3 broke. The suite used to hand-mount five routers
# and hand-patch five get_triton_client names; three of those modules are
# gone and the five-name literal would now fail at import. It is not
# trimmed to two by hand either: the routers and the prefixes are read out
# of ai/gateway/main.py's include_router lines and resolved through the same
# import path the app uses, so the mount list cannot drift from production,
# and the patch targets are DERIVED from it. A third adapter entering the
# gateway therefore adds a ROW to the derived list on its own — a new
# mounted router is a new patch target automatically, which is the whole
# point of the multi-target rule (patching one adapter's name silently
# leaves every other mounted adapter on real gRPC).
# ---------------------------------------------------------------------------
_MAIN_SITE = REPO_ROOT / "ai/gateway/main.py"
_INCLUDE_ROUTER = re.compile(
    r"include_router\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:,\s*[^)]*?prefix\s*=\s*['\"]([^'\"]+)['\"])?",
)


def _gateway_mounts() -> tuple[tuple[str, str, str], ...]:
    """(import module, router attribute, prefix) for every adapter router the
    production gateway mounts. Module comes from the file the name was
    imported FROM (read out of main.py's own import lines), so a router
    imported from a non-adapter module is a loud error, not a silent skip."""
    src = _MAIN_SITE.read_text(encoding="utf-8")
    bound: dict[str, tuple[str, str]] = {}
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if ".adapters." not in f"{node.module}.":
            continue
        for alias in node.names:
            local = alias.asname or alias.name
            bound[local] = (node.module, alias.name)
    mounts: list[tuple[str, str, str]] = []
    for router_var, prefix in _INCLUDE_ROUTER.findall(src):
        if router_var not in bound:
            continue  # a non-adapter router (none today) is not our driving shape
        module, attr = bound[router_var]
        mounts.append((module, attr, prefix or ""))
    derived = tuple(mounts)
    # Non-vacuity, asserted here rather than at each call site: the derived
    # mount list must be the shipped one, or every gateway drive below is
    # driving an app production does not run.
    assert len(derived) >= 2, f"expected the surviving adapter mounts, got {derived}"
    for module, _attr, prefix in derived:
        assert module.startswith("ai.gateway.adapters."), module
        assert prefix, f"{module} mounted without its production prefix"
    return derived


def _gateway_patch_targets() -> tuple[str, ...]:
    """One patch target per MOUNTED adapter module, derived from
    `_gateway_mounts()`. Two targets today; three the day someone mounts a
    third router — and they get the third automatically."""
    return tuple(f"{module}.get_triton_client" for module, _attr, _p in _gateway_mounts())


# ---------------------------------------------------------------------------
# Source helpers (AST/regex reads of the repo — same mechanism as
# test_fake_provider.py's mirror tests).
# ---------------------------------------------------------------------------


def _schema_property_names(node: Any, found: set[str] | None = None) -> set[str]:
    """Every PROPERTY NAME a JSON schema declares, at any depth (the keys of
    any `properties` / `$defs` map). V3's 'no surviving contract spells this
    concept another way' arm needs a structural walk rather than a substring
    grep: `"class"` appears as the VALUE of a `"type"`-style keyword in these
    files, and a grep would report a hit that is not a key."""
    out: set[str] = set() if found is None else found
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("properties", "$defs") and isinstance(value, dict):
                out.update(value.keys())
            _schema_property_names(value, out)
    elif isinstance(node, list):
        for item in node:
            _schema_property_names(item, out)
    return out


def _ast_assign(path: Path, name: str) -> Any:
    """literal_eval the module-level assignment of `name` (Assign or
    AnnAssign) — raises AssertionError if the symbol vanished (renames
    must redden here, not silently in a fake)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found as a module-level literal in {path}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fake_app():
    from backend.ai_contract.fake import create_fake_app

    return create_fake_app()


@pytest.fixture(scope="module")
def fake_registered():
    """Register the fake in-test (the WP8.2 registration mechanism); the
    matrix guard needs it present regardless of pytest-randomly order."""
    from backend.ai_contract.fake import fake_provider_ops
    from backend.ai_contract.provider import (
        ProviderId,
        register_provider,
        registered_providers,
    )

    if "fake" not in registered_providers():
        register_provider(ProviderId.FAKE, fake_provider_ops(), OPERATIONS, deployed=True)
    return registered_providers()["fake"]


@pytest.fixture
async def fake_client(fake_app):
    transport = ASGITransport(app=fake_app)
    async with AsyncClient(transport=transport, base_url="http://fake") as client:
        yield client


@asynccontextmanager
async def _patched_gateway_client(app):
    """One AsyncMock shared by EVERY derived patch target, over a given app.

    Patching one adapter's `get_triton_client` while another mounted adapter
    still holds the real name is the failure this shape exists to prevent:
    the other adapter would dial real gRPC and the suite would hang rather
    than fail. The target list is derived from the mount list, so the two can
    never disagree about how many adapters are in play."""
    mock = AsyncMock()
    mock.infer = AsyncMock()
    mock.is_model_ready = AsyncMock(return_value=True)
    mock.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output0"}]})
    targets = _gateway_patch_targets()
    assert len(targets) == len(_gateway_mounts()) >= 2, targets
    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, return_value=mock))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gw") as client:
            yield client, mock


@pytest.fixture(scope="module")
def gateway_app():
    """The surviving adapter routers with their production prefixes on one
    FastAPI app, derived from ai/gateway/main.py (see `_gateway_mounts`).
    Importing the adapters costs a few tenths of a second and is done lazily
    inside the builder so collection stays cheap."""
    from fastapi import FastAPI

    app = FastAPI(title="WP8.3 vocabulary conformance gateway app")
    for module, attr, prefix in _gateway_mounts():
        app.include_router(getattr(importlib.import_module(module), attr), prefix=prefix)
    return app


@pytest.fixture
async def gateway_client(gateway_app):
    """(client, mock_triton) — the full surviving gateway surface."""
    async with _patched_gateway_client(gateway_app) as pair:
        yield pair


# ---------------------------------------------------------------------------
# Drive helpers
# ---------------------------------------------------------------------------


def _request_kwargs(op_id: str) -> dict[str, Any]:
    """Same convention as test_fake_provider.py._request_kwargs: GET ops
    send nothing; committed golden payloads where they exist; multipart
    for uploads; neutral JSON otherwise."""
    example = (
        REPO_ROOT
        / "backend/tests/contracts/ai_providers/golden/payloads"
        / f"{op_id}.request.example.json"
    )
    if OPERATIONS[op_id].method == "GET":
        return {}
    if example.exists():
        payload = json.loads(example.read_text(encoding="utf-8"))
        if op_id == "yolo26_detect_batch":
            return {"files": [("files", ("f0.jpg", b"fake-image", "image/jpeg"))]}
        if isinstance(payload, str):
            return {"files": [("file", ("f.jpg", payload.encode(), "image/jpeg"))]}
        if payload == {}:
            return {}
        return {"json": payload}
    return {"json": {"image_base64": "ZmFrZS1pbWFnZQ=="}}


def _make_test_image(width: int = 640, height: int = 480) -> bytes:
    """Real decodable JPEG so the yolo adapter gets past Image.open
    (adapters/yolo26.py:351); shape copied from
    ai/gateway/tests/test_adapters_yolo26.py:35-41."""
    import io

    from PIL import Image  # adapter's own dependency (adapters/yolo26.py:26)

    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_yolo_output(
    detections: list[dict],
    num_classes: int = 80,
    num_preds: int = 8400,
) -> Any:
    """Synthetic (1, num_classes+4, num_preds) pre-NMS output tensor — copied
    from the working template ai/gateway/tests/test_adapters_yolo26.py:44-67."""
    import numpy as np

    output = np.zeros((1, num_classes + 4, num_preds), dtype=np.float32)
    for i, det in enumerate(detections):
        if i >= num_preds:
            break
        output[0, 0, i] = det["cx"]
        output[0, 1, i] = det["cy"]
        output[0, 2, i] = det["w"]
        output[0, 3, i] = det["h"]
        output[0, 4 + det["class_id"], i] = det["confidence"]
    return output


async def _drive_gateway_detect(client, mock, class_ids_and_confs: list[tuple[int, float]]):
    """POST /yolo26/detect (multipart upload, adapters/yolo26.py:332-333)
    with a mocked Triton output. 640x480 frame keeps letterbox math
    trivial (scale 1.0) so boxes survive the geometry guards."""
    dets = [
        {"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": cid, "confidence": conf}
        for cid, conf in class_ids_and_confs
    ]
    mock.infer.side_effect = None
    mock.infer.return_value = {"output0": _make_yolo_output(dets)}
    return await client.post(
        "/yolo26/detect", files={"file": ("test.jpg", _make_test_image(), "image/jpeg")}
    )


# ===========================================================================
# V1 — class vocabulary: 9 (native server) vs 80 (gateway adapter,
#      unfiltered), plus the orphaned third filter table (V1c).
# ===========================================================================


class TestV1ClassVocabulary:
    def test_V1a_security_classes_mirror_the_server_source(self) -> None:
        """V1a: ai/yolo26/model.py:151 defines exactly the 9 security
        classes, keyed off the COCO id->name map at :154 and applied by the
        ONE server-side filter at :1085 (re-measured this slice: model.py
        carries exactly two SECURITY_CLASSES lines — the definition and that
        single membership test — so the draft's "second path" note was
        already stale when written and is corrected here rather than
        inherited).
        Source: ai/yolo26/model.py:151,154,1085.
        Provider-agnostic AST pin (not drivable) — GREEN."""
        src_lines = (REPO_ROOT / "ai/yolo26/model.py").read_text(encoding="utf-8").splitlines()
        table = _ast_assign(REPO_ROOT / "ai/yolo26/model.py", "SECURITY_CLASSES")
        assert set(table) == WP83_SECURITY_CLASSES
        assert len(table) == 9
        # one definition + one filter site, and nothing else reaches for it
        cites = [ln for ln in src_lines if "SECURITY_CLASSES" in ln]
        assert len(cites) == 2, cites
        assert sum("not in SECURITY_CLASSES" in ln for ln in cites) == 1, cites

    async def test_V1a_fake_security_profile_expresses_the_nine(self, fake_client) -> None:
        """V1a via the fake: /fake/profiles/classes exposes both tables as
        DATA; X-Fake-Profile: security switches the yolo vocabulary to the
        filtered 9.
        Source: backend/ai_contract/fake/app.py (PROFILE_HEADER, _TABLE,
        /fake/profiles/classes). GREEN against fake; n/a for gateway (the
        gateway HAS no 9-class expression — that is the divergence)."""
        profiles = (await fake_client.get("/fake/profiles/classes")).json()
        assert set(profiles["security"]) == WP83_SECURITY_CLASSES

        r = await fake_client.post(
            "/yolo26/detect",
            headers={"X-Fake-Profile": "security"},
            **_request_kwargs("yolo26_detect"),
        )
        classes = {d["class"] for d in r.json()["detections"]}
        assert classes, "fake security profile must emit detections, not none"
        assert classes <= WP83_SECURITY_CLASSES

    def test_V1b_gateway_adapter_returns_all_eighty_unfiltered(self) -> None:
        """V1b: adapters/yolo26.py:42 COCO_CLASSES has 80 names (the 9
        security names are a strict subset), BOTH postprocess paths emit
        "class" (:201 post-NMS, :318 pre-NMS), and the file contains ZERO
        references to SECURITY/filtering — the adapter keeps everything
        above its flat 0.25 floor (:37). Tier A divergence, pinned at source.
        Source: ai/gateway/adapters/yolo26.py:37,42,186,201,311,318."""
        src = (REPO_ROOT / "ai/gateway/adapters/yolo26.py").read_text(encoding="utf-8")
        coco = _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "COCO_CLASSES")
        assert len(coco) == 80
        assert set(coco) > WP83_SECURITY_CLASSES  # strict superset: 71 extras
        assert "SECURITY" not in src
        assert (
            _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "CONFIDENCE_THRESHOLD") == 0.25
        )
        # the "class" spelling on both postprocess paths, derived from the
        # source rather than remembered: exactly the two dict keys of the two
        # detection builders, and no third naming.
        assert src.count('"class": cls_name') == 2
        assert '"label": ' not in src and '"class_name": ' not in src

    async def test_V1b_gateway_provider_streams_classes_outside_the_nine(
        self, gateway_client
    ) -> None:
        """V1b drivable: with the adapter's OWN postprocess running over a
        mocked Triton tensor, COCO class ids 24/26/28 (backpack, handbag,
        suitcase — ids per the adapter's :42 table) pass through
        unfiltered — a detection stream the native server would have dropped
        at model.py:1085. Retargeted by the mount-list derivation only: the
        drive and the claim are unchanged.
        Source: adapters/yolo26.py:186,201 (name + "class" key), :240
        (flat conf mask); COCO indices in the :42 table."""
        client, mock = gateway_client
        # COCO ids: 24 backpack, 26 handbag, 28 suitcase — the trio the
        # backend table pretends to gate (see V2c). 0.9 conf clears the
        # flat 0.25 floor.
        r = await _drive_gateway_detect(client, mock, [(24, 0.9), (26, 0.9), (28, 0.9)])
        assert r.status_code == 200, r.text[:300]
        classes = {d["class"] for d in r.json()["detections"]}
        assert classes == {"backpack", "handbag", "suitcase"}
        assert classes.isdisjoint(WP83_SECURITY_CLASSES)
        # and the same tensor would be dropped server-side: the guard the
        # gateway does NOT have is one membership test against the 9.
        assert classes & WP83_SECURITY_CLASSES == set()

    async def test_V1b_fake_gateway_profile_carries_the_eighty_names(self, fake_client) -> None:
        """V1b via the fake: the DEFAULT profile is gateway (the deployed
        provider is unfiltered — fake/app.py docstring); the gateway table
        has 80 names strictly containing the 9.
        Source: backend/ai_contract/fake/app.py (_TABLE, default
        profile="gateway"), generators.py (GATEWAY_CLASSES). GREEN vs fake."""
        profiles = (await fake_client.get("/fake/profiles/classes")).json()
        assert len(profiles["gateway"]) == 80
        assert set(profiles["gateway"]) > WP83_SECURITY_CLASSES
        r = await fake_client.post("/yolo26/detect", **_request_kwargs("yolo26_detect"))
        classes = {d["class"] for d in r.json()["detections"]}
        assert classes <= set(profiles["gateway"])

    def test_V1c_triton_client_filter_is_real_but_orphaned(self) -> None:
        """V1c characterization, RE-MEASURED after the S3 sweep: ai/triton/
        client.py:230 TritonClient.SECURITY_CLASSES is the same 9 with
        filters at :692/:752 — REAL but ORPHANED. The sweep is what makes
        this pin worth its keep: the heavy enrichment tier (the module's
        historical consumer) is gone, so the symbol is now load-bearing on
        nobody, and a future suite must not mistake it for the gateway's
        filter. The live gateway path (ai/gateway/triton_client.py) filters
        NOTHING — zero SECURITY references anywhere under ai/gateway.
        Source: ai/triton/client.py:230,692,752; ai/gateway/** (census, zero).
        GREEN (ai/triton import is numpy + stdlib only)."""
        from ai.triton import TritonClient

        assert set(TritonClient.SECURITY_CLASSES) == WP83_SECURITY_CLASSES
        # the filters are real code, not a dead constant: both membership
        # tests still read the ClassVar.
        client_src = (REPO_ROOT / "ai/triton/client.py").read_text(encoding="utf-8")
        assert client_src.count("in self.SECURITY_CLASSES") == 2, client_src.count(
            "in self.SECURITY_CLASSES"
        )

        # orphan proof: no PRODUCTION module outside ai/triton/ imports it.
        consumers = _production_ai_triton_consumers()
        assert consumers == [], f"ai.triton has unexpected consumers: {consumers}"

        # Non-vacuity (doctrine 3, stated in the test that needs it): the
        # census can actually FIND an importer — otherwise "no consumers" is
        # a claim about a scan that scanned nothing. ai/triton/__init__.py is
        # a real importer of the same import form, excluded from the census
        # ONLY by the self-module rule, so feeding the census's own predicate
        # over that file must hit.
        own_site = REPO_ROOT / "ai/triton/__init__.py"
        assert _ORPHAN_NEEDLE in own_site.read_text(encoding="utf-8")
        assert _ORPHAN_IMPORT.search(own_site.read_text(encoding="utf-8"))

        # and the LIVE gateway path filters nothing
        gw_tree = REPO_ROOT / "ai/gateway"
        gw_files = [p for p in gw_tree.rglob("*.py") if "__pycache__" not in p.parts]
        assert gw_files, "the gateway tree vanished — this arm would pass vacuously"
        for path in gw_files:
            assert "SECURITY_CLASSES" not in path.read_text(encoding="utf-8", errors="replace"), (
                path
            )


# ===========================================================================
# V2 — two divergent per-class confidence tables in series.
# ===========================================================================


class TestV2ConfidenceTables:
    def test_V2a_server_table_values(self) -> None:
        """V2a: ai/yolo26/model.py:173 _DEFAULT_CLASS_CONFIDENCE_THRESHOLDS
        — person 0.45, car/truck/bus 0.70, motorcycle/bicycle 0.65,
        dog/cat/bird 0.55; env override YOLO26_CLASS_THRESHOLDS (:189-219);
        applied server-side at :1093 inside the single detect() path.
        Source: ai/yolo26/model.py:173,197,219,1093. Characterization of the
        server constants via AST read — drivable nowhere else without
        booting the server. GREEN."""
        table = _ast_assign(
            REPO_ROOT / "ai/yolo26/model.py", "_DEFAULT_CLASS_CONFIDENCE_THRESHOLDS"
        )
        assert table == WP83_SERVER_THRESHOLDS
        assert set(table) == WP83_SECURITY_CLASSES  # the table is exactly the 9
        # the env-override story the docstring claims is real plumbing, not
        # a comment: the default is copied then merged from the env var.
        src = (REPO_ROOT / "ai/yolo26/model.py").read_text(encoding="utf-8")
        assert "YOLO26_CLASS_THRESHOLDS" in src
        assert "dict(_DEFAULT_CLASS_CONFIDENCE_THRESHOLDS)" in src

    def test_V2b_backend_table_is_strictly_lower(self) -> None:
        """V2b: backend/core/config.py:1829 declared default — every one of
        the 9 shared values STRICTLY LOWER than the server table (so the two
        tables in series = the server gates everything on the native path);
        fallback 0.40 at :1816. Read from Settings.model_fields[...].default
        (declared default, env-proof). Consumption: detector_client.py:295
        (`self._class_thresholds = settings.detection_class_thresholds`) ->
        :1191-1193. GREEN (pure constants)."""
        backend_table = Settings.model_fields["detection_class_thresholds"].default
        assert backend_table == WP83_BACKEND_THRESHOLDS
        assert Settings.model_fields["detection_confidence_threshold"].default == 0.40
        for cls, server_v in WP83_SERVER_THRESHOLDS.items():
            assert backend_table[cls] < server_v, cls

    def test_V2c_dead_entries_never_fire_on_the_native_path(self) -> None:
        """V2c (native-path truth): the three extras {backpack, handbag,
        suitcase} are exactly the backend-table keys outside the 9, the
        server table has NO entry for them, and the server drops them at the
        SECURITY filter (model.py:1085) before the backend can see them — so
        under the shipped default (use_ai_gateway=False, config.py:1516) they
        can never fire. Dead-entry characterization, NOT a runtime guarantee.
        Source: config.py:1516,1829; model.py:151,173,1085. GREEN."""
        backend_table = Settings.model_fields["detection_class_thresholds"].default
        assert set(backend_table) - WP83_SECURITY_CLASSES == WP83_DEAD_ENTRIES
        assert not (set(WP83_SERVER_THRESHOLDS) & WP83_DEAD_ENTRIES)
        assert Settings.model_fields["use_ai_gateway"].default is False

    async def test_V2c_gateway_profile_reanimates_the_dead_entries(self, fake_client) -> None:
        """V2c divergence: with the gateway provider the trio becomes live —
        the gateway vocabulary (the deployed default profile) carries all
        three, and the backend table defines real thresholds for them, so a
        gateway provider emitting backpack@0.55 PASSES a gate the native path
        never lets reach the backend. Pinned via the fake's profile data (no
        import of the fake's consts, per WP8.2 precedent).
        Source: config.py:1829 (entries), adapters/yolo26.py:42 (names
        emitted), model.py:1085 (native drop that keeps them dead only on
        the server path). GREEN against fake."""
        profiles = (await fake_client.get("/fake/profiles/classes")).json()
        backend_table = Settings.model_fields["detection_class_thresholds"].default
        assert set(profiles["gateway"]) >= WP83_DEAD_ENTRIES
        assert all(cls in backend_table for cls in WP83_DEAD_ENTRIES)
        # server table has no say over them — the gate is backend-only
        # for these classes => gateway path: backend table becomes the
        # effective (lower) gate. Characterization of that consequence:
        assert all(backend_table[cls] < 0.70 for cls in WP83_DEAD_ENTRIES)
        # The effective gate the consumer computes for each of the three,
        # read out of the consumer's own expression (`_class_thresholds.get(
        # object_class, _confidence_threshold)` — detector_client.py:1191-
        # 1193 with the two fields at :295 / config.py:1816): because the
        # trio HAS table entries, the fallback 0.40 is NOT what gates them.
        fallback = Settings.model_fields["detection_confidence_threshold"].default
        for cls in sorted(WP83_DEAD_ENTRIES):
            effective = backend_table.get(cls, fallback)
            assert effective == backend_table[cls] != fallback, cls
        # 0.55 clears backpack's 0.50 gate but would never reach it: the
        # server dropped the class upstream. The sentence the trio pins.
        assert backend_table["backpack"] < 0.55

    def test_V2_gateway_adapter_has_no_per_class_table(self) -> None:
        """V2 shape fact: the gateway adapter has NO per-class table — a
        single flat floor CONFIDENCE_THRESHOLD = 0.25 (adapters/yolo26.py:37;
        default arg at :130; mask at :240) where the server path applies a
        9-entry table at model.py:1093. Same input -> different detection
        set per provider. Source: adapters/yolo26.py:37,130,240;
        model.py:173,1093. GREEN (AST/regex)."""
        src = (REPO_ROOT / "ai/gateway/adapters/yolo26.py").read_text(encoding="utf-8")
        assert "CLASS_CONFIDENCE" not in src  # no per-class table anywhere
        assert (
            _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "CONFIDENCE_THRESHOLD") == 0.25
        )
        # the flat floor is the ONLY threshold in the adapter (a per-class
        # dict smuggled in later would leave a second name behind).
        assert "THRESHOLD" in src  # the flat floor + NMS floor exist...
        assert _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "NMS_THRESHOLD") == 0.45
        assert "class_threshold" not in src  # ...and neither does the server's name


# ===========================================================================
# V3 — three names for one concept. At drafting the shipped surface spelled
#      the class name THREE ways depending on the provider: "class" (yolo,
#      both gateway paths and the fake), "label" (every Florence detection),
#      and "type" -> "class_name" (the enrichment threat dict, whose two
#      read sites even disagreed about precedence). V4/V5's consumer reads
#      ONE of them.
# ===========================================================================


def _deleted_registry_ops() -> frozenset[str]:
    """The WP7.3 deleted-op ratchet, read out of the SIBLING suite's literal
    by AST (test_ai_contract_registry.py owns it; importing a test module to
    reach a constant is the cross-test coupling this tier avoids, and a
    hand-copy would drift). A missing literal raises rather than returns
    empty: 'adopted by the ratchet' has to be able to fail loudly."""
    src = (
        REPO_ROOT / "backend/tests/contracts/ai_providers/test_ai_contract_registry.py"
    ).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        names: list[str] = []
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        if "DELETED_REGISTRY_OPS" not in names or node.value is None:
            continue
        (arg,) = node.value.args
        return frozenset(ast.literal_eval(elt) for elt in arg.elts)
    raise AssertionError("DELETED_REGISTRY_OPS literal not found in the registry suite")


class TestV3ThreeNames:
    async def test_V3_yolo_wire_key_is_class_on_both_providers(
        self, fake_client, gateway_client
    ) -> None:
        """V3 yolo side, LIVE: every yolo-family detection item keys its class
        name as "class" and NEVER "label"/"type". Survives the sweep
        unchanged because yolo survives — only the gateway app it drives is
        now derived rather than hand-mounted.
        Sources: adapters/yolo26.py:201,:318 (gateway, both postprocess
        paths); fake generators.py:378-383 (_yolo_detection -> "class");
        fake drives yolo26_detect + yolo26_segment; gateway drive yolo26_detect.
        GREEN against fake AND gateway (both emit "class")."""
        for op in _detections_keyed_ops():
            r = await fake_client.request(
                OPERATIONS[op].method, OPERATIONS[op].path, **_request_kwargs(op)
            )
            assert r.status_code == 200, f"{op}: {r.status_code}"
            dets = r.json()[WP83_DETECTIONS_KEY]
            assert dets, f"{op}: the fake emitted no detections — this arm would pass vacuously"
            for d in dets:
                assert WP83_WIRE_KEY in d, f"{op} item missing 'class': {sorted(d)}"
                assert "label" not in d and "type" not in d, (
                    f"{op} item carries a foreign key: {sorted(d)}"
                )

        client, mock = gateway_client
        rg = await _drive_gateway_detect(client, mock, [(0, 0.9)])
        assert rg.status_code == 200, rg.text[:300]
        assert rg.json()[WP83_DETECTIONS_KEY], "gateway drive produced no detections"
        for d in rg.json()[WP83_DETECTIONS_KEY]:
            assert set(d) == {WP83_WIRE_KEY, "confidence", "bbox"}

    async def test_V3_light_lane_uses_the_same_class_spelling(self, gateway_client) -> None:
        """V3's third lane, RETARGETED (R8 S3). The heavy enrichment tier's
        threat dict used to be the divergent spelling ("type" read into
        "class_name"); it is gone, and the surviving threat responder is the
        light adapter — which keys the same concept "class" like yolo does.
        Pinned from the adapter's OWN name table (read out of its source, not
        remembered) over a driven tensor, so a rename of THREAT_CLASSES or of
        the dict key reddens here.
        Source: ai/gateway/adapters/enrichment_light.py:84 (table), :111
        ("class": cls_name), route :130 (model_name="threat").
        GREEN against gateway (mocked Triton)."""
        import base64

        names = _threat_classes()
        assert len(names) >= 2, names  # the table has to be a table
        client, mock = gateway_client
        # one prediction per name: class id k scores highest on slot k, so
        # the adapter's argmax must land on THREAT_CLASSES[k].
        dets = [
            {"cx": 100, "cy": 100, "w": 40, "h": 40, "class_id": k, "confidence": 0.8}
            for k in range(len(names))
        ]
        mock.infer.side_effect = None
        mock.infer.return_value = {"output0": _make_yolo_output(dets, num_classes=len(names))}
        r = await client.post(
            OPERATIONS["enrich_lt_threat_detect"].path,
            json={"image": base64.b64encode(_make_test_image(200, 200)).decode()},
        )
        assert r.status_code == 200, r.text[:300]
        rows = r.json()["threats_detected"]
        assert len(rows) == len(names), rows  # every name in the table reached the wire
        emitted = [row[WP83_WIRE_KEY] for row in rows]
        assert sorted(emitted) == sorted(names), emitted
        for row in rows:
            assert set(row) == {WP83_WIRE_KEY, "confidence", "bbox"}
            assert "label" not in row and "type" not in row and "class_name" not in row
        # and the route really is the Triton `threat` model (a drive that
        # silently hit a different model would prove nothing about this lane).
        assert mock.infer.call_args.kwargs["model_name"] == "threat"

    def test_V3_per_provider_wire_key_spelling_is_now_one_spelling_TOMBSTONED(self) -> None:
        """TOMBSTONE (R8 S3, owner ruling 1 — the provider that carried the
        divergence retires whole).

        The hazard this test pinned, in full: ONE concept — "what object is
        this" — left the shipped surface under THREE different wire spellings
        depending on which provider answered, and the divergence was not
        cosmetic because the consumer picks up exactly one of them
        (detector_client.py:1286 `object_type=detection_data.get("class")`,
        written to a plain nullable String column):

          * yolo (gateway + fake) answered ``class``;
          * every Florence detection answered ``label`` (its committed
            schema's $defs.Detection required exactly ["label","bbox"] and
            did not define ``class`` at all);
          * the heavy enrichment threat dict answered ``type`` at one read
            site and ``class_name`` at another (the precedence split,
            tombstoned below in this class by S2).

        So a client written against the CANONICAL name — the one the DB
        column is named for — was correct for one provider and silently wrong
        for the others: it stored NULL object_type for every Florence row and
        nothing validated it, because the column is nullable with no
        enum/CHECK. The pins that made that visible drove BOTH spellings
        through BOTH providers (fake schema-walked payloads and mounted
        adapters), which is why they cannot be re-pointed at one provider.

        It cannot retarget: there is no ``label`` responder left to drive.
        Florence's routes, adapter, client module, serving dir and Triton dir
        were swept by ruling 1, so the second spelling has no shipped home —
        and per the S2b grammar this dies as a tombstone, not a skip. The
        per-provider angle stays HERE; the fourth spelling (an x1/y1/x2/y2
        CORNERS dict on the request/backend-internal side) is recorded by
        test_conformance_geometry.py::TestG4FourthSpelling, which owns that
        shape-and-rarity claim and this file does not repeat it.

        What is asserted: the retired spellings' ops are absent from the
        contract and adopted by the ratchet; NO surviving committed response
        schema declares any of the three foreign name keys; and the
        vocabulary class this property belonged to is still doing real work
        (non-vacuity), because the ``class`` spelling above is the only one
        left and it is pinned on two providers."""
        # (a) the divergence's second responder is out of the contract...
        retired = ("florence_detect", "florence_detect_security_objects")
        for op_id in retired:
            assert op_id not in OPERATION_IDS, op_id
            assert op_id in _deleted_registry_ops(), f"{op_id} dropped from the ratchet"
        # ...and unimportable as an adapter (import failure, not text).
        for module in ("ai.gateway.adapters.florence", "backend.services.florence_client"):
            with pytest.raises(ModuleNotFoundError):
                importlib.import_module(module)

        # (b) no SURVIVING committed response schema declares a foreign name
        # key at ANY depth. Reads live forms only (the schema tree that
        # exists), so a tombstone sentence cannot satisfy it.
        foreign: dict[str, list[str]] = {}
        for op_id in sorted(OPERATIONS):
            path = SCHEMA_DIR / f"{op_id}.response.json"
            if not path.exists():
                continue
            names = _schema_property_names(json.loads(path.read_text(encoding="utf-8")))
            hits = sorted(names & {"label", "class", "class_name"})
            if hits:
                foreign[op_id] = hits
        assert foreign == {}, f"a surviving schema declares a detection-name key: {foreign}"

        # (c) NON-VACUITY: the scan in (b) can find things — the same walker
        # over a hand-built tree DOES return the three spellings, so an empty
        # result above means "none exist", not "none are looked for".
        probe = {
            "properties": {
                "label": {"type": "string"},
                "class": {"type": "string"},
                "class_name": {"type": "string"},
            }
        }
        assert _schema_property_names(probe) == {"class", "class_name", "label"}

        # (d) NON-VACUITY: the class still has live work — the surviving
        # spellings this tombstone replaced are pinned drivably above, and
        # the detections-keyed set it feeds is non-empty.
        assert _detections_keyed_ops(), "the vocabulary class lost every member"
        assert WP83_WIRE_KEY == "class"  # the spelling the DB write reads

    def test_V3_enrichment_precedence_split_died_with_the_tier(self) -> None:
        """V3 enrichment side, TOMBSTONED by R8 S2 (2026-09-29).

        The characterization this test used to pin: the SAME file read the one
        concept with OPPOSITE precedence twice —
          backend/services/enrichment_pipeline.py:3961  type -> class_name
          backend/services/enrichment_pipeline.py:5220  class_name -> type
        (cites as re-keyed 2026-09-26 by the re-ID swap; dossier V3 first
        logged :3942/:5196). A threat dict carrying both keys resolved to
        DIFFERENT values on the two paths — a documented hazard with a parked
        RULING (plan §3.4), pinned by regex so line drift reddened here.

        The split was DELETED, not fixed: enrichment_pipeline.py went with the
        legacy enrichment tier and no shipped code reads a threat dict's
        type/class_name precedence anymore (verified: zero `threat_class`
        sites under backend/ outside tests). A pin against deleted text cannot
        retarget — there is no surviving text — so it dies HERE, with the
        hazard spelled out, instead of becoming a skip. If anyone re-grows a
        threat-dict precedence chain in shipped code, THIS docstring is the
        paragraph they must read first; the provider-side V3 pins in this
        class (wire key spellings differ per provider) carry the live half of
        the concept."""
        assert not (REPO_ROOT / "backend/services/enrichment_pipeline.py").exists()
        # Non-vacuity (doctrine 3, stated where it is needed): the surviving
        # threat lane is still drivable and still carries a class name — the
        # test above drives it — so this tombstone is not the last word on
        # threat vocabulary, only on the deleted precedence chain.
        assert len(_threat_classes()) == 4

    async def test_V3_threat_rows_carry_no_canonical_name_at_all(self, fake_client) -> None:
        """V3 consequence, drivable: the fake's threat rows
        (enrich_lt_threat_detect) carry NO class/label/type key — the
        schema is additionalProperties-free-form objects
        (enrich_lt_threat_detect.response.json threats_detected
        items = bare object). A provider MAY put any of the three names
        there; today the conformance surface cannot say. Characterization
        of the hole (parked), pinned against the fake's shape. The gateway's
        REAL rows for the same op do carry "class" (pinned by the light-lane
        test above), so the hole is specifically that the CONTRACT cannot
        express it.
        Source: schema + fake generator (alpha/bravo payload). GREEN vs fake."""
        op = "enrich_lt_threat_detect"
        r = await fake_client.request(
            OPERATIONS[op].method, OPERATIONS[op].path, **_request_kwargs(op)
        )
        threats = r.json()["threats_detected"]
        assert threats
        for t in threats:
            assert not (set(t) & {"class", "label", "type"}), sorted(t)


# ===========================================================================
# V4 — "detections" must be PRESENT and a LIST. The plan's :1419 cite is
#      WRONG (dossier cite_ok=false); the real routing was grepped directly:
#        detector_client.py:1153  `if "detections" not in result:`  (KEY ONLY)
#        detector_client.py:1158  -> record_pipeline_error("malformed_response")
#        inside async def detect_objects (starts :993)
#      The check tests presence ONLY — no isinstance(list) guard exists; and
#      the gateway's failure shapes answer HTTP 503 (adapters/yolo26.py:381-
#      383) before any key check, so they trip *_server_error instead
#      (detector_client.py:806, measured end-to-end below).
# ===========================================================================


class TestV4DetectionsKey:
    @pytest.mark.parametrize("profile", ["gateway", "security"])
    @pytest.mark.parametrize("op_id", _detections_keyed_ops())
    async def test_V4_detections_present_and_list_from_fake(
        self, fake_client, op_id: str, profile: str
    ) -> None:
        """V4 present+list on the fake, both profiles, every
        detections-keyed op. Membership is DERIVED from the committed
        schemas (`_detections_keyed_ops`, see its note) — the hand list this
        replaces named two Florence ops that R8 S3 took out of the contract,
        and a literal like that rots silently instead of failing. Batch is
        excluded BY THE RULE (per-item detections; the consumer reads the top
        level only), not by a hand-edit.
        Source: detector_client.py:1153-1158 (the consumer property); fake
        generators.py:386-394. GREEN against fake."""
        op = OPERATIONS[op_id]
        r = await fake_client.request(
            op.method,
            op.path,
            headers={"X-Fake-Profile": profile},
            **_request_kwargs(op_id),
        )
        assert r.status_code == 200, f"{op_id}: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert WP83_DETECTIONS_KEY in body, f"{op_id}/{profile} omitted the key"
        assert isinstance(body[WP83_DETECTIONS_KEY], list), f"{op_id}/{profile}: not a list"

    async def test_V4_detections_present_and_list_from_gateway(self, gateway_client) -> None:
        """V4 present+list on the gateway, drivable subset. RETARGETED, not
        trimmed: the draft drove yolo26_detect plus the two Florence routes;
        Florence is gone, so the same property now runs over EVERY
        detections-keyed gateway route that a mocked Triton can drive — both
        yolo SINGLE-image routes (detect, segment). The claim is unchanged:
        a success ALWAYS carries the key as a list (adapters/yolo26.py:375
        and :500), which is the same key the consumer requires.
        Source: adapters/yolo26.py:332,375,447,500. GREEN against gateway
        under mocks — the whole point of mounting adapters over a mocked
        Triton.

        The drive set is DERIVED twice over and never hand-listed: the ops
        whose committed contract carries the key (`_detections_keyed_ops`)
        intersected with the gateway availability column, then driven at
        their REGISTRY PATHS. Adding a detections-bearing gateway route
        therefore adds a drive automatically; dropping one shrinks the set
        instead of leaving a green drive against a path nobody serves.
        Non-vacuity is the last line: the set must be non-empty AND the
        drives must have returned real detections (a route that answered
        200 with `detections: []` on every input would satisfy "key present
        and is a list" forever)."""
        client, mock = gateway_client
        served = [
            op_id for op_id in _detections_keyed_ops() if _provider_vocab_column(op_id, "gateway")
        ]
        assert served, "the gateway slot serves no detections-keyed op — arm is vacuous"
        drove_nonempty = 0
        for op_id in served:
            op = OPERATIONS[op_id]
            mock.infer.side_effect = None
            mock.infer.return_value = {
                "output0": _make_yolo_output(
                    [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 0, "confidence": 0.9}]
                )
            }
            r = await client.post(
                op.path, files={"file": ("t.jpg", _make_test_image(), "image/jpeg")}
            )
            assert r.status_code == 200, f"{op.path}: {r.status_code} {r.text[:300]}"
            body = r.json()
            assert WP83_DETECTIONS_KEY in body, f"{op.path} omitted the key"
            assert isinstance(body[WP83_DETECTIONS_KEY], list), op.path
            # the same four keys the committed x-deployed-keys declare — a
            # BARE-DICT route's snapshot cannot catch a key rename, so the
            # drive states the envelope.
            declared = json.loads(
                (SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8")
            )["x-deployed-keys"]
            assert sorted(body) == sorted(declared), (op.path, sorted(body), sorted(declared))
            if body[WP83_DETECTIONS_KEY]:
                drove_nonempty += 1
        assert drove_nonempty == len(served), [OPERATIONS[o].path for o in served]

    async def test_V4_gateway_triton_failure_answers_503_not_absent_key(
        self, gateway_client
    ) -> None:
        """V4 failure-shape divergence, RETARGETED onto the pair the shipped
        code actually forms (measured this slice, not assumed).

        Under a Triton failure the two yolo SINGLE-image routes answer
        HTTPException 503 (adapters/yolo26.py:381-383 detect, :506-508
        segment) — they never produce a 200-without-"detections" body. The
        BATCH route, hit with the SAME failing Triton, answers 200 and
        isolates the failure per item ({detections: [], error: str(e)},
        adapters/yolo26.py:429-436). So "a provider failure looks like X" is
        false as stated; the failure's SHAPE depends on which route was
        asked. Pinning both halves in one test is the point: a change to
        either side (batch started raising 503, or detect started returning
        200-with-error-key) reddens here, and a suite that only knew one of
        them would train the wrong failure route.
        Source: adapters/yolo26.py:381-383,429-436,506-508. GREEN (mock infer
        raises TritonClientError)."""
        from ai.gateway.adapters.yolo26 import TritonClientError

        client, mock = gateway_client
        frame = ("test.jpg", _make_test_image(), "image/jpeg")
        mock.infer.side_effect = TritonClientError("triton down")
        for path in ("/yolo26/detect", "/yolo26/segment"):
            r = await client.post(path, files={"file": frame})
            assert r.status_code == 503, f"{path}: {r.status_code} {r.text[:300]}"
            # the 503 body is FastAPI's {"detail": ...} — it carries NO
            # "detections" key, which is exactly why the consumer's presence
            # check is not what catches this failure.
            assert WP83_DETECTIONS_KEY not in r.json(), path
            assert "triton down" in r.json()["detail"], r.text[:200]

        # same failing Triton, the batch route: 200, per-item error, every
        # item still key-shaped.
        r = await client.post(
            "/yolo26/detect/batch",
            files=[("files", ("f0.jpg", _make_test_image(), "image/jpeg"))],
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert WP83_DETECTIONS_KEY not in body  # top level never had it
        assert body["batch_size"] == 1 and len(body["results"]) == 1
        item = body["results"][0]
        assert item["error"] and item[WP83_DETECTIONS_KEY] == [], item
        mock.infer.side_effect = None

    async def test_V4_gateway_503_routes_the_consumer_to_server_error_not_malformed(
        self, gateway_client
    ) -> None:
        """V4's consequence arm, driven END TO END (this slice): the gateway
        503 above, consumed by the real DetectorClient. The naive rule
        "any provider response without detections increments
        malformed_response" is FALSE for gateway error shapes, and the
        evidence is now a drive rather than a grep: the client raises
        DetectorUnavailableError, records exactly one
        "{detector_type}_server_error", makes one HTTP attempt (max_retries=1)
        and records NO malformed_response. The presence check at
        detector_client.py:1153 is never reached, because raise_for_status
        (:672) fails first.
        Source: adapters/yolo26.py:381-383 -> detector_client.py:672,784-806,
        1153-1158. GREEN (gateway adapter + real consumer, no network)."""
        from ai.gateway.adapters.yolo26 import TritonClientError
        from backend.services import detector_client as dc_module
        from backend.services.detector_client import (
            DetectorClient,
            DetectorUnavailableError,
        )

        client, mock = gateway_client
        mock.infer.side_effect = TritonClientError("triton down")
        # The adapter answers 503 on real HTTP; hand the consumer that exact
        # status over its own httpx seam and let the retry/metric code run.
        r = await client.post(
            "/yolo26/detect", files={"file": ("t.jpg", _make_test_image(), "image/jpeg")}
        )
        assert r.status_code == 503  # the shape the consumer must react to
        mock.infer.side_effect = None

        import httpx

        with patch.object(dc_module, "record_pipeline_error", autospec=True) as malformed:
            consumer = DetectorClient(max_retries=1)
            assert consumer._detector_type == "yolo26", consumer._detector_type
            with patch.object(
                consumer, "_validate_image_for_detection_async", return_value=True, autospec=True
            ):
                session = AsyncMock()
                mock_service = MagicMock()
                mock_service.update_baseline = AsyncMock()
                response = MagicMock()
                response.status_code = r.status_code
                response.text = r.text
                response.json.return_value = r.json()
                response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "503", request=MagicMock(), response=response
                )
                with (
                    patch("pathlib.Path.exists", return_value=True, autospec=True),
                    patch("pathlib.Path.read_bytes", return_value=b"fake-image", autospec=True),
                    patch("httpx.AsyncClient.post", autospec=True) as mock_post,
                    patch.object(
                        dc_module, "get_baseline_service", return_value=mock_service, autospec=True
                    ),
                ):
                    mock_post.return_value = response
                    with pytest.raises(DetectorUnavailableError):
                        await consumer.detect_objects("fake-frame.jpg", "front_door", session)

                assert mock_post.call_count == 1
                recorded = [call.args[0] for call in malformed.call_args_list]
                assert "yolo26_server_error" in recorded, recorded
                assert WP83_MALFORMED_METRIC not in recorded, recorded

    async def test_V4_absent_key_routes_the_consumer_to_malformed_response(self) -> None:
        """V4 ABSENCE behavior, characterized against the REAL consumer
        path named by grep (plan's :1419 cite is the bbox-write region —
        FALSE): detector_client.detect_objects (:993) checks key presence at
        :1153 and records record_pipeline_error("malformed_response") at
        :1158, returning []. Driven through the same seam the unit tests use
        (patch httpx.AsyncClient.post + validate + baseline; precedent:
        backend/tests/unit/services/test_detector_client.py:143-171 — those
        tests do NOT cover this branch).
        Source: detector_client.py:1153-1158. GREEN (provider-agnostic
        consumer characterization)."""
        from backend.services import detector_client as dc_module
        from backend.services.detector_client import DetectorClient

        with patch.object(dc_module, "record_pipeline_error", autospec=True) as malformed:
            client = DetectorClient()
            with patch.object(
                client, "_validate_image_for_detection_async", return_value=True, autospec=True
            ):
                session = AsyncMock()
                session.add = MagicMock()
                mock_service = MagicMock()
                mock_service.update_baseline = AsyncMock()
                with (
                    patch("pathlib.Path.exists", return_value=True, autospec=True),
                    patch("pathlib.Path.read_bytes", return_value=b"fake-image", autospec=True),
                    patch("httpx.AsyncClient.post", autospec=True) as mock_post,
                    patch.object(
                        dc_module,
                        "get_baseline_service",
                        return_value=mock_service,
                        autospec=True,
                    ),
                ):
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {
                        "image_width": 640,
                        "image_height": 480,
                        "inference_time_ms": 10.0,
                    }  # NO "detections" key
                    mock_post.return_value = resp

                    detections = await client.detect_objects(
                        "fake-frame.jpg", "front_door", session
                    )

                assert detections == []
                assert mock_post.call_count == 1
                malformed.assert_called_once_with(WP83_MALFORMED_METRIC)

    async def test_V4_non_list_detections_bypasses_the_malformed_branch(self) -> None:
        """V4 list-ness, characterized: the consumer NEVER checks list type
        (dossier V4; no isinstance(result["detections"], list) in the file —
        re-grepped this slice, still zero hits, so the property stands after
        the sweep). Grep verdict for a NON-dict item in the list:
        `for detection_data in result["detections"]` (:1184) yields a str;
        .get raises AttributeError, which is NOT in the per-item except tuple
        (:1324 ValueError/TypeError/KeyError) nor in any outer except (:1399
        ValueError / CircuitBreakerError / DetectorUnavailableError / :1424
        OSError,RuntimeError) — so the CRASH ESCAPES detect_objects (the
        dossier's "dies silently" is over-stated for str items; verified by
        except-clause enumeration). NOTE the adjacent truth that keeps this a
        hazard, not just a crash: a dict item with missing keys is dropped
        silently (confidence defaults 0.0 at :1186 -> filtered at :1194 with
        NO malformed_response metric).
        Source: detector_client.py:1153,1184-1194,1324. GREEN: AttributeError
        propagates, malformed_response NEVER called."""
        from backend.services import detector_client as dc_module
        from backend.services.detector_client import DetectorClient

        # the absence the characterization rests on, asserted rather than
        # remembered. Scoped to detect_objects' own body (an isinstance on
        # the bbox shape at :1205 is real and unrelated), and scoped to the
        # detections value: the ONLY test applied to result["detections"] is
        # key presence — no list-ness check anywhere. A guard added later
        # reddens here before it silently changes the contract.
        consumer_src = (REPO_ROOT / "backend/services/detector_client.py").read_text(
            encoding="utf-8"
        )
        body = consumer_src.split("async def detect_objects", 1)[1]
        body = body.split("\n    def ", 1)[0].split("\n    async def ", 1)[0]
        detections_lines = [ln for ln in body.splitlines() if WP83_DETECTIONS_KEY in ln]
        assert detections_lines, "the consumer stopped naming the key at all"
        assert not [ln for ln in detections_lines if "isinstance(" in ln], detections_lines
        assert sum(f'"{WP83_DETECTIONS_KEY}" not in' in ln for ln in detections_lines) == 1, (
            detections_lines
        )

        with patch.object(dc_module, "record_pipeline_error", autospec=True) as malformed:
            client = DetectorClient()
            with patch.object(
                client, "_validate_image_for_detection_async", return_value=True, autospec=True
            ):
                session = AsyncMock()
                session.add = MagicMock()
                mock_service = MagicMock()
                mock_service.update_baseline = AsyncMock()
                with (
                    patch("pathlib.Path.exists", return_value=True, autospec=True),
                    patch("pathlib.Path.read_bytes", return_value=b"fake-image", autospec=True),
                    patch("httpx.AsyncClient.post", autospec=True) as mock_post,
                    patch.object(
                        dc_module,
                        "get_baseline_service",
                        return_value=mock_service,
                        autospec=True,
                    ),
                ):
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {WP83_DETECTIONS_KEY: ["not-a-dict"]}
                    mock_post.return_value = resp

                    with pytest.raises(AttributeError):
                        await client.detect_objects("fake-frame.jpg", "front_door", session)

                assert WP83_MALFORMED_METRIC not in [c.args[0] for c in malformed.call_args_list]


# ===========================================================================
# V5 — no class allowlist gates the DB write; the only allowlist
#      (KNOWN_OBJECT_CLASSES) is METRICS-ONLY.
# ===========================================================================


class TestV5DbWriteVocabulary:
    def test_V5_db_write_is_ungated_and_the_allowlist_is_metrics_only(self) -> None:
        """V5: the DB write takes the raw wire name — object_type=
        detection_data.get("class") (detector_client.py:1286) — and the
        column is plain String nullable (backend/models/detection.py:54),
        no enum/CHECK. KNOWN_OBJECT_CLASSES (core/sanitization.py:245)
        gates ONLY Prometheus labels (sanitize_object_class :445 ->
        metrics.py:1386,2242), mapping unknowns to "other" for METRICS.
        Quantified divergence, DERIVED (a strict, non-empty part of the
        stream — the size is computed, not remembered; it measured 16 of 80
        at drafting): the gateway's stream names the metrics allowlist does
        not know, incl. "traffic light" — the plan's "in KNOWN" example is
        FALSE; the list spells no traffic-light entry. Every one of them
        still stores verbatim.
        Sources: dossier V5 (traffic-light detail corrected by this
        draft's enumeration), sanitization.py:245,445; detection.py:54."""
        from backend.core.sanitization import KNOWN_OBJECT_CLASSES, sanitize_object_class
        from backend.models.detection import Detection

        col = Detection.__table__.columns["object_type"]
        assert col.nullable is True
        # `String` with no length and no Enum/CheckConstraint: an unbounded
        # text column, which is what "the wire name is stored as-is" means at
        # the schema level.
        assert type(col.type).__name__ == "String"
        assert getattr(col.type, "length", None) is None, col.type
        from sqlalchemy import Enum as SAEnum

        assert not isinstance(col.type, SAEnum)
        # the shape of "ungated", asserted structurally: the table's CHECK
        # constraints exist (media_type, confidence ranges) and NONE of them
        # mentions object_type — so no DB-level vocabulary gate.
        checks = sorted(
            c.name or ""
            for c in Detection.__table__.constraints
            if type(c).__name__ == "CheckConstraint"
        )
        assert checks, "the model lost all CHECK constraints — this arm is vacuous"
        assert not [c for c in checks if "object_type" in c], checks

        coco = _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "COCO_CLASSES")
        outside = {c for c in coco if c not in KNOWN_OBJECT_CLASSES}
        # DERIVED, not the remembered 16: the gap is a strict, non-empty
        # part of the stream (a stream fully covered by the allowlist would
        # mean the metrics demotion never happens and this pin is dead), and
        # every gapped name sanitizes to "other" while the write still takes
        # it — that is the divergence, stated as a pair.
        assert 0 < len(outside) < len(coco), (len(outside), len(coco))
        assert all(sanitize_object_class(c) == "other" for c in outside)
        assert "traffic light" in outside  # plan's example: FALSE membership
        assert sanitize_object_class("class_81") == "other"
        assert sanitize_object_class("traffic light") == "other"
        assert sanitize_object_class("person") == "person"
        # the 9 the native server filters to ARE all allowlisted: the
        # metrics gap is exclusively about the gateway's unfiltered extras.
        assert set(KNOWN_OBJECT_CLASSES) >= WP83_SECURITY_CLASSES

    async def test_V5_gateway_synthetic_name_is_unreachable_through_the_real_tensor(
        self, gateway_client
    ) -> None:
        """V5, the yolo half, re-measured rather than inherited.

        The draft drove a num_classes=82 tensor to force the adapter's
        synthetic `class_{id}` fallback (adapters/yolo26.py:186 post-NMS,
        :311 pre-NMS) and pinned the name on the wire. That fallback is
        still in the code and still correct — but the drive was only ever
        possible because the MOCKED tensor had 86 rows. The shipped model
        answers (1, 84, 8400): 80 class slots, so argmax at :236 can never
        exceed 79 and the pre-NMS fallback is unreachable in production.
        This test pins BOTH halves of that, so the suite never claims a
        production path from a mock-shaped input:

          * with a shipped-shape tensor (84 rows) and a high class id, the
            adapter answers with the REAL COCO name, not a synthetic one;
          * the synthetic spelling only appears when the tensor lies about
            its width (86 rows) — the format survives as a code path,
            pinned, without pretending the server can produce it.

        Source: adapters/yolo26.py:186,236,311 + COCO_CLASSES (:42)."""
        client, mock = gateway_client

        # (1) shipped shape: 84 rows => id 79 is a real COCO name.
        mock.infer.return_value = {
            "output0": _make_yolo_output(
                [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 79, "confidence": 0.9}],
                num_classes=80,
            )
        }
        r = await client.post(
            "/yolo26/detect", files={"file": ("t.jpg", _make_test_image(), "image/jpeg")}
        )
        assert r.status_code == 200, r.text[:300]
        name = r.json()[WP83_DETECTIONS_KEY][0][WP83_WIRE_KEY]
        coco = _ast_assign(REPO_ROOT / "ai/gateway/adapters/yolo26.py", "COCO_CLASSES")
        assert name == coco[79], (name, coco[79])
        assert not name.startswith("class_"), name

        # (2) the tensor lies about its width: the fallback fires, and the
        #     name FORMAT is what survives (not a production claim).
        mock.infer.return_value = {
            "output0": _make_yolo_output(
                [{"cx": 320, "cy": 240, "w": 100, "h": 100, "class_id": 81, "confidence": 0.9}],
                num_classes=82,
            )
        }
        r = await client.post(
            "/yolo26/detect", files={"file": ("t.jpg", _make_test_image(), "image/jpeg")}
        )
        assert r.status_code == 200, r.text[:300]
        dets = r.json()[WP83_DETECTIONS_KEY]
        assert dets and dets[0][WP83_WIRE_KEY] == "class_81", dets
        # argmax over the real 80 slots can never reach 80+ — the numeric
        # reason the fallback is unreachable, restated as a bound.
        assert len(coco) == 80

    async def test_V5_reachable_synthetic_name_lands_on_the_light_lane(
        self, gateway_client
    ) -> None:
        """V5's drivable synthetic-name leg, RETARGETED (R8 S3). The
        `threat_{id}` fallback at adapters/enrichment_light.py:108 is the
        surviving one that a REALISTIC tensor can produce: the light
        adapter's postprocess runs over whatever width the `threat` model
        answers (docstring: (1, 8, 8400) => 4 class slots, table of 4), so
        an id >= 4 is an ordinary deployment divergence (a re-export with an
        extra class), not a mock artifact — unlike yolo's id>79 case pinned
        above. Name format, key spelling, and metrics treatment, all three:
        Source: adapters/enrichment_light.py:84,108,111. GREEN (mocked Triton).
        """
        import base64

        from backend.core.sanitization import KNOWN_OBJECT_CLASSES, sanitize_object_class

        names = _threat_classes()
        client, mock = gateway_client
        mock.infer.return_value = {
            "output0": _make_yolo_output(
                [
                    {
                        "cx": 100,
                        "cy": 100,
                        "w": 40,
                        "h": 40,
                        "class_id": len(names),  # first id the table cannot name
                        "confidence": 0.8,
                    }
                ],
                num_classes=len(names) + 1,
            )
        }
        r = await client.post(
            OPERATIONS["enrich_lt_threat_detect"].path,
            json={"image": base64.b64encode(_make_test_image(200, 200)).decode()},
        )
        assert r.status_code == 200, r.text[:300]
        rows = r.json()["threats_detected"]
        assert rows, r.text[:200]
        synthetic = rows[0][WP83_WIRE_KEY]
        assert synthetic == f"threat_{len(names)}", rows
        assert synthetic not in names
        assert synthetic not in KNOWN_OBJECT_CLASSES
        assert sanitize_object_class(synthetic) == "other"

    async def test_V5_synthetic_and_unknown_names_reach_the_column_verbatim(self) -> None:
        """V5 drivable, RETARGETED onto the live DB-write lane (R8 S3).

        The draft drove yolo's synthetic name and asserted it on the WIRE,
        one step short of the claim its own title makes ("reaches the wire
        verbatim" — the wire is not the point, the COLUMN is). The property
        is that NOTHING between the provider's name and the stored row
        consults an allowlist, so this drives the real consumer with three
        names of increasing weirdness and reads the objects it added to the
        session:

          * "class_81"  — a synthetic-shaped name (the format pinned above);
          * "traffic light" — a REAL gateway name the metrics allowlist
            rejects (the plan believed it was allowlisted);
          * a row with NO "class" key at all — the column takes NULL,
            because the write is `detection_data.get("class")` with no
            default and no gate.

        All three store, verbatim, while sanitize_object_class() has already
        demoted the first two to "other" for Prometheus. A swap that invents
        a name table therefore cannot silently change which names become DB
        rows — and cannot silently start rejecting them either.
        Source: detector_client.py:1286 (write), :1191-1193 (the only gate:
        a CONFIDENCE one), models/detection.py:54. GREEN."""
        from backend.core.sanitization import KNOWN_OBJECT_CLASSES, sanitize_object_class
        from backend.services import detector_client as dc_module
        from backend.services.detector_client import DetectorClient

        for name in ("class_81", "traffic light"):
            assert name not in KNOWN_OBJECT_CLASSES
            assert sanitize_object_class(name) == "other"

        with patch.object(dc_module, "record_pipeline_error", autospec=True) as malformed:
            client = DetectorClient()
            with patch.object(
                client, "_validate_image_for_detection_async", return_value=True, autospec=True
            ):
                session = AsyncMock()
                # sync on the ORM seams (add/flush are not coroutines) so no
                # "coroutine never awaited" warning leaks into the report.
                session.add = MagicMock()
                session.get = AsyncMock(return_value=None)  # skip the camera row
                mock_service = MagicMock()
                mock_service.update_baseline = AsyncMock()
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {
                    "image_width": 640,
                    "image_height": 480,
                    "inference_time_ms": 5.0,
                    WP83_DETECTIONS_KEY: [
                        {
                            WP83_WIRE_KEY: "class_81",
                            "confidence": 0.9,
                            "bbox": {"x": 10, "y": 10, "width": 50, "height": 50},
                        },
                        {
                            WP83_WIRE_KEY: "traffic light",
                            "confidence": 0.9,
                            "bbox": {"x": 20, "y": 20, "width": 40, "height": 40},
                        },
                        {  # no class key at all
                            "confidence": 0.9,
                            "bbox": {"x": 30, "y": 30, "width": 30, "height": 30},
                        },
                    ],
                }
                with (
                    patch("pathlib.Path.exists", return_value=True, autospec=True),
                    patch("pathlib.Path.read_bytes", return_value=b"fake-image", autospec=True),
                    patch("httpx.AsyncClient.post", autospec=True) as mock_post,
                    patch.object(
                        dc_module, "get_baseline_service", return_value=mock_service, autospec=True
                    ),
                ):
                    mock_post.return_value = resp
                    stored = await client.detect_objects("fake-frame.jpg", "front_door", session)

        # Non-vacuity: three rows in, three rows out — an empty result would
        # make "nothing is filtered" trivially true.
        assert len(stored) == 3, [d.object_type for d in stored]
        assert [d.object_type for d in stored] == ["class_81", "traffic light", None]
        assert [d.confidence for d in stored] == [0.9, 0.9, 0.9]
        # the metric the allowlist WOULD have driven is not recorded: the
        # write path has one gate, and it is a confidence gate.
        recorded = [c.args[0] for c in malformed.call_args_list]
        assert recorded == [], recorded


# ===========================================================================
# Matrix guard (harness driving-shape): vocabulary operations must be
# claimed exactly as the availability matrix declares, per provider.
# per_model_http + llamacpp_llm are GUARD-ONLY here — their registered
# callables hit real network; never invoked. Absent-op 404 checks belong
# to the app-driven suites (green guards), and the fake is app-driven in
# this module — the fake leg below additionally proves per-op drivability
# for every vocabulary op it declares.
# ===========================================================================


class TestVocabularyProviderColumn:
    @pytest.mark.parametrize(
        "provider_id",
        [
            "gateway",
            "gateway_light",
            "per_model_http",
            "llamacpp_llm",
            "openai_vlm",
            "rtvi_vlm",
            "fake",
        ],
    )
    async def test_V1_V4_vocabulary_ops_match_the_availability_column(
        self, provider_id: str, fake_registered, fake_client
    ) -> None:
        """For every vocabulary (detections-bearing) op — DERIVED, see
        `_detections_keyed_ops` — and every provider: claimed in
        provider.operations() <=> the matrix column says available. With the
        UNION-slot subset providers (llamacpp_llm, and the 1.1 VLM engines
        openai_vlm/rtvi_vlm — SUBSET_REQUIRED mirrored from
        test_conformance_ops) the documented exception: each declares ONLY
        its required subset, so it claims NO vocabulary op; per_model_http
        additionally pinned UNDEPLOYED.

        R8 S3 note: the vocabulary set this loops over is now derived, so
        the seven legs below cannot be driven against a retired op — which
        is the exact failure this file had (KeyError on a Florence id inside
        a hand-written tuple).
        Sources: backend/ai_contract/provider.py (PROVIDER_SLOT),
        operations.py availability matrix; providers.py _register_all
        (per_model_http deployed=False, subset providers required=subset)."""
        from backend.ai_contract.provider import PROVIDER_SLOT, registered_providers

        # The fixture's VALUE is asserted, not just its registration
        # side-effect: vulture (main-only Dead Code Detection, red on main
        # run 35476647132) flags a fixture param never named in the body at
        # 100% confidence; this guard is the true statement of why we
        # request it — the fake's registration record must exist.
        assert fake_registered is not None
        rec = registered_providers()[provider_id]
        slot = PROVIDER_SLOT[rec.provider_id]
        declared = set(rec.operations())

        vocabulary = _detections_keyed_ops()
        assert vocabulary, "derived vocabulary set is empty — every arm below is vacuous"

        if provider_id == "llamacpp_llm":
            assert declared == {"llm_completion", "llm_chat_completion"}
        elif provider_id in ("openai_vlm", "rtvi_vlm"):
            # union-slot exception, 1.1 shape: each VLM engine declares ONLY
            # required={"vlm_assess"} inside the per_model_server union.
            assert declared == {"vlm_assess"}
        for op_id in vocabulary:
            available = _provider_vocab_column(op_id, slot)
            if provider_id in ("llamacpp_llm", "openai_vlm", "rtvi_vlm"):
                # union-slot exception this test's docstring states: a subset
                # provider declares ONLY its required subset, so it claims NO
                # vocabulary op even where the per_model_server column (its
                # slot) is available. Discovery fix: the equality loop failed
                # on yolo26_detect (declared False vs column True).
                assert op_id not in declared, f"{provider_id}/{op_id}"
            else:
                assert (op_id in declared) == available, (
                    f"{provider_id}/{op_id}: declaration {op_id in declared} "
                    f"vs column {available} — vocabulary surface drifted from the matrix"
                )
            if provider_id == "fake" and available:
                r = await fake_client.request(
                    OPERATIONS[op_id].method, OPERATIONS[op_id].path, **_request_kwargs(op_id)
                )
                assert r.status_code == 200
                assert isinstance(r.json()[WP83_DETECTIONS_KEY], list)

        if provider_id == "per_model_http":
            assert rec.deployed is False
        if provider_id == "llamacpp_llm":
            assert declared == {"llm_completion", "llm_chat_completion"}
