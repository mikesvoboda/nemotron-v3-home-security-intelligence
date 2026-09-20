"""Tests for scripts/check-ai-provider-parity.py (WP9.1).

The gate: cross-provider AI parity, measured statically (AST-only) across the
gateway adapters, the native model servers and the six backend caller
modules, gated against the WP7.3 availability matrix. Doctrine this suite
pins:

  * ABSENCE is never a violation — a surface NOT serving an op the matrix
    marks False is exactly what was declared (D4's gateway:True
    per_model_server:False split stays green, informational).
  * PRESENCE that contradicts the matrix, caller URLs that resolve (as
    deployed) to a surface where nothing serves them, provider key/shape/
    guard drift, and phantom paths ARE violations — even when every
    individual module looks fine in isolation (the Tier-A lesson: no
    single-module test could ever have caught D1-D6).
  * the synthetic "provider renames a key" RED case (plan WP9.1 bullet 2)
    is exercised on fixtures, so a future provider drift fails loud here.
  * against the REAL tree the checker must reproduce the adjudicated
    Tier-A list D1-D6 EXACTLY (WP8.4 dossier ground truth): this is the
    WP9.1 MEASURE. The id set is pinned by equality — a NEW divergence
    fails CI until adjudicated into the golden list; a VANISHING one fails
    as GOLDEN-LOST so fixes re-ratchet instead of rotting the baseline.

Fixture families use REAL family names (clip/...) on purpose: the checker's
family routing is keyed by the same NATIVE_FAMILY_PREFIX map the real tree
exercises, so a synthetic family name would silently route nothing and test
nothing.

Conventions ride check-mock-spec/check-ratchet: subprocess-only (the gate
is never imported — it must survive trees it cannot import), --json report,
--expect golden file, exit 0/1/2.

Run: uv run pytest scripts/test_check_ai_provider_parity.py -q
CI wiring (landed): this file runs in the collection-sanity job's "Run the
anti-rot gates' own tests" list, and the gate itself runs there against the
real tree via --expect .github/ai-parity-baseline.json — WP1.3's ratchet
shape (see the CI stanza block in check-ai-provider-parity.py's docstring).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

GATE = Path(__file__).resolve().with_name("check-ai-provider-parity.py")
# Installed at scripts/, so parents[1] IS the repo root — in-tree and in CI
# checkout alike. The /tmp draft carried a machine-specific fallback path and
# a pytest.skip when neither candidate resolved; both removed at integration
# (goal rule: no skip anywhere — a root that does not carry the registry is a
# broken checkout and must FAIL loud, not silently skip six real-tree legs).
REAL_ROOT = Path(__file__).resolve().parent.parent
assert (REAL_ROOT / "backend/ai_contract/operations.py").is_file(), (
    f"scripts/test_check_ai_provider_parity.py sits outside a repo root: {REAL_ROOT}"
)


def gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args], capture_output=True, text=True, check=False
    )


def scan(root: Path) -> tuple[int, dict]:
    r = gate("--root", str(root), "--json")
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        report = {"stdout": r.stdout, "stderr": r.stderr}
    return r.returncode, report


def ids(report: dict) -> set[str]:
    return {d["id"] for d in report.get("divergences", [])}


def tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    return tmp_path


# ---------------------------------------------------------------------------
# the base fixture: one family (clip), two providers, one client, one matrix.
# GREEN by construction — every RED test is a one-line drift on top of it.
# ---------------------------------------------------------------------------

OPS = """
from typing import Any
OPERATIONS: dict[str, Any] = {
    "clip_do": Operation(
        id="clip_do",
        method="POST",
        path="/clip/do",
        availability={"gateway": True, "enrichment_light_adapter": False,
                      "per_model_server": True, "fake": True},
        client_methods=["ClipClient.do"],
        evidence="fixture",
    ),
    "clip_seg": Operation(
        id="clip_seg",
        method="POST",
        path="/clip/seg",
        availability={"gateway": True, "enrichment_light_adapter": False,
                      "per_model_server": False, "fake": True},
        client_methods=["ClipClient.seg"],
        evidence="fixture",
    ),
    "clip_batch": Operation(
        id="clip_batch",
        method="POST",
        path="/clip/batch",
        availability={"gateway": True, "enrichment_light_adapter": False,
                      "per_model_server": True, "fake": True},
        client_methods=[],
        evidence="fixture",
    ),
    "clip_flag": Operation(
        id="clip_flag",
        method="POST",
        path="/clip/flag",
        availability={"gateway": True, "enrichment_light_adapter": False,
                      "per_model_server": True, "fake": True},
        client_methods=[],
        evidence="fixture",
    ),
    "bare_status": Operation(
        id="bare_status",
        method="GET",
        path="/models/status",
        availability={"gateway": False, "enrichment_light_adapter": False,
                      "per_model_server": True, "fake": True},
        client_methods=["ClipClient.status"],
        evidence="fixture",
    ),
    "model_unload": Operation(
        id="model_unload",
        method="POST",
        path="/models/unload",
        availability={"gateway": False, "enrichment_light_adapter": False,
                      "per_model_server": True, "fake": True},
        client_methods=[],
        evidence="fixture",
    ),
}
"""

MAIN = """
from ai.gateway.adapters.clip import router as clip_router
app.include_router(clip_router, prefix="/clip")
"""

GW_ADAPTER = """
from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

