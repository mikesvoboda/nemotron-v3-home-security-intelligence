# WP4.4 Triage Dossier — backend/services/insight_generator.py

- **Source under mutation:** `backend/services/insight_generator.py` (467 lines)
- **Survivors: 135** (meta also holds 160 killed, 21 unchecked as of this snapshot; the live run
  re-checked verdicts mid-triage — first snapshot was 134, one more landed while triaging).
  Verdicts read from `mutants/backend/services/insight_generator.py.meta`.
- **All 135 diffs captured:** `/tmp/wp25/wp44-triage/ig-diffs.txt` (via `uv run mutmut show`,
  no cache timeouts encountered).
- **Covering tests:** `backend/tests/unit/services/test_insight_generator.py` (604 lines) is the
  **only** file that covers any of the 7 mutated functions (checked via
  `mutants/mutmut-stats.json` → tests_by_mangled_function_name; all calls flow through the public
  `generate_insights` entry point). Key lines cited per cluster; fixtures are `MagicMock`
  events at lines 33–87.

## Key shorthand

Full keys are `backend.services.insight_generator.xǁInsightGeneratorǁ<fn>__mutmut_<N>`.
Tables use `gcs`=_gather_camera_stats, `ges`=_gather_entity_stats, `gei`=_generate_entity_insights,
`gti`=_generate_trend_insights, `gca`=_generate_camera_insights, `gnai`=_generate_no_activity_insight,
`gi`=_generate_insights (public).

## Why 135 survive (root causes)

1. **MagicMock hides attribute names.** Every fixture event (test file :33–87) is a `MagicMock`,
   so `hasattr(event, "XXcameraXX")`, `getattr(event, "RISK_LEVEL", None)`,
   `getattr(event, "XXrisk_levelXX", None)` all behave exactly like the originals — mocks auto-create
   any attribute. A plain object (`SimpleNamespace`) is needed to kill string-argument mutants.
   This is the single biggest survivor source (cluster T1).
2. **Vacuously-guarded assertions.** `test_known_person_lower_priority` (:259–278) wraps every
   assert in `if entity_insights:` / `if known_person_insights:` — if a mutant deletes the known-persons
   insight entirely, the test passes having asserted nothing. Same `if`-guard pattern in
   `test_activity_below_baseline` (:362), `test_trend_insight_percentage` (:379), `test_no_events`
   (:453), `test_event_without_camera_relationship` (:518).
3. **Weak disjunction/substring asserts.** e.g. `assert "2" in desc or "events" in desc.lower()` (:190),
   `"camera" in action_url or "front_door" in action_url` (:208 — survives `action_url=None`? no, None
   fails on `.action_url is not None` (:207) — but survives URL casing because the substring
   "camera" stays), `"above" in desc or "increase" in desc` (:341), `priority >= 8` (:257),
   `len(camera_insights) >= 1` everywhere. These accept the slop the mutants produce.
4. **No boundary tests** at the 50 %-increase / −30 %-decrease thresholds, at
   `baseline<=0 & current==0`, or at the singular ("Review 1 event") description branch.

## Cluster table (authoritative; counts sum to 135)

TEST-GAP: 24 clusters / 79 keys. LOW-VALUE: 6 clusters / 49 keys. EQUIVALENT: 4 clusters / 7 keys.

