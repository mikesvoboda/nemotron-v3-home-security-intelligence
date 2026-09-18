# WP4.4 Triage Dossier — backend/services/package_tracking_service.py

**Date:** 2026-09-17 · **Source:** `mutants/backend/services/package_tracking_service.py.meta` (313 keys: 163 killed, **116 survived**, 34 untested)
**Method note:** the `mutants/…​.py` copy in this run is a plain, byte-identical copy of the original
(mtime identical, zero `__mutmut` markers), so `mutmut show` fails (`Could not find original function`)
and the `.spans` index is stale (07:43 regeneration vs 19:27 plain copy). Diffs were reconstructed
by re-running mutmut 3.8.0's own mutation engine (`create_mutations` + `deep_replace`) **in-memory**
(no files written, no tests run). Alignment proven three ways: (a) all 313 meta keys ⊆ regenerated key
set, extras strictly trailing (= `mutate_only_covered_lines` filter — `_run_yolo_world_detection` has 0
meta keys = uncovered); (b) all 15 `hash_by_function_name` entries match current file content;
(c) per-function kill/survive patterns are line-wise coherent.
**Caveat:** several survivors are not plausible given their listed covering tests (e.g.
process_detection #44 sets `new_package = None` → `None.id` would crash
`test_package_appears_in_zone_state_delivered`, yet meta says survived; #42, check_removal_context #11/#26,
cleanup #2 similar). WP4.3's committed-history + hash-gated verdict reuse likely inherited stale exit
codes for these keys. They are listed as TEST-GAP where the behavior is genuinely unasserted anyway;
the drafted tests kill them under a fresh run.

**Covering tests (all of them):** `backend/tests/unit/services/test_package_tracking_service.py`
(`tests_by_mangled_function_name` — every function's covering set is inside this one file).
Key anchors: serialization test `:1010` (`test_tracked_package_to_dict`), cleanup `:886`
(`test_cleanup_removes_old_packages`), theft detection `:602/:638/:674`, state tracking `:459-596`,
detection filtering `:410`, singleton `:868`, property tests `:961/:986`.

## Cluster table (116 survivors, sum exact)

| #         | Cluster                                                                                                                                                                                                                                    | Function(s)                                                                          | n       | Class                                      | Example keys (≤3)                                                                                     | Note                                                                                                                                                                                         |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ | ------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1         | logger call mutants: message arg → `None`/removed, `extra=` removed, extra-dict keys cased (`XXkXX`/`UPPER`)                                                                                                                               | process_detection, check_removal_context, cleanup_old_packages, mark_package_removed | 31      | LOW-VALUE                                  | `process_detection__mutmut_64`, `check_removal_context__mutmut_16`, `cleanup_old_packages__mutmut_22` | No test uses `caplog`; asserting structured-log keys is brittle. Leave. Full membership: pd 64,66-72; crc 12,14-22; cleanup 18,20-24; mpr 7,8,10-14                                          |
| 2         | `to_dict` output keys renamed/cased (`zone_id→XXzone_idXX/ZONE_ID`, camera_id, removal_time, is_suspicious, class_name)                                                                                                                    | TrackedPackage.to_dict                                                               | 10      | TEST-GAP                                   | `to_dict__mutmut_17,19,21`                                                                            | `test_tracked_package_to_dict:1010` asserts `d["id"]/d["state"]/d["confidence"]` by value but only membership (`"first_seen" in d`) for the rest; renamed keys pass. Killed by Draft A       |
| 3         | `to_dict` None-guards flipped: `if self.X else None` → `(X) and False` / `(X) or True` (first_seen #11,12; last_seen #15,16; removal_time #23)                                                                                             | TrackedPackage.to_dict                                                               | 5       | TEST-GAP                                   | `to_dict__mutmut_11,15,23`                                                                            | `and False` turns a populated timestamp into `None` — value never asserted (membership only). Killed by Draft A                                                                              |
| 4         | detection-dict parsing mutated: key rewrite (`"confidence"→"CONFIDENCE"/"XX..XX"/None`), default/arg removal → `.get` returns default/None, whole assignment → None (bbox L309, confidence L310, class_name L311)                          | process_detection                                                                    | 15      | TEST-GAP                                   | `process_detection__mutmut_13,14,16`                                                                  | No test asserts `result.confidence` / `result.class_name` / `result.bbox` off `process_detection`'s return; parse corruption is silent. Killed by Draft B (+existing `result.state` asserts) |
| 5         | fallback-default tweaks for missing detection keys (`class_name` default → `None`/`"XXpackageXX"`/`"PACKAGE"` #18,23,24; `confidence` default → `1.0` #15)                                                                                 | process_detection                                                                    | 4       | LOW-VALUE                                  | `process_detection__mutmut_15,18`                                                                     | Real change only for malformed detection dicts tests never feed; defensive-default cosmetics                                                                                                 |
| 6         | zone passthrough arg killed: `_find_matching_package(..., zone_id)` → `None` / arg removed (#33, #36)                                                                                                                                      | process_detection                                                                    | 2       | EQUIVALENT                                 | `process_detection__mutmut_33`                                                                        | `zone_id` param is `noqa: ARG002` reserved-unused in `_find_matching_package` — provably no effect                                                                                           |
| 7         | matched-package field updates not asserted: `matched_package.confidence = confidence` → None (#38), `.last_seen = frame_timestamp` → None (#39)                                                                                            | process_detection                                                                    | 2       | TEST-GAP                                   | `process_detection__mutmut_38,39`                                                                     | `test_package_partially_occluded:753` checks count only; never re-reads `.confidence`/`.last_seen` after a match. Killed by Draft B-ext                                                      |
| 8         | re-detection state guard inverted: `if state not in (DELIVERED, PRESENT)` → `in` (L327, #40)                                                                                                                                               | process_detection                                                                    | 1       | TEST-GAP                                   | `process_detection__mutmut_40`                                                                        | Killed only for REMOVED→PRESENT revival, never exercised. Killed by Draft B-ext                                                                                                              |
| 9         | new-package identity plumbing: `package_id = None` (#42), dict registration value → None (#63)                                                                                                                                             | process_detection                                                                    | 2       | LOW-VALUE                                  | `process_detection__mutmut_42`                                                                        | package_id/keying is internal plumbing; asserting dict-key identity is low value. (Verdicts suspect — see caveat)                                                                            |
| 10        | new-package constructor kwargs → None/removed (`new_package=None` #44, `bbox=None` #46, `state=None` #48, `zone_id=None` #51, `camera_id=None` #52, `camera_id=` arg removed #61)                                                          | process_detection                                                                    | 6       | TEST-GAP                                   | `process_detection__mutmut_46,51,52`                                                                  | No test reads these fields off a newly created package. Killed by Draft B                                                                                                                    |
| 11        | camera guard inverted: `if camera_id not in self._tracked_packages` → `in` (L445, #2) — every valid-camera check now returns None                                                                                                          | check_removal_context                                                                | 1       | TEST-GAP                                   | `check_removal_context__mutmut_2`                                                                     | Killed by Draft D/E (existing theft tests touch this line but assert after; verdict suspect)                                                                                                 |
| 12        | `is_suspicious = True`→False in suspicious branch (#11); `is_suspicious = False`→True in benign branch (#26)                                                                                                                               | check_removal_context                                                                | 2       | TEST-GAP                                   | `check_removal_context__mutmut_11,26`                                                                 | Existing tests DO assert `result.is_suspicious` (lines 635/671) — meta survival implausible, likely stale reused verdict; Draft D kills on fresh run                                         |
| 13        | return-count plumbing never asserted: `removed_count = 0→None` #6, `packages_to_remove = []→None` #9, `append(package_id)→append(None)` #11, `+=1` → `=1` #12, `-=1` #13, `+=2` #14                                                        | cleanup_old_packages                                                                 | 6       | TEST-GAP                                   | `cleanup_old_packages__mutmut_11,12,13`                                                               | `test_cleanup_removes_old_packages:886` asserts only `len(tracked)==0`, never the returned count, and uses one old package only. Killed by Draft C                                           |
| 14        | cutoff computation → None (#2) — every comparison crashes                                                                                                                                                                                  | cleanup_old_packages                                                                 | 1       | TEST-GAP                                   | `cleanup_old_packages__mutmut_2`                                                                      | Killed by Draft C (TypeError → test error). Verdict suspect                                                                                                                                  |
| 15        | empty-camera cleanup guard inverted: `if not self._tracked_packages[camera_id]` → `if ...` (#15) — deletes still-populated camera entries                                                                                                  | cleanup_old_packages                                                                 | 1       | TEST-GAP                                   | `cleanup_old_packages__mutmut_15`                                                                     | Killed by Draft C (young package assert)                                                                                                                                                     |
| 16        | summary-log gate `removed_count > 0` → `>= 0` (#16) / `> 1` (#17)                                                                                                                                                                          | cleanup_old_packages                                                                 | 2       | LOW-VALUE                                  | `cleanup_old_packages__mutmut_16,17`                                                                  | Only changes whether a log line fires                                                                                                                                                        |
| 17        | model/image args → None in `_run_yolo_world_detection(model, image)` call (#3, #4)                                                                                                                                                         | detect_packages                                                                      | 2       | LOW-VALUE                                  | `detect_packages__mutmut_3`                                                                           | The method is mocked `autospec=True` in every test — args unobservable by construction                                                                                                       |
| 18        | threshold-filter default mutants that still filter identically: `d.get("confidence", None)` #9 (all test detections carry confidence), arg removed #11 (→None, same)                                                                       | detect_packages                                                                      | 2       | EQUIVALENT                                 | `detect_packages__mutmut_9`                                                                           | Only diverges for detections missing `confidence` — never fed                                                                                                                                |
| 19        | filter default `0→1` (#14): keyless detections now pass threshold                                                                                                                                                                          | detect_packages                                                                      | 1       | LOW-VALUE                                  | `detect_packages__mutmut_14`                                                                          | Malformed-input edge; tests never send keyless detections                                                                                                                                    |
| 20        | filter operator `>=` → `>` at the 0.35 boundary (#15)                                                                                                                                                                                      | detect_packages                                                                      | 1       | TEST-GAP                                   | `detect_packages__mutmut_15`                                                                          | `test_package_detection_filters_low_confidence:410` uses 0.25/0.45, never exactly 0.35. Killed by Draft F                                                                                    |
| 21        | `processing_time_ms` math/None/kwarg mutants (#16,17,18,19,21,23: `*1000→/1000,+,*1001`,→None,kwarg removed)                                                                                                                               | detect_packages                                                                      | 6       | LOW-VALUE                                  | `detect_packages__mutmut_17`                                                                          | Wall-clock telemetry; no test asserts it (only `PackageDetectionResult.to_dict` passes a hand-set 45.5)                                                                                      |
| 22        | zone-match guard `and` → `or` (#2) — removal marks any package in camera with a matching zone OR active state                                                                                                                              | mark_package_removed                                                                 | 1       | TEST-GAP                                   | `mark_package_removed__mutmut_2`                                                                      | No test with two zones + removal. Killed by Draft G                                                                                                                                          |
| 23        | `package.removal_time = removal_timestamp` → None (#6)                                                                                                                                                                                     | mark_package_removed                                                                 | 1       | TEST-GAP                                   | `mark_package_removed__mutmut_6`                                                                      | `test_package_disappears...:488` asserts state, never `removal_time`. Killed by Draft G                                                                                                      |
| 24        | IoU best-match compound condition mutated: `and→or` #12, `>=→>` threshold #13, `>→>=` best_iou tie #14                                                                                                                                     | \_find_matching_package                                                              | 3       | TEST-GAP                                   | `_find_matching_package__mutmut_12,13`                                                                | #12/14 real only with 2+ candidates in one camera (never present); #13 exact-IoU-0.5 edge never exercised. Killed by Draft H                                                                 |
| 25        | crash/sentinel swaps that are unreachable-equivalent: `iou = _calculate_iou(bbox, )` → TypeError (#11)? No — meta survivor because…; `best_match = ""` sentinel (#2) returned as-is → falsy, all callers truthiness-test → None-equivalent | \_find_matching_package                                                              | 2       | EQUIVALENT                                 | `_find_matching_package__mutmut_2`                                                                    | #2: `""` behaves like None for every consumer (`if matched_package`); #11 only fires when camera dict non-empty — see caveat, suspect verdict                                                |
| 26        | IoU disjointness `or` → `and` (#39): edge-touching boxes now intersect with zero/negative-width math                                                                                                                                       | \_calculate_iou                                                                      | 1       | TEST-GAP                                   | `__calculate_iou__mutmut_39`                                                                          | Killed by Draft I (vertical edge-touch asserts 0.0)                                                                                                                                          |
| 27        | IoU boundary strictness `<=→<` (#40,#41) and `union <=0→<0` (#58): touch cases compute 0.0/-0.0 anyway; union-0 unreachable when intersection>0                                                                                            | \_calculate_iou                                                                      | 3       | EQUIVALENT                                 | `__calculate_iou__mutmut_40,41,58`                                                                    | `-0.0 == 0.0` holds; provably same value                                                                                                                                                     |
| 28        | singleton guard `is None → is not None` (#1), init assign → None (#2) in `get_package_tracking_service`                                                                                                                                    | module singleton                                                                     | 2       | EQUIVALENT                                 | `get_package_tracking_service__mutmut_1`                                                              | After first call the guard branch is never re-taken; `test_...singleton:868` calls twice post-init. #2 also guarded                                                                          |
| **total** |                                                                                                                                                                                                                                            |                                                                                      | **116** | 57 TEST-GAP / 47 LOW-VALUE / 12 EQUIVALENT |                                                                                                       |                                                                                                                                                                                              |

## Drafted tests (UNVERIFIED — not yet run red/green)

All go in `backend/tests/unit/services/test_package_tracking_service.py`. Style follows the file
(module-level `pytestmark = pytest.mark.unit`, `@pytest.mark.asyncio` for async, `MagicMock` zones).
TDD procedure for each: apply the cluster's mutant to the source, run the new test → assertion
failure/TypeError (red); revert mutant → green.

### Draft A — to_dict full-value contract (kills clusters 2 + 3; 15 mutants)

Add to `TestPackageTrackingSerialization`:

```python
    def test_tracked_package_to_dict_exact_contract(self) -> None:
        """Every field must serialize under its exact key with its exact value."""
        from backend.services.package_tracking_service import PackageState, TrackedPackage

        first_seen = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        last_seen = datetime(2026, 1, 15, 10, 35, tzinfo=UTC)

        package = TrackedPackage(
            id="pkg_abc",
            bbox={"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
            confidence=0.72,
            state=PackageState.PRESENT,
            first_seen=first_seen,
            last_seen=last_seen,
            zone_id="delivery_zone_001",
            camera_id="front_door",
        )

        d = package.to_dict()

        assert d["zone_id"] == "delivery_zone_001"
        assert d["camera_id"] == "front_door"
        assert d["is_suspicious"] is False
        assert d["class_name"] == "package"
        assert d["removal_time"] is None          # unset -> key present with None
        assert d["first_seen"] == first_seen.isoformat()
        assert d["last_seen"] == last_seen.isoformat()

        package.removal_time = last_seen
        assert package.to_dict()["removal_time"] == last_seen.isoformat()
```

Renamed/cased keys raise KeyError on the asserts (cluster 2); `and False` guard mutants yield
`None` for populated timestamps (cluster 3). Passes on original since every asserted value is what
`to_dict` produces today.

### Draft B — new-package field population (kills cluster 10; with cluster 4 via state/field asserts, 6+15)

Add to `TestPackageStateTracking`:

```python
    @pytest.mark.asyncio
    async def test_process_detection_new_package_populates_all_fields(self) -> None:
        """A first-time detection must store the full parsed detection in the tracker."""
        from backend.services.package_tracking_service import PackageState, PackageTrackingService

        service = PackageTrackingService()
        detection = {
            "class_name": "Amazon box",
            "confidence": 0.72,
            "bbox": {"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.7},
        }
        zone = MagicMock()
        zone.id = "delivery_zone_001"
        ts = datetime.now(UTC)

        result = await service.process_detection(
            detection=detection,
            camera_id="front_door",
            zone=zone,
            frame_timestamp=ts,
        )

        assert result.camera_id == "front_door"
        assert result.zone_id == "delivery_zone_001"
        assert result.bbox == detection["bbox"]
        assert result.confidence == 0.72
        assert result.class_name == "Amazon box"
        assert result.state == PackageState.DELIVERED
        assert result.first_seen == ts
        assert result.last_seen == ts
        assert service.get_tracked_packages("front_door") == [result]
```

Cluster-4 key rewrites return `.get` defaults → `confidence == 0.0` fails; kwargs→None fail their
field asserts; `new_package = None` raises AttributeError.

### Draft C — cleanup return count + camera-entry retention (kills clusters 13, 14, 15; 8 mutants)

Replace/extend in `TestPackageTrackingServiceLifecycle`:

```python
    @pytest.mark.asyncio
    async def test_cleanup_old_packages_returns_removed_count(self) -> None:
        """Cleanup returns the number deleted and keeps young packages and the camera entry."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()
        zone = MagicMock()
        zone.id = "delivery_zone_001"
        base = datetime.now(UTC)
        boxes = [
            {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
            {"x1": 0.5, "y1": 0.5, "x2": 0.6, "y2": 0.6},
            {"x1": 0.1, "y1": 0.6, "x2": 0.2, "y2": 0.7},
        ]
        ages_hours = [25, 30, 1]  # two stale, one young
        for bbox, age in zip(boxes, ages_hours):
            await service.process_detection(
                detection={"class_name": "package", "confidence": 0.7, "bbox": bbox},
                camera_id="front_door",
                zone=zone,
                frame_timestamp=base - timedelta(hours=age),
            )

        removed = await service.cleanup_old_packages(retention_hours=24)

        assert removed == 2
        tracked = service.get_tracked_packages("front_door")
        assert len(tracked) == 1
        assert tracked[0].bbox == boxes[2]
```

`+=1` mutants return 1/-2/4 (fail `== 2`); `append(None)` / `removed_count = None` /
`packages_to_remove = None` / `cutoff_time = None` crash (error); the young-package +
`bbox` asserts kill the inverted empty-camera-cleanup guard (#15).

### Draft D — removal-context suspiciousness quadrants (kills cluster 12; 2 mutants)

Add to `TestPackageTheftDetection`:

```python
    @pytest.mark.asyncio
    async def test_check_removal_context_all_presence_combinations(self) -> None:
        """Suspicious iff NEITHER household member NOR delivery person present (all 4 quadrants)."""
        from backend.services.package_tracking_service import PackageState, PackageTrackingService

        ts = datetime.now(UTC)
        cases = [
            (False, False, True),   # nobody: theft
            (True, False, False),   # homeowner: benign
            (False, True, False),   # courier: benign
            (True, True, False),    # both: benign
        ]
        for i, (member, courier, suspicious) in enumerate(cases):
            service = PackageTrackingService()
            zone = MagicMock()
            zone.id = "delivery_zone_001"
            x = 0.05 * i
            await service.process_detection(
                detection={
                    "class_name": "package",
                    "confidence": 0.7,
                    "bbox": {"x1": x, "y1": 0.1, "x2": x + 0.05, "y2": 0.2},
                },
                camera_id="front_door",
                zone=zone,
                frame_timestamp=ts,
            )

            result = await service.check_removal_context(
                camera_id="front_door",
                zone_id="delivery_zone_001",
                household_member_present=member,
                removal_timestamp=ts,
                delivery_person_present=courier,
            )

            assert result is not None, f"case {cases[i]}"
            assert result.is_suspicious is suspicious
            expected = (
                PackageState.SUSPICIOUS_REMOVAL if suspicious else PackageState.REMOVED
            )
            assert result.state == expected
            assert result.removal_time == ts
```

#11 breaks case 0 (`is_suspicious` False vs True); #26 breaks cases 1-3 (benign branch sets True).

### Draft E — unknown-camera guard (kills cluster 11; 1 mutant)

```python
    @pytest.mark.asyncio
    async def test_check_removal_context_unknown_camera_returns_none(self) -> None:
        """Camera never seen must yield None, not a crash or a package."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()
        result = await service.check_removal_context(
            camera_id="ghost_cam",
            zone_id="delivery_zone_001",
            household_member_present=False,
            removal_timestamp=datetime.now(UTC),
        )
        assert result is None
```

(Draft D also kills #2 — flipped guard returns None on a _known_ camera → `result.is_suspicious`
AttributeError.)

### Draft F — confidence boundary is inclusive (kills cluster 20; 1 mutant)

```python
    @pytest.mark.asyncio
    async def test_package_detection_includes_exact_threshold_confidence(
        self, mock_yolo_world_model
    ) -> None:
        """A detection at exactly 0.35 must pass the filter (>=, not >)."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()
        mock_detection = {
            "class_name": "package",
            "confidence": 0.35,
            "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
            "class_id": 0,
        }

        with patch.object(
            service, "_run_yolo_world_detection", return_value=[mock_detection], autospec=True
        ):
            result = await service.detect_packages(mock_yolo_world_model, MagicMock())

        assert result.has_packages is True
        assert len(result.detections) == 1
```

### Draft G — removal marks zone_id + removal_time only for the matching zone (kills clusters 22, 23; 2 mutants)

Add to `TestPackageStateTracking`:

```python
    @pytest.mark.asyncio
    async def test_mark_package_removed_sets_removal_time_and_targets_zone(self) -> None:
        """mark_package_removed stamps removal_time and ignores packages in other zones."""
        from backend.services.package_tracking_service import PackageState, PackageTrackingService

        service = PackageTrackingService()
        ts = datetime.now(UTC)
        for zone_id, bbox in [
            ("zone_a", {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2}),
            ("zone_b", {"x1": 0.7, "y1": 0.7, "x2": 0.8, "y2": 0.8}),
        ]:
            zone = MagicMock()
            zone.id = zone_id
            await service.process_detection(
                detection={"class_name": "package", "confidence": 0.7, "bbox": bbox},
                camera_id="front_door",
                zone=zone,
                frame_timestamp=ts,
            )

        removal_ts = ts + timedelta(seconds=30)
        result = await service.mark_package_removed(
            camera_id="front_door",
            zone_id="zone_a",
            removal_timestamp=removal_ts,
        )

        assert result is not None
        assert result.zone_id == "zone_a"
        assert result.state == PackageState.REMOVED
        assert result.removal_time == removal_ts
        # the zone_b package is untouched
        other = service.get_tracked_packages("front_door", zone_id="zone_b")[0]
        assert other.state == PackageState.DELIVERED
        assert other.removal_time is None
```

`or`-flip (#2) marks zone_b's package too → its state assert fails; #6 (`removal_time = None`) fails
the `removal_time` assert.

### Draft H — best-match selection semantics (kills cluster 24; 3 mutants)

Add a new class near `_calculate_iou` tests:

```python
class TestIouMatchingSemantics:
    """_find_matching_package must keep threshold AND best-score semantics."""

    @pytest.mark.asyncio
    async def test_exact_iou_at_threshold_matches(self) -> None:
        """IoU of exactly 0.5 counts as a match (>=, not >)."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()
        # Two unit-height boxes: A=[0,0,0.5,1], query=[0.25,0,0.75,1] -> IoU = 1/3 < 0.5 (no match);
        # A=[0,0,0.5,1], query=[0.0,0,0.5,0.5] -> inter=0.25, union=0.5 -> IoU exactly 0.5
        await service.process_detection(
            detection={"class_name": "p", "confidence": 0.9,
                       "bbox": {"x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 1.0}},
            camera_id="cam", zone=None, frame_timestamp=datetime.now(UTC),
        )
        result = await service.process_detection(
            detection={"class_name": "p", "confidence": 0.9,
                       "bbox": {"x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 0.5}},
            camera_id="cam", zone=None, frame_timestamp=datetime.now(UTC),
        )
        assert len(service.get_tracked_packages("cam")) == 1  # matched, not duplicated
        assert result.state in (PackageState.DELIVERED, PackageState.PRESENT)

    @pytest.mark.asyncio
    async def test_best_iou_candidate_wins_over_or_and_ties(self) -> None:
        """With two candidates, the strictly-best IoU (above threshold) is chosen, not the first."""
        from backend.services.package_tracking_service import PackageTrackingService

        service = PackageTrackingService()
        ts = datetime.now(UTC)
        near = {"x1": 0.0, "y1": 0.0, "x2": 0.4, "y2": 0.4}   # will overlap query strongly
        far = {"x1": 0.05, "y1": 0.05, "x2": 0.45, "y2": 0.45}  # weaker overlap with query
        for tag, bbox in (("near", near), ("far", far)):
            await service.process_detection(
                detection={"class_name": tag, "confidence": 0.9, "bbox": bbox},
                camera_id="cam", zone=None, frame_timestamp=ts,
            )
        result = await service.process_detection(
            detection={"class_name": "query", "confidence": 0.9,
                       "bbox": {"x1": 0.0, "y1": 0.0, "x2": 0.4, "y2": 0.4}},
            camera_id="cam", zone=None, frame_timestamp=ts,
        )
        # identical bbox to "near" -> IoU 1.0 must beat "far" (IoU 16/49 ~ 0.327 < threshold)
        assert result.class_name == "near"
        assert len(service.get_tracked_packages("cam")) == 2
```

`and→or` (#12) picks any candidate above-threshold-or-better, `>` (#13) misses the exact-0.5 case
(created 2nd package), `>=` tie-break (#14) changes which candidate wins in the two-candidate
dict-iteration case. NOTE: the 0.5-exact arithmetic (`0.25/0.5`) is float-exact here
(powers of two); the second test's IoUs (1.0 and 16/49) keep it robust.

### Draft I — IoU edge-touching semantics (kills cluster 26; 1 mutant)

```python
class TestIoUCalculation:
    def test_identical_boxes_iou_is_one(self) -> None:
        from backend.services.package_tracking_service import _calculate_iou

        b = {"x1": 0.2, "y1": 0.1, "x2": 0.6, "y2": 0.9}
        assert _calculate_iou(b, b) == pytest.approx(1.0)

    def test_edge_touching_vertically_is_zero(self) -> None:
        """Boxes sharing only an edge have zero intersection -> IoU 0 (or-branch, <= boundary)."""
        from backend.services.package_tracking_service import _calculate_iou

        a = {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 0.5}
        b = {"x1": 0.0, "y1": 0.5, "x2": 1.0, "y2": 1.0}
        assert _calculate_iou(a, b) == 0.0

    def test_edge_touching_horizontally_is_zero(self) -> None:
        from backend.services.package_tracking_service import _calculate_iou

        a = {"x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 1.0}
        b = {"x1": 0.5, "y1": 0.0, "x2": 1.0, "y2": 1.0}
        assert _calculate_iou(a, b) == 0.0

    def test_partial_overlap_iou_value(self) -> None:
        from backend.services.package_tracking_service import _calculate_iou

        a = {"x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 1.0}
        b = {"x1": 0.25, "y1": 0.0, "x2": 0.75, "y2": 1.0}
        assert _calculate_iou(a, b) == pytest.approx(1 / 3)
```

#39 (`or→and`) makes the vertical-touch case compute `(1-0)*(0.5-0)=0.5` → returns 0.5 ≠ 0.0 (red);
green on original.

## Cluster-to-draft map

| Cluster                               | Killed by                                                                                                                                                            |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2, 3 (to_dict, 15)                    | Draft A                                                                                                                                                              |
| 4, 10 (pd parse/kwargs, 21)           | Draft B                                                                                                                                                              |
| 13, 14, 15 (cleanup, 8)               | Draft C                                                                                                                                                              |
| 12 (crc suspicious, 2)                | Draft D                                                                                                                                                              |
| 11 (crc guard, 1)                     | Drafts D + E                                                                                                                                                         |
| 20 (detect `>` boundary, 1)           | Draft F                                                                                                                                                              |
| 22, 23 (mark_removed, 2)              | Draft G                                                                                                                                                              |
| 24 (find_matching semantics, 3)       | Draft H                                                                                                                                                              |
| 26 (IoU `or→and`, 1)                  | Draft I                                                                                                                                                              |
| 7 (matched .confidence/.last_seen, 2) | Draft B extension: after `process_detection` of a second overlapping frame, assert `result.confidence == 0.42 and result.last_seen == ts2` (same pattern as Draft B) |
| 8 (re-detection guard, 1)             | mark removed, then re-detect same bbox; assert `result.state == PackageState.PRESENT`                                                                                |
| LOW-VALUE (47) / EQUIVALENT (12)      | intentionally not killed — log plumbing + provable no-ops                                                                                                            |

**WP4.4 recommendation:** land Drafts A, B, C, D first (kill 39 survivors for ~4 tests); F-I are
cheap single-purpose add-ons. Also worth a harness bug: re-run this module with a fresh mutants copy
— at least ~8 "survivors" (pd #42/#44, crc #2/#11/#26, cleanup #2) crash their _existing_ listed
covering tests and are almost certainly stale reused verdicts from the committed-history pipeline.
