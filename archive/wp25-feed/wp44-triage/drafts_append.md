
## Drafted tests - UNVERIFIED: not yet run red/green

TDD procedure for each: run the test against the mutant tree (red - assertion fails on the
mutant diff), then against the original backend/services/nemotron_analyzer.py (green). The
serial WP4.4 lane owns red-on-mutant -> green-on-original -> killed verification.

### T1 test_call_llm_backoff_schedule_and_retry_exhaustion
Kills: C-RETRY (38: delay-formula 2**attempt variants, `attempt < self._max_retries - 1`
boundary flips, retry-count in message, `last_exception` nulling via original_error) plus
payload-key members of C-STR-FUNC / C-HTTP-KEYS.
Target: backend/tests/unit/services/test_nemotron_analyzer.py (append after
test_call_llm_unexpected_error_with_retry, ~line 4395).

```python
@pytest.mark.asyncio
async def test_call_llm_backoff_schedule_and_retry_exhaustion(analyzer):
    """NEM-1343/NEM-1465: retry budget, exponential backoff, error causality.

    Existing retry tests (test_call_llm_asyncio_timeout / _client_error_no_retry /
    _unexpected_error_with_retry) only assert raise + call count; nothing asserts
    sleep delays, the completion payload contract, or exception chaining.
    """
    # NOTE: built without the literal ChatML marker sequence so this dossier can be
    # round-tripped through tool channels that reserve "<|...|>" token forms.
    im_end = "<" + "|im_end|>"
    im_start = "<" + "|im_start|>"

    analyzer._max_retries = 3  # two sleep gaps, then the final attempt raises
    post_kwargs: list[dict] = []

    async def always_fail(*args, **kwargs):
        post_kwargs.append(kwargs)
        raise httpx.ConnectError("boom")

    slept: list[float] = []

    async def fake_sleep(delay):
        slept.append(delay)

    with (
        patch("httpx.AsyncClient.post", side_effect=always_fail, autospec=True),
        patch("backend.services.nemotron_analyzer.asyncio.sleep", new=fake_sleep),
    ):
        with pytest.raises(AnalyzerUnavailableError) as excinfo:
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )

    assert len(post_kwargs) == 3
    assert slept == [1, 2]  # min(2**attempt, 30): 2**0 then 2**1
    err = excinfo.value
    assert "after 3 attempts" in str(err)
    assert isinstance(err.original_error, httpx.ConnectError)
    assert err.__cause__ is err.original_error

    body = post_kwargs[0]["json"]
    assert body["temperature"] == 0.3
    assert body["top_p"] == 0.95
    assert body["stop"] == [im_end, im_start]
    assert body["cache_prompt"] is True
    assert "prompt" in body and "max_tokens" in body
```

Kill logic (T1): `attempt <= max_retries-1` / `+1` mutants add a third sleep
(slept == [1,2,4] != [1,2]); `-2` / `==` mutants suppress the first sleep ([] != [1,2]);
`2 * attempt` gives [0,2]; `3**attempt` gives [1,3]; `last_exception=None` mutants fail the
original_error / __cause__ asserts; clobbered payload keys (temperature/top_p/stop/
cache_prompt/prompt/max_tokens) fail the body contract; the retry-count message mutants fail
`after 3 attempts`. Red on mutant, green on original.

### T2 test_build_prompt_enrichment_gating_contract
Kills: C-PROMPT-GATES members around `has_enriched_context or enrichment_result is not None`,
the `if enrichment_result is not None [and ...]` reid/pose/action/scene/ondemand gates, and the
`x if enriched_context else None` cross-camera ternaries (andFalse/orTrue/is-flip/and-or flips).
Target: same file, after test_build_prompt_basic (~line 4395).