| # | Pattern | N | Class | Example keys |
|---|---------|---|-------|--------------|
| T1 | risk_level fetched from wrong/mangled attr (`=None`, `getattr(None,…)`, `"XXrisk_levelXX"`, `"RISK_LEVEL"`) in gcs — invisible under MagicMock, silently zeroes high_critical_count for real Events | 4 | TEST-GAP | gcs_23, gcs_24, gcs_29 |
| T2 | high/critical membership flipped/sentinelled (`not in`, `"XXhighXX"`, `"XXcriticalXX"`) in gcs | 3 | TEST-GAP | gcs_31, gcs_32, gcs_34 |
| T3 | membership literal casing (`"HIGH"`, `"CRITICAL"`) — real Events persist lowercase (models/event.py:238 CHECK constraint), so this silently stops counting | 2 | TEST-GAP | gcs_33, gcs_35 |
| T4 | `risk_score or 0` → `and 0` makes max(0, None) raise TypeError for Events with NULL risk_score | 1 | TEST-GAP | gcs_40 |
| T5 | high_critical_count arithmetic (`+=1`→`=1`/`-=1`/`+=2`) — feeds camera priority 6-vs-5 + " (N high/critical)" suffix, never asserted | 3 | TEST-GAP | gcs_36, gcs_37, gcs_38 |
| T6a | camera-name resolution in gcs (`hasattr "XXcameraXX"/"CAMERA"`, `camera_id=None` → action_url "/timeline?camera_id=None") | 3 | TEST-GAP | gcs_9, gcs_10, gcs_16 |
| T6b | camera-name resolution duplicated in ges + `name or` → `name and` (silently swaps name→id) | 4 | TEST-GAP | ges_14, ges_18, ges_22 |
| T7 | event_count arithmetic + singular/plural branch (`==1`→`!=1`/`==2`) — "Review 1 event" vs "1 events" never pinned | 4 | TEST-GAP | gcs_20, gcs_22, gca_17, gca_18 |
| T8 | person counters (`known +=1`→`=1`/`-=1`/`+=2`, `unknown +=1`→`+=2`) flow into asserted-but-too-loose descriptions | 4 | TEST-GAP | ges_44, ges_45, ges_49 |
| T9 | unknown_person_cameras dedupe `not in`→`in` (list stops filling) | 1 | TEST-GAP | ges_50 |
| T10 | recognized safety-default `False`→`True` — missing `recognized` key flips unknown→known classification | 1 | TEST-GAP | ges_43 |
| T11 | `continue`→`break` on entity-less event — truncates stats for mixed event lists (testable with SimpleNamespace events) | 1 | TEST-GAP | ges_11 |
| T12 | known-persons gate + plural branches (`>0`→`>=0` phantom "0 recognized persons detected" insight; `>0`→`>1`; `==1`→`!=1`/`==2`) — surviving only because :259 test is `if`-guarded | 4 | TEST-GAP | gei_34, gei_35, gei_36 |
| T13 | camera-list join in unknown-persons description: `", ".join`→None(crash)/`"XX, XX".join`, slice `[:3]`→`[:4]`, `>3`→`>=3` (" and 0 more")/`>4` | 5 | TEST-GAP | gei_10, gei_13, gei_16 |
| T14 | action_url kwarg removed → None across gei(4: 23,28,46,51)/gti(6: 12,17,34,39,53,58) builds — the click-through URL IS the feature contract; existing url asserts too weak/`if`-guarded. (The one removal whose value equalled the dataclass default, gnai_9, is instead E1.) | 10 | TEST-GAP | gei_23, gei_46, gti_12 |
| T15 | `type=InsightType.X` → `type=None` — str(Enum), so `type.value`/`to_dict()` raises AttributeError → 500s the summaries API (routes/summaries.py:99) | 4 | TEST-GAP | gnai_1, gti_8, gti_49 |
| T16 | `title=` → None (gca/gti builds) — AttributeError in to_dict | 4 | TEST-GAP | gca_28, gti_10, gti_32 |
| T17 | `description=` → None (gei/gti/gnai) — AttributeError in to_dict | 4 | TEST-GAP | gei_38, gti_11, gnai_4 |
| T18 | gnai `priority=None` — breaks sort key + to_dict | 1 | TEST-GAP | gnai_2 |
| T19 | trend boundary gates: `current_count>0`→`>=0` (phantom at baseline 0,count 0) and `>1`; `>=50`→`>50`; `<=-30`→`<-30` (exact -30 loses insight); `<=-30`→`<=+30` (30 % dip mislabeled "below baseline") | 5 | TEST-GAP | gti_5, gti_28, gti_46 |
| T20 | pct_change formula (`/`→`*` kills all trend insights; `*100`→`*101`) — description percent is user-visible | 2 | TEST-GAP | gti_25, gti_27 |
| T21 | camera sort `reverse=True`→False/None/removed (insights move to the LEAST active cameras) + top-3 cap → 4 | 4 | TEST-GAP | gca_5, gca_8, gca_10 |
| T22 | camera HIGH-priority threshold `>0`→`>=0` (everything HIGH) / `>1` (single high event demoted) + same flip on suffix append | 4 | TEST-GAP | gca_13, gca_14, gca_21 |
| G1 | public `generate_insights(max_insights=5)` default → 6 (only reachable via default-arg callers; sole prod caller summaries.py:95 passes 5 explicitly — still public contract, docstring promises 5) | 1 | TEST-GAP | gi_1 |
| L1 | title cosmetic casing/sentinel text across all 6 builders (`"XXQuiet PeriodXX"`, `"camera activity"`, `"CAMERA ACTIVITY"`, …) — content is product copy, no consumer pins it (frontend renders the string as a prop; API passes through). Only the 4 `title=None` crashers are T16; cosmetic casing = cosmetic change | 21 | LOW-VALUE | gca_36, gei_29, gti_18 |
| L2 | description cosmetic casing/sentinel (fixed strings in gei singular branches + gnai) | 7 | LOW-VALUE | gei_7, gei_39, gnai_13 |
| L3 | action_url cosmetic casing/sentinel (`"/TIMELINE"`, `"XX/analyticsXX"`, `"/TIMELINE?ENTITY_TYPE=…"`) — real behavior change, but no test should pin marketing-grade URL casing; a typo here would also make D3/D4 exact-URL asserts red | 10 | LOW-VALUE | gei_32, gti_21, gti_44 |
| L4 | gcs `risk_score` fetch degraded (`getattr(None,…)`, `or 1`, `max(...)→None`) — field `max_risk_score` is **write-only**: grep shows no reader of `_CameraStats.max_risk_score` anywhere in backend/ | 3 | LOW-VALUE | gcs_41, gcs_48, gcs_49 |
| L5 | vehicle counting all mutations (`==`→`!=`, casing, arithmetic) — field `_EntityStats.vehicles` is **write-only**: no reader anywhere in backend/ (all other `.vehicles` hits are the unrelated entity_recognition_service class) | 6 | LOW-VALUE | ges_52, ges_55, ges_57 |
| L6 | `entity.get("type","").lower()` default removed → AttributeError, but only for entity dicts lacking `"type"`; `isinstance(entity, dict)` guard already covers the documented shape | 2 | LOW-VALUE | ges_27, ges_29 |
| E1 | `action_url=None` kwarg removed in gnai — dataclass default is None; semantically identical | 1 | EQUIVALENT | gnai_9 |
| E2 | `entity.get("recognized", False)` default dropped/None'd — falsy → falsy, same branch | 2 | EQUIVALENT | ges_38, ges_40 |
| E3 | entity-type default `""`→`"XXXX"` — `"xxxx"` never equals `"person"`/`"vehicle"`; unclassified dicts stay unclassified | 1 | EQUIVALENT | ges_32 |
| E4 | getattr **default-arg** dropped where the attribute always exists (`getattr(event, "risk_level", )` / `"risk_score", )` — risk_level/risk_score/camera/entities are always-present attributes on Event per models/event.py; Event.camera is a non-nullable FK relationship) → same value | 3 | EQUIVALENT | gcs_28, gcs_45, ges_7 |

