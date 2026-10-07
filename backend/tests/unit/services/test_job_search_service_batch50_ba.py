"""Campaign #50 (batch-50, battery BA) - `backend.services.job_search_service`.

# TARGET-MODULE: backend.services.job_search_service

The module sat at 185 survivors / 475 keys (61.0526%). The shipped test file
drives the search entry points through REAL filters and asserts the RESULT
SETS, but never the exact log message/extra surface, never the sort-key
DEFAULTS on absent fields, never the filter-helper DEFAULT polarities
(job.get(x, "") arms), never the exact filter-kwarg forwarding, and never
the exact timestamp/duration BOUNDARIES - so the None-swap / XX-wrap /
case-flip / drop-argument families survived: the 34 sort-key arms, the
aggregation "unknown" default arms, the filter-kwarg families of both
module-level searches (m11-m32 / m11-m33), the log message + extra-key
families, the boundary <= families and the sort_order comparison arms.

Harness contract (b30 sweep, /home/agent/runs/b30-sweep.py): NO pytest
fixtures, NO parametrize, NO monkeypatch - the sweep imports this file
directly and calls every module-level ``test_*`` with zero arguments in ONE
process, flipping os.environ[MUTANT_UNDER_TEST] per key. Async entry points
are driven with asyncio.run INSIDE the test body; the wrapper seam is
patched through the TARGET MODULE's globals
(jss.search_jobs_with_aggregations is looked up in the module dict at call
time) with attribute save/restore through _Patcher so a mid-test assert
failure cannot leak a patch into the next key's window. No filesystem, no
sleeps, no TZ dependence: every datetime in the drives is tz-aware UTC and
EVERY filter boundary is asserted at the EXACT boundary instant.

KILL CONSTRUCTIONS (why each family bites its keys, not just its shipped run):

  * CollectorCtx + MESSAGE EQUALITY on r.getMessage() (search_jobs logs
    DEBUG "Job search completed", sjwa logs INFO "Job search with
    aggregations completed"): the None / XX / lower / UPPER arms all die to
    equality - never a substring or level-only census (fragment-count
    family is a documented survivor cause). Structured-extra arms die to
    record.<key> attribute reads (total / returned / filters / aggregations)
    plus a FULL-DICT equality on the nested filters dict - a renamed or
    case-flipped key lands under a different attribute (getattr sentinel
    mismatch) or a different dict key; extra=None / dropped extra= leave
    the attributes absent (sentinel mismatch).
  * Filter-kwarg families (query/statuses/job_types/queue/created_*/
    completed_*/has_error/min_/_max_duration, both None-swap and DROP
    forms) are killed through the FILTER EFFECT: every drive sets exactly
    one filter to a value that EXCLUDES one of two tracker jobs; a
    dropped/None'd filter returns the excluded job too (total + id-list
    mismatch). The wrapper (JobSearchService.search) arms are killed at the
    CALL SITE with a fixed-surface recording spy (dropped-kwarg memory: an
    arg drop with a value-equal default is invisible downstream - the
    spy's kwargs-dict EQUALITY is the only surface that sees it).
  * `or []` arms (search_jobs m13/m24/m34, sjwa m12/m23/m33): the falsy leg
    (None / [] passed for statuses/job_types) must NOT filter (both jobs
    return), and the truthy leg must pass the list VERBATIM - m34/m33
    (`job_types and []` / `statuses and []`) turn a truthy selection into
    the [] wildcard, so the truthy drive asserts the EXCLUDED job is gone.
  * Sort arms: two jobs whose progress order is the REVERSE of their
    created_at order (order-robust sort pitfall - no ties anywhere), driven
    with sort_by="progress" AND both sort_order legs. reverse=None is
    FALSY (reorders like False), the != arm flips, the always-False arms
    (sort_order==None / sort_order.lower()=="XXdescXX" / =="DESC") reorder;
    the sort_by->None arms silently sort by created_at.
  * Default-polarity arms ("" vs None vs 0 vs "XXXX" vs case keys): every
    helper gets an ABSENT-field drive (dict.get default live) AND a
    PRESENT-field drive (wrong-key arms return the default), asserting
    VALUE EQUALITY - the trailing-comma family (mutmut drops the default
    after a lone comma) is covered by the same absent-field drives because
    get(k) == get(k, None).
  * Boundary arms (<= vs <, >= vs >): driven at the EXACT boundary
    timestamp/duration (inclusive semantics: equality PASSES the filter)
    and one second past - the only inputs where <= and < diverge.

LEDGER CANDIDATE (pre-adjudicated, env-independent proof; disposition is
confirmed post-run by BODY identity - never by key number). FIVE keys:

  * search_jobs m14 / m25 and search_jobs_with_aggregations m14 / m25 -
    the queue= kwarg into JobSearchFilters set to None / dropped.
    JobSearchFilters.queue is a WRITE-ONLY field: the only reads of
    filters.* in the module are query/statuses/job_types/created_after/
    created_before/completed_after/completed_before/has_error/min_duration/
    max_duration (the _filter_job body) - queue is never read, never
    serialized (the log filters dict names only query/statuses/job_types/
    has_error; JobSearchResult.to_dict has jobs/total/aggregations), and no
    consumer outside the module constructs or inspects JobSearchFilters
    (backend/api/dependencies.py and backend/api/routes/jobs.py go through
    the wrapper, which forwards queue as an ARGUMENT - and THOSE arms,
    wrapper m5/m18, are killable by the spy). No environment can separate
    the two.
  * _calculate_job_duration m9 `not started or not completed` -> `not
    started and not completed` is DEAD-GUARD-ABSORBED. The mutant only
    proceeds past the first guard when at least one stamp is present; the
    SECOND guard `if started_at and completed_at` (unmutated under m9)
    returns None whenever a parse is missing, and _parse_datetime is TOTAL
    (every failure path returns None, never raises), so for every input the
    mutant reaches, shipped already returned the same value - both None
    when exactly one stamp is absent, both the exact float when both
    parse. The M46 dead-guard and #38 precedents. Witness tests below.

NOT ledger, killed drives (pre-adjudication REVISED by measurement):

  * _parse_datetime m7 replace("Z", "+00:00") -> replace("XXZXX", ...) is
    NOT a no-op: the full-length "…T12:00:00Z" leg IS a native-parse clone
    on the pinned 3.14 (fromisoformat accepts a trailing Z, measured
    identical aware datetime), but a DATE-ONLY "2026-01-15Z" diverges -
    shipped's replace yields fromisoformat("2026-01-15+00:00") = naive
    midnight, the mutant's no-op raises ValueError -> None (both measured
    on the pinned .venv). Driven by an EQUALITY assert on that input. The
    first adjudication claimed clone-on-every-input; the date-only input
    falsifies it - corrected BEFORE the run, not post-hoc.
  * search_jobs_with_aggregations m45 reverse = sort_order.upper() ==
    "desc": divergent on sort_order="DESC" (shipped reverse=True, mutant
    False). Driven by the order leg on the case-insensitive input.

Key numbers cited in comments (m7, m9, m14, m45...) are the b50-era tree
spellings from b50-survivor-table.txt (real key numbers from the meta, NOT
diff line numbers - the b49 lesson); post-run adjudication is BY BODY.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from backend.services import job_search_service as jss

T = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
T_MINUS = datetime(2026, 1, 15, 11, 0, 0, tzinfo=UTC)
T_PLUS = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
T_EXACT = datetime(2026, 1, 15, 12, 0, 1, tzinfo=UTC)  # 1 s past T
T_DONE = datetime(2026, 1, 15, 10, 0, 30, tzinfo=UTC)  # job A's completed instant
T_DONE_PAST = datetime(2026, 1, 15, 10, 0, 31, tzinfo=UTC)  # 1 s past it
_SENT = object()  # missing-attribute sentinel


# ---------------------------------------------------------------------------
# Harness helpers (b30-clean: no fixtures, no monkeypatch, no parametrize)
# ---------------------------------------------------------------------------


class _Patcher:
    """Minimal attribute save/restore (no monkeypatch in the b30 harness)."""

    def __init__(self, *triples: tuple[Any, str, Any]) -> None:
        self.triples = triples
        self.saved: list[tuple[Any, str, Any]] = []

    def __enter__(self) -> None:
        for obj, attr, value in self.triples:
            self.saved.append((obj, attr, getattr(obj, attr)))
            setattr(obj, attr, value)

    def __exit__(self, *exc: Any) -> bool:
        for obj, attr, value in reversed(self.saved):
            setattr(obj, attr, value)
        return False


class LogCollector(logging.Handler):
    """Collects records off jss.logger (DEBUG level, propagation off)."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class CollectorCtx:
    def __init__(self) -> None:
        self.collector = LogCollector()
        self._old_level = 0
        self._old_propagate = False

    def __enter__(self) -> LogCollector:
        self._old_level = jss.logger.level
        self._old_propagate = jss.logger.propagate
        jss.logger.addHandler(self.collector)
        jss.logger.setLevel(logging.DEBUG)
        jss.logger.propagate = False
        return self.collector

    def __exit__(self, *exc: Any) -> bool:
        jss.logger.removeHandler(self.collector)
        jss.logger.setLevel(self._old_level)
        jss.logger.propagate = self._old_propagate
        return False