```python
@pytest.mark.asyncio
async def test_build_prompt_enrichment_gating_contract(analyzer):
    """_build_prompt must include every enrichment section when data exists and
    fall back to defaults when it does not. Only test_build_prompt_basic exists
    today, and it covers the *basic* template - the enriched branch is untested.

    // UNVERIFIED - not yet run red/green
    """
    from contextlib import ExitStack

    fmt_names = [
        "format_cross_camera_person_tracking", "format_weather_context",
        "format_image_quality_context", "format_confidence_quality_summary",
        "format_pose_analysis_context", "format_action_recognition_context",
        "format_trajectory_context", "format_vehicle_classification_context",
        "format_vehicle_damage_context", "format_clothing_analysis_context",
        "format_pet_classification_context", "format_depth_context",
        "format_clip_analysis_context", "format_detections_with_all_enrichment",
        "format_violence_context",
    ]

    def marker(name):
        return lambda *args, **kwargs: f"<<{name}>>"

    enricher = MagicMock()
    enricher.format_zone_analysis.return_value = "<<ZONE>>"
    enricher.format_baseline_comparison.return_value = "<<BASELINE>>"
    enricher.format_cross_camera_summary.return_value = "<<XCSUM>>"

    ctx = MagicMock()
    ctx.camera_id = "cam-7"
    ctx.zones = ["zone-a"]
    ctx.cross_camera = ["cam-b"]
    ctx.baselines = MagicMock()
    ctx.baselines.day_of_week = "Tuesday"
    ctx.baselines.deviation_score = 1.23

    er = MagicMock()
    er.vision_extraction = MagicMock()
    er.vision_extraction.environment_context.time_of_day = "night"
    er.vision_extraction.scene_analysis = None
    er.person_reid_matches = [MagicMock()]
    er.vehicle_reid_matches = []
    er.pose_results = {}
    er.action_results = None
    er.weather_classification = None
    er.trajectory_analyses = None
    er.vehicle_classifications = {}
    er.vehicle_damage = {}
    er.clothing_classifications = {}
    er.clothing_segmentation = None
    er.pet_classifications = {}
    er.depth_analysis = None

    with ExitStack() as stack:
        for name in fmt_names:
            stack.enter_context(
                patch(f"backend.services.nemotron_analyzer.{name}", new=marker(name))
            )
        stack.enter_context(
            patch("backend.services.reid_service.format_full_reid_context",
                  new=lambda p, v: f"<<REID:{bool(p)}/{bool(v)}>>")
        )
        stack.enter_context(
            patch("backend.services.vision_extractor.format_scene_analysis",
                  new=marker("SCENE"))
        )
        stack.enter_context(patch.object(analyzer, "_get_context_enricher", return_value=enricher))
        stack.enter_context(
            patch.object(analyzer, "_build_ondemand_enrichment_context",
                         new=lambda *_a, **_k: "<<ONDEMAND>>")
        )

        prompt = analyzer._build_prompt(
            camera_name="Front Door",
            start_time="2025-12-23T14:30:00",
            end_time="2025-12-23T14:31:00",
            detections_list="1. 14:30:00 - person",
            enriched_context=ctx,
            enrichment_result=er,
        )
        for token in ("<<ZONE>>", "<<BASELINE>>", "<<XCSUM>>", "<<REID:True/False>>",
                      "<<ONDEMAND>>", "Tuesday", "night", "1.23"):
            assert token in prompt, token

        # context WITHOUT baselines: enriched path via `or`, baseline defaults must appear
        ctx.baselines = None
        prompt_nb = analyzer._build_prompt(
            camera_name="Front Door", start_time="t0", end_time="t1",
            detections_list="d", enriched_context=ctx, enrichment_result=er,
        )
        assert "Baseline comparison: Not available" in prompt_nb
        assert "<<REID:True/False>>" in prompt_nb

        # no context at all: cross-camera kwargs fall back to None (or-True mutants crash here)
        prompt_nc = analyzer._build_prompt(
            camera_name="Front Door", start_time="t0", end_time="t1",
            detections_list="d", enriched_context=None, enrichment_result=er,
        )
        assert "<<REID:True/False>>" in prompt_nc
        assert "Zone analysis: Not available" in prompt_nc
```

Kill logic (T2): `has_enriched_context = ... and enrichment_result is not None` (mutmut_67)
collapses call 2 to the basic template -> "<<REID:True/False>>" absent -> red; `if enrichment_result
is not None` -> `and False` (35/38/40/43) drops <<ONDEMAND>>/pose/action sections -> red; `or True`
members (36/27/29/64/66) crash (AttributeError on None) on call 3 or bypass the None-ternary
default on call 2 -> red; reid ternaries fed `None` instead of the match lists fail the exact
`<<REID:True/False>>` marker. Green on original.
### T3 test_build_context_sources_populated_and_empty
Kills: C-CTX-FLAGS (150; `is not None` -> `is None` value flips, empty-branch `False` -> `True`,
`-> None` nulls, and XX/UPPER-clobbered dict keys) - the function has ZERO direct tests; its dict
is persisted as LLMInteraction.context_sources (analyze_batch ~line 2992/3019).
Target: same file (new section near test_run_enrichment_pipeline tests).

