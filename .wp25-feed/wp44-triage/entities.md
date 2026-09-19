# WP4.4 Triage Dossier — backend/api/routes/entities.py

**Source:** 130 mutants generated, all checked, **39 survived** (`mutants/backend/api/routes/entities.py.meta`).
**Diff source:** `uv run mutmut show <key>` (all 39 captured; none needed manual fallback).
**Covering tests:** `backend/tests/unit/api/routes/test_entities.py` (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`).

Functions hit by survivors: `_entity_model_to_summary` (entities.py:782), `_extract_cameras_seen_from_entity` (entities.py:745), `_entity_to_trust_response` (entities.py:263), `_entity_to_summary` (entities.py:86).

## Environment note (not a mutation artifact)

Lines 286/553/806/1085 read `except ValueError, TypeError:` — py2-era syntax, but **this is in the ORIGINAL file** and Python 3.14 parses it via PEP 758 (verified with `ast.parse` on 3.14.4). Not mutant corruption; worth a separate cleanup ticket (3.13 would reject it), out of scope here.

## Cluster table (counts sum to 39)

| # | Pattern (function / concern) | Count | Keys (≤3 examples) | Classification | Kill condition |
|---|---|---|---|---|---|
| C1 | `dict.get("trust_status"/"trust_updated_at")` key swapped to `None`/`"XX…XX"`/`"TRUST_*"`, extraction replaced by `None`, or kwarg dropped → trust fields silently lost from `EntitySummary` (`_entity_model_to_summary`) | 10 | `…entity_model_to_summary__mutmut_6`, `_mutmut_11`, `_mutmut_24` (also 5,7,8,9,10,12,33) | **TEST-GAP** | TestListEntities never puts trust keys in fixture metadata and never asserts `items[0].trust_status` / `.trust_updated_at` |
| C2 | `dict.get("cameras_seen")` key mangled (→`None`/`"XXcameras_seenXX"`/`"CAMERAS_SEEN"`), extraction replaced by `None`, or `and`→`or` in the list guard (`_extract_cameras_seen_from_entity`) | 5 | `…extract_cameras_seen…__mutmut_1`, `_mutmut_3`, `_mutmut_5` (also 2,4) | **TEST-GAP** | No test anywhere exercises the `cameras_seen`-list branch — `test_list_entities_multiple_cameras` (test_entities.py:299) only uses the `camera_id` fallback despite its name |
| C3 | thumbnail suppressed on the summary: `thumbnail_url` init `None`→`""`, call replaced by `None`, `str(entity.primary_detection_id)`→`str(None)`, kwarg dropped, entire kwarg removed (`_entity_model_to_summary`) | 5 | `…entity_model_to_summary__mutmut_14`, `_mutmut_16`, `_mutmut_32` (also 13,23) | **TEST-GAP** | `test_list_entities_with_data` (test_entities.py:164) asserts entity_type/appearance_count/cameras_seen but never `items[0].thumbnail_url` |
| C4 | `trust_updated_at=trust_updated_at` kwarg → `None` in the return (`_entity_model_to_summary`) — parsed timestamp silently dropped | 1 | `…entity_model_to_summary__mutmut_25` | **TEST-GAP** | Same as C1; killed by the same drafted test (kwarg-drop visible only when metadata carries the key) |
| C5 | `trust_status` init `None`→`""` — observable only when `entity_metadata` is falsy, then serializes `""` vs `None` (`_entity_model_to_summary`) | 1 | `…entity_model_to_summary__mutmut_3` | **LOW-VALUE** | Real but display-only (`str|None` field, both falsy); not worth an assertion |
| C6 | `id=str(entity.id)` → `str(None)` — summary id becomes `"None"` (`_entity_model_to_summary`) | 1 | `…entity_model_to_summary__mutmut_35` | **TEST-GAP** | No test asserts `result.items[0].id`; `get_entity` builds its own `EntityDetail` so helper coverage never checks it |
| C7 | `raise ValueError("Cannot create summary…")` message wrapped with `XX` (`_entity_to_summary`) | 1 | `…entity_to_summary__mutmut_3` | **EQUIVALENT** | Test uses `pytest.raises(ValueError, match="Cannot create summary from empty")` (test_entities.py:112) — a prefix search, so prefix-`XX` still matches. Message-text mutant, semantics identical |
| C8 | `trust_status_str` init/default mutants (`"unclassified"`→`None`/`"XX…"`/`"UNCLASSIFIED"`, `get` default-arg mangled) (`_entity_to_trust_response`) | 7 | `…entity_to_trust_response__mutmut_1`, `_mutmut_3`, `_mutmut_8` (also 2,10,13,14) | **EQUIVALENT** | Every garbage value is funneled through `try: TrustStatus(str) except ValueError: UNCLASSIFIED` (entities.py:291-293); when metadata is truthy the init is overwritten by the untouched `get` line anyway. Enum-conversion guard makes all variants semantically identical |
| C9 | `first_seen`/`last_seen` set to `None`, `appearance_count=entity.detection_count`→`None`, or those kwargs removed entirely (`_entity_to_trust_response`) — schema defaults are `None` so removal == set-to-None | 6 | `…entity_to_trust_response__mutmut_37`, `_mutmut_39`, `_mutmut_46` (also 38,47,48) | **TEST-GAP** | `TestEntityToTrustResponse` (test_entities.py:877-943) and the trust-update tests assert trust fields + thumbnail but never `first_seen`/`last_seen`/`appearance_count` |
| C10 | `thumbnail_url` init `None`→`""` when `primary_detection_id` is falsy (`_entity_to_trust_response`) | 1 | `…entity_to_trust_response__mutmut_28` | **LOW-VALUE** | `""` vs `None` on an optional URL; the existing test only covers the populated branch (entity always has detection id 123) |

**Totals:** TEST-GAP 28 (C1 10 + C2 5 + C3 5 + C4 1 + C6 1 + C9 6) · EQUIVALENT 9 (C7 1 + C8 7 + … C8's seven + C7) · LOW-VALUE 2 (C5 1 + C10 1). 10+5+5+1+1+1+1+7+6+1 = 39. ✔

## Why the covering tests miss these (read of test_entities.py)

- `test_list_entities_with_data` (**:164-190**): fixture metadata is `{"camera_id": "front_door"}` (test_entities.py:138 default). Asserts `entity_type`, `appearance_count`, `cameras_seen` only → id/thumbnail/trust fields/first_seen/last_seen of `EntitySummary` are never asserted → C1-C6,C9-style survives on the list path.
- `test_list_entities_multiple_cameras` (**:299-316**): despite the name, feeds `{"camera_id": "front_door"}` — the `cameras_seen` list branch of `_extract_cameras_seen_from_entity` is executed-zero times → C2.
- `TestEntityToTrustResponse` (**:877-943**): asserts trust_status/notes/updated_at/thumbnail, never the temporal trio → C9. The metadata-without-trust tests (`:902`, `:918`, `:932`) exercise exactly the branches that make C8 equivalent.
- `TestEntityToSummary::test_empty_embeddings_raises_error` (**:110-113**): `match=` is a search, so `XX`-prefixed message still passes → C7.

## Drafted tests (target file: `backend/tests/unit/api/routes/test_entities.py`)

TDD procedure (one line): add the test, run it against each mutant copy in the cluster — assertion must FAIL on mutant, PASS on original — before marking green.

All four are **UNVERIFIED — not yet run red/green** (mutation run owns the machine; no pytest executed per task constraints).

### T1 — kills C1 + C4 (11 survivors)

```python
class TestEntityModelToSummary:
    """Direct tests for _entity_model_to_summary trust-field extraction."""

    def test_summary_carries_trust_fields(self) -> None:
        """Trust status and parsed trust_updated_at survive conversion to EntitySummary."""
        # UNVERIFIED - not yet run red/green
        from backend.api.routes.entities import _entity_model_to_summary

        entity = _create_test_entity(
            entity_type="person",
            entity_metadata={
                "camera_id": "front_door",
                "trust_status": "trusted",
                "trust_updated_at": "2025-12-23T14:30:00+00:00",
            },
        )

        summary = _entity_model_to_summary(entity)

        assert summary.trust_status == "trusted"
        assert summary.trust_updated_at == datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
```

Kill logic: key-mangled/None-swapped `.get` calls (C1: mutmut_5-12,24,33) make both fields `None` → first assert fails; the `trust_updated_at=None` kwarg mutant (C4: mutmut_25) fails the datetime assert. Passes on original because `dt.fromisoformat("2025-12-23T14:30:00+00:00") == datetime(..., tzinfo=UTC)`.

### T2 — kills C2 (5 survivors)

```python
class TestExtractCamerasSeen:
    """Direct tests for _extract_cameras_seen_from_entity metadata fallbacks."""

    def test_prefers_cameras_seen_list_and_ignores_non_list(self) -> None:
        """cameras_seen list is returned as-is; a non-list value falls back to camera_id."""
        # UNVERIFIED - not yet run red/green
        from backend.api.routes.entities import _extract_cameras_seen_from_entity

        entity = _create_test_entity(
            entity_metadata={"cameras_seen": ["front_door", "backyard", "driveway"]}
        )
        assert _extract_cameras_seen_from_entity(entity) == [
            "front_door",
            "backyard",
            "driveway",
        ]

        # Truthy non-list must NOT satisfy the isinstance-and-truthy guard:
        # original falls through to the camera_id fallback.
        bogus = _create_test_entity(
            entity_metadata={"cameras_seen": "not-a-list", "camera_id": "cam_x"}
        )
        assert _extract_cameras_seen_from_entity(bogus) == ["cam_x"]
```

Kill logic: keys 1-4 (mangled key) → first assert gets `[]` (falls to absent `camera_id`, detached `primary_detection` access is swallowed by the `except Exception` at entities.py:776). Key 5 (`and`→`or`) survives the first assert but the second assert sees a per-character list from iterating the string → fails.

### T3 — kills C3 + C6 (6 survivors)

```python
    def test_summary_thumbnail_url_and_id(self) -> None:
        """Summary keeps the entity id and builds the thumbnail URL from the primary detection."""
        # UNVERIFIED - not yet run red/green
        from backend.api.routes.entities import _entity_model_to_summary

        entity = _create_test_entity(primary_detection_id=123)

        summary = _entity_model_to_summary(entity)

        assert summary.id == str(entity.id)
        assert summary.thumbnail_url == "/api/detections/123/image"

        # No primary detection -> thumbnail stays None (not "", not absent).
        entity_no_det = _create_test_entity()
        entity_no_det.primary_detection_id = None
        assert _entity_model_to_summary(entity_no_det).thumbnail_url is None
```

Kill logic: `str(None)` id (C6 mutmut_35) → `"None" != str(uuid)`; thumbnail suppression/`str(None)`/kwarg-drop (C3 mutmut_14,16,23,32) fail the second assert; the `""` init (mutmut_13) fails the third (`"" is not None`). Follows the file's existing manual-attribute style (cf. test_entities.py:938).

### T4 — kills C9 (6 survivors)

```python
    def test_entity_trust_response_carries_temporal_fields(self) -> None:
        """first_seen / last_seen / appearance_count are copied from the Entity model."""
        # UNVERIFIED - not yet run red/green
        from backend.api.routes.entities import _entity_to_trust_response

        entity = _create_test_entity(
            first_seen=datetime(2025, 12, 23, 9, 15, 0, tzinfo=UTC),
            last_seen=datetime(2025, 12, 23, 18, 45, 0, tzinfo=UTC),
            detection_count=4,
        )

        result = _entity_to_trust_response(entity)

        assert result.first_seen == entity.first_seen_at
        assert result.last_seen == entity.last_seen_at
        assert result.appearance_count == 4
```

Kill logic: set-to-None mutants (37,38,39) and kwarg-removal mutants (46,47,48 — `EntityTrustResponse` defaults these to `None`, entities.py schemas:888-891) each break exactly one assert.

**Coverage of the drafted batch: T1-T4 kill all 28 TEST-GAP survivors (C1,C2,C3,C4,C6,C9). C5/C7/C8/C10 (11) are EQUIVALENT/LOW-VALUE and intentionally not chased.**

## Side observations

- The `except ValueError, TypeError:` legacy syntax at entities.py:286/553/806/1085 only survives because the sandbox/CI run ≥3.14 (PEP 758). Recommend normalizing to `except (ValueError, TypeError):` in a separate chore — flagging because it briefly looked like mutant corruption.
- `_entity_model_to_summary` is covered only via `list_entities` route tests (stats: 5 tests) — direct-helper tests as drafted above would also insulate future refactors from route-mock brittleness.
