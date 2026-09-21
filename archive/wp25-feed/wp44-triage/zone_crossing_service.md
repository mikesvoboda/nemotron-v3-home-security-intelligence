# WP4.4 Triage Dossier — backend/services/zone_crossing_service.py

- **Verdict source:** `mutants/backend/services/zone_crossing_service.py.meta` — 504 keys, all checked, **97 survivors** (exit_code 0). Snapshot taken 2026-09-18 while the run holds the machine (no tests executed, repo untouched).
- **Diff method:** `uv run mutmut show` not used (cache concurrently written); diffs extracted mechanically by parsing the full clobbered-variants copy `mutants/backend/services/zone_crossing_service.py` (AST, body-region diff of each `xǁZoneCrossingServiceǁ<fn>__mutmut_N` against `__mutmut_orig`). 97/97 diffs recovered, 0 missing, 0 empty.
- **Covering tests:** everything routes through `backend/tests/unit/services/test_zone_crossing_service.py` (2004 lines) — confirmed via `tests_by_mangled_function_name` in `mutants/mutmut-stats.json`. Key anchors: `TestComputeEntityId` L100, `TestComputeEntityType` L170, `TestGetDetectionInZone` L231, `TestProcessDetection` L320, `TestEmitWebSocketEvent` L858, `TestEdgeCases` L971, `TestEventSchema` L1154, `TestAdditionalCoverage` L1313, `TestZoneCrossingMetrics` L1579.

## Source landmarks (original, `backend/services/zone_crossing_service.py`)

- `process_detection` L355-457: `detection_id = str(getattr(detection,"id",""))` L381; `thumbnail_url` L382; `timestamp ... or utc_now()` L383; EntityPosition creation L386-390; tracker field writes L393-395; width/height defaulting L402-403; priority sort loop L405-408; exit/enter transition calls L411-440; `elif current_zone_id is not None and entity.entered_at is not None:` dwell branch L442.
- `_handle_zone_enter` L254, `_handle_zone_exit` L203, `_handle_zone_dwell` L298 (threshold gates L324, L330-333), `_emit_zone_enter` L520 (intrusion branch L562), `_emit_zone_exit` L586 (dwell-metric gate L629), `_emit_zone_dwell` L640 (gate L680), `_emit_websocket_event` L686 (channel fallback L699, swallow L704-705).

## Structural note that shapes several classifications

`process_detection` re-defaults `width/height` (L402-403) **and** `_get_detection_in_zone` re-defaults internally (L194-195). So any mutation of either defaulting layer is invisible *unless the caller passes explicit non-default dims* — no test ever does. This makes the dimension cluster a genuine TEST-GAP, while mutants that produce None *before* a re-defaulting layer are EQUIVALENT.

---

## Cluster table (24 clusters, counts sum to 97)