class FixedTracker:
    """JobTracker twin: get_all_jobs() answers a fixed job list (fresh copy)."""

    def __init__(self, jobs: list[dict[str, Any]]) -> None:
        self.jobs = jobs

    def get_all_jobs(self) -> list[dict[str, Any]]:
        return list(self.jobs)


def J(**over: Any) -> dict[str, Any]:
    """Job twin with DISTINCT fixed values; overrides win. Defaults match
    NO query, carry no error, and have NO duration stamps."""
    job: dict[str, Any] = {
        "job_id": "J-1",
        "job_type": "face_enrollment",
        "status": "completed",
        "created_at": T,
        "started_at": None,
        "completed_at": None,
        "progress": 100,
        "message": "routine text",
        "error": None,
        "result": None,
    }
    job.update(over)
    return job


def A(**over: Any) -> dict[str, Any]:
    """Order pair member A: created T (LATER) but progress 0 (FIRST asc)."""
    return J(job_id="A", created_at=T, progress=0, **over)


def B(**over: Any) -> dict[str, Any]:
    """Order pair member B: created T-1h (EARLIER) but progress 100 (LAST)."""
    return J(job_id="B", created_at=T_MINUS, progress=100, **over)


def attr(rec: logging.LogRecord, name: str) -> Any:
    """getattr with a MISSING sentinel (an absent extra key mismatches)."""
    return getattr(rec, name, _SENT)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


class SpyFn:
    """Recording async twin of search_jobs_with_aggregations with a FIXED
    keyword surface: stores the EXACT kwargs dict (a dropped/renamed
    forwarded kwarg is a dict-equality mismatch) and hands back a sentinel
    the wrapper must return verbatim."""

    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    async def __call__(self, **kwargs: Any) -> str:
        self.kwargs = kwargs
        return "SPYRESULT"


