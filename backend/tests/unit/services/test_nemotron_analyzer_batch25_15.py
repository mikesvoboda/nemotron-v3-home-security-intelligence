"""Batch-25 kill battery — chunk "NemotronAnalyzer._build_context_sources#chunk2" (20 keys: mutmut_133..152).

Every survivor sits on the three context-flag assignments at the tail of
_build_context_sources (shipped backend/services/nemotron_analyzer.py:1850-1857):

    if enriched_context is not None:
        sources["has_baselines"] = enriched_context.baselines is not None   # L1851
        sources["has_zones"] = bool(enriched_context.zones)                 # L1852
        sources["has_cross_camera"] = bool(enriched_context.cross_camera)   # L1853
    else:
        sources["has_baselines"] = False                                     # L1855
        sources["has_zones"] = False                                         # L1856
        sources["has_cross_camera"] = False                                  # L1857

Branch -> key mapping (verified occurrence-by-occurrence against the
instrumented copy mutants/backend/services/nemotron_analyzer.py, variant
bodies xǁNemotronAnalyzerǁ_build_context_sources__mutmut_133 .. _152):

  IF-branch (enriched_context is not None):
    133 has_zones=None          134 XXhas_zonesXX      135 HAS_ZONES      136 has_zones=bool(None)
    137 has_cross_camera=None   138 XXhas_cross_cameraXX 139 HAS_CROSS_CAMERA
                                140 has_cross_camera=bool(None)
  ELSE-branch (enriched_context is None):
    141 has_baselines=None      142 XXhas_baselinesXX  143 HAS_BASELINES  144 has_baselines=True
    145 has_zones=None          146 XXhas_zonesXX      147 HAS_ZONES      148 has_zones=True
    149 has_cross_camera=None   150 XXhas_cross_cameraXX 151 HAS_CROSS_CAMERA
                                152 has_cross_camera=True

Each of the 20 keys is its OWN shape group in feed.json
(functions['xǁNemotronAnalyzerǁ_build_context_sources'].shapes 130..149, one
key each) — no occurrence twins inside this chunk.

Reachability proof (why none of these is equivalent):
EnrichedContext is a slots dataclass whose three fields are independent and
public (backend/services/context_enricher.py:138-158: zones/baselines/cross_camera
all carry defaults, baselines: BaselineContext | None = None), so all four
input classes used below are constructible and the function reads every one of
the three values into its returned dict. That dict is not write-only: it is
assigned to LLMInteraction.context_sources (nemotron_analyzer.py:2992 and
:3486 feed it into the persisted record), so a mutated key name or a mutated
value is an observable contract break — the JSON audit payload loses
`has_zones` / gains `HAS_ZONES` / carries None where the schema says bool.
The 136/140 `bool(None)` shapes are NOT no-ops: bool(None) is False while the
shipped operand is truthy for a populated context, so they are only detectable
with a POPULATED context (test A), and the 133/137 `None` shapes are only
detectable with an EMPTY (but not None) context (test B), because shipped
already yields False there — `is False` vs `is None` is what separates them.
Keys 141..152 sit in the else-branch and are only executed when
enriched_context is None (test C).

No repo test or the batch-25 draft battery kills any of these: the only
repo assertions on this function are
`assert llm_interaction.context_sources is not None` /
`isinstance(..., dict)` (backend/tests/unit/services/
test_nemotron_analyzer.py:5335-5336 and :5629) — name- and value-blind — and
batch-16c mocks _build_context_sources outright (test_nemotron_streaming_
batch16c.py:98) while batch-16b replaces it with a MagicMock returning
"SOURCES" (test_nemotron_streaming_batch16b.py:64). The draft battery
(/tmp/wp-batch25/test_nemotron_analyzer_batch25.py) only drives
_parse_llm_response / _validate_risk_data / _extract_json_objects.
=> zero keys are killed_by_draft; all 20 are killable.

GREEN-CHECK: cd /agents/agent-veranda3/workspace && .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_15.py -p no:cacheprovider -o addopts= -q
RED-CHECK (on a lane): apply each key individually to
backend/services/nemotron_analyzer.py, run the named test, expect failure.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.unit

# The part file lives outside the repo tree, so backend/tests/conftest.py does
# NOT apply. Mirror the minimum env vars that conftest sets BEFORE any backend
# import (values copied verbatim from backend/tests/conftest.py
# reset_settings_cache / DEFAULT_DEV_POSTGRES_URL handling).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

from backend.services.context_enricher import EnrichedContext
from backend.services.nemotron_analyzer import NemotronAnalyzer

# Full key set the shipped function always returns, pinned as a literal
# (probe of shipped _build_context_sources(None, ...) on 2026-09-24). The
# three context flags are overridden per test; the other 18 entries are
# identical in every scenario because enrichment_result is None throughout.
_BASE_KEYS = {
    "enrichment_available": False,
    "has_license_plates": False,
    "has_faces": False,
    "has_weather": False,
    "has_pose": False,
    "has_action": False,
    "has_violence": False,
    "has_clothing": False,
    "has_vehicle_classification": False,
    "has_vehicle_damage": False,
    "has_pet_classification": False,
    "has_image_quality": False,
    "has_vision_extraction": False,
    "has_person_reid": False,
    "has_vehicle_reid": False,
    "has_household_person_matches": False,
    "has_household_vehicle_matches": False,
    "has_baselines": False,
    "has_zones": False,
    "has_cross_camera": False,
}

# The three flag names must be EXACTLY these; the mutant key spellings
# ("XXhas_zonesXX", "HAS_ZONES", ...) are contract breaks, not aliases.
_CONTEXT_FLAG_KEYS = ("has_baselines", "has_zones", "has_cross_camera")

# Sentinel zone/cross_camera/baseline payloads. The shipped function only ever
# applies bool(...) / `is not None` to these fields, so identity objects are
# enough — and they additionally prove the flag is read from the field the
# shipped line names (an operand-swap shape cannot masquerade as a pass when
# only ONE of the three fields is populated, see test A).
_ZONE = object()
_BASELINE = object()
_CROSS = object()


def _analyzer() -> NemotronAnalyzer:
    # __new__ skips the heavy __init__ (model/client wiring); the helper under
    # test touches only its arguments, never instance state.
    return NemotronAnalyzer.__new__(NemotronAnalyzer)


def _assert_contract(
    sources: dict,
    expected_flags: dict[str, bool],
    context_available: bool,
) -> None:
    """Pin the shipped dict contract: exact key set + strict bool identity."""
    expected = {
        **_BASE_KEYS,
        "context_available": context_available,
        **expected_flags,
    }
    # Exact key set: kills every key-name shape (134/135/138/139 in the
    # if-branch, 142/143/146/147/150/151 in the else-branch) because the
    # mutant drops the canonical flag entry AND introduces a stray key.
    assert set(sources) == set(expected), sorted(sources)
    for flag in ("context_available", *_CONTEXT_FLAG_KEYS):
        # `is` (not `==`): shipped writes real bools, so None/1/0 must fail.
        assert sources[flag] is expected[flag], flag
    # Re-pin the 17 constant entries so no sibling assignment can drift.
    assert sources == expected


class TestBuildContextSourcesPopulated:
    def test_populated_context_flags_all_true_and_operand_identity(self):
        """Kills mutant keys 134, 135, 136, 138, 139, 140.

        134 sources["XXhas_zonesXX"] = bool(enriched_context.zones)
        135 sources["HAS_ZONES"] = bool(enriched_context.zones)
        136 sources["has_zones"] = bool(None)                -> False vs True
        138 sources["XXhas_cross_cameraXX"] = bool(enriched_context.cross_camera)
        139 sources["HAS_CROSS_CAMERA"] = bool(enriched_context.cross_camera)
        140 sources["has_cross_camera"] = bool(None)         -> False vs True

        A fully populated EnrichedContext is the ONLY input class where the
        if-branch writes True, so 136/140 (bool(None) collapses to False) and
        the two key-rewrite pairs are observable here. (Keys 133/137 write
        None, which is also non-True — they are additionally detected by this
        test but are adjudicated under test B, where shipped-vs-mutant
        actually separates on `is False`.)

        The second half of the test drives a context where ONLY cross_camera
        is populated: shipped derives each flag from the field its own line
        names, so has_zones must stay False there — this pins the operand
        identity of the two bool() lines I am mutating around.
        """
        a = _analyzer()
        populated = EnrichedContext(
            camera_name="front_door",
            camera_id="cam-1",
            zones=[_ZONE],
            baselines=_BASELINE,
            cross_camera=[_CROSS],
        )
        sources = a._build_context_sources(None, populated)
        _assert_contract(
            sources,
            {"has_baselines": True, "has_zones": True, "has_cross_camera": True},
            context_available=True,
        )

        only_cross = EnrichedContext(
            camera_name="front_door",
            camera_id="cam-1",
            cross_camera=[_CROSS],
        )
        _assert_contract(
            a._build_context_sources(None, only_cross),
            {"has_baselines": False, "has_zones": False, "has_cross_camera": True},
            context_available=True,
        )

    def test_empty_context_flags_all_false(self):
        """Kills mutant keys 133, 137.

        133 sources["has_zones"] = None                     -> None vs False
        137 sources["has_cross_camera"] = None              -> None vs False

        enriched_context is NOT None but every field is empty (zones=[],
        baselines=None, cross_camera=[] — the dataclass defaults,
        context_enricher.py:152-155), so shipped takes the if-branch and
        writes False for all three flags. That is the only input class that
        separates `= None` from the shipped False inside the if-branch,
        because with a populated context both shipped and mutant give True/
        False-but-not-None indistinguishably for 133/137 only under `is False`.
        """
        a = _analyzer()
        empty = EnrichedContext(camera_name="driveway", camera_id="cam-2")
        sources = a._build_context_sources(None, empty)
        # if-branch taken: context_available is True while every flag is False
        assert sources["context_available"] is True
        _assert_contract(
            sources,
            {"has_baselines": False, "has_zones": False, "has_cross_camera": False},
            context_available=True,
        )


class TestBuildContextSourcesNoContext:
    def test_none_context_flags_all_false(self):
        """Kills mutant keys 141, 142, 143, 144, 145, 146, 147, 148, 149, 150,
        151, 152.

        141 sources["has_baselines"] = None              142 "XXhas_baselinesXX"
        143 "HAS_BASELINES"                              144 has_baselines = True
        145 sources["has_zones"] = None                  146 "XXhas_zonesXX"
        147 "HAS_ZONES"                                  148 has_zones = True
        149 sources["has_cross_camera"] = None           150 "XXhas_cross_cameraXX"
        151 "HAS_CROSS_CAMERA"                           152 has_cross_camera = True

        enriched_context=None is the only way to execute the else-branch
        (shipped nemotron_analyzer.py:1854-1857). Shipped reports "this source
        was unavailable" as an explicit False — never None, never True — and
        under the canonical key names; the strict-identity plus exact-key-set
        assertions separate all twelve shapes.
        """
        a = _analyzer()
        sources = a._build_context_sources(None, None)
        # else-branch entry condition, pinned independently of the flags so a
        # mutant that rewrites the `if enriched_context is not None` guard is
        # also caught (that guard is chunk 1's territory, not this chunk's).
        assert sources["context_available"] is False
        assert sources["enrichment_available"] is False
        _assert_contract(
            sources,
            {"has_baselines": False, "has_zones": False, "has_cross_camera": False},
            context_available=False,
        )