router = APIRouter()

class DoRequest(BaseModel):
    image: str = Field(..., description="b64")

class DoResponse(BaseModel):
    label: str = Field(...)

class SegResponse(BaseModel):
    mask: str = Field(...)

MAX_BATCH_SIZE = 32

class BatchRequest(BaseModel):
    texts: list[str] = Field(...)

    @field_validator("texts")
    @classmethod
    def cap(cls, v):
        if len(v) > MAX_BATCH_SIZE:
            raise ValueError("too many")
        return v

class FlagRequest(BaseModel):
    image: str = Field(...)
    camera_type: str = Field(default="standard")

@router.post("/do", response_model=DoResponse)
async def do(request: DoRequest) -> DoResponse:
    return DoResponse(label="x")

@router.post("/seg", response_model=SegResponse)
async def seg(file: str) -> SegResponse:
    return SegResponse(mask="m")

@router.post("/batch")
async def batch(request: BatchRequest):
    return {"ok": True}

@router.post("/flag")
async def flag(request: FlagRequest):
    return {"ok": request.camera_type}

@router.get("/health")
async def health():
    return {"ok": True}
"""

NATIVE_MODEL = """
from fastapi import FastAPI
from enum import Enum
from pydantic import BaseModel, Field, field_validator

app = FastAPI()

class DoRequest(BaseModel):
    image: str = Field(..., description="b64")

class DoResponse(BaseModel):
    label: str = Field(...)

MAX_BATCH_SIZE = 32

class BatchRequest(BaseModel):
    texts: list[str] = Field(...)

    @field_validator("texts")
    @classmethod
    def cap(cls, v):
        if len(v) > MAX_BATCH_SIZE:
            raise ValueError("too many")
        return v

class CameraType(str, Enum):
    STANDARD = "standard"

class FlagRequest(BaseModel):
    image: str = Field(...)
    camera_type: CameraType = Field(default=CameraType.STANDARD)

@app.post("/do", response_model=DoResponse)
async def do(request: DoRequest) -> DoResponse:
    return DoResponse(label="x")

@app.post("/batch")
async def batch(request: BatchRequest):
    return {"ok": True}

@app.post("/flag")
async def flag(request: FlagRequest):
    return {"ok": request.camera_type.value}

@app.get("/health")
async def health():
    return {"ok": True}
"""

CLIENT = """
class ClipClient:
    def __init__(self, settings):
        gw = getattr(settings, "ai_gateway_url", None)
        self._use_gw = getattr(settings, "use_ai_gateway", False) is True and isinstance(gw, str)
        if self._use_gw:
            self._base_url = f"{gw.rstrip('/')}/clip"
        else:
            self._base_url = settings.clip_url.rstrip("/")
        self._status_url = settings.clip_url.rstrip("/") + "/models/status"
        self._http_client = None

    def do(self, image):
        payload = {"image": image}
        response = self._http_client.post(f"{self._base_url}/do", json=payload)
        return response.json()

    def seg(self, image):
        response = self._http_client.post(f"{self._base_url}/seg", files={"file": image})
        return response.json()

    def status(self):
        response = self._http_client.get(self._status_url)
        return response.json()
