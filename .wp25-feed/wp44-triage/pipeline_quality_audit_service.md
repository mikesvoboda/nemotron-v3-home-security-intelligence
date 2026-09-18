# WP4.4 Triage Dossier — backend/services/pipeline_quality_audit_service.py

Snapshot: 111 survivors / 722 tracked mutants (394 still `null` = unchecked — verdicts may move as
the live run continues; this dossier covers only exit_code==0 at read time).
All 111 diffs recovered via `uv run mutmut show` except two cache-race victims
(`run_evaluation_llm_calls__mutmut_26` FileNotFoundError, `_run_prompt_improvement__mutmut_20`
JSONDecodeError), recovered by manual function-region diff of `mutants/backend/...py`
against the original. Key naming below omits the
`backend.services.pipeline_quality_audit_service.xǁPipelineQualityAuditServiceǁ` prefix
(e.g. `_run_rubric_eval__mutmut_2`).

## Covering tests (from mutmut-stats tests_by_mangled_function_name)

Unit file (all listed covering tests): `backend/tests/unit/services/test_pipeline_quality_audit_service.py`
- run_evaluation_llm_calls → TestRunFullEvaluation (L485; success L505, consistency L583), TestEdgeCases
  (long_prompt L1530, none_risk L1589) — all drive it via run_full_evaluation with the 4 mode helpers patched
- _run_rubric_eval → TestRunRubricEval L733, TestPromptFormatting::test_rubric_eval_prompt_format L1455, TestLLMResponseParsing
- _run_consistency_check → TestRunConsistencyCheck L791 (incl. strips_assistant_tag L814), TestLLMResponseParsing
- _run_prompt_improvement → TestRunPromptImprovement L866, TestPromptFormatting::test_prompt_improvement_prompt_format L1475
- get_stats → TestGetStats L923 (empty L950, with_audits L973, camera_filter L1033 — camera test only asserts
  `execute.assert_awaited_once()`), TestGetStatsAuditsByDay, TestEdgeCases::test_get_stats_handles_none_scores L1564
- get_leaderboard → TestGetLeaderboard L1053 — **every** test patches `get_stats` (L1071/L1099/L1129) and never asserts call args
- persist_record → TestPersistRecord L451
Integration file: `backend/tests/integration/test_pipeline_quality_audit_service.py` (test_get_stats_empty L159,
test_get_stats_with_data L180, test_get_leaderboard L230 — all insert `audited_at=now`, none asserts cutoff-window
exclusion of old rows).

Structural blind spots that explain most survivors:
1. run_evaluation_llm_calls is only ever reached through run_full_evaluation **with all 4 mode helpers
   patched** → helper call args, the rubric-improvement parse/defaults, prompt snapshot content all unobserved.
2. get_stats/get_leaderboard unit tests **replace session.execute with a MagicMock** → every SQL-shape
   mutation (cutoff sign, `>=` vs `>`, `where(None)`, select(None), camera filter drop/invert) is invisible.
3. get_leaderboard tests patch get_stats with a fully-populated fake dict → the real delegation and the
   `.get(model, 0)` default are both untested surfaces.
4. Prompt-format tests assert only the template skeleton (`"CONTEXT_USAGE" in prompt`), never that
   **event data** is interpolated (compare TestPromptFormatting::test_self_critique_prompt_includes_event_data
   L1438, which does it right for Mode 1).

## Cluster table (counts sum to 111)