SPY_KEYS = {
    "job_tracker",
    "query",
    "statuses",
    "job_types",
    "queue",
    "created_range",
    "completed_range",
    "has_error",
    "duration_range",
    "limit",
    "offset",
    "sort_by",
    "sort_order",
}

# Distinct per-argument values so ANY swap/None/drop is a dict mismatch.
SPY_ARGS: dict[str, Any] = {
    "query": "needle",
    "statuses": ["running"],
    "job_types": ["face_enrollment"],
    "queue": "q7",
    "created_range": (T_MINUS, T_PLUS),
    "completed_range": (T, T_PLUS),
    "has_error": False,
    "duration_range": (5.0, 95.0),
    "limit": 3,
    "offset": 1,
    "sort_by": "progress",
    "sort_order": "asc",
}


def wrapper_full_kwargs() -> dict[str, Any]:
    return {"job_tracker": "TRACKER", **SPY_ARGS}


# ---------------------------------------------------------------------------
# _parse_datetime
# ---------------------------------------------------------------------------


def test_parse_datetime_none_and_datetime_pass_through() -> None:
    assert jss._parse_datetime(None) is None
    assert jss._parse_datetime(T) is T
    assert jss._parse_datetime("2026-01-15T12:00:00") == datetime(
        2026, 1, 15, 12, 0
    )  # naive stays naive


def test_parse_datetime_z_suffix_yields_utc_aware() -> None:
    # m7 clone leg: shipped replaces Z->+00:00, the mutant no-ops; 3.14
    # fromisoformat accepts a trailing Z natively -> BOTH spellings
    # produce this exact aware datetime.
    assert jss._parse_datetime("2026-01-15T12:00:00Z") == T
    assert jss._parse_datetime("2026-01-15T12:00:00.000Z") == T


def test_parse_datetime_date_only_z_diverges_from_native_parse() -> None:
    # m7 kill leg: shipped "2026-01-15Z" -> replace -> fromisoformat(
    # "2026-01-15+00:00") = NAIVE midnight; the mutant's no-op replacement
    # leaves "2026-01-15Z", which native parsing REJECTS (ValueError ->
    # None). Both outcomes measured on the pinned .venv.
    assert jss._parse_datetime("2026-01-15Z") == datetime(2026, 1, 15, 0, 0)


def test_parse_datetime_lowercase_z_and_garbage_are_none() -> None:
    # m8 replace("z", "+00:00") PARSES the lowercase leg shipped REJECTS
    # (fromisoformat is strict about the lowercase z).
    assert jss._parse_datetime("2026-01-15T12:00:00z") is None
    assert jss._parse_datetime("garbage") is None
    assert jss._parse_datetime("-1") is None


# ---------------------------------------------------------------------------
# _calculate_job_duration
# ---------------------------------------------------------------------------


def test_duration_happy_path_is_exact_seconds() -> None:
    job = J(started_at="2026-01-15T10:00:00Z", completed_at="2026-01-15T10:00:30Z")
    assert jss._calculate_job_duration(job) == 30.0


def test_duration_missing_either_stamp_is_none() -> None:
    # LEDGER witness (_calculate_job_duration m9): or/and guards answer
    # None identically for EVERY absent-stamp input (second guard + the
    # total _parse_datetime).
    assert jss._calculate_job_duration(J(started_at=None, completed_at=None)) is None
    assert (
        jss._calculate_job_duration(J(started_at="2026-01-15T10:00:00Z", completed_at=None)) is None
    )
    assert (
        jss._calculate_job_duration(J(started_at=None, completed_at="2026-01-15T10:00:00Z")) is None
    )


def test_duration_unparseable_stamp_is_none_not_typeerror() -> None:
    # m16 (`started_at and completed_at` -> `or`): with BOTH strings
    # present but one unparseable, shipped falls through to None; the
    # mutant subtracts None -> TypeError.
    assert (
        jss._calculate_job_duration(J(started_at="2026-01-15T10:00:00Z", completed_at="nonsense"))
        is None
    )
    assert (
        jss._calculate_job_duration(J(started_at="nonsense", completed_at="2026-01-15T10:00:30Z"))
        is None
    )


# ---------------------------------------------------------------------------
# _matches_text_query
# ---------------------------------------------------------------------------


def test_text_query_hits_each_field_and_misses_all() -> None:
    assert jss._matches_text_query(J(), "") is True  # empty query matches all
    assert jss._matches_text_query(J(job_type="Face_Enroll"), "face") is True
    assert jss._matches_text_query(J(job_type="other", error="NEEDLE failed"), "needle") is True
    assert jss._matches_text_query(J(job_type="other", message="a NEEDLE here"), "needle") is True
    assert jss._matches_text_query(J(job_type="other", result="found a NEEDLE"), "needle") is True
    assert (
        jss._matches_text_query(J(job_type="other", result={"k": "NEEDLE inside"}), "needle")
        is True
    )
    assert jss._matches_text_query(J(job_type="other", result={"k": 5}), "needle") is False


def test_text_query_absent_job_type_default_is_empty_string() -> None:
    # m8/m10: default None -> None.lower() AttributeError; the shipped
    # default "" makes the miss fall through to the other arms.
    job = J()
    del job["job_type"]
    assert jss._matches_text_query(job, "face") is False


def test_text_query_absent_job_type_default_is_not_xxxx() -> None:
    # m13: default "XXXX" would match the query "xxxx"; shipped never does.
    job = J()
    del job["job_type"]
    assert jss._matches_text_query(job, "xxxx") is False