"""


def clean_tree(tmp_path: Path) -> Path:
    return tree(
        tmp_path,
        {
            "backend/ai_contract/operations.py": OPS,
            "ai/gateway/main.py": MAIN,
            "ai/gateway/adapters/clip.py": GW_ADAPTER,
            "ai/clip/model.py": NATIVE_MODEL,
            "backend/services/clip_client.py": CLIENT,
        },
    )


# ---------------------------------------------------------------------------
# green baseline: agreement + a DECLARED availability split (the D4 shape)
# --------------------------------------------------------------------------


def test_clean_tree_is_green(tmp_path):
    rc, report = scan(clean_tree(tmp_path))
    assert rc == 0, report.get("divergences")
    assert ids(report) == set()


def test_declared_split_is_informational(tmp_path):
    # clip_seg (gateway:True per_model_server:False, like yolo26_segment/D4)
    # and bare_status/model_unload show up under "declared", never "divergences"
    rc, report = scan(clean_tree(tmp_path))
    declared = {d["op"]: d for d in report["declared"]}
    assert "clip_seg" in declared
    assert declared["clip_seg"]["served_gateway"] and not declared["clip_seg"]["served_native"]
    assert rc == 0


def test_declared_absence_is_never_a_violation(tmp_path):
    # gateway does not serve bare_status (matrix gateway:False) and nothing
    # resolves there: exactly what the False slot declares -> green
    root = clean_tree(tmp_path)
    client = (
        (root / "backend/services/clip_client.py")
        .read_text()
        .replace(
            "    def status(self):\n        response = self._http_client.get(self._status_url)\n        return response.json()\n",
            "",
        )
    )
    (root / "backend/services/clip_client.py").write_text(client)
    rc, report = scan(root)
    assert rc == 0, ids(report)


# ---------------------------------------------------------------------------
# RED: "provider renames a key" (plan WP9.1 bullet 2) — both directions
# ---------------------------------------------------------------------------


def test_provider_renames_a_request_key_is_red(tmp_path):
    root = clean_tree(tmp_path)
    native = (
        (root / "ai/clip/model.py")
        .read_text()
        .replace(
            '    image: str = Field(..., description="b64")',
            '    image_src: str = Field(..., description="b64")',
        )
    )
    (root / "ai/clip/model.py").write_text(native)
    rc, report = scan(root)
    assert rc == 1
    assert "AI-PARITY-KEY-clip_do-image" in ids(report)
    detail = next(
        d["detail"] for d in report["divergences"] if d["id"] == "AI-PARITY-KEY-clip_do-image"
    )
    assert "ai/clip/model.py" in detail  # evidence points AT the renamed provider


def test_gateway_renamed_response_key_is_red(tmp_path):
    root = clean_tree(tmp_path)
    gw = (
        (root / "ai/gateway/adapters/clip.py")
        .read_text()
        .replace(
            "class DoResponse(BaseModel):\n    label: str = Field(...)",
            "class DoResponse(BaseModel):\n    label_v2: str = Field(...)",
        )
    )
    (root / "ai/gateway/adapters/clip.py").write_text(gw)
    rc, report = scan(root)
    assert rc == 1
    assert "AI-PARITY-KEY-clip_do-response" in ids(report)


# ---------------------------------------------------------------------------
# RED: value shape diverges for a shared key (D1's mechanism) — and the
# honest superset annotation stays green (rejection test, not equality test)
# ---------------------------------------------------------------------------


def _add_bbox(root: Path, gw_type: str, nat_type: str) -> None:
    gw = (root / "ai/gateway/adapters/clip.py").read_text()
    gw = gw.replace(
        'class DoRequest(BaseModel):\n    image: str = Field(..., description="b64")',
        f'class DoRequest(BaseModel):\n    image: str = Field(..., description="b64")\n    bbox: {gw_type} = Field(default=None)',
    )
    (root / "ai/gateway/adapters/clip.py").write_text(gw)
    nat = (root / "ai/clip/model.py").read_text()
    nat = nat.replace(
        'class DoRequest(BaseModel):\n    image: str = Field(..., description="b64")',
        f'class DoRequest(BaseModel):\n    image: str = Field(..., description="b64")\n    bbox: {nat_type} = Field(default=None)',
    )
    (root / "ai/clip/model.py").write_text(nat)


def test_shape_divergence_is_red(tmp_path):
    root = clean_tree(tmp_path)
    _add_bbox(root, "dict[str, float] | None", "list[float] | None")
    rc, report = scan(root)
    assert rc == 1
    assert "AI-PARITY-SHAPE-clip_do-bbox" in ids(report)


def test_gateway_accepting_superset_shape_is_green(tmp_path):
    # the light adapter's tolerance pattern: dict | list covers the native
    # list -> no finding. SHAPE is a REJECTION test, not literal equality.
    root = clean_tree(tmp_path)
    _add_bbox(root, "dict[str, float] | list[float] | None", "list[float] | None")
    rc, report = scan(root)
    assert rc == 0, ids(report)


# ---------------------------------------------------------------------------
# RED: native's constant-capped list guard dropped at the gateway (D6) —
# and literal-capped guards are invisible BY DESIGN
# ---------------------------------------------------------------------------


def _drop_gw_batch_guard(root: Path) -> None:
    gw = (root / "ai/gateway/adapters/clip.py").read_text()
    gw = gw.replace(
        """    @field_validator("texts")
    @classmethod
    def cap(cls, v):
        if len(v) > MAX_BATCH_SIZE:
            raise ValueError("too many")
        return v