Coverage sanity: 79 + 49 + 7 = 135 = survivors_total. Partition validated programmatically
(135 unique keys, zero overlap, zero unassigned).

## Which tests execute-but-don't-assert (TEST-GAP evidence, file = backend/tests/unit/services/test_insight_generator.py)

- T1/T2/T3/T5/T22: every camera test (:136–211, :457, :499) calls generate_insights over events
  with `risk_level` set, but no test asserts camera priority or the " (N high/critical)" suffix.
- T6a/T6b/T7: `test_event_without_camera_relationship` (:499–525) is *designed* for the fallback
  but only asserts `isinstance(insights, list)` + a disjunction (:522) that the id-swap mutant also
  satisfies; `test_camera_insight_includes_event_count` (:165) accepts `"2" in desc or "events" in …`.
- T8/T12/T13: `test_multiple_unknown_persons_count` (:280) accepts "2"/"multiple"/"persons"
  (survives the doubling); the only known-persons test (:259) is if-guarded so the phantom/missing
  insight mutants ride through.
- T14/T16/T17/T19/T20: `test_activity_below_baseline` (:348) / `test_trend_insight_percentage` (:366)
  skip their assert when the mutant suppresses the insight; `test_baseline_zero` (:527) asserts only
  `isinstance(list)`; no test calls the privates directly.