```python
def test_build_context_sources_populated_and_empty(analyzer):
    """NEM-4234: context_sources flags record which enrichment fields had data.

    // UNVERIFIED - not yet run red/green
    """
    from backend.services.context_enricher import EnrichedContext

    er = MagicMock()
    er.has_license_plates = True
    er.has_faces = False
    er.weather_classification = None
    er.pose_results = {}
    er.action_results = None
    er.has_violence = False
    er.has_clothing_classifications = False
    er.has_vehicle_classifications = False
    er.has_vehicle_damage = False
    er.has_pet_classifications = False
    er.has_image_quality = False
    er.has_vision_extraction = False
    er.person_reid_matches = []
    er.vehicle_reid_matches = []
    er.person_household_matches = []
    er.vehicle_household_matches = []

    ctx = MagicMock()
    ctx.baselines = None
    ctx.zones = []
    ctx.cross_camera = []

    sources = analyzer._build_context_sources(enrichment_result=er, enriched_context=ctx)

    assert sources["enrichment_available"] is True
    assert sources["context_available"] is True
    assert sources["has_license_plates"] is True
    assert sources["has_faces"] is False
    assert sources["has_weather"] is False
    assert sources["has_pose"] is False
    assert sources["has_action"] is False
    assert sources["has_baselines"] is False
    assert sources["has_zones"] is False
    assert sources["has_cross_camera"] is False

    # fully-empty call: every has_* flag must be False (empty branches + availability)
    empty = analyzer._build_context_sources(enrichment_result=None, enriched_context=None)
    assert empty["enrichment_available"] is False
    assert empty["context_available"] is False
    assert all(v is False for k, v in empty.items() if k.startswith("has_")), empty

    # baselines present -> has_baselines True
    ctx.baselines = MagicMock()
    assert analyzer._build_context_sources(er, ctx)["has_baselines"] is True


def test_build_context_sources_keys_are_stable_contract(analyzer):
    """Keys of context_sources are persisted to LLMInteraction and consumed by
    calibration/debug tooling - renaming one (XX/UPPER clobber) is a breaking change.

    // UNVERIFIED - not yet run red/green
    """
    expected = {
        "enrichment_available", "context_available", "has_license_plates", "has_faces",
        "has_weather", "has_pose", "has_action", "has_violence", "has_clothing",
        "has_vehicle_classification", "has_vehicle_damage", "has_pet_classification",
        "has_image_quality", "has_vision_extraction", "has_person_reid", "has_vehicle_reid",
        "has_household_person_matches", "has_household_vehicle_matches",
        "has_baselines", "has_zones", "has_cross_camera",
    }
    out = analyzer._build_context_sources(enrichment_result=None, enriched_context=None)
    assert set(out) == expected
```

Kill logic (T3): `sources["has_weather"] = ... is not None` -> `is None` (mutmut_18) flips
False->True -> red; empty-branch `= False` -> `= True` flips `all(v is False ...)` -> red;
`has_baselines ... is not None` -> `is None` (132) flips the last assert -> red; XX/UPPER key
clobbers fail the exact-key set assert -> red. Green on original.

### T4 test_extract_json_objects_balanced_scanner
Kills: C-EXTRACT (43; `i = 0` -> `1`, `i += 1` -> `+= 2/3`, `continue` -> `break`, all
brace/quote/escape comparison flips, `depth == 0` -> `!=`, `in_string = False` -> `True`).
The module-level scanner has no direct tests (grep 2026-09-18).
Target: same file, near the parse tests (~line 1660).

```python
def test_extract_json_objects_balanced_scanner():
    """Balanced-brace extraction: nesting depth, braces inside strings, escapes,
    multiple top-level objects, and unterminated fragments.

    // UNVERIFIED - not yet run red/green
    """
    from backend.services.nemotron_analyzer import _extract_json_objects

    assert _extract_json_objects('no braces here') == []

    # nested + string-embedded braces + escapes
    text = '{"a": "x{y}z", "b": {"c": 1}} tail {"d": 2}'
    assert _extract_json_objects(text) == ['{"a": "x{y}z", "b": {"c": 1}}', '{"d": 2}']

    # escaped quote inside a string keeps in_string true past the \"
    esc = '{"k": "he said \\"{\\" done", "n": {"x": 1}}}'
    assert _extract_json_objects(esc) == [esc]

    # unterminated trailing object is dropped (found_end guard)
    assert _extract_json_objects('{"ok": 1} {"broken": ') == ['{"ok": 1}']

    # text that starts inside ... i must start at 0
    assert _extract_json_objects('{"first": {"nested": 2}}{"second": 3}') == [
        '{"first": {"nested": 2}}', '{"second": 3}'
    ]
```