""",
        "",
    )
    (root / "ai/gateway/adapters/clip.py").write_text(gw)


def test_native_guard_missing_at_gateway_is_red(tmp_path):
    root = clean_tree(tmp_path)
    _drop_gw_batch_guard(root)
    rc, report = scan(root)
    assert rc == 1
    assert "AI-PARITY-GUARD-clip_batch-texts" in ids(report)


def test_literal_capped_native_guard_is_invisible_by_design(tmp_path):
    # literal cap = constant rule any provider could re-implement statically;
    # only env/CONSTANT-capped guards (deployment-tunable) are GUARD-worthy
    root = clean_tree(tmp_path)
    _drop_gw_batch_guard(root)
    nat = (
        (root / "ai/clip/model.py")
        .read_text()
        .replace("if len(v) > MAX_BATCH_SIZE:", "if len(v) > 30:")
    )
    (root / "ai/clip/model.py").write_text(nat)
    rc, report = scan(root)
    assert "AI-PARITY-GUARD-clip_batch-texts" not in ids(report)
    assert rc == 0


# ---------------------------------------------------------------------------
# RED: widened-to-primitive flag the gateway never reads (D5's mechanism)
# ---------------------------------------------------------------------------


def test_widened_never_read_flag_is_red(tmp_path):
    root = clean_tree(tmp_path)
    gw = (
        (root / "ai/gateway/adapters/clip.py")
        .read_text()
        .replace(
            'async def flag(request: FlagRequest):\n    return {"ok": request.camera_type}',
            'async def flag(request: FlagRequest):\n    return {"ok": True}',
        )
    )
    (root / "ai/gateway/adapters/clip.py").write_text(gw)
    rc, report = scan(root)
    assert rc == 1
    assert "AI-PARITY-TYPE-UNUSED-clip_flag-camera_type" in ids(report)


def test_widened_but_actually_read_flag_is_green(tmp_path):
    # the base fixture IS this case: str at the gateway, handler reads it ->
    # declared behaviour, not a silent-semantics bug
    _, report = scan(clean_tree(tmp_path))
    assert "AI-PARITY-TYPE-UNUSED-clip_flag-camera_type" not in ids(report)


# ---------------------------------------------------------------------------
# RED: a surface SERVES what the matrix forbids (CLAIM-AVAILABILITY)
# ---------------------------------------------------------------------------


def test_native_serving_matrix_forbidden_op_is_red(tmp_path):
    root = clean_tree(tmp_path)
    # clip_seg declares per_model_server:False; if the native server grows
    # the route, the matrix must shrink (update) or CI fails
    nat = (
        (root / "ai/clip/model.py").read_text()
        + """
@app.post("/seg")
async def seg2(file: str):
    return {"mask": "m"}