- T1: all fixtures are MagicMock (:33–87) — the mutated attribute *strings* can never diverge under
  mocks; no test uses a plain object.

## Drafted tests (WP4.4 candidates) — UNVERIFIED, not yet run red/green

All follow the existing file's style: `pytestmark = pytest.mark.unit` at module level, classes,
`MagicMock` fixtures where possible (new `types.SimpleNamespace` objects where the mutant is a
*string attribute name* — MagicMock cannot expose those). TDD procedure for each: add the test, run
`uv run pytest backend/tests/unit/services/test_insight_generator.py -k <name>` — assert must fail
(red) on the mutant source, pass (green) on original; the red proof is the mutation diff above.

### D1 — exact camera-insight text, priority and thresholds (kills T2, T3, T5, T6a-url, T7, T22, T16-gca + L1-gca)

```python
class TestCameraInsightExactText:
    """Pin the camera-insight priority rules and description grammar.

    Kills: gcs_31-38 (high/critical membership + counting), gcs_16 (camera_id None),
    gca_13/14/21/22 (thresholds), gca_17/18 (singular/plural), gcs_20/22 (counting),
    gca_28/36/37/38 (title None/casing).
    """

    _LOW = ...  # module-level helper events via _plain_event below

    @staticmethod
    def _plain_event(eid: int, cam_id: str, cam_name: str, risk_level: str, risk_score: int):
        """Non-mock event: MagicMock auto-creates attrs and hides name mutations."""
        return SimpleNamespace(
            id=eid, camera_id=cam_id, camera=SimpleNamespace(name=cam_name),
            risk_level=risk_level, risk_score=risk_score, entities=[],
        )

    def test_single_high_event_gets_high_priority_and_suffix(
        self, insight_generator: InsightGenerator, mock_event: MagicMock
    ) -> None:
        """One high-risk event: priority 6, singular noun, '(1 high/critical)' suffix."""
        insights = insight_generator.generate_insights([mock_event])
        cam = [i for i in insights if i.type == InsightType.CAMERA][0]
        assert cam.title == "Camera Activity"
        assert cam.priority == InsightGenerator.PRIORITY_CAMERA_HIGH  # 6, not 5
        assert cam.description == "Review 1 event from Front Door (1 high/critical)"
        assert cam.action_url == "/timeline?camera_id=front_door"

    def test_low_risk_camera_omits_high_critical_suffix_and_is_medium(
        self, insight_generator: InsightGenerator
    ) -> None:
        e = self._plain_event(1, "cam1", "Front Door", "low", 10)
        cam = [i for i in insight_generator.generate_insights([e])
               if i.type == InsightType.CAMERA][0]
        assert cam.priority == InsightGenerator.PRIORITY_CAMERA_MEDIUM  # 5
        assert cam.description == "Review 1 event from Front Door"  # no suffix
        assert cam.action_url == "/timeline?camera_id=cam1"

    def test_event_and_high_critical_counts_are_exact(
        self, insight_generator: InsightGenerator, mock_critical_event: MagicMock
    ) -> None:
        """4 events / 2 high on Front Door + 1 critical on Driveway: exact strings."""
        events = [
            self._plain_event(1, "front_door", "Front Door", "low", 10),
            self._plain_event(2, "front_door", "Front Door", "medium", 50),
            self._plain_event(3, "front_door", "Front Door", "high", 90),
            mock_critical_event,  # driveway, critical — also drives gcs_34/35
        ]
        cams = [i for i in insight_generator.generate_insights(events)
                if i.type == InsightType.CAMERA]
        by_url = {c.action_url: c for c in cams}
        front = by_url["/timeline?camera_id=front_door"]
        assert front.priority == InsightGenerator.PRIORITY_CAMERA_HIGH
        assert front.description == "Review 4 events from Front Door (2 high/critical)"
        drive = by_url["/timeline?camera_id=driveway"]
        assert drive.priority == InsightGenerator.PRIORITY_CAMERA_HIGH
        assert drive.description == "Review 1 event from Driveway (1 high/critical)"
```