def test_text_query_string_result_membership_is_case_frozen() -> None:
    # m38 (`in` -> `not in`) and m39 (`result.lower()` -> `result.upper()`)
    # both flip the string-result arm; membership stays case-SENSITIVE
    # because query_lower is already lower case.
    assert jss._matches_text_query(J(job_type="other", result="has NEEDLE"), "needle") is True
    assert jss._matches_text_query(J(job_type="other", result="no hit"), "needle") is False


# ---------------------------------------------------------------------------
# _matches_status_filter / _matches_type_filter
# ---------------------------------------------------------------------------


def test_status_filter_absent_status_default_polarities() -> None:
    # m6/m8: default None -> str(None) == "None" joins the filter universe;
    # shipped's default is the EMPTY string, which only matches [""].
    # m11: default "XXXX".
    job = J()
    del job["status"]
    assert jss._matches_status_filter(job, ["None"]) is False
    assert jss._matches_status_filter(job, [""]) is True
    assert jss._matches_status_filter(job, ["XXXX"]) is False


def test_status_filter_present_values() -> None:
    assert jss._matches_status_filter(J(), []) is True
    assert jss._matches_status_filter(J(), ["completed"]) is True
    assert jss._matches_status_filter(J(status="None"), ["None"]) is True  # str() wrap live
    assert jss._matches_status_filter(J(status="pending"), ["completed"]) is False


def test_type_filter_absent_type_default_polarities() -> None:
    # m4/m6 default None (`None in job_types` vs shipped `"" in job_types`)
    # and m9 default "XXXX".
    job = J()
    del job["job_type"]
    assert jss._matches_type_filter(job, [None]) is False
    assert jss._matches_type_filter(job, [""]) is True
    assert jss._matches_type_filter(job, ["XXXX"]) is False


def test_type_filter_present_values() -> None:
    assert jss._matches_type_filter(J(), []) is True
    assert jss._matches_type_filter(J(), ["face_enrollment"]) is True
    assert jss._matches_type_filter(J(job_type="other"), ["face_enrollment"]) is False


# ---------------------------------------------------------------------------
# _matches_timestamp_filter (boundary arms m7/m10/m21/m24)
# ---------------------------------------------------------------------------


def test_timestamp_created_boundaries_are_inclusive_at_equality() -> None:
    job = J(created_at=T)
    assert jss._matches_timestamp_filter(job, T, None, None, None) is True  # == after PASSES
    assert jss._matches_timestamp_filter(job, T_EXACT, None, None, None) is False
    assert jss._matches_timestamp_filter(job, None, T, None, None) is True  # == before PASSES
    assert jss._matches_timestamp_filter(job, None, T_MINUS, None, None) is False


def test_timestamp_completed_boundaries_are_inclusive_at_equality() -> None:
    job = J(completed_at=T)
    assert jss._matches_timestamp_filter(job, None, None, T, None) is True
    assert jss._matches_timestamp_filter(job, None, None, T_EXACT, None) is False
    assert jss._matches_timestamp_filter(job, None, None, None, T) is True
    assert jss._matches_timestamp_filter(job, None, None, None, T_MINUS) is False


def test_timestamp_completed_filters_reject_uncompleted_jobs() -> None:
    assert jss._matches_timestamp_filter(J(completed_at=None), None, None, T_MINUS, None) is False
    assert jss._matches_timestamp_filter(J(completed_at=None), None, None, None, None) is True


# ---------------------------------------------------------------------------
# _matches_error_filter (arms m10/m12)
# ---------------------------------------------------------------------------


def test_error_filter_empty_string_error_is_no_error() -> None:
    # m10: str(None).strip() == "None" != "" -> an empty-string error would
    # COUNT as an error in the mutant; shipped counts it as NO error.
    assert jss._matches_error_filter(J(error=""), False) is True
    assert jss._matches_error_filter(J(error=""), True) is False


def test_error_filter_nonblank_counts_and_polarity_matches() -> None:
    # m12 (`!= ""` -> `!= "XXXX"`): error "XXXX" HAS an error for shipped;
    # the mutant calls it error-free.
    assert jss._matches_error_filter(J(error="XXXX"), True) is True
    assert jss._matches_error_filter(J(error="boom"), True) is True
    assert jss._matches_error_filter(J(error="boom"), False) is False
    assert jss._matches_error_filter(J(error=None), None) is True
    assert jss._matches_error_filter(J(error="   "), False) is True  # blank strips to none


# ---------------------------------------------------------------------------
# _matches_duration_filter (boundary arms m11/m16)
# ---------------------------------------------------------------------------


def test_duration_filter_boundaries_are_inclusive() -> None:
    job = J(started_at="2026-01-15T10:00:00Z", completed_at="2026-01-15T10:00:30Z")
    assert jss._matches_duration_filter(job, 30.0, None) is True  # duration == min PASSES
    assert jss._matches_duration_filter(job, 31.0, None) is False
    assert jss._matches_duration_filter(job, None, 30.0) is True  # duration == max PASSES
    assert jss._matches_duration_filter(job, None, 29.0) is False
    assert jss._matches_duration_filter(job, None, None) is True


def test_duration_filter_uncomputable_duration_is_excluded() -> None:
    assert jss._matches_duration_filter(J(), 5.0, None) is False
    assert jss._matches_duration_filter(J(), None, None) is True


# ---------------------------------------------------------------------------
# _filter_job (argument-forwarding arms m23-m26, m33-m34, m37-m39)
# ---------------------------------------------------------------------------