"""
    )
    (root / "ai/clip/model.py").write_text(nat)
    rc, report = scan(root)
    assert rc == 1
    assert "AI-PARITY-CLAIM-AVAILABILITY-clip_seg" in ids(report)


# ---------------------------------------------------------------------------
# RED: caller URL claims — the D2 (gateway:False op, gateway-resolving URL)
# and D3 (phantom path) mechanisms, via BOTH D2 wiring paths
# ---------------------------------------------------------------------------

MODEL_MGMT_PHANTOM = """
ENRICH_URL = "http://ai-enrichment:8094"

def get_service_for_model(name):
    return ENRICH_URL

async def unload_model(http_client, model_name):
    service_url = get_service_for_model(model_name)
    response = await http_client.post(f"{service_url}/models/{model_name}/unload")
    return response
"""


def test_phantom_path_caller_is_red(tmp_path):
    # D3 mechanism: registry says POST /models/unload; the route module calls
    # /models/{model_name}/unload against a per-model host -> CLAIM-PATH
    root = clean_tree(tmp_path)
    tree(root, {"backend/api/routes/model_management.py": MODEL_MGMT_PHANTOM})
    rc, report = scan(root)
    assert rc == 1
    assert "AI-PARITY-CLAIM-PATH-model_unload" in ids(report)


def test_gateway_branch_calling_gateway_false_op_is_red(tmp_path):
    # D2 mechanism A (in-code): the use_ai_gateway branch builds
    # {gateway}/clip/models/status although bare_status declares gateway:False
    root = clean_tree(tmp_path)
    client = (
        (root / "backend/services/clip_client.py")
        .read_text()
        .replace(
            "        response = self._http_client.get(self._status_url)",
            '        response = self._http_client.get(f"{self._base_url}/models/status")',
        )
    )
    (root / "backend/services/clip_client.py").write_text(client)
    rc, report = scan(root)
    assert rc == 1
    assert "AI-PARITY-CLAIM-GW404-bare_status" in ids(report)


NO_GW_BRANCH = """        self._base_url = settings.clip_url.rstrip("/")"""

GW_BRANCH = """        gw = getattr(settings, "ai_gateway_url", None)
        self._use_gw = getattr(settings, "use_ai_gateway", False) is True and isinstance(gw, str)
        if self._use_gw:
            self._base_url = f"{gw.rstrip('/')}/clip"
        else:
            self._base_url = settings.clip_url.rstrip("/")"""

STATUS_VIA_BASE = '        response = self._http_client.get(f"{self._base_url}/models/status")'


def test_settings_base_without_compose_rewrite_is_green(tmp_path):
    # same call shape minus the gateway branch, and NO compose in the tree:
    # the settings URL may legitimately point at a native host -> no claim
    root = clean_tree(tmp_path)
    client = (root / "backend/services/clip_client.py").read_text()
    client = client.replace(
        "        response = self._http_client.get(self._status_url)", STATUS_VIA_BASE
    )
    client = client.replace(GW_BRANCH, NO_GW_BRANCH)
    (root / "backend/services/clip_client.py").write_text(client)
    _, report = scan(root)
    assert "AI-PARITY-CLAIM-GW404-bare_status" not in ids(report)


def test_compose_rewritten_settings_base_is_red(tmp_path):
    # D2 mechanism B (the LIVE production one): no gateway flag in the client
    # at all — compose rewrites CLIP_URL to http://ai-gateway:8090/clip, so
    # settings.clip_url IS gateway-prefixed as deployed, and the caller hits a
    # gateway path for an op the gateway does not serve
    root = clean_tree(tmp_path)
    client = (root / "backend/services/clip_client.py").read_text()
    client = client.replace(
        "        response = self._http_client.get(self._status_url)", STATUS_VIA_BASE
    )
    client = client.replace(GW_BRANCH, NO_GW_BRANCH)
    (root / "backend/services/clip_client.py").write_text(client)
    tree(
        root,
        {
            "docker-compose.prod.yml": """
services:
  backend:
    environment:
      - CLIP_URL=http://ai-gateway:8090/clip
  ai-gateway:
    image: x
