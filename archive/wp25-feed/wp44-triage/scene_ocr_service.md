# WP4.4 Triage Dossier — backend/services/scene_ocr_service.py

**Survivors: 283** (meta: 705 keys, 417 killed, 2 unchecked). All 283 diffs pulled read-only via `mutmut show` (raw: `/tmp/wp25/wp44-triage/iou-diffs/*.diff`; machine partition: `/tmp/wp25/wp44-triage/final_part.json`, built by deterministic per-key classifier over the raw diffs — totals are folded from the artifact, not hand-typed).

**Totals: TEST-GAP 183 / EQUIVALENT 53 / LOW-VALUE 47 = 283.**

## Covering tests

- `backend/tests/unit/services/test_scene_ocr_service.py` (primary; 903 lines) — anchors: dataclasses L75-310, IoU/overlap L318-413, classify L421-447, init/disabled L490-505, full-frame L507-578, crop L580-644, dedup L646-767, region L769-791, integration L793-846, singleton L854-874, thresholds L882-903.
- `backend/tests/unit/services/test_enrichment_pipeline.py` — patches `_get_client` wholesale (L2030,2080,2141,2188,3301,3349,3397,4753): real client path and HTTP kwargs never observed.
- `backend/tests/unit/core/test_scene_ocr_metrics.py` — calls metric functions directly; never asserts the label VALUES passed from scene_ocr_service call sites.

Root cause of most survivals: OCR tests assert only lengths/flags (`len(results)`, `has_scene_texts`, `call_count == 2`) while the mock `client.post` accepts any URL/payload, parsed-result bbox/confidence/schema go unasserted, and `_determine_region` is only tested via its three mapped regions (`chest`/`top`/`bottom`) — the `left`/`right`/`center`-fallback outputs are never produced.

## Cluster table (22 clusters; counts sum to 283)