TDD: e.g. `gcs_37` (`+=1`→`-=1`) makes front description "…(-2 high/critical)" red; original green.
`from types import SimpleNamespace` must be added to the imports block (:13–16).

### D2 — known-persons insight is unconditionally exact (kills T12, T8-known, T14-gei, T17-gei, L1-gei known, L2-gei known)

Replaces the if-guarded `test_known_person_lower_priority` (:259) *in intent* (keep the old one;
this adds teeth):

```python
class TestKnownPersonInsightExact:
    """The known-persons insight must always exist with exact text (test file :259 is if-guarded)."""

    def test_two_known_persons_exact_description(self, insight_generator, mock_known_person_event):
        second = MagicMock()
        second.camera_id = "backyard"
        second.camera = MagicMock()
        second.camera.name = "Backyard"
        second.risk_level = "low"
        second.risk_score = 10
        second.entities = [{"type": "person", "recognized": True}]
        ent = [i for i in insight_generator.generate_insights(
                   [mock_known_person_event, second])
               if i.type == InsightType.ENTITY]
        assert len(ent) == 1                       # kills gei_34 phantom, ges_45 missing
        assert ent[0].title == "Known Persons Activity"      # kills ges/gei title None+casing
        assert ent[0].priority == InsightGenerator.PRIORITY_KNOWN_ENTITY  # 4
        assert ent[0].description == "2 recognized persons detected"      # kills ges_44/46, gei_36/37
        assert ent[0].action_url == "/timeline?entity_type=person&recognized=true"  # kills gei_46/51, gei_55/56

    def test_single_known_person_singular(self, insight_generator, mock_known_person_event):
        ent = [i for i in insight_generator.generate_insights([mock_known_person_event])
               if i.type == InsightType.ENTITY]
        assert len(ent) == 1                       # kills gei_35 (>1 gate drops single)
        assert ent[0].description == "1 recognized person detected"  # kills gei_36/37/38/39/40
```

TDD: `gei_34` (`>= 0`) adds a "Known Persons Activity" with "0 recognized persons detected" →
`len(ent) == 1` red; original green.

### D3 — unknown-persons description: exact join, slice, "N more" (kills T8-unknown, T9, T13, T14-gei, L1 gei unknown, T6b names)

```python
class TestUnknownPersonDescriptionExact:
    """Pin ' at A, B' camera list: dedupe (ges_50), 3-way slice (gei_13), 'N more' gate (gei_16/17)."""

    @staticmethod
    def _cam_event(eid, cam_id, cam_name):
        return SimpleNamespace(
            id=eid, camera_id=cam_id, camera=SimpleNamespace(name=cam_name),
            risk_level="medium", risk_score=40,
            entities=[{"type": "person", "recognized": False}],
        )

    def test_three_cameras_listed_without_more_suffix(self, insight_generator):
        events = [
            self._cam_event(1, "cam1", "Front Door"),
            self._cam_event(2, "cam2", "Driveway"),
            self._cam_event(3, "cam3", "Patio"),
            self._cam_event(4, "cam1", "Front Door"),   # same camera: dedupe keeps 3 cameras
        ]
        ent = [i for i in insight_generator.generate_insights(events)
               if i.type == InsightType.ENTITY
               and i.title == "Unknown Persons Detected"][0]
        assert ent.priority == InsightGenerator.PRIORITY_UNKNOWN_PERSON  # 10
        assert ent.description == "4 unknown persons detected at Front Door, Driveway, Patio"
        assert ent.action_url == "/timeline?entity_type=person&recognized=false"
        # kills: ges_49 (would say '8 unknown persons'), ges_50 (empty camera list -> no ' at …'),
        # gei_16 (would append ' and 0 more'), gei_10/12 (crash/foreign separator)

    def test_fourth_camera_adds_more_suffix(self, insight_generator):
        events = [self._cam_event(n, f"cam{n}", f"Cam{n}") for n in (1, 2, 3, 4)]
        ent = [i for i in insight_generator.generate_insights(events)
               if i.type == InsightType.ENTITY
               and i.title == "Unknown Persons Detected"][0]
        assert ent.description == (
            "4 unknown persons detected at Cam1, Cam2, Cam3 and 1 more"
        )  # kills gei_13 (slice :4 -> all four listed), gei_17 (>4 gate drops ' and 1 more')
```