Kill logic (T4): `i = 1` mutant shifts the scan origin -> misses/mis-slices the object starting
at index 0 (mutmut_3 red on case 3); `i += 3` skips a char after non-braces -> misses `{"d": 2}`
at its true offset (case 2); `continue` -> `break` (11) stops after the first top-level object ->
case 2/4 return only the first (red); quote/escape comparison flips (22/26/27/31) break
string-skip on `"x{y}z"` -> depth tracked wrong -> wrong slice (case 2/3); `elif c == "{"` /
`"}"` flips (35/40) destroy depth accounting (case 4 `depth == 0` -> `!=` returns nothing);
`in_string = True` (init) treats the whole doc as inside a string -> [] (case 1-style text red
via case 2). Green on original.

### T5 test_parse_llm_response_candidate_and_brace_selection
Kills: C-PARSE members around candidate gating and brace selection: `isinstance(data, dict) and
"risk_score" in data` -> `or` / `not in` (74/77), candidate loop `continue` -> `break` (83),
`first_brace = find("{")` -> `rfind` (34) and `first_brace >= 0` trunc-gate flips.
Existing parse tests (lines 272-360, 1625, 4232) only feed single-candidate text without
braces-after-the-risk-object.
Target: same file, after test_parse_llm_response_nested_json (~line 1660).

```python
def test_parse_llm_response_selects_first_candidate_with_risk_score(analyzer):
    """When the completion contains decoy objects and a trailing fragment, the
    parser must pick the first object that actually carries risk_score.

    // UNVERIFIED - not yet run red/green
    """
    text = (
        '{"oops": ,} {"note": 1} '
        '{"risk_score": 60, "risk_level": "medium", "summary": "s", "reasoning": "r",'
        ' "meta": {"deep": {"x": 1}}} {"dangling": '
    )
    result = analyzer._parse_llm_response(text)
    assert result["risk_score"] == 60
    assert result["risk_level"] == "medium"


def test_parse_llm_response_preamble_and_nested_only(analyzer):
    """Preamble is stripped at the FIRST brace; nested-2-deep objects force the
    balanced-extraction path (legacy single-nesting regex cannot recover them).

    // UNVERIFIED - not yet run red/green
    """
    text = (
        'preamble noise {"risk_score": 42, "risk_level": "low", "summary": "s",'
        ' "reasoning": "r", "meta": {"deep": {"x": 1}}} {"tail": '
    )
    assert analyzer._parse_llm_response(text)["risk_score"] == 42
```

Kill logic (T5): `and` -> `or` (74) and `and "risk_score" not in data` (77) make the decoy
`{"note": 1}` return first -> risk_score 1->KeyError/60-mismatch red; `continue` -> `break` (83)
abandons extraction at the unparseable `{"oops": ,}` and the nested risk object is invisible to
the single-nesting regex fallback -> ValueError red; `find("{")` -> `rfind` (34) anchors the
preamble strip / truncation fragment at the trailing dangling brace -> red in both tests.
Residual near-equivalents intentionally not chased: fastpath `startswith` guards (62/63,
fast-path toggle when cleaned is a single object), `json_start` find/rfind (18/26) where no
brace follows the JSON, `first_brace > 0` <-> `>= 0` (36/59). Green on original.

### T6 test_event_created_webhook_payload_contract
Kills: C-WEBHOOK (31: soft-delete guard `is not None` -> `is None`, `isoformat() if event.started_at`
andFalse/orTrue, key/value nulling, arg deletion) + C-HTTP-KEYS webhook members (18 key clobbers).
`_trigger_event_created_webhook` has zero tests today. Target: same file, near test_broadcast_event
(~line 591). Requires `from contextlib import asynccontextmanager` added to the import block.