def test_filter_job_timestamp_arguments_are_forwarded() -> None:
    job = J(created_at=T, completed_at=T)
    assert jss._filter_job(job, jss.JobSearchFilters(created_after=T_EXACT)) is False  # m23
    assert jss._filter_job(job, jss.JobSearchFilters(created_before=T_MINUS)) is False  # m24
    assert jss._filter_job(job, jss.JobSearchFilters(completed_after=T_EXACT)) is False  # m25
    assert jss._filter_job(job, jss.JobSearchFilters(completed_before=T_MINUS)) is False  # m26
    assert jss._filter_job(job, jss.JobSearchFilters()) is True  # all-None twin


def test_filter_job_error_filter_receives_job_and_polarity() -> None:
    # m33 passes None as the job (_matches_error_filter .get AttributeError);
    # m34 passes None as has_error (the filter silently disables).
    assert jss._filter_job(J(error="boom"), jss.JobSearchFilters(has_error=True)) is True
    assert jss._filter_job(J(error="boom"), jss.JobSearchFilters(has_error=False)) is False


def test_filter_job_duration_arguments_are_forwarded() -> None:
    job = J(started_at="2026-01-15T10:00:00Z", completed_at="2026-01-15T10:00:30Z")
    assert (
        jss._filter_job(job, jss.JobSearchFilters(min_duration=30.0)) is True
    )  # m37 job->None: TypeError
    assert (
        jss._filter_job(job, jss.JobSearchFilters(min_duration=31.0)) is False
    )  # m38 min->None keeps it
    assert (
        jss._filter_job(job, jss.JobSearchFilters(max_duration=29.0)) is False
    )  # m39 max->None keeps it


def test_filter_job_text_and_status_and_type_arguments_are_forwarded() -> None:
    # the m22/m23-family upstream: text/status/type legs run BEFORE the
    # timestamp leg, so a wrong query/statuses/job_types excludes job A.
    job = A()
    assert jss._filter_job(job, jss.JobSearchFilters(query="zzz")) is False
    assert jss._filter_job(job, jss.JobSearchFilters(statuses=["running"])) is False
    assert jss._filter_job(job, jss.JobSearchFilters(job_types=["clip_export"])) is False
    assert (
        jss._filter_job(
            job,
            jss.JobSearchFilters(
                query="face", statuses=["completed"], job_types=["face_enrollment"]
            ),
        )
        is True
    )


# ---------------------------------------------------------------------------
# _compute_aggregations (default + counter arms m6/m8/m11/m12/m15/m23/m25/m28/m29)
# ---------------------------------------------------------------------------


def test_aggregations_counts_keys_are_exact() -> None:
    j_statusless = J()
    del j_statusless["status"]
    j_typeless = J(job_id="J-9", job_type="x", status="failed")
    del j_typeless["job_type"]
    jobs = [
        J(status="completed", job_type="a"),
        J(status="completed", job_type="a"),
        j_statusless,  # shipped keys it "unknown" (get default)
        J(status=None, job_type=None),  # str(None) == "None"; by_type None key raw
        j_typeless,  # shipped keys it "unknown"
    ]
    agg = jss._compute_aggregations(jobs)
    # m6/m8 (status default None) and m15 (by_status.get(status->None)) all
    # collapse absent-status into the "None" key -> {completed:2, None:2,...};
    # m11 XXunknownXX and m12 UNKNOWN move the key; the shipped shape is
    # EXACT equality below.
    assert agg.by_status == {"completed": 2, "unknown": 1, "None": 1, "failed": 1}
    # m23/m25 (type default None) collapse the typeless job into the raw
    # None key (merging with the job_type=None job); m28 XXunknownXX and
    # m29 UNKNOWN move the key.
    assert agg.by_type == {"a": 2, "face_enrollment": 1, "unknown": 1, None: 1}
    assert agg.to_dict() == {"by_status": agg.by_status, "by_type": agg.by_type}


def test_aggregations_empty_list_is_empty_not_keyed() -> None:
    agg = jss._compute_aggregations([])
    assert agg.by_status == {}
    assert agg.by_type == {}


# ---------------------------------------------------------------------------
# _get_sort_key (34 surviving arms)
# ---------------------------------------------------------------------------


def test_sort_key_present_values_are_verbatim() -> None:
    job = A(started_at="2026-01-15T10:00:00Z", completed_at="2026-01-15T10:00:30Z")
    assert jss._get_sort_key(job, "created_at") == T
    assert jss._get_sort_key(job, "started_at") == "2026-01-15T10:00:00Z"
    assert jss._get_sort_key(job, "completed_at") == "2026-01-15T10:00:30Z"
    assert jss._get_sort_key(job, "progress") == 0
    assert jss._get_sort_key(job, "job_type") == "face_enrollment"
    assert jss._get_sort_key(job, "status") == "completed"


def test_sort_key_absent_and_none_stamps_default_to_empty_string() -> None:
    # created_at arms m3/m5/m8 (None / trailing-comma / "XXXX"): shipped
    # defaults to ""; started/completed `or ""` arms m10-m18 same family.
    job = A()
    del job["created_at"]
    assert jss._get_sort_key(job, "created_at") == ""
    assert jss._get_sort_key(job, "started_at") == ""  # value None -> or ""
    assert (
        jss._get_sort_key(job, "completed_at") == ""
    )  # m14 `and ""` -> "" for TRUTHY value live below
    job2 = A(started_at="START")
    assert (
        jss._get_sort_key(job2, "started_at") == "START"
    )  # m11/m12 wrong-key arms return "" mismatch; m14 truthy -> "" mismatches
    assert jss._get_sort_key(job2, "completed_at") == ""


def test_sort_key_progress_default_is_zero() -> None:
    # m20/m22 (None) / m25 (1): absent progress sorts at 0 in shipped.
    job = A()
    del job["progress"]
    assert jss._get_sort_key(job, "progress") == 0
    present = J(progress=None)  # J() - A() pins progress positionally
    assert (
        jss._get_sort_key(present, "progress") is None
    )  # value IS None: get returns it, default unused