TDD: `gei_13` lists "Cam1, Cam2, Cam3, Cam4 and 1 more" → red; original green.

### D4 — trend thresholds + full trend insight spec (kills T19, T20, T15-gti, T16-gti, T17-gti, T14-gti, L3-gti)

Calls the private method directly (the existing file never does — all trend coverage is end-to-end
and if-guarded):

```python
class TestTrendBoundaries:
    """Boundary tests at the documented 50 % increase / 30 % decrease thresholds."""

    def _titles(self, gen, current, baseline):
        return [(i.title, i.priority, i.description, i.action_url, i.type)
                for i in gen._generate_trend_insights(current, baseline)]

    def test_exactly_50_percent_increase_triggers(self, insight_generator):
        out = insight_generator._generate_trend_insights(15, 10)   # +50 %
        assert len(out) == 1
        title, priority, desc, url, itype = out[0]
        assert title == "Activity Above Baseline"      # kills gti_32/40/41/42
        assert priority == InsightGenerator.PRIORITY_TREND_HIGH
        assert desc == "Activity is 50% above baseline (15 vs 10 events)"   # kills gti_27/28
        assert url == "/analytics"                     # kills gti_34/39/44/45
        assert itype is InsightType.TREND              # kills gti_8/gti_49-type family

    def test_exactly_30_percent_decrease_triggers_quiet_period(self, insight_generator):
        out = insight_generator._generate_trend_insights(7, 10)    # -30 %
        assert len(out) == 1
        title, priority, desc, url, itype = out[0]
        assert title == "Quiet Period"                 # kills gti_51/59/60/61
        assert priority == InsightGenerator.PRIORITY_TREND_LOW
        assert desc == "Activity is 30% below baseline (7 vs 10 events)"  # kills gti_46/47
        assert url == "/analytics"
        assert itype is InsightType.TREND              # kills gti_49

    def test_29_percent_change_is_quiet_and_silent(self, insight_generator):
        assert insight_generator._generate_trend_insights(71, 100) == []
        assert insight_generator._generate_trend_insights(29, 100) == []

    def test_zero_baseline_with_events_is_new_activity(self, insight_generator):
        out = insight_generator._generate_trend_insights(2, 0)
        assert len(out) == 1
        title, _, desc, url, itype = out[0]
        assert title == "New Activity Detected"        # kills gti_10/18/19/20
        assert desc == "2 events detected where none were expected"   # kills gti_11
        assert url == "/timeline"                      # kills gti_12/17/21/22
        assert itype is InsightType.TREND              # kills gti_8

    def test_zero_baseline_zero_events_is_silent(self, insight_generator):
        # kills gti_5 (>= 0 would emit a phantom "0 events" insight) and pins gti_6 (current > 1)
        assert insight_generator._generate_trend_insights(0, 0) == []
        assert insight_generator._generate_trend_insights(1, 0)[0].title == "New Activity Detected"

    def test_no_baseline_is_silent(self, insight_generator):
        assert insight_generator._generate_trend_insights(100, None) == []
```

TDD: `gti_25` (`/`→`*`) yields 1500% / misclassification → `desc == "Activity is 50% …"` red.

### D5 — camera order, top-3 cap, default insight limit (kills T21, G1, plus sort-sensitive L-adjacent)