| ID | Cluster | n | Class | Example keys (prefix `…` = `backend.services.scene_ocr_service.`) |
|----|---------|---|-------|-------------|
| A1 | No-overlap guard `or`→`and` in `_calculate_iou`/`_calculate_overlap_ratio` — real sign bug: one-axis-separated boxes get negative-intersection garbage IoU | 2 | TEST-GAP | `…x__calculate_iou__mutmut_23`, `…x__calculate_overlap_ratio__mutmut_23` |
| A2 | `_determine_region` degenerate-bbox guard flips + center/size arithmetic index swaps (`det_bbox[3]-det_bbox[1]`→`+`, `text_center_x` index swaps) — tests never pass a zero-area det_bbox nor verify derived center math | 10 | TEST-GAP | `…_determine_region__mutmut_1,2,17,18,21,27` |
| A3 | Crop-OCR request/pipeline unasserted: URL→None/removed, `json=None`/removed, `"image"` key UPPER/XX, `crop=None`/`crop_base64=None`, plus det_id fallback ternary + `id(None)` variants | 30 | TEST-GAP | `…_run_crop_ocr__mutmut_69,70,71,73,74` |
| A4 | Full-frame request/payload + parse defaults unasserted (URL None, `json=None`/removed, `"image"` key mangled, `text/confidence/bbox` get()-defaults) | 21 | TEST-GAP | `…_run_full_frame_ocr__mutmut_9,10,13,14,42` |
| A5 | Crop class-filter token `"truck"/"bus"/"motorcycle"/"bicycle"/"package"`→`XX…XX` — membership check breaks (note: UPPER variants like `"TRUCK"` are EQUIVALENT because filter lowercases); tests only use `person`/`car` | 10 | TEST-GAP | `…_run_crop_ocr__mutmut_6,8,10,12,14` |
| A7 | `_deduplicate` det_id derivation + output schema keys (`"value"/"confidence"/"region"`→UPPER/XX, assoc dict→None, `detection_id=None`) — consumer reads never asserted | 20 | TEST-GAP | `…_deduplicate__mutmut_12,13,67,64,31` |
| A8 | `_determine_region` h/v region tokens & 33/66 boundary (`"left"`→XX, `<=`/`>=` equality at 0.33) — outputs for `left`/`right`/boundary cases never produced | 10 | TEST-GAP | `…_determine_region__mutmut_52,54,55,41,47` |
| A9 | Dedup association logic: IoU `>=0.70`→`>0.70` (#42), similar-band `<1.05` (#46 — frame even when strictly higher conf), `overlap >= best` (#60), `best_det_id=None` (#62), `not in`→`in` (#63) | 5 | TEST-GAP | `…_deduplicate__mutmut_42,46,60,62,63` |
| A10 | `is_uncertain` boundary flips: `LOW <=`→`<` at 0.50, `<HIGH`→`<=HIGH` at 0.80 (docstring says 0.50-0.79 uncertain) | 2 | TEST-GAP | `…_deduplicate__mutmut_84,85` |
| A11 | `_determine_region` region_map side entries + h tokens UPPER/XX (`("top","left")`→`("TOP",…)`/`("XXtopXX",…)` etc.) — `left`/`right`/`top-left` entries have ZERO test coverage; UPPER keys silently fall through to "center" default | 36 | TEST-GAP | `…_determine_region__mutmut_79,84,97,101,114` |
| A12 | `confidence < CONFIDENCE_EXCLUDE`→`<=` in both OCR paths: a 0.50-equal detection is now excluded — exact-threshold case untested | 2 | TEST-GAP | `…_run_full_frame_ocr__mutmut_34`, `…_run_crop_ocr__mutmut_93` |
| A13 | Florence quadrilateral bbox `len(bbox)==8`→`9`: 8-point min/max reduction silently disabled | 2 | TEST-GAP | `…_run_full_frame_ocr__mutmut_49`, `…_run_crop_ocr__mutmut_107` |
| A14 | Result-field construction: full-frame `bbox=(int(b[1]),…)` index swaps (#67/69/71), dedup SceneTextResult `confidence=None`/`bbox=None` (#88/89) — result bbox/fields never asserted | 5 | TEST-GAP | `…_run_full_frame_ocr__mutmut_67,69,71`, `…_deduplicate__mutmut_88,89` |
| A15 | Init/transport contract: `florence_url` settings-fallback mangling (getattr name/default), `_client=""` (breaks the `is None` identity check → client rebuilt per call), `_get_client` `is None`→`is not None` / client→None (caching broken; real client never exercised) | 8 | TEST-GAP | `…__init____mutmut_5,11,16`, `…_get_client__mutmut_1,2` |
| A16 | `_classify_text_type` boundaries: `<=5`→`<5` (4-digit miss), `<=5`→`<=6` (6-digit false positive), sign branch `or`→`and` (substring containment dead) | 3 | TEST-GAP | `…x__classify_text_type__mutmut_4,5,15` |
| A20 | `_image_to_base64` `buffer.seek(0)`→`seek(1)` — real PNG byte truncation, invisible because both OCR tests mock `_image_to_base64`/`_get_client` | 1 | TEST-GAP | `…x__image_to_base64__mutmut_9` |
| B3 | `process_frame` `asyncio.gather(..., return_exceptions=True)`→False/None/removed — one side's failure now aborts instead of degrading to empty result | 3 | TEST-GAP | `…process_frame__mutmut_13,16,17` |
| B4 | `process_frame` crop_task call-args mangled (`image`→None, `detections`→None/removed) | 4 | TEST-GAP | `…process_frame__mutmut_6,7,8,9` |
| B5 | Service-provider wiring unasserted: `match_all(None)`/filter-key mangles, `max(..., key=…)` key→None (TypeError on ties), scene-text `match=None`/`match(None)` — no test asserts `service_match` end-to-end | 9 | TEST-GAP | `…process_frame__mutmut_30,37,42,43` |
| A17 | Log message text mangles (None/case/XX-wrap) in `logger.info/warning/debug` | 8 | EQUIVALENT | `…_run_full_frame_ocr__mutmut_84-87`, `…process_frame__mutmut_62` |
| A18 | Metrics/pool internals: label UPPER/XX/None (`"crop"`→`"CROP"`, `"full_frame"`→XX…), count-guard `>0`→`>1`/`>=0`, timing arithmetic (`*1001`, `/1001.0`, `perf_counter()+start`), one-pixel guard tweaks (`union<=1`, `ocr_area<=1`), semaphore 4→5, httpx `Timeout`/`Limits` values, `self.timeout=None` | 47 | LOW-VALUE | `…_run_full_frame_ocr__mutmut_2`, `…process_frame__mutmut_45,57` |
| A19 | Semantically-identical guard/tuple/token tweaks: falsy swaps (`False↔None`, `best_det_id=""`), degenerate zero-area guards (`<=0`→`<0`: intersection>0 forces union>0/area>0), unreachable defaults (`region_map` default; dedup det-bbox fallbacks), UPPER-cased crop class tokens (filter lowercases), `source="frame"` arg removed (== dataclass default), codec/format case aliases (`"PNG"`/`"png"`, `"utf-8"`/`"UTF-8"`), missing-regions default→None (crash caught → same empty return), `abs(a+b)<0.05`/`abs diff <=0.05` float-unreachable equality bands (verified: no decimal confidence pair hits 0.05 exactly), inner-break→outer-continue, `total_texts>=0` | 45 | EQUIVALENT | `…x__calculate_iou__mutmut_42`, `…_determine_region__mutmut_122`, `…_deduplicate__mutmut_35` |

Per-cluster key membership: `/tmp/wp25/wp44-triage/final_part.json` (`clusters` array lists all keys per cluster).

## Drafted tests (highest-value TEST-GAP clusters)

TDD procedure for each: add test → run against the mutated module (`mutmut`-instrumented copy) and confirm the new assertion FAILS (red) → run against original source and confirm PASSES (green) → spot-check one member key per drafted cluster with the run's harness. All drafted code below is **// UNVERIFIED — not yet run red/green** (harness constraint: no test execution in this sandbox turn).

Style note: follows existing conventions — `from __future__ import annotations`, `MockDetectionInput`/`MockBoundingBox` local dataclasses already in the file, `patch.object(service, "_get_client", autospec=True)` + `AsyncMock` client, `@pytest.mark.asyncio`.

### D1. `test_deduplicate_frame_bbox_untouched` — kills A1 (IoU/overlap `or`→`and`)

```python
def test_iou_one_axis_separated_returns_zero(self) -> None:
    """Boxes separated on exactly one axis must yield IoU 0.0.

    Guards the intersection guard `x2_i <= x1_i or y2_i <= y1_i`; flipping
    `or` to `and` lets one-axis-separated boxes fall through to a negative
    intersection term and a nonzero (or crash-prone) IoU.
    """
    assert _calculate_iou((0, 0, 50, 50), (60, 0, 100, 50)) == 0.0   # x-separated only
    assert _calculate_iou((0, 0, 50, 50), (0, 60, 50, 100)) == 0.0   # y-separated only
    assert _calculate_iou((10, 10, 20, 20), (10, 10, 20, 20)) == 1.0
```
Red on `…x__calculate_iou__mutmut_23` (first assert: `and`-variant reaches `intersection/union` with garbage → != 0.0); green on original. (Overlap-ratio twin `…x__calculate_overlap_ratio__mutmut_23` is killed by the same pattern if a companion assert is added; recommend one-line sibling:
`assert _calculate_overlap_ratio((0, 0, 50, 50), (60, 0, 100, 50)) == 0.0`.)

### D2. `test_determine_region_side_regions_full_map` — kills A11 (region_map side entries/tokens) + A8 h-token/`left` boundary (#52/#54/#56)

Existing tests only hit `(middle,center)→chest`, `top→top`, `bottom→bottom`; every `left`/`right` map entry and the default fallback survive untouched. This test drives all nine grid cells of det_bbox (100,50)-(300,400) whose centers are exactly at rel (1/6, 1/2, 5/6) × same — no boundary equality involved.

```python
def test_determine_region_side_regions_full_map(self, service: SceneOCRService) -> None:
    """Every region_map entry (incl. left/right/center) must be reachable and exact.

    Existing coverage only exercises top/middle/bottom x center; this pins the
    left/right columns and the ("middle","center")="chest" mapping so token or
    key mangles inside region_map / h_region can no longer fall through to the
    "center" default silently.
    """
    det = (100, 50, 300, 400)  # 200x350; column centers rel_x ~0.19 / 0.5 / 0.83
    # top row (center_y ~90 -> rel_y ~0.11 < 0.33)
    assert service._determine_region((120, 40, 146, 66), det) == "top"      # (top,left)
    assert service._determine_region((190, 40, 216, 66), det) == "top"      # (top,center)
    assert service._determine_region((253, 40, 279, 66), det) == "top"      # (top,right)
    # middle row — the discriminating trio: left / chest / right
    assert service._determine_region((120, 210, 146, 240), det) == "left"   # (middle,left)
    assert service._determine_region((190, 210, 216, 240), det) == "chest"  # (middle,center)
    assert service._determine_region((253, 210, 279, 240), det) == "right"  # (middle,right)
    # bottom row
    assert service._determine_region((120, 358, 146, 384), det) == "bottom"
    assert service._determine_region((190, 358, 216, 384), det) == "bottom"
    assert service._determine_region((253, 358, 279, 384), det) == "bottom"
    # h-token mangles ("XXleftXX"/"LEFT") would mis-key the lookup: left cells -> "center" or crash
```
Red: `("XXmiddleXX","left")`-style key breaks (mutmut_109,111,114…) → `region_map` miss → `"center"` ≠ `"left"`; `"XXleftXX"` h-token (mutmut_54) breaks middle-left AND bottom-left lookups. Green: all nine asserts hold on original.

### D3. `test_process_frame_sets_service_match_from_crop_text` — kills B5 (+ co-kills A7 schema-key cluster: `_deduplicate` `value` key UPPER/XX #12/13/65/66/67/68 also break this assert)

No existing test asserts `service_match` on a `process_frame` result — the whole provider-matching leg of the pipeline is unprotected.

```python
@pytest.mark.asyncio
async def test_process_frame_sets_service_match_from_crop_text(
    self,
    service: SceneOCRService,
    test_image: Image.Image,
    mock_detections: list[MockDetectionInput],
) -> None:
    """process_frame must attach the provider match found in detection OCR text."""
    frame_response = MagicMock()
    frame_response.status_code = 200
    frame_response.json.return_value = {"regions": []}  # keep frame leg out of the way

    crop_response = MagicMock()
    crop_response.status_code = 200
    crop_response.json.return_value = {
        "regions": [{"text": "FedEx", "confidence": 0.94, "bbox": [50, 150, 150, 180]}]
    }

    with patch.object(service, "_get_client", autospec=True) as mock_get_client:
        mock_client = AsyncMock()
        calls = {"n": 0}

        async def mock_post(url: str, **kwargs: object) -> MagicMock:
            calls["n"] += 1
            return frame_response if calls["n"] == 1 else crop_response

        mock_client.post.side_effect = mock_post
        mock_get_client.return_value = mock_client

        result = await service.process_frame(test_image, mock_detections)

    assert result.has_service_matches is True
    matched = [d for d in result.detection_ocr.values() if d.service_match is not None]
    assert len(matched) == 1
    assert matched[0].service_match.provider == "FedEx"
```
Red: `matches = self.service_matcher.match_all(all_texts)` → `match_all(None)`/`if t.get("VALUE")` (B5 #30-32) → no match → `has_service_matches` False; `max(matches, key=None)` (B5 #37) → TypeError (single-element max with key=None raises); scene-text `match=None` (#42) is on the scene leg — covered by a companion assert if frame regions carry "123"/"FedEx". Green on original (matcher matches "FedEx" — matcher doc: partial match "FedEx Ground"→FedEx). Note: if `service.service_matcher` is patched elsewhere in the suite, use the real matcher as the fixture does today (`get_service_provider_matcher()`); FedEx is a known provider per `service_provider_matcher.py` docs.

### D4. `test_process_frame_survives_frame_failure` — kills B3 (`return_exceptions=True` removed/flipped)

```python
@pytest.mark.asyncio
async def test_process_frame_survives_frame_failure(
    self,
    service: SceneOCRService,
    test_image: Image.Image,
    mock_detections: list[MockDetectionInput],
) -> None:
    """A failing full-frame OCR leg must degrade to empty, not sink the whole result."""
    crop_response = MagicMock()
    crop_response.status_code = 200
    crop_response.json.return_value = {
        "regions": [{"text": "FedEx", "confidence": 0.94, "bbox": [50, 150, 150, 180]}]
    }

    # Failure must originate INSIDE _run_full_frame_ocr's coroutine boundary so it
    # reaches asyncio.gather (the method's own `except Exception` swallows post-level
    # raises before gather ever sees them). Replacing the bound method is the one
    # deterministic way to fail exactly one leg.
    service._run_full_frame_ocr = AsyncMock(side_effect=RuntimeError("frame down"))

    with patch.object(service, "_get_client", autospec=True) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.return_value = crop_response
        mock_get_client.return_value = mock_client
        result = await service.process_frame(test_image, mock_detections)

    # crop leg succeeded; with return_exceptions=True it must survive
    assert result.has_service_matches is True
    assert result.processing_time_ms >= 0
```
Red: `return_exceptions=False`/`None`/kwarg-removed (B3 #13/16/17) → RuntimeError propagates out of `gather` into `process_frame`'s broad `except Exception` → empty fallback `SceneOCRResult` → `has_service_matches` False. Green: original returns the crop-leg result. Single patch point, deterministic first-failure.

### D5. `test_confidence_boundary_050_included_and_uncertainty_boundaries` — kills A12 + A10

```python
@pytest.mark.asyncio
async def test_confidence_exactly_at_exclude_threshold_included(
    self, service: SceneOCRService, test_image: Image.Image
) -> None:
    """confidence == CONFIDENCE_EXCLUDE (0.50) must be INCLUDED (rule: exclude BELOW 0.50)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "regions": [{"text": "EDGE", "confidence": CONFIDENCE_EXCLUDE, "bbox": [0, 0, 10, 10]}]
    }
    with patch.object(service, "_get_client", autospec=True) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client
        results = await service._run_full_frame_ocr(test_image)
    assert [r.text for r in results] == ["EDGE"]  # `< EXCLUDE` keeps it; `<= EXCLUDE` drops it
```
Red on `…_run_full_frame_ocr__mutmut_34` / (crop twin `_run_crop_ocr__mutmut_93` if repeated via crop).
Companion dedup-side test (A10 #84/#85), same file style:

```python
def test_uncertain_flag_boundaries_inclusive_lower_exclusive_upper(
    self, service: SceneOCRService, mock_detections: list[MockDetectionInput]
) -> None:
    """is_uncertain must be True on [0.50, 0.80) exactly: True@0.50, False@0.80."""
    frame = [
        RawOCRResult(text="A", confidence=0.50, bbox=(10, 10, 50, 40), source="frame"),
        RawOCRResult(text="B", confidence=0.80, bbox=(600, 30, 680, 110), source="frame"),
    ]
    result = service._deduplicate(frame, {}, mock_detections)
    by_value = {t.value: t for t in result.scene_texts}
    assert by_value["A"].is_uncertain is True    # LOW <= conf: < -flip drops it
    assert by_value["B"].is_uncertain is False   # conf < HIGH: <= -flip flags it
```

### D6. `test_quad_bbox_reduced_to_axis_aligned` — kills A13 (+ co-kills A14 bbox-index asserts)

```python
@pytest.mark.asyncio
async def test_full_frame_quad_bbox_reduced_to_axis_aligned(
    self, service: SceneOCRService, test_image: Image.Image
) -> None:
    """Florence 8-point quadrilateral bbox must collapse to axis-aligned (min x, min y, max x, max y)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "regions": [
            # quad: (10,20),(90,25),(88,45),(12,40) -> axis-aligned (10,20,90,45)
            {"text": "QUAD", "confidence": 0.90, "bbox": [10, 20, 90, 25, 88, 45, 12, 40]},
        ]
    }
    with patch.object(service, "_get_client", autospec=True) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client
        results = await service._run_full_frame_ocr(test_image)
    assert results[0].bbox == (10, 20, 90, 45)  # ==8 disabled (==9) leaves 4-pt tuple -> int() of list slice crashes/misreads
```
Red: `len(bbox)==9` skips reduction → 8-element list passed to `int(bbox[0..3])` → bbox `(10,20,90,25)` ≠ expected. Green: original reduces correctly.

## Notes / caveats

- D3-D5 depend on the real `get_service_provider_matcher()` being deterministic in-test (existing `test_process_frame_integration` already relies on it; FedEx is a documented provider). If suite-wide autouse fixtures patch the matcher, assert via injected mock instead (`service.service_matcher = MagicMock(); .match_all.return_value = [ServiceMatch(provider="FedEx", category="DELIVERY", confidence=0.9, risk_modifier="low_risk_service")]`).
- Float-band mutants (`abs(diff) < 0.05` vs `<= 0.05`, `< 1.05` on the *elif* path): verified empirically that no decimal confidence pair has `abs`-difference exactly 0.05 — the `<=` variant is EQUIVALENT (see A19). #46 (`<1.05`) IS reachable on the elif path only when frame conf ≤ crop conf and |f−c|<1.05 — i.e. crop strictly-higher-confidence with IoU-dup: original drops frame, mutant KEEPS frame. Existing test `test_deduplicate_keeps_higher_confidence` asserts `len(texts) >= 1` (too weak). A one-line strengthening of THAT test (`assert len(texts) == 1` with frame conf < crop conf, IoU>0.7) kills A9 #46 without a new test — recommend it.
- `test_full_frame_ocr_success` already asserts `source == "frame"`; its crop-side counterpart (`results["1"][0].source == "crop"` — dead field, LOW-VALUE cluster A18 note) is NOT recommended (field unread by production consumers; verified grep).
- 2 keys unchecked (`null` in meta) — re-verify after the next mutmut sweep completes.
- All drafted tests: **UNVERIFIED — not yet run red/green** (WP4.3 harness forbade execution this wave). TDD loop per test: red on mutant copy diff, green on `backend/services/scene_ocr_service.py`.

Artifacts: raw diffs `/tmp/wp25/wp44-triage/iou-diffs/` (283), machine partition `/tmp/wp25/wp44-triage/final_part.json`, key list `/tmp/wp25/wp44-triage/survivor_keys.txt`.