def test_sort_key_type_and_status_absent_defaults() -> None:
    # job_type m27/m29/m32; status m33-m40 (str(get(..., "")) arms).
    job = A()
    del job["job_type"]
    del job["status"]
    assert jss._get_sort_key(job, "job_type") == ""
    assert jss._get_sort_key(job, "status") == ""
    present = A(status=None)
    assert (
        jss._get_sort_key(present, "status") == "None"
    )  # str(None): shipped wraps the PRESENT None; m33 str(None) bare-key lands "None" too - the absent drive above is the discriminator


def test_sort_key_case_keys_and_default_fallback() -> None:
    # case-flip arms (m12/m17/m39/m50: get("STARTED_AT") etc.) return the
    # DEFAULT with a present field; the sort_field_map miss falls back to
    # created_at VERBATIM (m42 None / m44 dropped default / m45-m51 arms).
    job = A()
    assert jss._get_sort_key(job, "created_at") == T  # map hit live
    assert jss._get_sort_key(job, "unmapped_field") == T  # fallback live
    assert (
        jss._get_sort_key(job, "STATUS") == T
    )  # "STATUS" MISSES the map -> created_at fallback (m39/m40 wrong-key map arms return the STATUS slot value - the map-HIT absent-status drive is the discriminator)


def test_sort_key_fallback_on_absent_created_at() -> None:
    # m42 (get(sort_by, None)) / m44 (no default -> None) / m46 (default
    # None) / m47 get("") / m51 "XXXX" all differ from shipped "" here.
    job = A()
    del job["created_at"]
    assert jss._get_sort_key(job, "unmapped_field") == ""


# ---------------------------------------------------------------------------
# search_jobs - filter effects (kwarg families m11-m32) + range unpacks
# (m2/m5/m8) + sort (m53) + pagination + log (m58-m78)
# ---------------------------------------------------------------------------


def sj(tracker: FixedTracker, **kw: Any) -> tuple[list[dict[str, Any]], int]:
    return run(jss.search_jobs(tracker, **kw))


def sjwa(tracker: FixedTracker, **kw: Any) -> Any:
    return run(jss.search_jobs_with_aggregations(tracker, **kw))


def ids(jobs: list[dict[str, Any]]) -> list[str]:
    return [j["job_id"] for j in jobs]


def two_jobs() -> FixedTracker:
    """A: completed, face_enrollment, no error, created T, dur 30 s.
    B: running, clip_export, error, created T-1h, no duration."""
    a = A(
        started_at="2026-01-15T10:00:00Z",
        completed_at="2026-01-15T10:00:30Z",
        message="plain A",
    )
    b = B(
        status="running",
        job_type="clip_export",
        error="NEEDLE broke",
        message="plain B",
    )
    return FixedTracker([a, b])


def test_search_query_filter_excludes_non_matching_job() -> None:
    # m11/m22 (query -> None / dropped): the filter disables -> B's NEEDLE
    # no longer excludes A... (shipped: query "needle" returns ONLY B).
    jobs, total = sj(two_jobs(), query="needle")
    assert (ids(jobs), total) == (["B"], 1)
    jobs, total = sj(two_jobs())
    assert (ids(jobs), total) == (["A", "B"], 2)


def test_search_statuses_filter_filters_and_falsy_legs_wildcard() -> None:
    jobs, total = sj(two_jobs(), statuses=["completed"])
    assert (ids(jobs), total) == (["A"], 1)
    jobs, total = sj(two_jobs(), statuses=None)  # m13-adjacent: `or []` falsy leg
    assert (ids(jobs), total) == (["A", "B"], 2)
    jobs, total = sj(two_jobs(), statuses=[])
    assert (ids(jobs), total) == (["A", "B"], 2)


def test_search_job_types_filter_verbatim_and_and_dropped() -> None:
    # m13/m24/m34: dropped/None'd job_types wildcard everything; m34
    # (`job_types and []`) makes even a truthy selection the wildcard.
    jobs, total = sj(two_jobs(), job_types=["clip_export"])
    assert (ids(jobs), total) == (["B"], 1)
    jobs, total = sj(two_jobs(), job_types=None)
    assert (ids(jobs), total) == (["A", "B"], 2)
    jobs, total = sj(two_jobs(), job_types=[])
    assert (ids(jobs), total) == (["A", "B"], 2)


def test_search_queue_filter_is_ignored_and_queue_arm_is_ledger() -> None:
    # LEDGER witness (search_jobs m14/m25): shipped forwards the queue INTO
    # the filters object, but filters.queue is READ by nothing - driving it
    # with a value that WOULD exclude job B changes no outcome, exactly the
    # mutant (None/dropped) behavior.
    jobs, total = sj(two_jobs(), queue="only-A-queue")
    assert (ids(jobs), total) == (["A", "B"], 2)


def test_search_created_range_unpacks_into_both_filters() -> None:
    # m2/m15/m16/m26/m27. created_at: A = T, B = T-1h. shipped excludes on
    # STRICT created_at < created_after / STRICT created_before comparisons,
    # so an EXACT boundary keeps that job - which is what kills the m7 (<=)
    # and m10 (>=) arms, and what a None'd/dropped leg (wildcard) cannot
    # reproduce.
    jobs, total = sj(two_jobs(), created_range=(T, None))
    assert (ids(jobs), total) == (["A"], 1)  # A == after boundary PASSES
    jobs, total = sj(two_jobs(), created_range=(T_EXACT, None))
    assert (ids(jobs), total) == ([], 0)  # both created strictly before T+1s
    jobs, total = sj(two_jobs(), created_range=(None, T))
    assert (ids(jobs), total) == (["A", "B"], 2)  # A == before boundary PASSES
    jobs, total = sj(two_jobs(), created_range=(None, T_MINUS))
    assert (ids(jobs), total) == (["B"], 1)  # A (T > T-1h) excluded
    jobs, total = sj(two_jobs(), created_range=(None, T_PLUS))
    assert (ids(jobs), total) == (["A", "B"], 2)