| # | Pattern | n | Class | Example keys |
|---|---------|---|-------|--------------|
| C1 | logging-call arg mutation across 4 methods: message text (case/XX/None), `exc_info=True`→None/False/dropped, `extra={"event_id":…}`→None/key-case/dropped. No functional behavior changes; nothing in the suite asserts on log records. | 37 | EQUIVALENT | `persist_record__mutmut_3`, `_run_rubric_eval__mutmut_15`, `_run_prompt_improvement__mutmut_17` |
| C2 | dead defensive defaults: `getattr(a, attr, False)`→None/True in get_stats (EventAudit always defines every `has_*` column) and `rates.get(model, 0)`→None/1 in get_leaderboard (rates dict is built from all MODEL_NAMES) — default branch unreachable on any real path | 6 | EQUIVALENT | `get_stats__mutmut_31`, `get_stats__mutmut_35`, `get_leaderboard__mutmut_27` |
| C3 | `_run_consistency_check`: `event.llm_prompt or ""` → `or "XXXX"` — fallback only reachable when llm_prompt is falsy, which the pipeline guards upstream (early return); direct-call behavior differs only for empty-prompt calls | 1 | LOW-VALUE | `_run_consistency_check__mutmut_3` |
| C4 | prompt-builder inputs → None: `RUBRIC_EVAL_PROMPT.format(llm_prompt/risk_score/summary/reasoning = None)` (rubric ×4) and `PROMPT_IMPROVEMENT_PROMPT.format(llm_prompt/risk_score/reasoning = None)` (×3). LLM would score a `"None"` prompt. Tests check template keywords only, never event data. | 7 | TEST-GAP | `_run_rubric_eval__mutmut_2`, `_run_rubric_eval__mutmut_3`, `_run_prompt_improvement__mutmut_4` |
| C5 | run_evaluation_llm_calls hands `None` instead of `event` to each mode helper (`_run_self_critique(None)` etc. ×4). Helpers are always patched in covering tests → arg never checked. In production the helper's `except Exception` would swallow the AttributeError → silently empty audit. | 4 | TEST-GAP | `run_evaluation_llm_calls__mutmut_3`, `…__mutmut_6`, `…__mutmut_36` |
| C6 | overall_quality_score aggregation: `scores.get("actionability", 3.0)` default→None/4.0, key→`3.0`, and `if valid_scores` → `if (valid_scores) or True` (→ ZeroDivisionError when all four scores are None). Survives because success test's scores average to the same with/without actionability and the {}-rubric test never asserts overall. | 6 | TEST-GAP | `run_evaluation_llm_calls__mutmut_19`, `…__mutmut_22`, `…__mutmut_32` |
| C7 | Mode-4 empty-list defaults: `improvements.get(key, [])` → default None (json.dumps writes `"null"`) or key replaced (value dropped) across the 5 audit JSON columns × mutants. Tests only feed fully-populated improvement dicts. | 13 | TEST-GAP | `run_evaluation_llm_calls__mutmut_62`, `…__mutmut_73`, `…__mutmut_94` |
| C8 | self_eval_prompt truncation operators: `>500`/`>300` → `>=`, `>501`, `and False`, `or True`, `event.reasoning or …`; slices `[:500]`/`[:300]` → off-by-one; `"..."` → `"XX...XX"`. Only asserts are `"..." in prompt` (matches "XX...XX") and `"AAA" in` (matches untruncated). | 13 | TEST-GAP | `run_evaluation_llm_calls__mutmut_108`, `…__mutmut_113`, `…__mutmut_121` |
| C9 | self_eval_prompt snapshot content: `risk_score=None`, `summary=None` — the debugging snapshot loses event context. Test only asserts `self_eval_prompt is not None`. | 2 | TEST-GAP | `run_evaluation_llm_calls__mutmut_101`, `…__mutmut_102` |
| C10 | audited_at stamping at end of run_evaluation_llm_calls: `= None` / `datetime.now(None)` (naive). No test observes audited_at after evaluation. | 2 | TEST-GAP | `run_evaluation_llm_calls__mutmut_123`, `…__mutmut_124` |
| C11 | get_stats query shape: cutoff `now - timedelta` → `+` (window flips to the future), `now(None)` (naive), `where(None)` (date filter dropped), `select(None)`, `>=`→`>`, `execute(None)`. Unit tests mock session.execute wholesale; integration tests only insert fresh rows so window bugs never show. | 6 | TEST-GAP | `get_stats__mutmut_2`, `get_stats__mutmut_6`, `get_stats__mutmut_9` |
| C12 | get_stats camera filter: `query = None` (filter application drops whole query), `where(None)`, and `==`→`!=` (inverted filter — returns *other* cameras' data). | 3 | TEST-GAP | `get_stats__mutmut_10`, `get_stats__mutmut_12` |
| C13 | get_stats rate guard `if total_events > 0` → `> 1`: with exactly one audit, every model contribution rate becomes 0. No test has a one-audit dataset asserting rates. | 1 | TEST-GAP | `get_stats__mutmut_41` |
| C14 | get_leaderboard query shape: same cutoff-sign / naive-now / `where(None)` / `select(None)` / `>=`→`>` mutations as C11, in its own correlation fetch. | 6 | TEST-GAP | `get_leaderboard__mutmut_2`, `get_leaderboard__mutmut_6`, `get_leaderboard__mutmut_9` |
| C15 | get_leaderboard → `get_stats(None, days)` / `(session, None)` / `(days)` / `(session,)`: wrong delegation args. Every test patches get_stats as a bare AsyncMock and never checks call args, so a crashed-stats session passes. | 4 | TEST-GAP | `get_leaderboard__mutmut_13`, `get_leaderboard__mutmut_15` |

Classification totals: EQUIVALENT 43, LOW-VALUE 1, TEST-GAP 67.

## Drafted tests (6) — kill all 67 TEST-GAP mutants

All go in `backend/tests/unit/services/test_pipeline_quality_audit_service.py` (append as class
`TestWP44FindingFeedGaps`). "// UNVERIFIED - not yet run red/green" per header.
TDD procedure for each: apply the mutant, run the named test, expect one assertion failure per
claimed kill; revert, expect green; then `uv run mutmut rerun` on the module.

### D1 — `test_eval_mode_prompts_include_event_data` (kills C4, 7 keys)
Style source: TestPromptFormatting (L1434), which already does exactly this for Mode 1 only.

```python
class TestWP44FindingFeedGaps:
    """Kills WP4.3 survivors from the finding feed (UNVERIFIED - not yet run red/green)."""

    @pytest.mark.asyncio
    async def test_rubric_eval_prompt_includes_event_data(self, audit_service, sample_event):
        """LLM prompt must carry actual event data, not 'None' placeholders."""
        captured = {}

        async def capture_prompt(prompt):
            captured["p"] = prompt
            return "{}"

        with patch.object(audit_service, "_call_llm", side_effect=capture_prompt):
            await audit_service._run_rubric_eval(sample_event)

        p = captured["p"]
        assert sample_event.llm_prompt in p
        assert str(sample_event.risk_score) in p
        assert sample_event.summary in p
        assert sample_event.reasoning in p

    @pytest.mark.asyncio
    async def test_prompt_improvement_prompt_includes_event_data(self, audit_service, sample_event):
        captured = {}

        async def capture_prompt(prompt):
            captured["p"] = prompt
            return "{}"

        with patch.object(audit_service, "_call_llm", side_effect=capture_prompt):
            await audit_service._run_prompt_improvement(sample_event)

        p = captured["p"]
        assert sample_event.llm_prompt in p
        assert str(sample_event.risk_score) in p
        assert sample_event.reasoning in p
```
Red proof: on `_run_rubric_eval__mutmut_2` the llm_prompt field renders `"None"` → first assert fails;
mutmut_3/4/5 each blank exactly one field. Same for improvement mutmut_2/3/4. Green on original.

### D2 — `test_overall_quality_actionability_fallback_and_forwarding` (kills C5, C6, C10; 12 keys)

```python
    @pytest.mark.parametrize(
        "rubric,expected_overall",
        [
            # empty rubric -> actionability falls back to 3.0 and IS the only valid score
            ({}, 3.0),
            # actionability absent -> default 3.0 joins the average: (4+4+4+3)/4 = 3.75
            ({"context_usage": 4.0, "reasoning_coherence": 4.0, "risk_justification": 4.0}, 3.75),
            # all scores explicitly None -> overall None (no ZeroDivisionError)
            (
                {
                    "context_usage": None,
                    "reasoning_coherence": None,
                    "risk_justification": None,
                    "actionability": None,
                },
                None,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_overall_quality_actionability_fallback_and_forwarding(
        self, audit_service, sample_event, rubric, expected_overall
    ):
        audit = EventAudit(event_id=1, audited_at=datetime.now(UTC))

        with (
            patch.object(
                audit_service, "_run_self_critique", new_callable=AsyncMock, return_value="ok"
            ) as critique,
            patch.object(
                audit_service, "_run_rubric_eval", new_callable=AsyncMock, return_value=rubric
            ) as rubric_eval,
            patch.object(
                audit_service, "_run_consistency_check", new_callable=AsyncMock, return_value={}
            ) as consistency,
            patch.object(
                audit_service, "_run_prompt_improvement", new_callable=AsyncMock, return_value={}
            ) as improvement,
        ):
            result = await audit_service.run_evaluation_llm_calls(audit, sample_event)

        # every mode helper must receive the EVENT, never None (kills arg->None mutants)
        for mock in (critique, rubric_eval, consistency, improvement):
            mock.assert_awaited_once_with(sample_event)

        # actionability default of 3.0 and the empty-average guard
        assert result.overall_quality_score == expected_overall

        # audited_at must be re-stamped as a timezone-aware instant
        assert result.audited_at is not None
        assert result.audited_at.tzinfo is not None
```
Red proof: case 1 kills mutmut_19/21/23/26 (overall becomes None/4.0); case 2 kills mutmut_22
(`scores.get(3.0)` → 4.0 ≠ 3.75); case 3 kills mutmut_32 (`or True` → ZeroDivisionError); the
mock-arg asserts kill mutmut_3/6/36/58 (`(None)` call); the tz assert kills 123 (None) and 124 (naive).

### D3 — `test_missing_improvement_keys_default_to_empty_json_lists` (kills C7, 13 keys)

```python
    @pytest.mark.asyncio
    async def test_missing_improvement_keys_default_to_empty_json_lists(
        self, audit_service, sample_event
    ):
        """Present keys are preserved; absent keys persist as '[]', never 'null'."""

        async def run_with(improvements: dict) -> EventAudit:
            audit = EventAudit(event_id=1, audited_at=datetime.now(UTC))
            with (
                patch.object(
                    audit_service, "_run_self_critique", new_callable=AsyncMock, return_value=""
                ),
                patch.object(
                    audit_service, "_run_rubric_eval", new_callable=AsyncMock, return_value={}
                ),
                patch.object(
                    audit_service, "_run_consistency_check", new_callable=AsyncMock, return_value={}
                ),
                patch.object(
                    audit_service,
                    "_run_prompt_improvement",
                    new_callable=AsyncMock,
                    return_value=improvements,
                ),
            ):
                return await audit_service.run_evaluation_llm_calls(audit, sample_event)

        # present keys must survive verbatim (kills key-swap mutants on confusing_sections)
        partial = await run_with({"missing_context": ["m1"], "confusing_sections": ["c1"]})
        assert json.loads(partial.missing_context) == ["m1"]
        assert json.loads(partial.confusing_sections) == ["c1"]
        assert json.loads(partial.unused_data) == []
        assert json.loads(partial.format_suggestions) == []
        assert json.loads(partial.model_gaps) == []

        # all keys absent -> every column is '[]' (kills default-None mutants: dumps "null")
        empty = await run_with({})
        for col in (
            empty.missing_context,
            empty.confusing_sections,
            empty.unused_data,
            empty.format_suggestions,
            empty.model_gaps,
        ):
            assert json.loads(col) == []
```
Red proof: default-None mutants (62/64/70/72/78/80/86/88/94/96) store `"null"` → `json.loads` → None ≠ [];
key-mutants (69/73/74) drop `["c1"]` → `[] ≠ ["c1"]`.

### D4 — `test_self_eval_prompt_truncation_contract` (kills C8, C9; 15 keys)

```python
    @pytest.mark.parametrize(
        "llm_prompt,expect_in,expect_not_in",
        [
            # 600 chars: truncated at exactly 500 + "..."
            ("A" * 600, ["A" * 500 + "..."], ["A" * 600, "A" * 501 + "..."]),
            # exactly 500: NOT truncated (boundary is >, not >=)
            ("C" * 500, [], ["C" * 500 + "..."]),
            # exactly 501: truncated
            ("D" * 501, ["D" * 500 + "..."], ["D" * 501]),
            # short prompt: never gets "..." appended (kills `or True`)
            ("SHORTPROMPT", ["SHORTPROMPT"], ["SHORTPROMPT..."]),
        ],
    )
    @pytest.mark.asyncio
    async def test_self_eval_prompt_truncates_llm_prompt_at_500(
        self, audit_service, sample_event, llm_prompt, expect_in, expect_not_in
    ):
        sample_event.llm_prompt = llm_prompt
        sample_event.reasoning = "Rshort"
        audit = EventAudit(event_id=1, audited_at=datetime.now(UTC))
        with (
            patch.object(
                audit_service, "_run_self_critique", new_callable=AsyncMock, return_value=""
            ),
            patch.object(
                audit_service, "_run_rubric_eval", new_callable=AsyncMock, return_value={}
            ),
            patch.object(
                audit_service, "_run_consistency_check", new_callable=AsyncMock, return_value={}
            ),
            patch.object(
                audit_service, "_run_prompt_improvement", new_callable=AsyncMock, return_value={}
            ),
        ):
            result = await audit_service.run_evaluation_llm_calls(audit, sample_event)

        snap = result.self_eval_prompt
        for chunk in expect_in:
            assert chunk in snap
        for chunk in expect_not_in:
            assert chunk not in snap
        assert "Rshort..." not in snap  # short reasoning must not be "truncated"
        # snapshot must carry the event context it is debugging (kills risk_score/summary=None)
        assert str(sample_event.risk_score) in snap
        assert sample_event.summary in snap

    @pytest.mark.parametrize(
        "reasoning,expect_in,expect_not_in",
        [
            ("B" * 400, ["B" * 300 + "..."], ["B" * 400, "B" * 301 + "..."]),
            ("E" * 300, [], ["E" * 300 + "..."]),  # exactly 300 is NOT truncated
            ("F" * 301, ["F" * 300 + "..."], ["F" * 301]),
        ],
    )
    @pytest.mark.asyncio
    async def test_self_eval_prompt_truncates_reasoning_at_300(
        self, audit_service, sample_event, reasoning, expect_in, expect_not_in
    ):
        sample_event.llm_prompt = "SHORTPROMPT"
        sample_event.reasoning = reasoning
        audit = EventAudit(event_id=1, audited_at=datetime.now(UTC))
        with (
            patch.object(
                audit_service, "_run_self_critique", new_callable=AsyncMock, return_value=""
            ),
            patch.object(
                audit_service, "_run_rubric_eval", new_callable=AsyncMock, return_value={}
            ),
            patch.object(
                audit_service, "_run_consistency_check", new_callable=AsyncMock, return_value={}
            ),
            patch.object(
                audit_service, "_run_prompt_improvement", new_callable=AsyncMock, return_value={}
            ),
        ):
            result = await audit_service.run_evaluation_llm_calls(audit, sample_event)

        snap = result.self_eval_prompt
        for chunk in expect_in:
            assert chunk in snap
        for chunk in expect_not_in:
            assert chunk not in snap
```
Red proof: llm cases kill 108/111 (600 case), 113 (500 case), 114 (501 case), 109 (short case);
reasoning cases kill 115/118/119 (400), 116/120/121 (300), 122 (301); ellipsis-text mutants 112/119 die on
the `expect_in` asserts ("XX...XX" breaks `"X"*N + "..."`); C9 dies on the risk_score/summary asserts.

### D5 — `test_get_stats_query_window_camera_filter_and_single_audit_rate` (kills C11, C12, C13; 10 keys)

```python
    @pytest.mark.asyncio
    async def test_get_stats_query_window_camera_filter_and_single_audit_rate(
        self, audit_service, mock_db_session
    ):
        """The unit suite must pin the SQL shape since session.execute is mocked everywhere."""
        now = datetime.now(UTC)
        audit = EventAudit(id=1, event_id=1, audited_at=now, has_yolo26=True)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [audit]
        mock_result.scalars.return_value = mock_scalars

        captured = []

        async def capture_execute(query, *args, **kwargs):
            captured.append(query)
            return mock_result

        mock_db_session.execute.side_effect = capture_execute

        stats = await audit_service.get_stats(mock_db_session, days=7, camera_id="front_door")

        # exactly one audit, has_yolo26=True -> rate 1.0 (kills `total_events > 1`)
        assert stats["model_contribution_rates"]["yolo26"] == 1.0

        assert captured, "get_stats must execute a query"
        query = captured[0]
        assert query is not None
        compiled = query.compile()
        sql = str(compiled)

        assert "event_audits" in sql  # kills select(None)
        assert "events" in sql  # join against events retained
        assert "audited_at >= " in sql  # kills where(None) and `>` (vs `>=`)
        assert "events.camera_id = " in sql  # kills filter drop / where(None) / `!=`

        params = compiled.params
        assert "front_door" in list(params.values())
        cutoffs = [
            v
            for v in params.values()
            if isinstance(v, datetime)
        ]
        assert cutoffs, "cutoff must be bound as a query parameter"
        cutoff = cutoffs[0]
        assert cutoff.tzinfo is not None  # kills datetime.now(None)
        assert now - timedelta(days=7.2) <= cutoff <= now - timedelta(days=6.8)  # kills +timedelta flip
```
Red proof: mutmut_2 (cutoff in the future), _3 (naive), _6 (no audited_at clause), _8 (`select(None)`
raises at build — the test errors on the mutant, which mutmut counts as a kill), _9 (`> ` renders without
`= `), _10 (query None / camera params absent), _11 (no camera_id clause), _12 (`!= ` text), _14
(`execute(None)` → captured None), _41 (rate 0.0 ≠ 1.0).

### D6 — `test_get_leaderboard_query_window_and_stats_delegation` (kills C14, C15; 10 keys)

```python
    @pytest.mark.asyncio
    async def test_get_leaderboard_query_window_and_stats_delegation(
        self, audit_service, mock_db_session
    ):
        now = datetime.now(UTC)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        captured = []

        async def capture_execute(query, *args, **kwargs):
            captured.append(query)
            return mock_result

        mock_db_session.execute.side_effect = capture_execute

        with patch.object(
            audit_service,
            "get_stats",
            new_callable=AsyncMock,
            return_value={
                "total_events": 0,
                "model_contribution_rates": dict.fromkeys(MODEL_NAMES, 0.0),
            },
        ) as stats_mock:
            board = await audit_service.get_leaderboard(mock_db_session, days=7)

        # delegation must pass (session, days) verbatim — kills get_stats arg mutants
        stats_mock.assert_awaited_once_with(mock_db_session, 7)

        assert board and len(board) == len(MODEL_NAMES)
        assert captured, "leaderboard must fetch audits"
        query = captured[0]
        assert query is not None  # kills execute(None)
        compiled = query.compile()
        assert "event_audits" in str(compiled)  # kills select(None)
        assert "audited_at >= " in str(compiled)  # kills where(None) and `>`
        cutoffs = [v for v in compiled.params.values() if isinstance(v, datetime)]
        assert cutoffs and cutoffs[0].tzinfo is not None
        assert now - timedelta(days=7.2) <= cutoffs[0] <= now - timedelta(days=6.8)
```
Red proof: mutmut_2/3 (window flip / naive), _6 (execute(None) → captured None), _7 (no where clause),
_8 (`select(None)` raises), _9 (`>` text), _13/14/15/16 (`assert_awaited_once_with(mock_db_session, 7)`
fails on (None, 7), (session, None), (7,), (session,)).

## Kill-coverage check
C4:7 (D1) + C5:4 (D2) + C6:6 (D2) + C7:13 (D3) + C8:13 (D4) + C9:2 (D4) + C10:2 (D2) + C11:6 (D5) +
C12:3 (D5) + C13:1 (D5) + C14:6 (D6) + C15:4 (D6) = **67/67 TEST-GAP survivors drafted**.
EQUIVALENT clusters (43) need no tests; if score optics matter later, one `caplog` test per method's
network-error path would mop up C1, but that asserts log text — low value, flagged as such.

## Notes / gotchas for WP4.4
- D2's case-3 (explicit None scores) is the *only* way to kill mutmut_32 (`or True` → ZeroDivisionError);
  the {}-rubric path alone leaves `valid_scores=[3.0]` non-empty and the mutant invisible.
- D5/D6 compile the captured statement with the default dialect — no DB needed; `compiled.params` carries
  the bound cutoff/camera values as real Python objects (tz check included). This technique is reusable
  for every query-shape survivor in other modules with MagicMock-session tests.
- Do not extend the *existing* leaderboard tests in place — their `get_stats` patch is precisely the
  blind spot C15 hides behind; the new test patches it as a spy instead.
- 394 mutants for this module were still `null` (unchecked) at snapshot time; re-run this triage after the
  live run finishes before closing the module's WP4.4 item.