```python
@pytest.mark.asyncio
async def test_event_created_webhook_payload_contract(analyzer):
    """NEM-3624: EVENT_CREATED payload keys/values are an external contract, and
    soft-deleted events must not fire webhooks.

    // UNVERIFIED - not yet run red/green
    """
    event = Event(
        id=7, batch_id="b7", camera_id="cam7",
        started_at=datetime(2025, 12, 23, 14, 30, 0),
        ended_at=None, risk_score=61, risk_level="medium",
        summary="s", reasoning="r", is_fast_path=True,
    )

    trigger = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield MagicMock()

    svc = MagicMock()
    svc.trigger_webhooks_for_event = trigger
    with (
        patch("backend.services.nemotron_analyzer.get_webhook_service", return_value=svc),
        patch("backend.services.nemotron_analyzer.get_session", new=fake_session),
    ):
        await analyzer._trigger_event_created_webhook(event)

    trigger.assert_awaited_once()
    payload = trigger.await_args.args[2]
    assert payload == {
        "event_id": 7, "batch_id": "b7", "camera_id": "cam7",
        "risk_score": 61, "risk_level": "medium", "summary": "s",
        "started_at": "2025-12-23T14:30:00", "ended_at": None,
        "is_fast_path": True,
    }
    assert trigger.await_args.kwargs == {"event_id": "7"}

    # soft-deleted events must not fire webhooks (guard flip fails both halves)
    event.deleted_at = datetime(2025, 12, 24, 0, 0)
    svc2 = MagicMock()
    svc2.trigger_webhooks_for_event = AsyncMock()
    with (
        patch("backend.services.nemotron_analyzer.get_webhook_service", return_value=svc2),
        patch("backend.services.nemotron_analyzer.get_session", new=fake_session),
    ):
        await analyzer._trigger_event_created_webhook(event)
    svc2.trigger_webhooks_for_event.assert_not_awaited()
```

Kill logic (T6): key clobbers (`"XXevent_idXX"` etc, webhook mutmut_11/13/15) fail dict equality;
`started_at` `and False` -> payload None fails equality, `or True` -> AttributeError on
`ended_at=None` swallowed by the fn's try/except -> trigger never awaited -> red; guard
`is not None` -> `is None` (mutmut_1) early-returns the live event (first half red) and fires the
deleted event (second half red). Green on original.

### T7 test_calculate_batch_priority_label_matching (small, 12 survivors in C-PRIORITY)
Target: same file. `calculate_batch_priority` has ZERO tests.

```python
def test_calculate_batch_priority_label_matching(analyzer):
    """Configured high-priority labels are matched case-insensitively via set
    intersection; everything else defers to the batch coalescer.

    // UNVERIFIED - not yet run red/green
    """
    from backend.services.batch_coalescer import Priority

    assert analyzer._priority_high_labels == frozenset({"weapon", "intruder", "fire"})

    coalescer = MagicMock()
    coalescer.calculate_priority.return_value = Priority.P2_NORMAL
    with patch.object(analyzer, "_get_batch_coalescer", return_value=coalescer):
        assert analyzer.calculate_batch_priority(["Weapon"]) == Priority.P0_CRITICAL
        assert analyzer.calculate_batch_priority(["car"]) == Priority.P2_NORMAL
        assert analyzer.calculate_batch_priority(["person"], is_known_face=True) == Priority.P3_LOW
```

Kill logic (T7): `label.lower()` -> `upper` in __init__ breaks the frozenset assert; `t.lower()`
-> `t.upper()` makes ["Weapon"] miss the high set -> P2 != P0 red; `types_lower & labels` -> `|`
matches for every input -> ["car"] == P0 red. Green on original.

## Draft coverage summary (of the 16 TEST-GAP clusters)

Drafted: C-RETRY (T1), C-PROMPT-GATES (T2), C-CTX-FLAGS (T3), C-EXTRACT (T4), C-PARSE (T5),
C-WEBHOOK + C-HTTP-KEYS webhook members (T6), C-PRIORITY members (T7). Also listed as
not-drafted small wins for the serial lane: C-GUIDED-BOUND (status-code boundary probe
sc=300 -> unsupported, sc=500 -> retried), C-ROLLOUT (fake rollout manager: group==CONTROL
routes to record_control_analysis), C-COLD (threshold-boundary timestamp test), C-SHADOW
(returns-dict key assert), C-STR-FUNC residual fallback-default members (two-line value
asserts on _validate_risk_data defaults), C-MISC Limits members (assert on
analyzer._http_client timeout/limits config).