def test_search_completed_range_unpacks_into_both_filters() -> None:
    # m5/m17/m18/m28/m29: A is the only COMPLETED job (completed_at =
    # T_DONE = 10:00:30Z); B is uncompleted so ANY completed filter drops
    # it (the not-completed_at leg of _matches_timestamp_filter).
    jobs, total = sj(two_jobs(), completed_range=(T_DONE, None))
    assert (ids(jobs), total) == (["A"], 1)  # == boundary passes inclusive
    jobs, total = sj(two_jobs(), completed_range=(T_DONE_PAST, None))
    assert (ids(jobs), total) == ([], 0)
    jobs, total = sj(two_jobs(), completed_range=(None, T_DONE))
    assert (ids(jobs), total) == (["A"], 1)
    jobs, total = sj(two_jobs(), completed_range=(None, T))
    assert (ids(jobs), total) == (["A"], 1)


def test_search_has_error_filter_polarities() -> None:
    # m19/m30: dropped/None'd -> everything.
    jobs, total = sj(two_jobs(), has_error=True)
    assert (ids(jobs), total) == (["B"], 1)
    jobs, total = sj(two_jobs(), has_error=False)
    assert (ids(jobs), total) == (["A"], 1)
    jobs, total = sj(two_jobs(), has_error=None)
    assert (ids(jobs), total) == (["A", "B"], 2)


def test_search_duration_range_unpacks_min_and_max() -> None:
    # m8/m20/m21: A's duration is exactly 30 s; B is uncomputable (any
    # duration filter excludes it).
    jobs, total = sj(two_jobs(), duration_range=(31.0, None))
    assert (ids(jobs), total) == ([], 0)  # 30 < 31
    jobs, total = sj(two_jobs(), duration_range=(None, 29.0))
    assert (ids(jobs), total) == ([], 0)  # 30 > 29
    jobs, total = sj(two_jobs(), duration_range=(30.0, 30.0))
    assert (ids(jobs), total) == (["A"], 1)  # inclusive boundary through the whole pipeline


def test_search_sort_by_progress_and_order_legs() -> None:
    # m53 (_get_sort_key sort_by -> None): silently sorts by created_at,
    # which is the REVERSE of the progress order for this pair.
    jobs, _ = sj(two_jobs(), sort_by="progress", sort_order="asc")
    assert ids(jobs) == ["A", "B"]  # progress 0 then 100
    jobs, _ = sj(two_jobs(), sort_by="progress", sort_order="desc")
    assert ids(jobs) == ["B", "A"]
    jobs, _ = sj(two_jobs(), sort_by="created_at", sort_order="asc")
    assert ids(jobs) == ["B", "A"]  # created T-1h then T


def test_search_pagination_window_is_exact() -> None:
    jobs, total = sj(two_jobs(), limit=1, offset=1, sort_by="created_at", sort_order="asc")
    assert (ids(jobs), total) == (["A"], 2)  # total is PRE-pagination
    jobs, total = sj(two_jobs(), limit=1, offset=0)
    assert (ids(jobs), total) == (["A", "B"][0:1], 2)


def test_search_log_message_and_extra_are_exact() -> None:
    # m58 (message None) m62/m63/m64 (XX/lower/UPPER) m59/m61 (extra None/
    # dropped) m65-m78 (extra key renames) - message EQUALITY + attribute
    # reads + full nested-dict equality.
    with CollectorCtx() as col:
        sj(
            two_jobs(),
            query="needle",
            statuses=["running"],
            job_types=["clip_export"],
            has_error=True,
        )
    assert len(col.records) == 1
    r = col.records[0]
    assert r.getMessage() == "Job search completed"
    assert r.levelno == logging.DEBUG
    assert attr(r, "total") == 1
    assert attr(r, "returned") == 1
    assert attr(r, "filters") == {
        "query": "needle",
        "statuses": ["running"],
        "job_types": ["clip_export"],
        "has_error": True,
    }


def test_search_log_default_extra_shape() -> None:
    # the all-defaults leg: every filters value None - renames of "query"/
    # "statuses"/"job_types"/"has_error" still land on the wrong attribute.
    with CollectorCtx() as col:
        sj(FixedTracker([J()]))
    assert len(col.records) == 1
    r = col.records[0]
    assert attr(r, "filters") == {
        "query": None,
        "statuses": None,
        "job_types": None,
        "has_error": None,
    }


# ---------------------------------------------------------------------------
# search_jobs_with_aggregations - statuses family (m12/m23/m33) + range/
# duration/query/queue (m11-m29) + sort_order arms (m44-m48) + sort_by
# (m50/m52/m55) + log (m60-m72)
# ---------------------------------------------------------------------------


def test_sjwa_statuses_filter_verbatim_and_dropped() -> None:
    # m12 (statuses -> None), m23 (dropped), m33 (`statuses and []`).
    res = sjwa(two_jobs(), statuses=["completed"])
    assert [j["job_id"] for j in res.jobs] == ["A"]
    assert res.total == 1
    res = sjwa(two_jobs(), statuses=None)
    assert res.total == 2
    res = sjwa(two_jobs(), statuses=[])
    assert res.total == 2