| # | Cluster | Count | Class | Pattern (one line) | Example keys (short) |
|---|---------|-------|-------|--------------------|----------------------|
| 1 | payload_field_values_unasserted | 20 | TEST-GAP | `entity_type` / `detection_id` / `thumbnail_url` args to emit/handle calls replaced by `None` (incl. `detection_id` extraction itself nulled → `"None"`) | `process_detection__mutmut_84`, `_handle_zone_exit__mutmut_15`, `_handle_zone_dwell__mutmut_22` |
| 2 | payload_keys_presence_only | 18 | TEST-GAP | Event-`data` dict keys `"entity_type"`,`"detection_id"`,`"timestamp"`,`"thumbnail_url"`,`"zone_name"` renamed to `XX..XX`/`UPPER` variants — schema tests only do `assert "key" in data` | `_emit_zone_exit__mutmut_16`, `_emit_zone_exit__mutmut_21`, `_emit_zone_dwell__mutmut_22` |
| 3 | publish_payload_unverified | 3 | TEST-GAP | `await self._emit_websocket_event(event)` → `...(None)`; tests assert `publish.called` only, never the published payload | `_emit_zone_enter__mutmut_42`, `_emit_zone_exit__mutmut_59`, `_emit_zone_dwell__mutmut_32` |
| 4 | dwell_threshold_boundary | 2 | TEST-GAP | `<` → `<=` at dwell gate (L324) and `>=` → `>` at dwell rate-limit (L332); tests use 35/40/70 s, never exactly the 30.0 boundary | `_handle_zone_dwell__mutmut_1`, `_handle_zone_dwell__mutmut_9` |
| 5 | dwell_metric_gate_0_to_1 | 2 | TEST-GAP | `observe_zone_dwell_time` gate `dwell_time > 0` → `> 1` (exit L629, dwell L680); sub-second (0 < t ≤ 1) dwells would silently skip the histogram | `_emit_zone_exit__mutmut_37`, `_emit_zone_dwell__mutmut_27` |
| 6 | image_dim_or_to_and | 4 | TEST-GAP | `width/height = image_width or DEFAULT` → `image_width and DEFAULT` (in both `_get_detection_in_zone` L194-195 and `process_detection` L402-403); with any *explicit* width this hands the DEFAULT to a caller that passed real dims | `_get_detection_in_zone__mutmut_4`, `process_detection__mutmut_48`, `process_detection__mutmut_50` |
| 7 | image_dim_swap | 2 | TEST-GAP | Call-site arg drop: `_get_detection_in_zone(detection, zone, height)` / `(…, width, )` — swaps/omits normalization dims | `process_detection__mutmut_74`, `process_detection__mutmut_75` |
| 8 | channel_default_fallback | 4 | TEST-GAP | `getattr(settings,"redis_event_channel","hsi:events")` fallback default → `None` / `""` / `"XXhsi:eventsXX"` / `"HSI:EVENTS"`; every test *stubs the attribute to exist*, so the fallback string itself is never exercised (it is the real-world value when an old settings object lacks the field) | `_emit_websocket_event__mutmut_9`, `_emit_websocket_event__mutmut_15`, `_emit_websocket_event__mutmut_16` |
| 9 | attr_name_string_mut | 5 | TEST-GAP | `getattr(detection,"id"/"thumbnail_path", …)` attr-name → `"XXidXX"`/`"ID"`/`"XXthumbnail_pathXX"`/`"THUMBNAIL_PATH"` on real pydantic `Detection` objects these paths feed → `detection_id="None"`, `thumbnail_url=None` silently | `process_detection__mutmut_14`, `process_detection__mutmut_15`, `process_detection__mutmut_23` |
| 10 | receiver_none_detection | 2 | TEST-GAP | `getattr(detection, …)` / `str(getattr(detection,…))` receiver → `None` (`detection_id` becomes literal `"None"`, thumbnail lost) | `process_detection__mutmut_8`, `process_detection__mutmut_18` |
| 11 | intrusion_branch_flip | 1 | TEST-GAP | `if zone.zone_type == CameraZoneType.ENTRY_POINT:` → `!=` at L562 — the NEM-4138 intrusion metric now fires on *every non-entry-point* enter and never on entry points; test file never sets `zone_type` at all (grep: zero hits for `zone_type|ENTRY_POINT|record_zone_intrusion`) | `_emit_zone_enter__mutmut_34` |
| 12 | exit_cleanup_tracking | 3 | TEST-GAP | Exit cleanup: `if previous_zone_id in self._zone_occupants:` → `not in` (L248); `discard(entity_id)` → `discard(None)` (L249); `_dwell_events_emitted.pop((entity_id,previous_zone_id),…)` → `pop(None,…)` (L250) → ghost occupants keep inflating the occupancy gauge and re-entry can suppress dwell emission | `_handle_zone_exit__mutmut_26`, `_handle_zone_exit__mutmut_27`, `_handle_zone_exit__mutmut_28` |
| 13 | getattr_default_removed | 6 | EQUIVALENT | `getattr(x,"attr",None)` → `getattr(x,"attr",)` — identical call (default omitted ⇒ None) | `_compute_entity_id__mutmut_6`, `process_detection__mutmut_22`, `_compute_entity_type__mutmut_16` |
| 14 | getattr_default_swap_harmless | 3 | EQUIVALENT | `""` ↔ `None` default in `str(getattr(detection,"id",…))` (L381) — both non-existent-attr paths already yield `"None"`; on real objects `.id` always exists. `process_detection_16` (`"XXXX"` default) unreachable on models with the attr | `process_detection__mutmut_10`, `process_detection__mutmut_13`, `process_detection__mutmut_16` |
| 15 | receiver_none_settings | 2 | EQUIVALENT | `settings = get_settings()` → `None` and `getattr(settings,…)` receiver→None (L698-699): tests' settings stub *has* the channel attr while `getattr(None,…)` returns the fallback — same channel string; unstubbed case → exception swallowed by L704 (same observable outcome). `settings` var is otherwise dead | `_emit_websocket_event__mutmut_5`, `_emit_websocket_event__mutmut_7` |
| 16 | priority_sort_default | 3 | EQUIVALENT | `sorted(zones, key=lambda z: getattr(z,"priority",0),…)` default → `None`/omitted/`1`; zones always carry `priority` (all test zones do; model defines it). Note `None` would raise on attr-less zones, but that input never occurs | `process_detection__mutmut_60`, `process_detection__mutmut_63`, `process_detection__mutmut_66` |
| 17 | dim_redefault_equivalent | 4 | EQUIVALENT | `width=None`/`height=None` at L402/403 and pass-None at call-site L406: `_get_detection_in_zone` re-defaults None internally (L194-195) ⇒ identical behavior | `process_detection__mutmut_47`, `process_detection__mutmut_70`, `process_detection__mutmut_71` |
| 18 | elif_and_to_or | 1 | EQUIVALENT | Dwell-branch `and` → `or` (L442): reached only when `previous_zone_id == current_zone_id`, so `current_zone_id is not None` already holds ⇒ left operand true in every reachable state | `process_detection__mutmut_119` |
| 19 | entitypos_type_arg_dropped | 1 | EQUIVALENT | `EntityPosition(entity_id=…, entity_type=entity_type,)` line-collapse → arg omitted ⇒ default `"unknown"`, but L393 immediately overwrites `entity.entity_type = entity_type` before any read | `process_detection__mutmut_39` |
| 20 | log_text_none | 1 | EQUIVALENT | `logger.warning(f"Failed to emit … {e}")` → `logger.warning(None)` — pure log-text change in the error swallow | `_emit_websocket_event__mutmut_22` |
| 21 | exit_dwell_time_empty_str | 1 | EQUIVALENT | `dwell_time = None` → `""` (L233): only flows out when `entity.entered_at` is falsy; every existing exit test gives the entity an `entered_at` (enter precedes exit, or EntityPosition built with one) so the empty-string branch is unreachable under test, and would only surface as `dwell_time=""` on an entered_at-less exit — same shape as the *covered* None case. (Kept EQUIVALENT-with-caveat; cheap to fold into Draft 2's flow if the team wants a strict kill.) | `_handle_zone_exit__mutmut_8` |
| 22 | enrichment_guard_or_equivalent | 2 | EQUIVALENT | `if enrichment and isinstance(enrichment, dict):` → `if enrichment or isinstance(...)` (L138/L166): non-dict truthy enrichment enters the block and raises `AttributeError` on `.get` — same observable failure (exception) as original's fall-through *only differs if caller catches*; for MagicMock non-dicts no test reaches this. The `or` also lets empty-dict through — `.get` returns None → `if entity_id` guard keeps behavior. Net: no test-executed divergence on realistic inputs | `_compute_entity_id__mutmut_9`, `_compute_entity_type__mutmut_19` |
| 23 | tracker_fields_dead | 5 | LOW-VALUE | `EntityPosition(entity_id=None,…)` / `entity_type=None` at creation L387-390 and tracker sync writes `entity.entity_type` / `last_detection_id` / `last_thumbnail_url` → None at L393-395. These fields are write-only: no reader exists outside this module (grep: `last_detection_id`/`last_thumbnail_url` referenced nowhere else; `entity.entity_type` only assigned here) — dead bookkeeping | `process_detection__mutmut_36`, `process_detection__mutmut_41`, `process_detection__mutmut_43` |
| 24 | next_default_removed | 2 | LOW-VALUE | `next((z for z in zones if …), None)` → `next(gen,)` (no default) at L280/L338 — raises `StopIteration` instead of returning None *only* when the zone vanished between selection and handler, an input no test creates (and `test_zone_not_found_in_transition` exercises only the *exit*-side `prev_zone` lookup, whose mutant is absent here) | `_handle_zone_enter__mutmut_4`, `_handle_zone_dwell__mutmut_14` |

**Totals:** TEST-GAP 12 clusters / **66 mutants**; EQUIVALENT 10 clusters / **24 mutants**; LOW-VALUE 2 clusters / **7 mutants**. 66 + 24 + 7 = 97. ✔ (Reconciled mechanically: every surviving key assigned to exactly one cluster via `scratch-zcs/final_clusters.py` — 0 missing, 0 extra.)

---

## Why the TEST-GAP clusters are gaps (per-assertion audit)

- **Clusters 1-3, 9, 10 (payload plumbing, 48 mutants).** `TestProcessDetection::test_emits_enter_event_when_entering_zone` (L344) asserts type/zone_id/zone_name/entity_id/entity_type of an *enter* event only — `detection_id` and `thumbnail_url` values are never asserted anywhere; the exit test (L383) asserts zone_id/entity_id/dwell_time only; `TestEventSchema` (L1154-1303) checks key *presence* (`assert "detection_id" in data`) for enter, and only dwell_time for exit/dwell. The Redis payload itself is checked only via `mock_redis.publish.assert_called_once_with("hsi:events", event)` in `test_emits_event_to_redis` (L862), where `event` is a hand-built dict — the service's *own* emitted payload never passes through. So renaming keys, nulling values, or even publishing `None` are all invisible.
- **Cluster 4 (boundary).** `test_emits_dwell_event_after_threshold` uses +35 s; `test_no_duplicate_dwell_events` uses +35/+40/+70. Nothing sits at exactly 30.0 s, and the rate-limit check `>= DWELL_THRESHOLD` is only tested at 35 s (first emit) → 5 s (suppressed) → 30 s *gap* … wait, 70−40=30 but the stored `last_emitted` is 35 → gap 35 > 30, so the strict-`>` mutant also passes. Exact-boundary gaps both sides.
- **Cluster 5.** `test_emit_zone_exit_skips_dwell_time_when_zero` / `test_emit_zone_dwell_skips_zero_dwell_time` test the boundary from the wrong side only (0.0 skipped); nothing asserts 0 < dwell ≤ 1 is *recorded*.
- **Clusters 6-7 (dims).** `TestAdditionalCoverage::test_uses_default_image_dimensions` (L1317) only ever lets dims *default*; no test passes explicit `image_width/height` to `process_detection`/`_get_detection_in_zone` with pixel bboxes whose zone-hit depends on normalization. (Direct `_get_detection_in_zone` tests pass 1920×1080 = the DEFAULT itself, so or/and and swap are no-ops there.)
- **Cluster 8 (channel fallback).** `test_emits_event_to_redis` stubs `redis_event_channel` *present* on the settings mock, so the `getattr` fallback is only executed in unstubbed code paths where it's swallowed anyway. The fallback default value is the actual deploy-time contract (`config.py` L538 defines `redis_event_channel` but older settings instances/overrides can lack it).
- **Cluster 11 (intrusion).** `record_zone_intrusion` is imported at L27 but never patched/inspected by any test (`grep -n "record_zone_intrusion|zone_type|ENTRY_POINT" test_zone_crossing_service.py` → 0 hits). `test_full_enter_exit_flow_emits_all_metrics` (L1913) patches `record_zone_crossing`/`set_zone_occupancy`/`observe_zone_dwell_time` — but not the intrusion metric, and its zones are plain MagicMocks whose `zone_type` ≠ ENTRY_POINT in a way that can't flip `==` to `!=`.
- **Cluster 12 (exit cleanup).** Occupancy *gauge math* is tested (L1840, L1878) via pre-populated `_zone_occupants`, but no test asserts the set membership itself after an exit (`get_zone_occupants` test at L670 never exits anyone) or that `_dwell_events_emitted[(entity,zone)]` is cleared on exit (`test_clear_entity_removes_dwell_tracking` L1481 covers `clear_entity`, not exit).

---

## Drafted kill-tests (6) — UNVERIFIED, not run red/green

**TDD procedure (one line):** add the test → run it against each mutant variant in its cluster (expect the highlighted assertion to FAIL on the mutant diff) → run against `backend/services/zone_crossing_service.py` original (expect PASS) → only then count the cluster as covered.

All drafts drop into `backend/tests/unit/services/test_zone_crossing_service.py`, reuse its idiom (local import, `MagicMock` detections/zones, `AsyncMock` redis, `patch(...get_settings, autospec=True)`).

### Draft 1 — enter-event full payload + published payload
Kills: cluster 1 (enter-side `process_detection` 84,85,87 / `_handle_zone_enter` 12,14 + 6,7,17,104,106,126,127,129 exit/dwell sides via Draft 2), cluster 10 (8,18), cluster 3 (all 3), cluster 9 (12,14,23,24 — via `detection_id`/`thumbnail_url` value equality). Insert in `TestEventSchema` after `test_enter_event_schema` (~L1198).

```python
    @pytest.mark.asyncio
    async def test_enter_event_full_payload_values(self) -> None:
        """Enter events must carry exact detection-derived field values, and the
        published Redis payload must be the event itself.

        // UNVERIFIED - not yet run red/green
        """
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        ts = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = ts
        detection.thumbnail_path = "/thumbnails/enter.jpg"
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        with patch("backend.core.config.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            events = await service.process_detection(detection, zones=[zone])

        assert len(events) == 1
        data = events[0]["data"]
        assert data["detection_id"] == "123"
        assert data["thumbnail_url"] == "/thumbnails/enter.jpg"
        assert data["entity_type"] == "person"
        assert data["timestamp"] == ts.isoformat()
        # Redis must receive the exact event dict (kills _emit_websocket_event(None))
        mock_redis.publish.assert_called_once_with("hsi:events", events[0])
```

Kill mechanics: `detection_id = None` (pd_6/84/104/126) → `data["detection_id"] is None`; `str(None)` (pd_7) or attr-name swap (pd_14/15) or receiver None (pd_8) → `"None"`; `""` fallback variants die on equality too. `thumbnail_url = None` (pd_17/87/106/129, attr 23/24, receiver pd_18) → mismatch. Handler-arg nulls (`_handle_zone_enter__12/14`) propagate None into the same fields. Publish-payload mutants (`_emit_zone_enter__42` …) publish `None` → `assert_called_once_with("hsi:events", events[0])` fails.

### Draft 2 — exit & dwell event exact schema (keys + values)
Kills: cluster 2 (all 18), cluster 1 (exit/dwell handler args 14,15,17 / 20,21,22,24), residual payload keys. Insert in `TestEventSchema` after `test_dwell_event_schema` (~L1306).

```python
    @pytest.mark.asyncio
    async def test_exit_and_dwell_payload_exact_schema(self) -> None:
        """Exit and dwell payloads must expose the documented key set with the
        detection-derived values — not just key presence.

        // UNVERIFIED - not yet run red/green
        """
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        base = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        def make_det(det_id: int, offset: int, in_zone: bool, thumb: str | None) -> MagicMock:
            det = MagicMock()
            det.id = det_id
            det.object_type = "person"
            det.enrichment_data = {"entity_id": "entity-001"}
            det.detected_at = base + timedelta(seconds=offset)
            det.thumbnail_path = thumb
            if in_zone:
                det.bbox_x, det.bbox_y, det.bbox_width, det.bbox_height = 100, 100, 100, 100
            else:
                det.bbox_x, det.bbox_y, det.bbox_width, det.bbox_height = 1800, 1000, 50, 100
            return det

        expected_keys = {
            "zone_id", "zone_name", "entity_id", "entity_type",
            "detection_id", "timestamp", "thumbnail_url", "dwell_time",
        }

        with patch("backend.core.config.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter at t0
            await service.process_detection(make_det(123, 0, True, "/thumb-0.jpg"), zones=[zone])

            # Dwell at t+35
            dwell_events = await service.process_detection(
                make_det(124, 35, True, "/thumb-1.jpg"), zones=[zone]
            )
            assert len(dwell_events) == 1
            dwell_data = dwell_events[0]["data"]
            assert set(dwell_data.keys()) == expected_keys
            assert dwell_data["zone_name"] == "Front Yard"
            assert dwell_data["entity_type"] == "person"
            assert dwell_data["detection_id"] == "124"
            assert dwell_data["thumbnail_url"] == "/thumb-1.jpg"
            assert dwell_data["timestamp"] == (base + timedelta(seconds=35)).isoformat()
            assert dwell_data["dwell_time"] == 35.0
            # published payload must be the dwell event itself (kills _emit_websocket_event(None))
            mock_redis.publish.assert_called_with("hsi:events", dwell_events[0])

            # Exit at t+60
            exit_events = await service.process_detection(
                make_det(125, 60, False, "/thumb-2.jpg"), zones=[zone]
            )
            assert len(exit_events) == 1
            exit_data = exit_events[0]["data"]
            assert set(exit_data.keys()) == expected_keys
            assert exit_data["zone_name"] == "Front Yard"
            assert exit_data["entity_type"] == "person"
            assert exit_data["detection_id"] == "125"
            assert exit_data["thumbnail_url"] == "/thumb-2.jpg"
            assert exit_data["timestamp"] == (base + timedelta(seconds=60)).isoformat()
            assert exit_data["dwell_time"] == 60.0
            mock_redis.publish.assert_called_with("hsi:events", exit_events[0])
```

Kill mechanics: `set(keys) == expected_keys` fails under every `XX…`/`UPPER` key rename (cluster 2, both emit fns); value equalities fail under handler-arg nulls (`_handle_zone_exit__14/15/17`, `_handle_zone_dwell__20-24`).

### Draft 3 — dwell thresholds pinned at exactly 30 s
Kills: cluster 4 (`_handle_zone_dwell__1`, `__9`). Insert in `TestProcessDetection` after `test_no_duplicate_dwell_events` (~L541).

```python
    @pytest.mark.asyncio
    async def test_dwell_threshold_boundary_exactly_30_seconds(self) -> None:
        """Dwell must emit AT exactly the 30 s threshold (not require >30), and the
        rate-limit must re-emit at an exactly-30 s gap (not require >30).

        // UNVERIFIED - not yet run red/green
        """
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        base = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        def make_det(det_id: int, offset: int) -> MagicMock:
            det = MagicMock()
            det.id = det_id
            det.object_type = "person"
            det.enrichment_data = {"entity_id": "entity-001"}
            det.detected_at = base + timedelta(seconds=offset)
            det.thumbnail_path = None
            det.bbox_x, det.bbox_y, det.bbox_width, det.bbox_height = 100, 100, 100, 100
            return det

        with patch("backend.core.config.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter at t0
            await service.process_detection(make_det(1, 0), zones=[zone])

            # Exactly 30 s in: first dwell event MUST fire (kills `<=` at the gate)
            events = await service.process_detection(make_det(2, 30), zones=[zone])
            assert [e["type"] for e in events] == ["zone.dwell"]

            # 5 s later: suppressed (rate limit holds)
            assert await service.process_detection(make_det(3, 35), zones=[zone]) == []

            # Exactly 30 s after last emit (t=60): re-emit MUST fire (kills `>` in should_emit)
            events = await service.process_detection(make_det(4, 60), zones=[zone])
            assert [e["type"] for e in events] == ["zone.dwell"]
```

### Draft 4 — sub-second dwell times still record the histogram
Kills: cluster 5 (`_emit_zone_exit__37`, `_emit_zone_dwell__27`). Insert in `TestZoneCrossingMetrics` (~L1802, next to the existing zero-dwell tests).

```python
    @pytest.mark.asyncio
    async def test_sub_second_dwell_times_still_record_histogram(self) -> None:
        """The gate is dwell_time > 0, not > 1: a 0.5 s dwell must be observed.

        // UNVERIFIED - not yet run red/green
        """
        from backend.services.zone_crossing_service import ZoneCrossingService

        ts = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        for emit_name, kwargs in [
            ("_emit_zone_exit", {"zone_id_kw": "zone-sub-1", "dwell_time": 0.5}),
            ("_emit_zone_dwell", {"zone_id_kw": "zone-sub-2", "dwell_time": 0.5}),
        ]:
            mock_redis = AsyncMock()
            service = ZoneCrossingService(redis_client=mock_redis)
            zone = MagicMock()
            zone.id = kwargs["zone_id_kw"]
            zone.name = "Test Zone"

            with (
                patch("backend.core.config.get_settings", autospec=True) as mock_settings,
                patch(
                    "backend.services.zone_crossing_service.observe_zone_dwell_time",
                    autospec=True,
                ) as mock_observe,
            ):
                mock_settings.return_value.redis_event_channel = "hsi:events"
                await getattr(service, emit_name)(
                    zone=zone,
                    entity_id="entity-001",
                    entity_type="person",
                    detection_id="123",
                    timestamp=ts,
                    thumbnail_url=None,
                    dwell_time=kwargs["dwell_time"],
                )

            mock_observe.assert_called_once_with(
                zone_id=kwargs["zone_id_kw"], duration_seconds=0.5
            )
```

### Draft 5 — explicit image dimensions drive zone membership (dims are not always the default)
Kills: cluster 6 (`_get_detection_in_zone__4,6`; `process_detection__48,50`) and cluster 7 (`74,75`). Insert in `TestEdgeCases` (~L1152).

```python
    @pytest.mark.asyncio
    async def test_explicit_image_dimensions_drive_zone_membership(self) -> None:
        """A detection that is OUTSIDE the zone under the 1920x1080 default must be
        INSIDE under a real 800x400 frame — the caller's dims must win.

        // UNVERIFIED - not yet run red/green
        """
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-br"
        zone.name = "Bottom Right"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.6, 0.6], [1.0, 0.6], [1.0, 1.0], [0.6, 1.0]]

        base = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-900"}
        detection.detected_at = base
        detection.thumbnail_path = None
        # center = (700, 350) px: normalized (0.875, 0.875) under 800x400 -> inside;
        # (0.365, 0.324) under the 1920x1080 default -> outside.
        detection.bbox_x, detection.bbox_y = 650, 300
        detection.bbox_width, detection.bbox_height = 100, 100

        with patch("backend.core.config.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Same pixel detection: miss under default dims, hit under explicit dims.
            assert service._get_detection_in_zone(detection, zone) is False
            assert service._get_detection_in_zone(detection, zone, 800, 400) is True

            events = await service.process_detection(
                detection, zones=[zone], image_width=800, image_height=400
            )
            assert [e["type"] for e in events] == ["zone.enter"]
            assert events[0]["data"]["zone_id"] == "zone-br"
            assert service.get_entity_zone("entity-900") == "zone-br"
```

### Draft 6 — Redis channel fallback value when settings lack the field
Kills: cluster 8 (`_emit_websocket_event__9,12,15,16`). Insert in `TestEmitWebSocketEvent` (~L927).

```python
    @pytest.mark.asyncio
    async def test_channel_fallback_value_when_settings_lack_field(self) -> None:
        """When the settings object has no redis_event_channel, the fallback must be
        exactly 'hsi:events' — not None/''/'XX…'/'HSI:EVENTS'.

        // UNVERIFIED - not yet run red/green
        """
        from types import SimpleNamespace

        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)
        event = {"type": "zone.enter", "data": {}}

        with patch(
            "backend.services.zone_crossing_service.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = SimpleNamespace()  # no redis_event_channel
            await service._emit_websocket_event(event)

        mock_redis.publish.assert_called_once_with("hsi:events", event)
```

### One-liner sketch for the two smaller TEST-GAP clusters (not drafted in full)

- **Cluster 11 (intrusion flip):** in `TestZoneCrossingMetrics`, patch `record_zone_intrusion` (autospec) + `get_settings`, call `service._emit_zone_enter(zone=<MagicMock with zone_type=CameraZoneType.ENTRY_POINT>, entity_type="person", …)` → `assert_called_once_with(zone_id=…, severity="high")`; repeat with `zone_type=CameraZoneType.YARD` → `assert_not_called()`. (Imports `CameraZoneType` from `backend.models.camera_zone`; members verified: ENTRY_POINT/YARD exist.)
- **Cluster 12 (exit cleanup):** enter an entity into zone-abc, then exit it: `assert service.get_zone_occupants("zone-abc") == []` and `assert ("entity-001","zone-abc") not in service._dwell_events_emitted`; optionally re-enter + dwell-at-30 to prove the cleared dwell map allows re-emission.

---

## Notes for the fix wave

1. **Highest leverage single change:** value-equality payload assertions (Drafts 1-2) — they alone target 48 of the 66 TEST-GAP mutants because clusters 1, 2, 3, 9, 10 all funnel through the same unasserted `event["data"]` surface.
2. Draft 5 assumes `point_in_zone` handles an axis-aligned quad (existing tests use the same quad shape) and that the 800×400-normalized center (0.875, 0.875) passes the edge-inclusive ray-cast used in `zone_service.point_in_zone` — verify on the green run.
3. Cluster 21 (`dwell_time=""`) is the most debatable EQUIVALENT call; if the team reclassifies it TEST-GAP, Draft 2's flow (all exits carry entered_at) still won't kill it — it would need an exit for an entity that never had `entered_at` set.
4. No files under the repo were touched; no tests were run. All statements above are static-analysis-derived — the drafts are UNVERIFIED until the serial pytest lane runs them red-against-mutant / green-against-original.