```python
class TestCameraOrderAndLimits:
    """Busiest cameras first (high_critical then count), capped at 3; default cap 5 overall."""

    @staticmethod
    def _cam_events():
        def ev(eid, cam_id, cam_name, risk):
            return SimpleNamespace(
                id=eid, camera_id=cam_id, camera=SimpleNamespace(name=cam_name),
                risk_level=risk, risk_score=50,
                entities=[{"type": "person", "recognized": False}] if eid == 1 else [],
            )
        return [
            ev(1, "front", "Front Door", "low"),      # (hc 0, n 1)
            ev(2, "back", "Back Yard", "low"),         # (hc 0, n 3)
            ev(3, "back", "Back Yard", "low"),
            ev(4, "back", "Back Yard", "low"),
            ev(5, "drive", "Driveway", "critical"),    # (hc 1, n 1) -> must sort FIRST
            ev(6, "garage", "Garage", "low"),          # (hc 0, n 1) -> must be cut by top-3
        ]

    def test_sort_order_and_top_three(self, insight_generator):
        insights = insight_generator.generate_insights(
            self._cam_events(), baseline_event_count=1)
        cams = [i for i in insights if i.type == InsightType.CAMERA]
        assert [c.description for c in cams] == [
            "Review 1 event from Driveway (1 high/critical)",
            "Review 3 events from Back Yard",
            "Review 1 event from Front Door",
        ]  # kills gca_5/8/10 (ascending order) and gca_11 (Garage would appear)

    def test_default_limit_is_five(self, insight_generator):
        # 6 insights exist (1 unknown-person + 1 trend + 3 camera + driveway-critical unknown
        # person already merged into the one entity insight; baseline=1 -> +500% trend).
        insights = insight_generator.generate_insights(self._cam_events(), baseline_event_count=1)
        assert len(insights) == 5   # kills gi_1 (default 6 returns 6)
```

Note: the 6th insight count depends on driveway event also carrying an unknown person
(`eid == 1` is front; adjust the entities lambda so exactly one entity insight exists + trend +
3 cams + … — trim to assert `len(insights) == 5` after confirming the exact generated set in the
green run; if the scenario yields only 5 naturally, move the entities marker onto a second camera
to force 6 candidates). This is the one assert that may need a count adjustment on first green run —
everything else is pinned string-equality.

TDD: `gca_10` (`reverse=False`) puts "Front Door" first → red; original green.

### D6 — real (non-mock) event objects expose every string-arg mutation (kills T1, T2-mock-blind, T3, T4, T6a/T6b, T10, T11, L6, E3)

```python
class TestRealEventObjects:
    """MagicMock auto-creates ANY attribute, so mutated attr NAMES are invisible under mocks
    (memory: mock FORWARDREF/attribute-name traps). These events are plain objects."""

    def _event(self, **kw):
        base = dict(id=1, camera_id="cam1",
                    camera=SimpleNamespace(name="Front Door"),
                    risk_level="high", risk_score=75,
                    entities=[{"type": "person", "recognized": False}])
        base.update(kw)
        return SimpleNamespace(**base)

    def test_named_camera_used_and_null_camera_falls_back(self, insight_generator):
        named = self._event()
        null_cam = self._event(id=2, camera_id="cam2", camera=None)
        cams = insight_generator._gather_camera_stats([named, null_cam])
        assert cams["cam1"].camera_name == "Front Door"   # kills gcs_9/10 (name silently drops to id)
        assert cams["cam2"].camera_name == "cam2"          # pins the fallback branch
        assert cams["cam1"].camera_id == "cam1"            # kills gcs_16
        assert cams["cam1"].high_critical_count == 1       # kills gcs_23/24/29/30/31/32/33 (lowercase
                                                          # 'high' must match; 'HIGH'/'XXhighXX'/None must not)

    def test_missing_risk_score_does_not_crash(self, insight_generator):
        e = self._event(risk_score=None)
        cams = insight_generator._gather_camera_stats([e])
        assert cams["cam1"].max_risk_score == 0   # kills gcs_40: `risk_score and 0` -> None -> max(0, None) TypeError

    def test_recognized_key_absent_counts_as_unknown(self, insight_generator):
        e = self._event(entities=[{"type": "person"}])   # safety default must be falsy
        st = insight_generator._gather_entity_stats([e])
        assert st.unknown_persons == 1 and st.known_persons == 0  # kills ges_43

    def test_empty_entities_event_does_not_abort_sweep(self, insight_generator):
        first = self._event(entities=None)               # no entities -> continue, not break
        second = self._event(id=2, entities=[{"type": "person", "recognized": False}])
        st = insight_generator._gather_entity_stats([first, second])
        assert st.unknown_persons == 1                   # kills ges_11 (break would stop at event 1)

    def test_unknown_entity_type_is_skipped_not_matched(self, insight_generator):
        e = self._event(entities=[{"type": "dog"}, {"type": "PERSON"}])
        st = insight_generator._gather_entity_stats([e])  # lowercase() contract + exact match
        assert st.unknown_persons == 1 and st.known_persons == 0  # kills ges_32/53/54 casing drift
        # ges_27/29 (crash on missing "type") stay LOW-VALUE by policy — not asserted

    def test_entity_camera_name_uses_real_attr(self, insight_generator):
        e = self._event(entities=[{"type": "person", "recognized": False}])
        st = insight_generator._gather_entity_stats([e])
        assert st.unknown_person_cameras == ["Front Door"]  # kills ges_14/18/19/22
```