def test_sjwa_filter_families_exclude_one_job_each() -> None:
    res = sjwa(two_jobs(), query="needle")
    assert [j["job_id"] for j in res.jobs] == ["B"]
    res = sjwa(two_jobs(), job_types=["face_enrollment"])
    assert [j["job_id"] for j in res.jobs] == ["A"]
    res = sjwa(two_jobs(), queue="only-A")
    assert res.total == 2  # LEDGER witness (sjwa m14/m25): queue is write-only
    res = sjwa(two_jobs(), created_range=(T, None))
    assert [j["job_id"] for j in res.jobs] == ["A"]
    res = sjwa(two_jobs(), created_range=(None, T_MINUS))
    assert [j["job_id"] for j in res.jobs] == ["B"]
    res = sjwa(two_jobs(), completed_range=(T_DONE, None))
    assert [j["job_id"] for j in res.jobs] == ["A"]
    res = sjwa(two_jobs(), completed_range=(None, T_DONE_PAST))
    assert [j["job_id"] for j in res.jobs] == ["A"]
    res = sjwa(two_jobs(), has_error=False)
    assert [j["job_id"] for j in res.jobs] == ["A"]
    res = sjwa(two_jobs(), duration_range=(30.0, 30.0))
    assert [j["job_id"] for j in res.jobs] == ["A"]


def test_sjwa_sort_order_legs_and_case() -> None:
    # m45 (sort_order.upper() == "desc"): "ASC".upper() never equals
    # "desc"; m47 ("XXdescXX") and m48 (== "DESC") never fire for shipped's
    # truthy inputs - both reorder; m46 (!=) inverts; m44 (None) falsifies.
    res = sjwa(two_jobs(), sort_by="progress", sort_order="asc")
    assert [j["job_id"] for j in res.jobs] == ["A", "B"]
    res = sjwa(two_jobs(), sort_by="progress", sort_order="ASC")
    assert [j["job_id"] for j in res.jobs] == ["A", "B"]
    res = sjwa(two_jobs(), sort_by="progress", sort_order="desc")
    assert [j["job_id"] for j in res.jobs] == ["B", "A"]
    res = sjwa(two_jobs(), sort_by="progress", sort_order="DESC")
    assert [j["job_id"] for j in res.jobs] == ["B", "A"]


def test_sjwa_sort_by_progress_orders_against_created() -> None:
    # m55 (_get_sort_key sort_by -> None silently sorts created_at - the
    # reverse order for this pair); m50 (reverse -> None falsy) / m52
    # (reverse dropped) reorder the asc-driven call to created-desc shape.
    res = sjwa(two_jobs(), sort_by="progress", sort_order="asc")
    assert [j["job_id"] for j in res.jobs] == ["A", "B"]
    res = sjwa(two_jobs(), sort_by="progress", sort_order="desc")
    assert [j["job_id"] for j in res.jobs] == ["B", "A"]


def test_sjwa_aggregations_and_result_shape() -> None:
    res = sjwa(two_jobs())
    assert res.total == 2
    assert [j["job_id"] for j in res.jobs] == ["A", "B"]  # default created_at DESC
    assert res.to_dict() == {
        "jobs": [res.jobs[0], res.jobs[1]],
        "total": 2,
        "aggregations": {
            "by_status": {"completed": 1, "running": 1},
            "by_type": {"face_enrollment": 1, "clip_export": 1},
        },
    }


def test_sjwa_log_message_and_extra_are_exact() -> None:
    # m60 (None) m64/m65/m66 (XX/lower/UPPER) m61/m63 (extra None/dropped)
    # m67-m72 (extra key renames).
    with CollectorCtx() as col:
        sjwa(two_jobs(), statuses=["completed"])
    assert len(col.records) == 1
    r = col.records[0]
    assert r.getMessage() == "Job search with aggregations completed"
    assert r.levelno == logging.INFO
    assert attr(r, "total") == 1
    assert attr(r, "returned") == 1
    assert attr(r, "aggregations") == {
        "by_status": {"completed": 1},
        "by_type": {"face_enrollment": 1},
    }


# ---------------------------------------------------------------------------
# JobSearchService.search wrapper - verbatim forwarding at the CALL SITE
# (arms m2-m9 None-swap, m12 sort_by->None, m15-m26 drops)
# ---------------------------------------------------------------------------


def test_wrapper_forwards_every_argument_verbatim() -> None:
    spy = SpyFn()
    tracker = FixedTracker([A()])
    with _Patcher((jss, "search_jobs_with_aggregations", spy)):
        svc = jss.JobSearchService("TRACKER")
        out = run(svc.search(**SPY_ARGS))
    assert out == "SPYRESULT"  # result returned verbatim
    assert spy.kwargs is not None
    assert set(spy.kwargs) == SPY_KEYS  # every forwarded name present
    assert spy.kwargs == wrapper_full_kwargs()  # every value verbatim


def test_wrapper_forwards_defaults_verbatim() -> None:
    spy = SpyFn()
    with _Patcher((jss, "search_jobs_with_aggregations", spy)):
        svc = jss.JobSearchService("TRACKER2")
        run(svc.search())
    assert spy.kwargs == {
        "job_tracker": "TRACKER2",
        "query": None,
        "statuses": None,
        "job_types": None,
        "queue": None,
        "created_range": None,
        "completed_range": None,
        "has_error": None,
        "duration_range": None,
        "limit": 50,
        "offset": 0,
        "sort_by": "created_at",
        "sort_order": "desc",
    }