""",
        },
    )
    rc, report = scan(root)
    assert rc == 1
    assert "AI-PARITY-CLAIM-GW404-bare_status" in ids(report)


# ---------------------------------------------------------------------------
# CLI contract: exit codes, --json, plain summary, --expect golden round trip
# ---------------------------------------------------------------------------


def test_missing_registry_is_checker_error_rc2(tmp_path):
    rc, _ = scan(tmp_path)
    assert rc == 2


def test_unparseable_registry_is_checker_error_rc2(tmp_path):
    tree(tmp_path, {"backend/ai_contract/operations.py": "OPERATIONS = {broken\n"})
    r = gate("--root", str(tmp_path))
    assert r.returncode == 2
    assert "checker error" in r.stderr


def test_plain_mode_summary(tmp_path):
    r = gate("--root", str(clean_tree(tmp_path)))
    assert r.returncode == 0
    assert "divergences detected: 0" in r.stdout
    assert "DECLARED clip_seg" in r.stdout


def test_json_report_shape(tmp_path):
    rc, report = scan(clean_tree(tmp_path))
    assert rc == 0
    assert report["tool"] == "check-ai-provider-parity"
    assert report["registry_ops"] == 6
    assert set(report) >= {"deploy", "surfaces", "divergences", "declared"}
    assert report["surfaces"]["caller_urls"] >= 2


def test_expect_roundtrip_and_drift(tmp_path):
    root = clean_tree(tmp_path)
    golden = tmp_path / "golden.json"
    assert gate("--root", str(root), "--update", "--expect", str(golden)).returncode == 0
    assert gate("--root", str(root), "--expect", str(golden)).returncode == 0
    # golden holds an id the tree cannot produce -> GOLDEN-LOST (a fix landed;
    # re-ratchet --update rather than let the baseline rot)
    data = json.loads(golden.read_text())
    data["divergences"].append(
        {
            "id": "AI-PARITY-KEY-clip_do-gone",
            "kind": "KEY",
            "op": "clip_do",
            "detail": "fixed upstream",
        }
    )
    golden.write_text(json.dumps(data))
    r = gate("--root", str(root), "--expect", str(golden))
    assert r.returncode == 1
    assert "GOLDEN-LOST" in r.stderr
    # new divergence not in golden -> NEW-DIVERGENCE fail; --allow-superset = warn only
    golden.write_text(json.dumps({"divergences": []}))
    red_root = clean_tree(tmp_path / "red")
    _drop_gw_batch_guard(red_root)
    r = gate("--root", str(red_root), "--expect", str(golden))
    assert r.returncode == 1 and "NEW-DIVERGENCE" in r.stderr
    r = gate("--root", str(red_root), "--expect", str(golden), "--allow-superset")
    assert r.returncode == 0 and "NEW-DIVERGENCE" in r.stderr


# ---------------------------------------------------------------------------
# THE WP9.1 MEASURE — the REAL tree reproduces Tier A (D1-D6) exactly
# ---------------------------------------------------------------------------

# The adjudicated 21: D1-D6 from the WP8.4 dossier plus 9 verified-true drift
# findings the checker surfaced while being built (each re-read against the
# tree at drafting time; none suppressed). Pinning by EQUALITY is the point:
# every entry is ground truth, so both a lost one (silent fix) and a new one
# (drift) must fail loudly.
REAL_TIER_A_IDS = {
    # D1: heavy-gateway bbox — client/native send list, gateway accepts dict -> 422
    "AI-PARITY-SHAPE-enrichment_vehicle_classify-bbox",  # pragma: allowlist secret
    "AI-PARITY-SHAPE-enrichment_clothing_classify-bbox",  # pragma: allowlist secret
    "AI-PARITY-SHAPE-enrichment_demographics-bbox",  # pragma: allowlist secret
    "AI-PARITY-SHAPE-enrichment_pet_classify-bbox",  # pragma: allowlist secret
    "AI-PARITY-SHAPE-enrichment_pose_analyze-bbox",  # pragma: allowlist secret
    # D2: gateway:False ops whose deployed caller URLs land on the gateway
    "AI-PARITY-CLAIM-GW404-model_status",
    "AI-PARITY-CLAIM-GW404-model_preload",
    "AI-PARITY-CLAIM-GW404-model_unload",
    "AI-PARITY-CLAIM-GW404-object_distance",  # pragma: allowlist secret
    # D3: phantom path /models/{model_name}/unload vs POST /models/unload
    "AI-PARITY-CLAIM-PATH-model_unload",
    # D5: camera_type widened to str at the gateway, handler never reads it
    "AI-PARITY-TYPE-UNUSED-clip_classify-camera_type",  # pragma: allowlist secret
    # D6: MAX_BATCH_TEXTS_SIZE native-only list guard
    "AI-PARITY-GUARD-clip_batch_similarity-texts",
    # verified extras (real provider drift, reported not suppressed):
    "AI-PARITY-KEY-enrich_lt_person_reid-response",
    "AI-PARITY-KEY-enrich_lt_pet_classify-response",
    "AI-PARITY-KEY-enrich_lt_pose_analyze-response",
    "AI-PARITY-KEY-enrichment_action_classify-labels",
    "AI-PARITY-KEY-enrichment_enrich-frames,options",
    "AI-PARITY-KEY-enrichment_enrich-response",
    "AI-PARITY-KEY-enrichment_pet_classify-response",
    "AI-PARITY-KEY-enrichment_pose_analyze-min_confidence",
    "AI-PARITY-KEY-enrichment_pose_analyze-response",
}


def real_report() -> tuple[int, dict]:
    # No skip branch (see the REAL_ROOT assert at module scope): a checkout
    # without the registry fails collection, which is the honest signal.
    return scan(REAL_ROOT)


def test_real_tree_reproduces_tier_a_exactly():
    rc, report = real_report()
    assert rc == 1
    got = ids(report)
    missing = REAL_TIER_A_IDS - got
    extra = got - REAL_TIER_A_IDS
    assert not missing, (
        f"checker LOST Tier-A ids — the checker is wrong, not the tree: {sorted(missing)}"
    )
    assert not extra, f"new drift detected — adjudicate it into the golden list: {sorted(extra)}"


def test_real_tree_d4_stays_declared_green():
    _, report = real_report()
    got = ids(report)
    assert not any("yolo26_segment" in i for i in got), (
        "D4 is a matrix-DECLARED split; it must never gate"
    )
    seg = next(d for d in report["declared"] if d["op"] == "yolo26_segment")
    assert seg["served_gateway"] and not seg["served_native"]


def test_real_tree_registry_and_deploy_facts():
    _, report = real_report()
    # 37, not the 38 this suite was written against (WP7.1 minted a 38-op
    # contract): e947e7ae "A7.x tail — 2 carry-cost deletions (contract
    # 38->37)" moved the contract deliberately and this golden should have
    # moved with it IN THAT COMMIT. It didn't — because the folded anti-rot
    # step swallowed this suite's argv (WP2.5 / AUDIT §7.3), so the pin never
    # executed and the drift stayed silent through the whole stack. WP2.5
    # un-swallowed the step; the suite ran for the first time and caught it.
    assert report["registry_ops"] == 37
    dep = report["deploy"]
    assert dep["compose_found"] is True
    # the compose rewrite IS the D1/D2 live-ness mechanism; pin the dossier's
    # topology facts as data so a compose edit that changes them is loud
    rewritten = dict(dep["compose_rewritten_settings"])
    assert rewritten.get("enrichment_url") == "/enrichment"
    assert rewritten.get("enrichment_light_url") == "/enrich-lt"
    # the native per-model servers are NOT deployed services (only the gateway is)
    assert "ai-enrichment" not in dep["native_services"]
    assert "ai-gateway" in dep["native_services"]


def test_real_tree_unanchored_documents_the_phantom_admin_route():
    # The report keeps a documented non-registry route (models/unload-all)
    # visible under the caller-urls-unanchored section: reported, never
    # silently suppressed, but also not gated (it is not in the matrix).
    _, report = real_report()
    unanchored = report["surfaces"]["caller_urls_unanchored"]
    assert any("/models/unload-all" in u for u in unanchored)


def test_real_tree_is_deterministic():
    _, a = real_report()
    _, b = real_report()
    assert [d["id"] for d in a["divergences"]] == [d["id"] for d in b["divergences"]]
    assert [d["op"] for d in a["declared"]] == [d["op"] for d in b["declared"]]


def test_real_tree_runtime_under_30s():
    start = time.monotonic()
    rc, _ = real_report()
    assert rc == 1
    assert time.monotonic() - start < 30