TDD: with `gcs_33` ("HIGH"), `cams["cam1"].high_critical_count == 0` → red; original green.

### D7 — no-activity insight fully specified (kills T15-gnai, T16-gnai? (n/a), T17-gnai, T18; makes :443 test_no_events non-vacuous)

```python
class TestNoActivityInsightSpec:
    """test_no_events (:443) passes with ANY list <=1 of ANYTHING. Pin the actual contract."""

    def test_no_activity_insight_is_fully_specified(self, insight_generator):
        out = insight_generator.generate_insights([])
        assert len(out) == 1
        ins = out[0]
        assert ins.type is InsightType.TREND          # kills gnai_1 (type None -> .value crashes
                                                      # in routes/summaries.py:99 -> API 500)
        assert ins.priority == InsightGenerator.PRIORITY_QUIET_PERIOD  # kills gnai_2
        assert ins.title == "No Recent Activity"      # kills gnai_10/11/12
        assert ins.description == (
            "No high-priority events detected in this period. The property has been quiet."
        )                                             # kills gnai_13/14/15, gnai_4 (None)
        assert ins.action_url is None                 # pins gnai_9 equivalence
        assert ins.to_dict() == {
            "type": "trend", "priority": 3, "title": "No Recent Activity",
            "description": ins.description, "action_url": None,
        }                                             # the type=None crash surfaces here too
```

TDD: `gnai_1` sets `type=None`; `ins.type is InsightType.TREND` red (and `to_dict()` raises
AttributeError); original green.

## Drafted-test kill map (for WP4.4 planning)

| Draft | Kills clusters | Approx keys killed |
|-------|----------------|--------------------|
| D1 | T2, T3, T5, T7, T22, T16(gca), T6a(partial) | ~20 |
| D2 | T12, T8(known), T14(gei), T17(gei), L1/L2(gei-known) | ~14 |
| D3 | T8(unknown), T9, T13, T6b | ~11 |
| D4 | T19, T20, T15(gti), T16(gti), T17(gti), T14(gti), L3(gti) | ~20 |
| D5 | T21, G1, L1(gca partial via exact desc) | ~6 |
| D6 | T1, T2(mock-blind), T3, T4, T6a/b, T10, T11, E3 | ~15 |
| D7 | T15(gnai), T17(gnai), T18, L2(gnai) | ~8 |

Residual after all drafts: L1/L2/L3 (cosmetic copy — deliberately not asserted; teams that want
marketing-copy regression locks can add one golden-string test per insight type instead),
L4/L5 (write-only fields — recommend deleting `max_risk_score`/`vehicles` from the stats
dataclasses or wiring consumers in a WP4.4 follow-up so the field stops being dead weight),
L6 + E-class (intentionally uncovered).

## Notes / caveats

- Meta was live during triage: the survivor set grew 134 → 135 mid-session (gi_1 checked
  survived while this dossier was being written). Snapshot date 2026-09-17; WP4.4 should re-diff
  keys against the final baseline before implementing.
- `mutmut show` succeeded for all 135 keys (no manual diffing fallback needed); raw diffs at
  `/tmp/wp25/wp44-triage/ig-diffs.txt`.
- D1's `mock_event` fixture path also exercises the *camera* insight for a mock event with
  entities; entity insights ride along harmlessly.
- Existing weak tests worth hardening in-place instead of duplicating (same file):
  :259 if-guard removal, :190 disjunction, :208 url disjunction, :522 disjunction,
  :348/:379 if-guards. The drafted classes are additive; a WP4.4 cleanup may fold them back.
