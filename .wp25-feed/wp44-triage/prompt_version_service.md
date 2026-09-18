# WP4.4 Triage Dossier — backend/services/prompt_version_service.py

Date: 2026-09-17 · Generated from `mutants/backend/services/prompt_version_service.py.meta`
(concurrent-write-safe load, single retry not needed).

- **Mutant keys total:** 249 · **Killed:** 107 · **Not yet checked (null):** 14 · **SURVIVED: 128**
- Key-prefix note: all keys are `backend.services.prompt_version_service.x<U+01C1>PromptVersionService<U+01C1><func>__mutmut_<N>`.
  Shorthands below use `<func>__mutmut_N` where `<U+01C1>` = `ǁ`.
- Method: `uv run mutmut show <key>` fails in this environment (`FileNotFoundError` — the U+01C1
  separator does not round-trip through the CLI arg), so all 128 diffs were recovered by
  **manual AST diffing**: each clobbered variant `def xǁ…ǁ<func>__mutmut_N` in
  `mutants/backend/services/prompt_version_service.py` was parsed and diffed against its
  `__mutmut_orig` twin (docstrings stripped, signatures included). 128/128 resolved, 0 errors.
  Working diff data: `/tmp/wp25/wp44-triage-work/diffs.json`.
- **Covering test file (all functions):** `backend/tests/unit/services/test_prompt_version_service.py`
  (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`). Region map:
  | class | lines |
  | ---------------------------------------------------------------------------------------------------------- | ------- |
  | TestGetActiveVersion | 80–109 |
  | TestGetVersionById | 112–139 |
  | TestGetVersionHistory | 142–200 |
  | TestGetNextVersionNumber | 203–230 |
  | TestCreateVersion | 233–298 |
  | TestRestoreVersion | 301–345 |
  | TestGetVersionDiff | 348–394 |
  | TestCalculateDiff | 397–441 |
  | TestCleanupOldVersions | 444–485 |
  | TestDeactivateCurrentVersion | 488–517 |
  | Secondary (endpoint smoke only, POSTGRES-gated): `backend/tests/integration/test_prompt_management_api.py` |
  | (GET /api/prompts/history ~L7, restore ~L11) — asserts response fields but not the exact |
  | `version`/`model`/`created_at` keys of the diff payload. |

## Root cause behind nearly every TEST-GAP cluster

The unit tests use `AsyncMock(spec=AsyncSession)` and patch out internal collaborators
(`_deactivate_current_version`, `_cleanup_old_versions`, `get_active_version`,
`get_version_by_id`, `create_version`). Consequences:

1. **Query objects are never inspected.** `session.execute(<query>)` records whatever is passed
   (including `None`), and `where(col == m)` → `where(col != m)` / `where(None)` / `limit(None)`
   produce queries that behave identically under a mock. Sanity-checked against the repo's
   SQLAlchemy 2.x: `where(None)` compiles to `... AND NULL` (no raise), `limit(None)` drops LIMIT.
   So every filter/order/pagination/operator mutant is invisible.
2. **Collaborator calls are counted, not argument-checked.** `assert_called_once()` everywhere
   (except one good `assert_called_once_with(mock_session, 1)` in `TestRestoreVersion` L325 —
   the pattern that's missing everywhere else).
3. **The constructed `PromptVersion` is never examined.** `session.add` is a `MagicMock`; nobody
   reads `add.call_args.args[0]`, so every field-wiring mutant (`version=None`,
   `is_active=None`, `config_json=None`, dropped kwargs) is invisible.
4. **Response payload asserted only by `["diff"]` and `["version_a"]["id"]`.** The
   `version`/`model`/`created_at` keys of the diff response are built but never read.

## Cluster table (128 survivors, 18 clusters, counts sum exactly)

| #   | Cluster (function · mutation pattern)                                                                                                                                                                                                                                                                                                                                                                             | Count | Class      | Example keys (≤3)                                                                                          |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------- | ---------------------------------------------------------------------------------------------------------- |
| C1  | `_calculate_diff`: `has_changes: bool(added or removed or changed)` → `bool(added or removed and changed)`                                                                                                                                                                                                                                                                                                        | 1     | TEST-GAP   | `_calculate_diff__mutmut_33`                                                                               |
| C2  | `_cleanup_old_versions`: retention SQL unchecked — count/keep/delete query `where` clauses dropped or `==`→`!=`, keep-set `.limit(None)`/`.order_by(None)/desc(None)`, `~id.in_(keep_ids)` → `id.in_(keep_ids)`, whole query / `execute()` arg → `None`                                                                                                                                                           | 21    | TEST-GAP   | `_cleanup_old_versions__mutmut_29`, `_cleanup_old_versions__mutmut_10`†, `_cleanup_old_versions__mutmut_6` |
| C3  | `_cleanup_old_versions`: `total = scalar() or 0` → `or 1`                                                                                                                                                                                                                                                                                                                                                         | 1     | EQUIVALENT | `_cleanup_old_versions__mutmut_9`                                                                          |
| C4  | `_cleanup_old_versions`: early-exit `if total <= MAX` → `if total < MAX`                                                                                                                                                                                                                                                                                                                                          | 1     | LOW-VALUE  | `_cleanup_old_versions__mutmut_10`                                                                         |
| C5  | `_cleanup_old_versions`: `logger.info(f"Cleaned up {len…}")` → `logger.info(None)`                                                                                                                                                                                                                                                                                                                                | 1     | LOW-VALUE  | `_cleanup_old_versions__mutmut_36`                                                                         |
| C6  | Cross-function: collaborator-call-site wiring mutated inside `_deactivate_current_version` (→`get_active_version`), `create_version` (→`get_next_version_number`/`_deactivate_current_version`/`_cleanup_old_versions`), `get_version_diff` (→`get_version_by_id` ×2), `restore_version` (→`create_version`); `session`/`model` args → `None`, first positional dropped; tests assert `assert_called_once()` only | 23    | TEST-GAP   | `_deactivate_current_version__mutmut_4`, `create_version__mutmut_32`, `get_version_diff__mutmut_8`         |
| C7  | `get_active_version`: WHERE-clause SQL unchecked — `is_active == True` → `!= True` / `== False`, `model ==` → `!=`, clause/`select()`/whole-statement → `None`                                                                                                                                                                                                                                                    | 9     | TEST-GAP   | `get_active_version__mutmut_9`, `get_active_version__mutmut_10`, `get_active_version__mutmut_8`            |
| C8  | `get_version_by_id`: `WHERE id == :id` unchecked — `==`→`!=`, clause/`select()`/`execute()` arg → `None`                                                                                                                                                                                                                                                                                                          | 4     | TEST-GAP   | `get_version_by_id__mutmut_5`                                                                              |
| C9  | `get_version_history`: filter/order/pagination SQL + total-count fallback unchecked — `if model is not None` → `is None`, filter `==`→`!=`/dropped, `ORDER BY created_at DESC` dropped, `limit/offset` → `None`, `scalar() or 0` → `or 1`, query/`execute()` → `None`                                                                                                                                             | 16    | TEST-GAP   | `get_version_history__mutmut_6`, `get_version_history__mutmut_22`, `get_version_history__mutmut_17`        |
| C10 | `create_version`: constructed `PromptVersion` row never examined — field kwargs (`model`,`version`,`config_json`,`created_at`,`created_by`,`change_description`,`is_active`) → `None` or dropped, `version=None`/`add(None)`, `refresh(None)`, `next_version=None`, `config_json=json.dumps(None,…)`                                                                                                              | 19    | TEST-GAP   | `create_version__mutmut_17`, `create_version__mutmut_25`, `create_version__mutmut_19`                      |
| C11 | `create_version`: `json.dumps(config, indent=2)` → `indent=None` / `indent` dropped / `indent=3` (whitespace-only)                                                                                                                                                                                                                                                                                                | 3     | EQUIVALENT | `create_version__mutmut_26`, `create_version__mutmut_28`, `create_version__mutmut_29`                      |
| C12 | `create_version`: `logger.info(f"Created version …")` → `logger.info(None)`                                                                                                                                                                                                                                                                                                                                       | 1     | LOW-VALUE  | `create_version__mutmut_36`                                                                                |
| C13 | `get_version_diff`: response contract unchecked — `"version"`/`"model"`/`"created_at"` keys → `"XX…XX"`/`"UPPER"` for both `version_a` and `version_b` blocks; `model_a`/`model_b` → `None`                                                                                                                                                                                                                       | 14    | TEST-GAP   | `get_version_diff__mutmut_31`, `get_version_diff__mutmut_43`, `get_version_diff__mutmut_21`                |
| C14 | `get_version_diff`: `isinstance(…, AIModel)` guards → `and False` / `or True`                                                                                                                                                                                                                                                                                                                                     | 4     | EQUIVALENT | `get_version_diff__mutmut_22`, `get_version_diff__mutmut_23`                                               |
| C15 | `restore_version`: hard-coded `make_active=True` → `None` / `False` (restore must activate the restored version)                                                                                                                                                                                                                                                                                                  | 2     | TEST-GAP   | `restore_version__mutmut_27`, `restore_version__mutmut_20`                                                 |
| C16 | `restore_version`: `isinstance(old_version.model, AIModel)` → `and False` / `or True`                                                                                                                                                                                                                                                                                                                             | 2     | EQUIVALENT | `restore_version__mutmut_12`, `restore_version__mutmut_13`                                                 |
| C17 | `restore_version`: `model_value` / log fiddling — `model_value=None`, `and False`/`or True` branch, `str(None)`, whole `logger.info(...)` → `logger.info(None)` (log-only consumer)                                                                                                                                                                                                                               | 5     | LOW-VALUE  | `restore_version__mutmut_32`, `restore_version__mutmut_28`, `restore_version__mutmut_29`                   |
| C18 | `restore_version`: `make_active=True` kwarg dropped → hits `create_version` default `True`                                                                                                                                                                                                                                                                                                                        | 1     | EQUIVALENT | `restore_version__mutmut_26`                                                                               |

† Cluster membership is a verified exact partition of the 128 survivor keys (no key in two
clusters, none missing; C10 = create_version {1,10–25,30,35}, C13 = get_version_diff
{21,24,31–36,41–46}, C14 = get_version_diff {22,23,25,26}, C6 includes restore_version
{15,21}). Full per-cluster key lists: `/tmp/wp25/wp44-triage-work/clusters.json`. The `_mutmut_10`
(`<` boundary) key is C4, not C2.
EQUIVALENT = 11, LOW-VALUE = 8, TEST-GAP = 109; sum = 128.

## Cluster notes

- **C1 (1, TEST-GAP).** `bool(added or removed and changed)` differs exactly when _only removed
  keys exist_ (`added={}`, `changed={}`, `removed` non-empty): original `has_changes=True`,
  mutant `False`. `TestCalculateDiff.test_identifies_removed_keys` (test file L411–419) exercises
  that exact config pair but asserts only the `removed` dict, never `has_changes`. One added
  assert kills it.
- **C2 (21, TEST-GAP).** The two cleanup tests (L444–485) mock `session.execute` with a
  `side_effect` list and assert only `execute.call_count == 1` / `delete.assert_called_once_with`.
  The most dangerous member is `__mutmut_29`: `~PromptVersion.id.in_(keep_ids)` →
  `id.in_(keep_ids)` — production retention would **delete the 50 newest and keep every old
  version**. `__mutmut_6/16/28` (`==`→`!=`) scope cleanup to _other models' rows_. All 21 killable
  by asserting the compiled SQL of the three `execute` args (see Draft 2).
- **C3 (1, EQUIVALENT).** `scalar()` comes from `SELECT count(*)` → `0` or `n>0` (or `None` only
  on a broken driver). `0→1` and `None→1` both satisfy `total <= 50` → same early return; no path
  to the cleanup body changes.
- **C4 (1, LOW-VALUE).** At the boundary `total == MAX_VERSIONS_PER_MODEL` the mutant runs the
  keep-query and delete-query anyway; every row is in the keep set, so 0 rows are deleted and no
  log fires. Cost: 2 extra no-op queries. Not worth an assertion.
- **C5/C12/C17 (7, LOW-VALUE).** `logger.info(None)` and the `model_value` ternary variants only
  alter the log line (`None` formats as `"None"`); no return value or state changes. Debug-log
  cosmetics — do not test.
- **C6 (23, TEST-GAP).** Two sub-shapes, same root cause (mocked collaborator + count-only assert):
  (a) patched collaborators (`AsyncMock`) silently swallow `None`/missing args — the real methods
  would `TypeError` (dropped first positional) or query the wrong model (`model=None`);
  (b) `get_next_version_number`/`get_version_by_id` (not always patched) receive `None` and the
  wrong-scope query is invisible. Kill style: `assert_called_once_with(mock_session, AIModel.X)`
  on the patches, plus one compiled-SQL assert for the unpatched ones. The existing
  `TestRestoreVersion` L325 proves the house style accepts `assert_called_with`.
- **C7 (9, TEST-GAP).** `is_active == True` → `!= True` / `== False` inverts the active-version
  lookup (restore/cleanup then deactivate the wrong rows or none). Tests only stub the result.
  One SQL-shape assert (Draft 5a) kills all 9.
- **C8 (4, TEST-GAP).** Same for the primary-key lookup: `id == :id` → `id != :id` makes
  `get_version_by_id(7)` return an arbitrary _other_ row — silently feeding the wrong config into
  restore/diff. `id == None` renders `IS NULL` (verified). Draft 5b.
- **C9 (16, TEST-GAP).** Includes the model-filter polarity flip `__mutmut_6` (filter applied to
  the unfiltered query and vice-versa — cross-model leakage), missing `DESC` ordering (oldest
  page returned first), dropped `LIMIT/OFFSET` (whole table returned / wrong page), and
  `total_count = scalar() or 1` (empty history reports total=1 to the API).
  `test_respects_limit_and_offset` (L185–200) even comments "_The actual query would have limit
  and offset applied_" — i.e., the test author knew nobody verified it. Draft 3.
- **C10 (19, TEST-GAP).** `session.add` is a `MagicMock` (fixture L37); nobody ever reads the row.
  Asserting `add.call_args.args[0]`'s fields (and that `refresh` got that same object) kills all
  19, including `is_active=None` (falsy — an "inactive" new active version), `created_at=None`
  (breaks retention ordering downstream) and `config_json="null"` (`__mutmut_25`, silently empty
  config; the model's `config` property would round-trip to `{}` via `safe_json_loads` default).
  Draft 4 covers the row shape.
- **C11 (3, EQUIVALENT).** `indent=2` vs `indent=None`/dropped/`3`: `json.loads` round-trips to the
  identical dict (verified against this repo's SQLAlchemy/py versions); the read side is
  `PromptVersion.config` → `safe_json_loads`. No consumer byte-compares `config_json`. Skip.
- **C13 (14, TEST-GAP, highest count).** The response _is_ built at the asserted path; the test
  only reads `["version_a"]["id"]`, `["version_b"]["id"]` and `["diff"]…`. Renamed/uppercased
  `version`/`model`/`created_at` keys break the API contract for the frontend diff view with no
  test redness. `model_a=None` (`__mutmut_21/24`) is included — killed by the same `== "nemotron"`
  assert. Draft 1 (biggest single-test kill per line of code).
- **C14 (4, EQUIVALENT).** `AIModel` is a **str-Enum** (`backend/models/prompt_version.py` L18):
  the member _is_ the string (`AIModel.NEMOTRON == "nemotron"` → True, verified), so `.value` vs
  the member JSON-serializes identically; `or True` (always-take `.value`) equals the original on
  real ORM rows (the column always loads an enum member — `values_callable` config); `and False`
  only downgrades str-purity of an already-str-compatible value. Only `type(x) is str` asserts
  could kill these — over-specification. Skip.
- **C15 (2, TEST-GAP).** `make_active=False` on restore is a real behavior bug: the "restored"
  version would sit inactive while the old active one stays active. The existing test inspects
  `create_version` call kwargs (L329–334) but skips `make_active`. Draft 4 includes the assert.
- **C16 (2, EQUIVALENT).** `AIModel(x)` accepts both a member and its value string and returns the
  identical member (verified: `AIModel(AIModel.NEMOTRON) is AIModel.NEMOTRON`,
  `AIModel("nemotron") == "nemotron"`), so forcing the constructor (`and False`) or skipping the
  conversion (`or True`) is indistinguishable for both input shapes reachable from ORM rows.
- **C18 (1, EQUIVALENT).** `create_version`'s default is `make_active=True`, so dropping the
  explicit kwarg preserves behavior exactly.

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure for every draft: apply the cluster's mutant line → run the new test → it must FAIL
(the assert names the mutated expression); revert to original source → it must PASS. Run only via
the WP4.4 runner window (no test execution was performed while producing this dossier).

All drafts target `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_prompt_version_service.py`
and reuse its existing `service` / `mock_session` / `sample_version` fixtures (L25–58) and imports
(L1–22); new imports required are listed per draft.

### Draft 1 — kills C13 (14 survivors) — diff response contract

Add to file (also needs `import re` if you assert ISO format; the equality asserts below don't need it):

```python
class TestGetVersionDiffResponseContract:
    """The diff response payload keys/values are part of the API contract."""

    @pytest.mark.asyncio
    async def test_diff_response_includes_version_model_and_created_at(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """version_a/version_b blocks expose id, version, model (string), created_at (ISO).

        Kills get_version_diff mutants that rename/case-mangle the "version"/"model"/
        "created_at" keys (__mutmut_31-36, 41-46) or null the model values (__mutmut_21, 24).
        """
        t_a = datetime(2026, 1, 1, tzinfo=UTC)
        t_b = datetime(2026, 1, 2, tzinfo=UTC)
        version_a = PromptVersion(
            id=1, model=AIModel.NEMOTRON, version=1,
            config_json=json.dumps({"prompt": "old"}), created_at=t_a, is_active=False,
        )
        version_b = PromptVersion(
            id=2, model=AIModel.NEMOTRON, version=2,
            config_json=json.dumps({"prompt": "new"}), created_at=t_b, is_active=True,
        )

        with patch.object(service, "get_version_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [version_a, version_b]

            result = await service.get_version_diff(mock_session, 1, 2)

            assert result["version_a"] == {
                "id": 1, "version": 1, "model": "nemotron", "created_at": t_a.isoformat(),
            }
            assert result["version_b"] == {
                "id": 2, "version": 2, "model": "nemotron", "created_at": t_b.isoformat(),
            }
```

Exact-dict equality kills key renames (`"XXversionXX"`, `"VERSION"`), value nulls, and any added
key. (`==` with a str-enum member passes for the `and False`/`or True` guards — those stay
EQUIVALENT in C14 by design.)

### Draft 2 — kills C2 (21 survivors) — cleanup retention SQL

Add import: `from sqlalchemy import select as sa_select` is NOT needed; add
`from typing import Sequence` only if type-hinting. Uses only existing imports plus
`Call` from unittest is unnecessary — read `mock_session.execute.call_args_list`.

```python
def _compiled(stmt) -> str:
    """Render a SQLAlchemy statement with literal binds, for SQL-shape assertions."""
    assert stmt is not None, "query passed to session.execute() was None"
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


class TestCleanupOldVersionsQueries:
    """Retention must scope to one model, keep the NEWEST MAX_VERSIONS and delete the rest."""

    @pytest.mark.asyncio
    async def test_cleanup_queries_are_correctly_scoped(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills _cleanup_old_versions mutants 2,3,5,6,11-17,19,22-28,32 (__mutmut_29 included):
        count/keep/delete queries lose the model filter, the keep-set limit/order, or the
        NOT-IN inversion that protects the newest versions.
        """
        count_result = MagicMock()
        count_result.scalar.return_value = MAX_VERSIONS_PER_MODEL + 5
        keep_result = MagicMock()
        keep_result.fetchall.return_value = [(i,) for i in range(MAX_VERSIONS_PER_MODEL)]
        old_version = MagicMock(spec=PromptVersion)
        delete_result = MagicMock()
        delete_result.scalars.return_value.all.return_value = [old_version]
        mock_session.execute.side_effect = [count_result, keep_result, delete_result]

        await service._cleanup_old_versions(mock_session, AIModel.NEMOTRON)

        count_q, keep_q, delete_q = (c.args[0] for c in mock_session.execute.call_args_list)

        count_sql = _compiled(count_q)
        assert "count(" in count_sql.lower()
        assert "prompt_versions.model = 'nemotron'" in count_sql

        keep_sql = _compiled(keep_q)
        assert "prompt_versions.model = 'nemotron'" in keep_sql
        assert "ORDER BY prompt_versions.created_at DESC" in keep_sql
        assert f"LIMIT {MAX_VERSIONS_PER_MODEL}" in keep_sql

        delete_sql = _compiled(delete_q)
        assert "prompt_versions.model = 'nemotron'" in delete_sql
        assert "NOT IN" in delete_sql.upper().replace("NOT  IN", "NOT IN")
        assert "prompt_versions.id IN" not in delete_sql.replace("NOT IN", "")
```

Verified against this repo's SQLAlchemy: the original compiles to
`... WHERE prompt_versions.model = 'nemotron' AND (prompt_versions.id NOT IN (...))`; the
`__mutmut_29` inversion compiles to `... AND prompt_versions.id IN (...)` with no `NOT IN`,
and `limit(None)` drops the `LIMIT` clause — each asserted line fails on its mutant.

### Draft 3 — kills C9 (16 survivors) — history filter/order/pagination SQL + total fallback

```python
class TestGetVersionHistoryQueries:
    """History SQL shape: model filter applied iff requested, newest-first, LIMIT/OFFSET, total 0."""

    @pytest.mark.asyncio
    async def test_history_sql_filters_by_model_when_given(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills get_version_history __mutmut_6/8/9/10/11/12 (filter polarity/content) and
        __mutmut_2/5/14/18/24 (query or execute-arg None)."""
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        versions_result = MagicMock()
        versions_result.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [count_result, versions_result]

        await service.get_version_history(mock_session, model=AIModel.NEMOTRON)

        count_q, page_q = (c.args[0] for c in mock_session.execute.call_args_list)
        assert "prompt_versions.model = 'nemotron'" in _compiled(count_q)
        assert "prompt_versions.model = 'nemotron'" in _compiled(page_q)

    @pytest.mark.asyncio
    async def test_history_sql_omits_filter_orders_and_pages(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills __mutmut_6 (no-model path gains a filter), 19-22 (offset/limit/order dropped)."""
        count_result = MagicMock()
        count_result.scalar.return_value = 100
        versions_result = MagicMock()
        versions_result.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [count_result, versions_result]

        await service.get_version_history(mock_session, limit=10, offset=20)

        count_q, page_q = (c.args[0] for c in mock_session.execute.call_args_list)
        assert "WHERE" not in _compiled(count_q)
        page_sql = _compiled(page_q)
        assert "WHERE" not in page_sql
        assert "ORDER BY prompt_versions.created_at DESC" in page_sql
        assert "LIMIT 10" in page_sql
        assert "OFFSET 20" in page_sql

    @pytest.mark.asyncio
    async def test_history_total_is_zero_when_no_versions(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills __mutmut_17 (`scalar() or 0` → `or 1`): empty history must report total 0."""
        count_result = MagicMock()
        count_result.scalar.return_value = None
        versions_result = MagicMock()
        versions_result.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [count_result, versions_result]

        _versions, total = await service.get_version_history(mock_session)

        assert total == 0
```

### Draft 4 — kills C10 (19) + C15 (2) + most of C6 (23) — row shape & collaborator args

```python
class TestCreateVersionRowAndWiring:
    """create_version must build a fully-populated row and call helpers with the right session/model."""

    @pytest.mark.asyncio
    async def test_create_version_builds_complete_prompt_version_row(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills create_version __mutmut_1,10-25,30,35 (row fields None/dropped, add/refresh(None))."""
        version_result = MagicMock()
        version_result.scalar.return_value = 3  # next version = 3
        mock_session.execute.return_value = version_result

        with (
            patch.object(service, "_deactivate_current_version", new_callable=AsyncMock),
            patch.object(service, "_cleanup_old_versions", new_callable=AsyncMock),
        ):
            config = {"system_prompt": "Test prompt"}
            await service.create_version(
                mock_session,
                model=AIModel.NEMOTRON,
                config=config,
                created_by="test_user",
                change_description="Test change",
                make_active=True,
            )

        row = mock_session.add.call_args.args[0]
        assert isinstance(row, PromptVersion)
        assert row.model == AIModel.NEMOTRON
        assert row.version == 3
        assert json.loads(row.config_json) == config  # kills config_json=None / dumps(None)
        assert row.created_at is not None
        assert row.created_by == "test_user"
        assert row.change_description == "Test change"
        assert row.is_active is True
        mock_session.refresh.assert_called_once_with(row)

    @pytest.mark.asyncio
    async def test_create_version_passes_session_and_model_to_collaborators(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills create_version __mutmut_3,6,7,8,9,31,32,33,34 (None/dropped call args)."""
        version_result = MagicMock()
        version_result.scalar.return_value = 1
        mock_session.execute.return_value = version_result

        with (
            patch.object(service, "get_next_version_number", new_callable=AsyncMock) as mock_next,
            patch.object(service, "_deactivate_current_version", new_callable=AsyncMock) as mock_deact,
            patch.object(service, "_cleanup_old_versions", new_callable=AsyncMock) as mock_clean,
        ):
            mock_next.return_value = 1
            await service.create_version(
                mock_session, model=AIModel.NEMOTRON, config={"k": "v"}, make_active=True
            )

        mock_next.assert_called_once_with(mock_session, AIModel.NEMOTRON)
        mock_deact.assert_called_once_with(mock_session, AIModel.NEMOTRON)
        mock_clean.assert_called_once_with(mock_session, AIModel.NEMOTRON)

    @pytest.mark.asyncio
    async def test_deactivate_current_version_queries_active_for_this_model(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills _deactivate_current_version __mutmut_2-5 (None/dropped call args)."""
        with patch.object(service, "get_active_version", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            await service._deactivate_current_version(mock_session, AIModel.NEMOTRON)
            mock_get.assert_called_once_with(mock_session, AIModel.NEMOTRON)

    @pytest.mark.asyncio
    async def test_get_version_diff_looks_up_both_ids_with_session(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills get_version_diff __mutmut_2-5,7-10 (None/dropped lookup args)."""
        from unittest.mock import call

        with patch.object(service, "get_version_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = ValueError("stop")  # fail fast after both lookups
            with pytest.raises(ValueError):
                await service.get_version_diff(mock_session, 1, 2)
            mock_get.assert_has_calls([call(mock_session, 1), call(mock_session, 2)])

    @pytest.mark.asyncio
    async def test_restore_version_reactivates_with_same_session(
        self,
        service: PromptVersionService,
        mock_session: AsyncMock,
        sample_version: PromptVersion,
    ) -> None:
        """Kills restore_version __mutmut_15,21 (session wiring) and __mutmut_20,27 (make_active)."""
        with patch.object(service, "get_version_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_version
            with patch.object(service, "create_version", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock(version=2)
                await service.restore_version(mock_session, version_id=1)
                kwargs = mock_create.call_args.kwargs
                assert kwargs["session"] is mock_session
                assert kwargs["make_active"] is True
```

Notes: `test_get_version_diff_looks_up_both_ids_with_session` relies on both lookups running
_before_ the None-check raises — `ValueError("stop")` as the `side_effect` makes the SECOND
lookup raise, after both `call`s are recorded. If a mutant drops the second lookup, `assert_has_calls`
fails. (The C6 member `get_version_diff__mutmut_4/9` — dropped first positional — makes the first
call `call(1)` instead of `call(mock_session, 1)` → `assert_has_calls` fails. ✓)

### Draft 5 — kills C7 (9) + C8 (4) + C1 (1) — selector WHERE clauses and has_changes

```python
class TestSelectorQueries:
    """Active-version and by-id lookups must compile to the intended WHERE clause."""

    @pytest.mark.asyncio
    async def test_get_active_version_sql_targets_active_rows_for_model(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills get_active_version __mutmut_2-10 (clause None/dropped, model flip,
        is_active == True → != True / == False)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await service.get_active_version(mock_session, AIModel.NEMOTRON)

        sql = _compiled(mock_session.execute.call_args.args[0])
        assert "prompt_versions.model = 'nemotron'" in sql
        assert "prompt_versions.is_active = true" in sql
        assert "!=" not in sql
        assert "is_active = false" not in sql.lower()

    @pytest.mark.asyncio
    async def test_get_version_by_id_sql_filters_on_exact_id(
        self, service: PromptVersionService, mock_session: AsyncMock
    ) -> None:
        """Kills get_version_by_id __mutmut_2-5 (execute/query None, clause dropped, id != )."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await service.get_version_by_id(mock_session, 7)

        sql = _compiled(mock_session.execute.call_args.args[0])
        assert "prompt_versions.id = 7" in sql
        assert "!=" not in sql

    def test_calculate_diff_removed_only_still_has_changes(self, service: PromptVersionService) -> None:
        """Kills _calculate_diff __mutmut_33 (`or` chain → `or removed and changed`)."""
        diff = service._calculate_diff({"existing": "v", "gone": "x"}, {"existing": "v"})

        assert diff["removed"] == {"gone": "x"}
        assert diff["has_changes"] is True
```

## Kill-coverage math

| Draft             | Clusters killed | Survivors                         |
| ----------------- | --------------- | --------------------------------- |
| D1                | C13             | 14                                |
| D2                | C2              | 21                                |
| D3                | C9              | 16                                |
| D4                | C10 + C15 + C6  | 44                                |
| D5                | C7 + C8 + C1    | 14                                |
| **Total drafted** |                 | **109 = every TEST-GAP survivor** |

Remaining 19: EQUIVALENT (11: C3, C11, C14, C16, C18) — recommend `mutmut` triage/skip markers,
not tests; LOW-VALUE (8: C4, C5, C12, C17) — log/boundary cosmetics, recommend skip.

## Sanity evidence (no repo tests were run)

A standalone script against this repo's own `.venv` SQLAlchemy confirmed every load-bearing
compile fact used in the drafts: `where(None)` → `... AND NULL` (no raise), `limit(None)`/
`offset(None)`/`order_by(None)` drop their clauses, `desc(None)` → `ORDER BY NULL DESC`,
`model == None` → `IS NULL`, original active-filter compiles to `model = 'nemotron' AND
is_active = true`, NOT-IN inversion loses `NOT IN`, str-Enum identity
(`AIModel(AIModel.NEMOTRON) is AIModel.NEMOTRON`, `== "nemotron"`), and `json.dumps`
`indent` variants round-trip equal via `json.loads`. Script:
`/tmp/wp25/wp44-triage-work/sanity.py`.
