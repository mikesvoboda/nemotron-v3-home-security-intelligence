"""Batch-25 kill battery — chunk "NemotronAnalyzer._build_context_sources#chunk1" (130 keys).

Shipped target: backend/services/nemotron_analyzer.py:1781-1853
NemotronAnalyzer._build_context_sources(enrichment_result, enriched_context).

The method is PURE (no self, no I/O): it builds a dict[str, bool] with two literal
availability keys, then an if/else on enrichment_result (16 has_* keys per branch),
then an if/else on enriched_context (3 has_* keys per branch), and returns it.
Probe (/tmp/wp-batch25/probes/chunk14/probe_shipped.py) pins shipped outputs:

  CASE A — populated EnrichmentResult + populated EnrichedContext:
      all 21 keys present, every value True.
  CASE B — (None, None):
      the same 21 keys present, every value False.

Every survivor in this chunk mutates exactly one of:
  (a) a dict-literal key string ("XX..."/"UPPER" renames of enrichment_available /
      context_available),
  (b) an availability VALUE expression (is-not-None -> is-None, ... -> None,
      bool(x) -> bool(None)),
  (c) a sources[...] KEY string in either branch (rename -> the canonical key is
      never set and an XX key appears instead),
  (d) an else-branch constant False -> None / True,
  (e) the `if enrichment_result is not None:` / `if enriched_context is not None:`
      guard (only mutmut_128).

A strict `result == expected` dict equality over the COMPLETE 21-key map kills all
of them under one of the two input cases: renames break the key set, value flips
break the value, branch-guard flips (128) route CASE A down the else branch (True
-> False for has_baselines/has_zones/has_cross_camera).

CASE A kills keys {2-7, 9-63, 128-132} (66 keys): every mutation lives on the
not-None code path or the dict literal, and its altered value/key is observable
against the all-True expectation.
CASE B kills keys {64-127} (64 keys): those mutations are on the else-branch
lines, which execute only when enrichment_result is None (and enriched_context is
None for 120-127, whose flipped guard additionally raises AttributeError on
None.baselines — the all-False expectation is the primary kill reason).

No twin shapes: every shape group in feed.json
(functions['xǁNemotronAnalyzerǁ_build_context_sources'].shapes[0..129]) holds a
single key, so per-key verdicts carry trivially.

killed_by_draft: none. The two repo tests that reach this function
(test_nemotron_analyzer.py:5258 and :5528-enrichment-None variant) only assert
`context_sources is not None` + isinstance dict — no key or value assertion — and
test_nemotron_streaming_batch16b/16c replace _build_context_sources with a
MagicMock, so no shipped test observes the dict contents. The draft battery
(/tmp/wp-batch25/test_nemotron_analyzer_batch25.py) covers _parse_llm_response /
_validate_risk_data only.

equivalent: none — every mutated operand is read into the returned dict, which the
two strict equalities below consume in full.

GREEN-CHECK: .venv/bin/python -m pytest \
    /tmp/wp-batch25/parts/test_batch25_14.py -p no:cacheprovider -o addopts= -q
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

# The part file lives outside the repo tree, so backend/tests/conftest.py does NOT
# apply. Mirror the minimum env vars the repo conftest sets BEFORE any backend
# import (values copied verbatim from backend/tests/conftest.py, as in lane 04).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

from backend.services.context_enricher import EnrichedContext
from backend.services.enrichment_pipeline import EnrichmentResult
from backend.services.nemotron_analyzer import NemotronAnalyzer

# The 21 context-source keys shipped by _build_context_sources (NEM-4234).
_ALL_KEYS = (
    "enrichment_available",
    "context_available",
    "has_license_plates",
    "has_faces",
    "has_weather",
    "has_pose",
    "has_action",
    "has_violence",
    "has_clothing",
    "has_vehicle_classification",
    "has_vehicle_damage",
    "has_pet_classification",
    "has_image_quality",
    "has_vision_extraction",
    "has_person_reid",
    "has_vehicle_reid",
    "has_household_person_matches",
    "has_household_vehicle_matches",
    "has_baselines",
    "has_zones",
    "has_cross_camera",
)


def _populated_enrichment_result() -> EnrichmentResult:
    """EnrichmentResult with every field the method reads populated.

    Field choices mirror what the shipped property expressions read:
    license_plates/faces lists non-empty (len>0), weather_classification /
    action_results / image_quality / vision_extraction non-None, pose_results /
    clothing_classifications / vehicle_classifications / pet_classifications /
    person_reid_matches / vehicle_reid_matches / person_household_matches /
    vehicle_household_matches non-empty dicts, violence_detection.is_violent True,
    vehicle_damage entries .has_damage True (has_vehicle_damage uses any()).
    """
    return EnrichmentResult(
        license_plates=[MagicMock()],
        faces=[MagicMock()],
        weather_classification=MagicMock(),
        pose_results={"1": MagicMock()},
        action_results={"1": "standing"},
        violence_detection=MagicMock(is_violent=True),
        clothing_classifications={"1": MagicMock()},
        vehicle_classifications={"1": MagicMock()},
        vehicle_damage={"1": MagicMock(has_damage=True)},
        pet_classifications={"1": MagicMock()},
        image_quality=MagicMock(),
        vision_extraction=MagicMock(),
        person_reid_matches={"1": [MagicMock()]},
        vehicle_reid_matches={"1": [MagicMock()]},
        person_household_matches={1: MagicMock()},
        vehicle_household_matches={2: MagicMock()},
    )


def _populated_enriched_context() -> EnrichedContext:
    """EnrichedContext with baselines / zones / cross_camera populated."""
    return EnrichedContext(
        camera_name="Front Door",
        camera_id="front_door",
        zones=[MagicMock()],
        baselines=MagicMock(),
        cross_camera=[MagicMock()],
    )


def test_context_sources_populated_exact():
    """Kills the 66 chunk keys on the not-None code path (CASE A: populated
    EnrichmentResult + populated EnrichedContext -> strict equality against the
    complete 21-key all-True map; renames, None-outs, is-not-None->is-None flips,
    bool(x)->bool(None) flips, and the enriched_context guard flip (mutmut_128,
    which routes CASE A into the else branch) all break the equality):

    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_2
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_3
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_4
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_5
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_6
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_7
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_9
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_10
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_11
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_12
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_13
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_14
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_15
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_16
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_17
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_18
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_19
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_20
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_21
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_22
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_23
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_24
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_25
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_26
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_27
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_28
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_29
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_30
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_31
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_32
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_33
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_34
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_35
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_36
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_37
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_38
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_39
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_40
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_41
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_42
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_43
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_44
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_45
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_46
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_47
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_48
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_49
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_50
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_51
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_52
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_53
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_54
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_55
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_56
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_57
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_58
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_59
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_60
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_61
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_62
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_63
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_128
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_129
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_130
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_131
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_132
    """
    sources = NemotronAnalyzer._build_context_sources(
        None, _populated_enrichment_result(), _populated_enriched_context()
    )
    expected = dict.fromkeys(_ALL_KEYS, True)
    assert sources == expected
    assert all(isinstance(v, bool) for v in sources.values())


def test_context_sources_no_enrichment_exact():
    """Kills the 64 chunk keys on the else code path (CASE B: _build_context_sources
    (None, None) -> strict equality against the complete 21-key all-False map;
    else-branch False->None / False->True mutations and the 64-127 key renames all
    break the equality; renames of the has_household_* else-branch keys at
    120-127 leave the canonical keys unset so the map misses required keys):

    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_64
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_65
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_66
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_67
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_68
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_69
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_70
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_71
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_72
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_73
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_74
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_75
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_76
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_77
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_78
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_79
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_80
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_81
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_82
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_83
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_84
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_85
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_86
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_87
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_88
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_89
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_90
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_91
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_92
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_93
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_94
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_95
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_96
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_97
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_98
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_99
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_100
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_101
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_102
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_103
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_104
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_105
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_106
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_107
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_108
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_109
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_110
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_111
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_112
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_113
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_114
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_115
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_116
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_117
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_118
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_119
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_120
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_121
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_122
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_123
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_124
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_125
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_126
    backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_context_sources__mutmut_127
    """
    sources = NemotronAnalyzer._build_context_sources(None, None, None)
    expected = dict.fromkeys(_ALL_KEYS, False)
    assert sources == expected
    assert all(isinstance(v, bool) for v in sources.values())
