# TARGET-MODULE: backend.services.prompt_service
"""Battery P - campaign #14 of the ladder (batch-38): kill-real coverage for
``backend/services/prompt_service.py`` (320 survivors at 53.01% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, so every seam swap restores in ``finally``.

The shipped batteries mock ``session`` with a bare AsyncMock (any mutated SQL
statement is swallowed) and assert membership-style, so the whole SQL-shape,
dict-key-flip and message layer survived. This battery kills it: the session
spy COMPILES the real statement with the postgresql dialect and pins the
FULL rendering (strings measured THIS session from the live models), FULL log
records (level, raw msg, args tuple, every ``extra`` attr probed via
``getattr(record, attr, _MISSING)`` - a DROPPED extra key is ABSENT, never
None), kwargs-as-dicts at every call spy, exception ``str()`` and result
dicts by ``==``, tz-awareness by ``tzinfo is UTC`` (measured identity), and a
frozen ``time`` module (swap in the function's REAL globals - three-worlds
safe) so every latency render is asserted as an exact integer.

Honesty ledger - dispositions registered EQUIVALENT at authoring (the sweep
must show GREEN on exactly these unless the sweep proves otherwise; anything
else GREEN is a test gap):

* ``xǁPromptServiceǁtest_prompt__mutmut_69`` / ``_mutmut_71`` (the
  ``config.get("system_prompt", "")`` default -> None / default ABSENT):
  the ONLY read is ``if not new_prompt:`` and "" and None are both falsy -
  every path through the guard is identical (falsy-either-way doctrine).

* ``xǁPromptRollbackCheckerǁcheck_rollback_needed__mutmut_30`` (DELETE the
  ``reason=None`` kwarg of the final return): ``RollbackCheckResult.reason``
  has dataclass default None - construction is field-identical.
* ``xǁPromptEvaluatorǁevaluate_prompt_version__mutmut_54`` (``if latencies``
  -> ``if (latencies) or True``) and ``_mutmut_57`` (the ``else 0.0`` ->
  ``else 1.0``): a successful iteration appends to BOTH lists, so whenever
  the ternary runs the list is non-empty - the else-arm is unreachable and
  truthiness-pinning changes nothing (measured path reading, lines 493-540).

* ``xǁPromptServiceǁtest_prompt__mutmut_17`` (initial result dict
  ``"test_duration_ms": 0`` -> ``1``): EVERY exit - all four early returns
  AND the tail after the except arms - REASSIGNS the key before returning,
  so the initial value is never observed (source reading 820-910: each early
  return re-sets duration one line before ``return result``).

(6 registered - the run-1 reconcile loop adjudicates the rest pre-launch.)
"""

import asyncio
import datetime as _dt
import logging
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, ClassVar

import httpx
from sqlalchemy.dialects import postgresql

import backend.services.prompt_service as _m
from backend.api.schemas.prompt_management import (
    AIModelEnum,
    PromptVersionConflictError,
)
from backend.services.prompt_service import (
    DEFAULT_CONFIGS,
    ABTestConfig,
    EvaluationBatch,
    EvaluationResults,
    PromptABTester,
    PromptEvaluator,
    PromptRollbackChecker,
    PromptService,
    PromptShadowRunner,
    RollbackCheckResult,
    RollbackConfig,
    RollbackExecutionResult,
    ShadowComparisonResult,
    ShadowModeConfig,
    VersionComparisonResult,
)

_MISSING = object()
_NO_LLM = object()
_MOD = "backend.services.prompt_service"
_PG = postgresql.dialect()


def _sql(stmt: Any) -> str:
    """FULL rendered SQL with literal binds (measured this session).

    A mutated ``.where(A == B)``, a swapped column, a dropped ``is_active``
    predicate, a flipped ``desc()``, an off-by-one ``limit``/``offset`` or a
    different aggregate all change this string - the shipped AsyncMock-based
    batteries swallowed every one of them.
    """
    compiled = stmt.compile(
        dialect=_PG,
        compile_kwargs={"literal_binds": True},
    )
    return " ".join(str(compiled).split())


def _params(stmt: Any) -> dict[str, Any]:
    """The bound-parameter dict of the SAME statement (non-literal form)."""
    return dict(stmt.compile(dialect=_PG).params)


class _FakeTime(ModuleType):
    def __init__(self, stamps: list[float]) -> None:
        super().__init__("time")
        self._stamps = list(stamps)

    def monotonic(self) -> float:
        return self._stamps.pop(0)


def _fake_time(stamps: list[float]) -> _FakeTime:
    return _FakeTime(stamps)


def _globals_of(fn: Any) -> dict[str, Any]:
    f = fn
    seen: set[int] = set()
    while hasattr(f, "__wrapped__") and id(f) not in seen:
        seen.add(id(f))
        f = f.__wrapped__
    return f.__globals__


class _LogCap(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _sig(r: logging.LogRecord) -> dict[str, Any]:
    return {"level": r.levelno, "msg": r.msg, "args": r.args}


def _extra(r: logging.LogRecord, **want: Any) -> None:
    for attr, exp in want.items():
        assert getattr(r, attr, _MISSING) is exp, (attr, exp)


class _Result:
    def __init__(
        self,
        scalar: Any = None,
        one: Any = None,
        rows: Any = (),
    ) -> None:
        self._scalar = scalar
        self._one = one
        self._rows = list(rows)

    def scalar(self) -> Any:
        return self._scalar

    def scalar_one_or_none(self) -> Any:
        return self._one

    def scalars(self) -> _Result:
        return self

    def all(self) -> list[Any]:
        return list(self._rows)


class _Sess:
    """Session spy: records executed STATEMENTS (compiled) and call order."""

    def __init__(self, results: list[Any]) -> None:
        self.statements: list[Any] = []
        self.calls: list[str] = []
        self._results = list(results)
        self.added: list[Any] = []
        self.refreshed: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.calls.append("execute")
        self.statements.append(stmt)
        return self._results.pop(0)

    def add(self, obj: Any) -> None:
        self.calls.append("add")
        self.added.append(obj)

    async def commit(self) -> None:
        self.calls.append("commit")

    async def refresh(self, obj: Any) -> None:
        self.calls.append("refresh")
        self.refreshed.append(obj)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class _StubPV:
    def __init__(self, **kw: Any) -> None:
        self.id = kw.get("id")
        self.model = kw.get("model")
        self.version = kw.get("version")
        self.name = kw.get("model")
        self.config_json = kw.get("config_json", "{}")
        self.change_description = kw.get("change_description")
        self.created_by = kw.get("created_by")
        self.is_active = kw.get("is_active")
        self.created_at = kw.get("created_at")

    @property
    def config(self) -> dict[str, Any]:
        import json

        return json.loads(self.config_json)


class _StubResp:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code != 200:
            req = httpx.Request("POST", "http://vlm.test/completion")
            raise httpx.HTTPStatusError(
                "Engine unavailable",
                request=req,
                response=httpx.Response(self.status_code, request=req),
            )

    def json(self) -> Any:
        return self._payload


class _FakeClient:
    factory_calls: ClassVar[list[dict[str, Any]]] = []
    posts: ClassVar[list[dict[str, Any]]] = []
    queue: ClassVar[list[Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        _FakeClient.factory_calls.append(dict(kwargs))

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def post(self, url: str, **kwargs: Any) -> Any:
        _FakeClient.posts.append({"url": url, **kwargs})
        item = _FakeClient.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def fn(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append((args, dict(kwargs)))


def _fake_httpx() -> ModuleType:
    """A stand-in for the module's ``httpx`` global: only AsyncClient is
    swapped, every exception name still resolves to the REAL class so the
    functions' ``except httpx.X`` arms keep their real semantics."""
    shim = ModuleType("fake_httpx_for_battery_p")
    shim.AsyncClient = _FakeClient  # type: ignore[attr-defined]
    for name in (
        "TimeoutException",
        "HTTPStatusError",
        "RequestError",
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "TransportError",
        "HTTPError",
        "Timeout",
    ):
        setattr(shim, name, getattr(httpx, name))
    return shim


def _patch_httpx_client() -> dict[str, Any]:
    """Swap the httpx the LLM paths resolve, restore with .undo()."""
    g = _globals_of(PromptService._run_llm_test)
    old = g["httpx"]
    g["httpx"] = _fake_httpx()
    _reset_httpx_state()

    def undo() -> None:
        g["httpx"] = old

    return {"undo": undo}


def _install_logger() -> tuple[logging.Logger, _LogCap, ModuleType]:
    old = _m.logger
    lg = logging.Logger("b38-p-sink")
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    cap = _LogCap()
    lg.addHandler(cap)
    _m.logger = lg
    return lg, cap, old


def _reset_httpx_state() -> None:
    _FakeClient.factory_calls = []
    _FakeClient.posts = []
    _FakeClient.queue = []


NEMO = AIModelEnum.NEMOTRON.value
MODELS = [m.value for m in AIModelEnum]


# =========================================================================
# __init__: settings re-home + the exact httpx.Timeout shape
# =========================================================================


def test_init_reads_vlm_url_and_exact_timeout_shape() -> None:
    svc = PromptService()
    assert svc._llm_url == "http://localhost:8098"
    t = svc._timeout
    assert (t.connect, t.read, t.write, t.pool) == (10.0, 120.0, 10.0, 10.0)


def test_init_timeout_is_a_real_timeout_not_none() -> None:
    t = PromptService()._timeout
    assert isinstance(t, httpx.Timeout)


# =========================================================================
# get_prompt_for_model: the active-version SELECT rendered in full
# =========================================================================


def test_get_prompt_for_model_select_shape_and_active_binding() -> None:
    cfg = {"system_prompt": "SP", "k": 1}
    pv = _StubPV(
        model="florence2",
        version=3,
        config_json='{"system_prompt": "SP", "k": 1}',
    )
    sess = _Sess([_Result(one=pv)])
    out = _run(PromptService().get_prompt_for_model(sess, "florence2"))
    assert len(sess.statements) == 1
    sql = _sql(sess.statements[0])
    assert sql == (
        "SELECT prompt_versions.id, prompt_versions.model, "
        "prompt_versions.version, prompt_versions.created_at, "
        "prompt_versions.created_by, prompt_versions.config_json, "
        "prompt_versions.change_description, prompt_versions.is_active, "
        "prompt_versions.row_version FROM prompt_versions WHERE "
        "prompt_versions.model = 'florence2' AND "
        "prompt_versions.is_active = true ORDER BY "
        "prompt_versions.version DESC LIMIT 1"
    )
    # the returned config is the version's copy with the version spliced in
    assert out == {"system_prompt": "SP", "k": 1, "version": 3}


def test_get_prompt_for_model_default_branch_exact_copy() -> None:
    sess = _Sess([_Result(one=None)])
    out = _run(PromptService().get_prompt_for_model(sess, "nemotron"))
    assert out == DEFAULT_CONFIGS["nemotron"]
    assert out is not DEFAULT_CONFIGS["nemotron"]
    assert sess.statements and "WHERE prompt_versions.model = 'nemotron'" in _sql(
        sess.statements[0]
    )


def test_get_prompt_for_model_unknown_model_gets_empty_dict() -> None:
    sess = _Sess([_Result(one=None)])
    out = _run(PromptService().get_prompt_for_model(sess, "no-such-model"))
    assert out == {}


# =========================================================================
# get_all_prompts: one exact get per enum member, in enum order
# =========================================================================


def test_get_all_prompts_maps_every_model_with_its_own_name() -> None:
    seen: list[str] = []

    async def _spy(self: Any, session: Any, model: str) -> dict[str, Any]:
        seen.append(model)
        return {"tag": f"cfg-{model}"}

    prev = PromptService.get_prompt_for_model
    PromptService.get_prompt_for_model = _spy  # type: ignore[method-assign]
    try:
        out = _run(PromptService().get_all_prompts(_Sess([])))
    finally:
        PromptService.get_prompt_for_model = prev  # type: ignore[method-assign]
    assert seen == MODELS
    assert out == {m: {"tag": f"cfg-{m}"} for m in MODELS}


# =========================================================================
# get_version_history: dual queries, filter both sides, count-or-0
# =========================================================================


def test_get_version_history_unfiltered_shape_and_call_order() -> None:
    rows = [_StubPV(model="nemotron", version=1), _StubPV(model="nemotron", version=2)]
    sess = _Sess([_Result(scalar=7), _Result(rows=rows)])
    versions, total = _run(PromptService().get_version_history(sess, limit=50, offset=5))
    assert sess.calls == ["execute", "execute"]
    count_sql = _sql(sess.statements[0])
    assert count_sql == ("SELECT count(prompt_versions.id) AS count_1 FROM prompt_versions")
    page_sql = _sql(sess.statements[1])
    assert page_sql.endswith(
        "FROM prompt_versions ORDER BY prompt_versions.created_at DESC LIMIT 50 OFFSET 5"
    )
    assert versions == rows
    assert total == 7


def test_get_version_history_model_filter_hits_both_queries() -> None:
    sess = _Sess([_Result(scalar=2), _Result(rows=[])])
    versions, total = _run(
        PromptService().get_version_history(sess, model="xclip", limit=10, offset=0)
    )
    count_sql = _sql(sess.statements[0])
    page_sql = _sql(sess.statements[1])
    assert "WHERE prompt_versions.model = 'xclip'" in count_sql
    assert "WHERE prompt_versions.model = 'xclip'" in page_sql
    assert count_sql.startswith("SELECT count(prompt_versions.id)")
    assert versions == []
    assert total == 2


def test_get_version_history_null_count_becomes_zero_not_one() -> None:
    sess = _Sess([_Result(scalar=None), _Result(rows=[])])
    _, total = _run(PromptService().get_version_history(sess))
    assert total == 0
    # defaults pinned too: LIMIT 50 OFFSET 0 (kills a default 0 -> 1 mutant)
    assert _sql(sess.statements[1]).endswith(
        "ORDER BY prompt_versions.created_at DESC LIMIT 50 OFFSET 0"
    )


# =========================================================================
# update_prompt_for_model: version math, conflict gate, deactivate UPDATE,
# row construction kwargs, INFO record
# =========================================================================


def test_update_creates_next_version_with_exact_row_kwargs() -> None:
    import json

    sess = _Sess([_Result(scalar=4), _Result()])
    lg, cap, old = _install_logger()
    try:
        out = _run(
            PromptService().update_prompt_for_model(
                sess,
                "florence2",
                {"queries": ["a"]},
                change_description="desc-1",
                created_by="alice",
            )
        )
    finally:
        _m.logger = old
    assert sess.calls == ["execute", "execute", "add", "commit", "refresh"]
    deact = _sql(sess.statements[1])
    assert deact == (
        "UPDATE prompt_versions SET is_active=false WHERE prompt_versions.model = 'florence2'"
    )
    assert out.version == 5
    assert out.model == "florence2"
    assert out.config_json == json.dumps({"queries": ["a"]})
    assert out.change_description == "desc-1"
    assert out.created_by == "alice"
    assert out.is_active is True
    assert out.created_at.tzinfo is _dt.UTC
    assert sess.added == [out] and sess.refreshed == [out]
    assert len(cap.records) == 1
    r = cap.records[0]
    assert r.levelno == logging.INFO
    assert r.msg == "Created new prompt version 5 for model florence2"
    _extra(r, model="florence2", version=5)


def test_update_first_version_null_max_falls_to_zero_then_one() -> None:
    sess = _Sess([_Result(scalar=None), _Result()])
    out = _run(PromptService().update_prompt_for_model(sess, "nemotron", {}))
    assert out.version == 1


def test_update_conflict_raises_with_exact_identity_and_warning() -> None:
    sess = _Sess([_Result(scalar=3)])
    lg, cap, old = _install_logger()
    try:
        try:
            _run(PromptService().update_prompt_for_model(sess, "nemotron", {}, expected_version=2))
            raise AssertionError("conflict did not raise")
        except PromptVersionConflictError as exc:
            assert exc.model == "nemotron"
            assert exc.expected_version == 2
            assert exc.actual_version == 3
    finally:
        _m.logger = old
    assert sess.calls == ["execute"]  # raised BEFORE the deactivate
    assert len(cap.records) == 1
    r = cap.records[0]
    assert r.levelno == logging.WARNING
    assert r.msg == (
        "Concurrent modification detected for model nemotron: expected version 2, actual version 3"
    )
    _extra(r, model="nemotron", expected_version=2, actual_version=3)


def test_update_conflict_gate_arms_at_max_version_one() -> None:
    # max==1 IS armed territory (the gate is max_version > 0): expected 2
    # against actual 1 MUST conflict; a max > 1 mutant silently skips it
    sess = _Sess([_Result(scalar=1)])
    try:
        _run(PromptService().update_prompt_for_model(sess, "nemotron", {}, expected_version=2))
        raise AssertionError("conflict did not raise at max==1")
    except PromptVersionConflictError as exc:
        assert exc.actual_version == 1
        assert exc.expected_version == 2
    assert sess.calls == ["execute"]


def test_update_matching_expected_version_does_NOT_conflict() -> None:
    sess = _Sess([_Result(scalar=3), _Result()])
    out = _run(PromptService().update_prompt_for_model(sess, "nemotron", {}, expected_version=3))
    assert out.version == 4


def test_update_expected_none_or_zero_max_skips_the_gate() -> None:
    sess = _Sess([_Result(scalar=0), _Result()])
    out = _run(PromptService().update_prompt_for_model(sess, "nemotron", {}, expected_version=99))
    assert out.version == 1  # max==0 arms the short-circuit


def test_update_max_version_query_shape() -> None:
    sess = _Sess([_Result(scalar=1), _Result()])
    _run(PromptService().update_prompt_for_model(sess, "xclip", {}))
    max_sql = _sql(sess.statements[0])
    assert max_sql == (
        "SELECT max(prompt_versions.version) AS max_1 FROM prompt_versions "
        "WHERE prompt_versions.model = 'xclip'"
    )


# =========================================================================
# restore_version: lookup by id, not-found raise, exact update kwargs
# =========================================================================


def test_restore_version_passes_the_old_rows_exact_values() -> None:
    old_row = _StubPV(id=9, model="yolo_world", version=3, config_json='{"classes": ["a"]}')
    sess = _Sess([_Result(one=old_row)])
    cap = _Recorder()
    prev = PromptService.update_prompt_for_model
    g = _globals_of(PromptService.restore_version)

    async def _spy(self: Any, **kw: Any) -> str:
        cap.fn(**kw)
        return "restored"

    PromptService.update_prompt_for_model = _spy  # type: ignore[method-assign]
    try:
        out = _run(PromptService().restore_version(sess, 9))
    finally:
        PromptService.update_prompt_for_model = prev  # type: ignore[method-assign]
    assert out == "restored"
    assert cap.calls == [
        (
            (),
            {
                "session": sess,
                "model": "yolo_world",
                "config": {"classes": ["a"]},
                "change_description": "Restored from version 3",
            },
        )
    ]
    assert _sql(sess.statements[0]) == (
        "SELECT prompt_versions.id, prompt_versions.model, "
        "prompt_versions.version, prompt_versions.created_at, "
        "prompt_versions.created_by, prompt_versions.config_json, "
        "prompt_versions.change_description, prompt_versions.is_active, "
        "prompt_versions.row_version FROM prompt_versions WHERE "
        "prompt_versions.id = 9"
    )


def test_restore_missing_version_raises_named_exact_message() -> None:
    sess = _Sess([_Result(one=None)])
    try:
        _run(PromptService().restore_version(sess, 42))
        raise AssertionError("did not raise")
    except ValueError as exc:
        assert str(exc) == "Version 42 not found"


# =========================================================================
# import_prompts: valid/invalid partition, exact update kwargs, records
# =========================================================================


def test_import_partitions_valid_and_unknown_models() -> None:
    lg, cap, old = _install_logger()
    cap_calls = _Recorder()
    prev = PromptService.update_prompt_for_model

    async def _spy(self: Any, **kw: Any) -> Any:
        cap_calls.fn(**kw)
        return _StubPV(model=kw["model"], version=7)

    PromptService.update_prompt_for_model = _spy  # type: ignore[method-assign]
    try:
        out = _run(
            PromptService().import_prompts(
                _Sess([]),
                {
                    "nemotron": {"system_prompt": "s"},
                    "bogbot": {"system_prompt": "x"},
                    "xclip": {"classes": ["c"]},
                },
            )
        )
    finally:
        PromptService.update_prompt_for_model = prev  # type: ignore[method-assign]
        _m.logger = old
    assert out["imported_models"] == ["nemotron", "xclip"]
    assert out["skipped_models"] == ["bogbot"]
    assert out["new_versions"] == {"nemotron": 7, "xclip": 7}
    assert out["message"] == "Imported 2 model configurations"
    assert set(out) == {"imported_models", "skipped_models", "new_versions", "message"}
    assert cap_calls.calls[0][1]["model"] == "nemotron"
    assert cap_calls.calls[0][1]["config"] == {"system_prompt": "s"}
    assert cap_calls.calls[0][1]["change_description"] == "Imported from JSON"
    assert cap_calls.calls[1][1]["model"] == "xclip"
    assert cap_calls.calls[1][1]["config"] == {"classes": ["c"]}
    warn = [r for r in cap.records if r.levelno == logging.WARNING]
    assert len(warn) == 1
    assert warn[0].msg == "Skipping unknown model: bogbot"


def test_import_swallows_update_failure_and_skips_model() -> None:
    lg, cap, old = _install_logger()
    prev = PromptService.update_prompt_for_model

    async def _boom(self: Any, **kw: Any) -> Any:
        raise RuntimeError("db exploded")

    PromptService.update_prompt_for_model = _boom  # type: ignore[method-assign]
    try:
        out = _run(PromptService().import_prompts(_Sess([]), {"nemotron": {"a": 1}}))
    finally:
        PromptService.update_prompt_for_model = prev  # type: ignore[method-assign]
        _m.logger = old
    assert out["imported_models"] == []
    assert out["skipped_models"] == ["nemotron"]
    assert out["new_versions"] == {}
    assert out["message"] == "Imported 0 model configurations"
    err = [r for r in cap.records if r.levelno == logging.ERROR]
    assert len(err) == 1
    assert err[0].msg == "Failed to import config for nemotron: db exploded"


# =========================================================================
# export_all_prompts: fixed version tag, tz-aware stamp, prompts passthrough
# =========================================================================


def test_export_all_prompts_exact_envelope() -> None:
    prev = PromptService.get_all_prompts

    async def _spy(self: Any, session: Any) -> dict[str, Any]:
        return {"nemotron": {"z": 1}}

    PromptService.get_all_prompts = _spy  # type: ignore[method-assign]
    try:
        out = _run(PromptService().export_all_prompts(_Sess([])))
    finally:
        PromptService.get_all_prompts = prev  # type: ignore[method-assign]
    assert out["version"] == "1.0"
    assert out["prompts"] == {"nemotron": {"z": 1}}
    assert set(out) == {"version", "exported_at", "prompts"}
    stamp = _dt.datetime.fromisoformat(out["exported_at"])
    assert stamp.tzinfo is _dt.UTC


class _TestClient:
    # Client stand-in for the test_prompt path: own queue, records every post.

    def __init__(self, q: list[Any]) -> None:
        self.q = q
        self.urls: list[Any] = []
        self.jsons: list[Any] = []
        self.headers: list[Any] = []
        self.timeouts: list[Any] = []

    async def __aenter__(self) -> _TestClient:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def post(self, url: Any, **kw: Any) -> Any:
        self.urls.append(url)
        self.jsons.append(kw.get("json", _MISSING))
        self.headers.append(kw.get("headers", _MISSING))
        item = self.q.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _test_httpx(client_factory: Any) -> ModuleType:
    shim = _fake_httpx()
    shim.AsyncClient = client_factory  # type: ignore[attr-defined]
    return shim


def _swap_llm_globals(httpx_new: Any, time_new: Any) -> dict[str, Any]:
    g = _globals_of(PromptService._run_llm_test)
    old = {"httpx": g["httpx"], "time": g["time"]}
    g["httpx"] = httpx_new
    g["time"] = time_new

    def undo() -> None:
        g["httpx"] = old["httpx"]
        g["time"] = old["time"]

    return {"undo": undo, "g": g}


def _llm_scenario(resp, stamps, system_prompt="SYS", context="CTX"):
    cli = _TestClient([resp])
    timeouts = []

    def _factory(**kw):
        timeouts.append(kw.get("timeout", _MISSING))
        return cli

    seam = _swap_llm_globals(_test_httpx(_factory), _fake_time(stamps))
    try:
        out = _run(PromptService()._run_llm_test(system_prompt, context))
    finally:
        seam["undo"]()
    cli.timeouts = timeouts
    return out, cli


def test_run_llm_test_happy_path_exact_wire():
    payload = '{"risk_score": 7, "note": "ok"}'
    out, cli = _llm_scenario(_StubResp({"content": payload}), [0.0])
    assert out == {"risk_score": 7, "note": "ok"}
    assert cli.urls == ["http://localhost:8098/completion"]
    assert cli.jsons == [
        {
            "prompt": "SYSCTX",
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": 1024,
            "stop": ["<|im_end|>", "<|im_start|>"],
        }
    ]
    assert cli.headers == [{"Content-Type": "application/json"}]
    svc_timeout = PromptService()._timeout
    assert cli.timeouts == [svc_timeout]


def test_run_llm_test_no_context_short_circuits_before_network():
    out, cli = _llm_scenario(_StubResp({}), [0.0], context=None)
    assert out == {"error": "No context available for testing"}
    assert cli.urls == []


def test_run_llm_test_nonjson_content_returns_raw_response():
    out, cli = _llm_scenario(_StubResp({"content": "prose only, no json"}), [0.0])
    assert out == {"raw_response": "prose only, no json"}


def test_run_llm_test_missing_content_key_becomes_raw_empty_string():
    out, cli = _llm_scenario(_StubResp({}), [0.0])
    assert out == {"raw_response": ""}


def test_run_llm_test_timeout_message_exact():
    exc = httpx.ConnectTimeout("timed out reading")
    out, cli = _llm_scenario(exc, [0.0])
    assert out == {"error": "Request timed out: timed out reading"}


def test_run_llm_test_http_status_error_message_exact():
    exc = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("POST", "http://vlm.test/completion"),
        response=httpx.Response(503),
    )
    out, cli = _llm_scenario(exc, [0.0])
    assert out == {"error": "HTTP error 503: boom"}


def test_run_llm_test_request_error_message_exact():
    exc = httpx.ConnectError("connection refused")
    out, cli = _llm_scenario(exc, [0.0])
    assert out == {"error": "Request failed: connection refused"}


def test_run_llm_test_data_error_becomes_raw_response():
    out, cli = _llm_scenario(_StubResp({"content": '{"k": [1, 2]}'}), [0.0])
    assert out == {"k": [1, 2]}


# =========================================================================
# test_prompt: result dict KEY SET, every early-return path, latency math
# =========================================================================


def _tp_scenario(
    stamps,
    model=NEMO,
    config=None,
    event_id=None,
    image_path=None,
    sess=None,
    llm=None,
    httpx_new=None,
):
    g = _globals_of(PromptService.test_prompt)
    old_time, old_httpx = g["time"], g["httpx"]
    old_llm = PromptService._run_llm_test
    g["time"] = _fake_time(stamps)
    if httpx_new is not None:
        g["httpx"] = httpx_new
    if llm is not _NO_LLM:
        PromptService._run_llm_test = llm  # type: ignore[method-assign]
    lg, cap, oldlg = _install_logger()
    try:
        out = _run(
            PromptService().test_prompt(
                sess if sess is not None else _Sess([]),
                model,
                config if config is not None else {},
                event_id=event_id,
                image_path=image_path,
            )
        )
    finally:
        g["time"] = old_time
        g["httpx"] = old_httpx
        PromptService._run_llm_test = old_llm  # type: ignore[method-assign]
        _m.logger = oldlg
    return out, cap


def test_test_prompt_unsupported_model_exact_error_shape():
    # delta 0.9995s: int(999.500...)=999 vs the *1001 mutant's 1000.5=1000
    out, cap = _tp_scenario([100.0, 100.9995], model="florence2")
    assert out == {
        "model": "florence2",
        "before_score": None,
        "after_score": None,
        "before_response": None,
        "after_response": None,
        "improved": None,
        "test_duration_ms": 999,
        "error": "Testing for model 'florence2' not yet implemented",
    }
    assert cap.records == []


def test_test_prompt_needs_event_or_image_exact():
    out, cap = _tp_scenario([10.0, 10.9995])
    assert out["error"] == "Either event_id or image_path must be provided"
    assert out["test_duration_ms"] == 999
    assert out["model"] == NEMO
    assert set(out) == {
        "model",
        "before_score",
        "after_score",
        "before_response",
        "after_response",
        "improved",
        "test_duration_ms",
        "error",
    }


def _event(**kw):
    return SimpleNamespace(
        id=kw.get("id", 7),
        risk_score=kw.get("risk_score", 20),
        llm_prompt=kw.get("llm_prompt", "LP"),
    )


def _llm_recorder(reply):
    seen = []

    async def _spy(self, system_prompt, context):
        seen.append((system_prompt, context))
        return reply

    _spy.seen = seen  # type: ignore[attr-defined]
    return _spy


def test_test_prompt_event_success_full_dict():
    sess = _Sess([_Result(one=_event())])
    llm = _llm_recorder({"risk_score": 25, "raw": "x"})
    out, cap = _tp_scenario(
        [0.0, 1.25],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=sess,
        llm=llm,
    )
    assert sess.calls == ["execute"]
    sql = _sql(sess.statements[0])
    assert "FROM events WHERE events.id = 7" in sql
    assert llm.seen == [("SP", "LP")]
    assert out == {
        "model": NEMO,
        "before_score": 20,
        "after_score": 25,
        "before_response": None,
        "after_response": {"risk_score": 25, "raw": "x"},
        "improved": True,
        "test_duration_ms": 1250,
        "error": None,
    }
    assert cap.records == []


def test_test_prompt_event_regressed_is_not_improved():
    out, cap = _tp_scenario(
        [5.0, 5.5],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=_Sess([_Result(one=_event())]),
        llm=_llm_recorder({"risk_score": 9}),
    )
    assert out["before_score"] == 20
    assert out["after_score"] == 9
    assert out["improved"] is False
    assert out["test_duration_ms"] == 500
    assert cap.records == []


def test_test_prompt_equal_score_zero_window_is_improved():
    # abs(20-20) == 0 satisfies the <= 10 rule; a <= -> < mutant flips this
    out, cap = _tp_scenario(
        [1.0, 1.1],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=_Sess([_Result(one=_event())]),
        llm=_llm_recorder({"risk_score": 20}),
    )
    assert out["improved"] is True
    assert out["after_score"] == 20
    assert out["test_duration_ms"] == 100


def test_test_prompt_ten_point_abs_window_is_improved():
    out, cap = _tp_scenario(
        [2.0, 2.25],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=_Sess([_Result(one=_event())]),
        llm=_llm_recorder({"risk_score": 30}),
    )
    assert out["improved"] is True
    assert out["test_duration_ms"] == 250


def test_test_prompt_eleven_point_abs_window_is_not_improved():
    out, cap = _tp_scenario(
        [3.0, 3.25],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=_Sess([_Result(one=_event())]),
        llm=_llm_recorder({"risk_score": 31}),
    )
    assert out["improved"] is False


def test_test_prompt_nonrisk_reply_scores_zero():
    out, cap = _tp_scenario(
        [4.0, 4.5],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=_Sess([_Result(one=_event())]),
        llm=_llm_recorder({"answer": "no score key here"}),
    )
    assert out["before_score"] == 20
    # .get("risk_score") has NO default: a missing key is None, and the
    # improved computation is skipped entirely (improved stays None)
    assert out["after_score"] is None
    assert out["improved"] is None
    assert out["after_response"] == {"answer": "no score key here"}
    assert out["error"] is None


# =========================================================================
# PromptABTester: logger identity, traffic-split boundary, metric call
# =========================================================================


def test_abtester_holds_config_and_a_name_bound_logger() -> None:
    cfg = ABTestConfig(
        control_version=3,
        treatment_version=4,
        traffic_split=0.5,
        model=NEMO,
    )
    tester = PromptABTester(cfg)
    assert tester._config is cfg
    assert tester._logger.name == _MOD


class _FakeSecrets(ModuleType):
    def __init__(self, val: int) -> None:
        super().__init__("secrets")
        self.val = val
        self.args: list[Any] = []

    def randbelow(self, n: int) -> int:
        self.args.append(n)
        return self.val


def _select_with(cfg: ABTestConfig, val: int) -> Any:
    fs = _FakeSecrets(val)
    g = _globals_of(PromptABTester.select_prompt_version)
    old = g["secrets"]
    g["secrets"] = fs
    try:
        return PromptABTester(cfg).select_prompt_version(), fs
    finally:
        g["secrets"] = old


def test_select_disabled_config_short_circuits_to_control() -> None:
    cfg = ABTestConfig(
        control_version=3,
        treatment_version=4,
        traffic_split=1.0,
        model=NEMO,
        enabled=False,
    )
    out, fs = _select_with(cfg, 0)
    assert out == (3, False)
    assert fs.args == []  # disabled: NO randomness consumed at all


def test_select_zero_draw_lands_on_treatment_at_the_boundary() -> None:
    cfg = ABTestConfig(
        control_version=3,
        treatment_version=4,
        traffic_split=0.0,
        model=NEMO,
    )
    out, fs = _select_with(cfg, 0)
    assert fs.args == [1000]
    # 0/1000.0 == 0.0 <= 0.0: the <= boundary routes to treatment
    assert out == (4, True)


def test_select_max_draw_vs_full_split_is_treatment() -> None:
    cfg = ABTestConfig(
        control_version=3,
        treatment_version=4,
        traffic_split=1.0,
        model=NEMO,
    )
    out, fs = _select_with(cfg, 999)
    assert fs.args == [1000]
    assert out == (4, True)  # 0.999 <= 1.0


def test_select_half_split_high_draw_is_control() -> None:
    cfg = ABTestConfig(
        control_version=3,
        treatment_version=4,
        traffic_split=0.5,
        model=NEMO,
    )
    out, fs = _select_with(cfg, 750)
    assert out == (3, False)  # 0.75 > 0.5


def test_select_divisor_is_exactly_1000() -> None:
    # split 0.9985 sits between 999/1001 (0.998...) and 999/1000 (0.999):
    # only the EXACT /1000.0 divisor routes the 999 draw to control
    cfg = ABTestConfig(
        control_version=3,
        treatment_version=4,
        traffic_split=0.9985,
        model=NEMO,
    )
    out, fs = _select_with(cfg, 999)
    assert out == (3, False)


def test_select_half_split_low_draw_is_treatment() -> None:
    cfg = ABTestConfig(
        control_version=3,
        treatment_version=4,
        traffic_split=0.5,
        model=NEMO,
    )
    out, fs = _select_with(cfg, 499)
    assert out == (4, True)  # 0.499 <= 0.5


def _metrics_spy() -> tuple[ModuleType, list[Any]]:
    calls: list[Any] = []
    mod = ModuleType("backend.core.metrics")

    def _rec(*args: Any) -> None:
        calls.append(args)

    for n in ("record_prompt_latency", "record_shadow_comparison", "record_prompt_rollback"):
        setattr(mod, n, _rec)
    return mod, calls


def _run_with_metrics(
    fn: Any,
    self: Any,
    *args: Any,
) -> tuple[Any, list[Any], list[Any]]:
    import backend.core.metrics as MET

    mod, calls = _metrics_spy()
    sys.modules["backend.core.metrics"] = mod  # type: ignore[assignment]
    lg, cap, old = _install_logger()
    try:
        out = _run(fn(self, *args))
    finally:
        sys.modules["backend.core.metrics"] = MET  # type: ignore[assignment]
        _m.logger = old
    return out, calls, cap.records


def test_record_prompt_execution_calls_metric_with_v_label() -> None:
    cfg = ABTestConfig(
        control_version=3,
        treatment_version=4,
        traffic_split=0.5,
        model=NEMO,
    )
    tester = PromptABTester(cfg)
    out, calls, records = _run_with_metrics(
        PromptABTester.record_prompt_execution, tester, 5, 1.25, 42
    )
    assert out is None
    assert calls == [("v5", 1.25)]
    assert records == []


# =========================================================================
# PromptShadowRunner.run_shadow_comparison: latencies, diff, metric,
# logger names, error capture
# =========================================================================


class _StubTime(ModuleType):
    def __init__(self, stamps: list[float]) -> None:
        super().__init__("time")
        self.stamps = list(stamps)

    def monotonic(self) -> float:
        return self.stamps.pop(0)


def _shadow_scenario(
    cfg: ShadowModeConfig,
    runner: Any,
    stamps: list[float],
) -> tuple[Any, list[Any], list[Any]]:
    import backend.core.metrics as MET

    mod, calls = _metrics_spy()
    sys.modules["backend.core.metrics"] = mod  # type: ignore[assignment]
    g = _globals_of(PromptShadowRunner.run_shadow_comparison)
    old_time = g["time"]
    g["time"] = _StubTime(stamps)
    lg = logging.getLogger("shadow-spy")
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    cap = _LogCap()
    lg.addHandler(cap)
    old_log = runner._logger
    runner._logger = lg
    try:
        out = _run(PromptShadowRunner.run_shadow_comparison(runner, "CTX"))
    finally:
        g["time"] = old_time
        sys.modules["backend.core.metrics"] = MET  # type: ignore[assignment]
        runner._logger = old_log
    return out, calls, cap.records


def _scripted_runner(
    cfg: ShadowModeConfig,
    script: dict[int, Any],
) -> tuple[Any, list[Any]]:
    seen: list[Any] = []

    async def _run_single(version: int, context: str) -> dict[str, Any]:
        seen.append((version, context))
        item = script[version]
        if isinstance(item, Exception):
            raise item
        return item

    runner = PromptShadowRunner(cfg)
    runner._run_single_prompt = _run_single  # type: ignore[method-assign]
    return runner, seen


def test_shadow_disabled_runs_control_only_with_exact_result() -> None:
    cfg = ShadowModeConfig(
        enabled=False,
        control_version=2,
        shadow_version=3,
        model=NEMO,
    )
    runner, seen = _scripted_runner(cfg, {2: {"risk_score": 12}})
    out, calls, records = _shadow_scenario(cfg, runner, [100.0, 100.5])
    assert seen == [(2, "CTX")]
    assert calls == []
    assert records == []
    assert out == ShadowComparisonResult(
        control_result={"risk_score": 12},
        control_latency_ms=500.0,
    )


def test_shadow_enabled_full_comparison_exact_every_field() -> None:
    cfg = ShadowModeConfig(
        enabled=True,
        control_version=2,
        shadow_version=3,
        model="xclip",
    )
    runner, seen = _scripted_runner(
        cfg,
        {2: {"risk_score": 12}, 3: {"risk_score": 20}},
    )
    out, calls, records = _shadow_scenario(cfg, runner, [10.0, 10.5, 20.0, 20.25])
    assert seen == [(2, "CTX"), (3, "CTX")]
    assert calls == [("xclip",)]
    assert out == ShadowComparisonResult(
        control_result={"risk_score": 12},
        shadow_result={"risk_score": 20},
        risk_score_diff=8,
        control_latency_ms=500.0,
        shadow_latency_ms=250.0,
    )
    assert len(records) == 1
    r = records[0]
    assert r.levelno == logging.INFO
    assert r.msg == "Shadow comparison: control=12, shadow=20, diff=8"


def test_shadow_score_missing_defaults_to_zero_not_none() -> None:
    cfg = ShadowModeConfig(
        enabled=True,
        control_version=2,
        shadow_version=3,
        model=NEMO,
    )
    runner, _seen = _scripted_runner(cfg, {2: {}, 3: {"risk_score": 3}})
    out, calls, records = _shadow_scenario(cfg, runner, [1.0, 1.0, 1.0, 1.0])
    assert out.risk_score_diff == 3
    r = records[0]
    assert r.msg == "Shadow comparison: control=0, shadow=3, diff=3"
    assert calls == [(NEMO,)]


def test_shadow_missing_key_on_shadow_side_defaults_to_zero() -> None:
    # shadow reply WITHOUT risk_score: default 0 -> diff = |4 - 0| = 4 and a
    # 'shadow=0' log line; None/absent defaults raise TypeError inside the
    # try (captured as shadow_error); default 1 gives diff 3
    cfg = ShadowModeConfig(
        enabled=True,
        control_version=2,
        shadow_version=3,
        model=NEMO,
    )
    runner, _seen = _scripted_runner(cfg, {2: {"risk_score": 4}, 3: {}})
    out, calls, records = _shadow_scenario(cfg, runner, [0.0, 0.0, 0.0, 0.0])
    assert out.shadow_error is None
    assert out.risk_score_diff == 4
    assert out.shadow_result == {}
    assert calls == [(NEMO,)]
    assert records[0].msg == "Shadow comparison: control=4, shadow=0, diff=4"


def test_shadow_metric_uses_the_configured_model_name() -> None:
    cfg = ShadowModeConfig(
        enabled=True,
        control_version=2,
        shadow_version=3,
        model="florence2",
        log_comparisons=False,
    )
    runner, _seen = _scripted_runner(
        cfg,
        {2: {"risk_score": 1}, 3: {"risk_score": 1}},
    )
    out, calls, records = _shadow_scenario(cfg, runner, [0.0, 0.0, 0.0, 0.0])
    assert calls == [("florence2",)]
    assert records == []  # log_comparisons=False silences the INFO line
    assert out.risk_score_diff == 0
    assert out.shadow_error is None


def test_shadow_failure_captures_message_and_warns() -> None:
    cfg = ShadowModeConfig(
        enabled=True,
        control_version=2,
        shadow_version=3,
        model=NEMO,
    )
    runner, seen = _scripted_runner(cfg, {2: {"risk_score": 4}, 3: RuntimeError("boom")})
    out, calls, records = _shadow_scenario(cfg, runner, [3.0, 3.0, 30.0, 30.0])
    assert seen == [(2, "CTX"), (3, "CTX")]
    assert calls == []
    assert out.shadow_error == "boom"
    assert out.shadow_result is None
    assert out.risk_score_diff == 0.0
    assert out.control_latency_ms == 0.0
    assert len(records) == 1
    r = records[0]
    assert r.levelno == logging.WARNING
    assert r.msg == "Shadow prompt failed: boom"


# =========================================================================
# PromptRollbackChecker: gate order, boundary math, reason strings,
# rollback execution incl. the hasattr-model fork
# =========================================================================


def _checker_with_logger(cfg: RollbackConfig) -> tuple[Any, _LogCap]:
    chk = PromptRollbackChecker(cfg)
    lg = logging.getLogger("rollback-spy")
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    cap = _LogCap()
    lg.addHandler(cap)
    chk._logger = lg
    return chk, cap


def test_checker_holds_config_and_a_name_bound_logger() -> None:
    cfg = RollbackConfig()
    chk = PromptRollbackChecker(cfg)
    assert chk._config is cfg
    assert chk._logger.name == _MOD
    assert PromptEvaluator()._logger.name == _MOD
    tcfg = ABTestConfig(
        control_version=1,
        treatment_version=2,
        traffic_split=0.0,
        model=NEMO,
    )
    s = ShadowModeConfig(
        enabled=False,
        control_version=1,
        shadow_version=2,
        model=NEMO,
    )
    assert PromptShadowRunner(s)._logger.name == _MOD
    assert PromptABTester(tcfg)._logger.name == _MOD


def test_checker_disabled_returns_exact_disabled_reason() -> None:
    cfg = RollbackConfig(enabled=False, min_samples=1)
    chk, _cap = _checker_with_logger(cfg)
    m = SimpleNamespace(sample_count=1_000_000, latency_increase_pct=9e9, score_variance=9e9)
    out = _run(chk.check_rollback_needed(m))
    assert out == RollbackCheckResult(should_rollback=False, reason="Rollback disabled")


def test_checker_insufficient_samples_reason_is_an_exact_render() -> None:
    cfg = RollbackConfig(min_samples=100)
    chk, _cap = _checker_with_logger(cfg)
    m = SimpleNamespace(sample_count=99, latency_increase_pct=9e9, score_variance=9e9)
    out = _run(chk.check_rollback_needed(m))
    assert out == RollbackCheckResult(
        should_rollback=False,
        reason="Insufficient samples (99/100)",
    )


def test_checker_sample_count_equal_min_passes_the_gate() -> None:
    cfg = RollbackConfig(min_samples=100, max_latency_increase_pct=50.0, max_score_variance=15.0)
    chk, _cap = _checker_with_logger(cfg)
    m = SimpleNamespace(sample_count=100, latency_increase_pct=1.0, score_variance=1.0)
    out = _run(chk.check_rollback_needed(m))
    # 100 < 100 is False: at the boundary evaluation PROCEEDS, ending in the
    # clean no-rollback result with a None reason
    assert out == RollbackCheckResult(should_rollback=False, reason=None)


def test_checker_latency_equal_threshold_does_NOT_rollback() -> None:
    cfg = RollbackConfig(min_samples=2, max_latency_increase_pct=50.0, max_score_variance=15.0)
    chk, _cap = _checker_with_logger(cfg)
    m = SimpleNamespace(sample_count=5, latency_increase_pct=50.0, score_variance=1.0)
    out = _run(chk.check_rollback_needed(m))
    assert out.reason is None
    assert out.should_rollback is False


def test_checker_latency_over_threshold_reason_is_one_decimal() -> None:
    cfg = RollbackConfig(min_samples=2, max_latency_increase_pct=50.0, max_score_variance=15.0)
    chk, _cap = _checker_with_logger(cfg)
    m = SimpleNamespace(sample_count=5, latency_increase_pct=50.05, score_variance=1.0)
    out = _run(chk.check_rollback_needed(m))
    assert out == RollbackCheckResult(
        should_rollback=True,
        reason="Latency increase 50.0% exceeds threshold",
    )


def test_checker_variance_equal_threshold_does_NOT_rollback() -> None:
    cfg = RollbackConfig(min_samples=2, max_score_variance=15.0)
    chk, _cap = _checker_with_logger(cfg)
    m = SimpleNamespace(sample_count=5, latency_increase_pct=1.0, score_variance=15.0)
    out = _run(chk.check_rollback_needed(m))
    assert out == RollbackCheckResult(should_rollback=False, reason=None)


def test_checker_variance_over_threshold_rolls_back() -> None:
    cfg = RollbackConfig(min_samples=2, max_latency_increase_pct=50.0, max_score_variance=15.0)
    chk, _cap = _checker_with_logger(cfg)
    m = SimpleNamespace(sample_count=5, latency_increase_pct=1.0, score_variance=15.1)
    out = _run(chk.check_rollback_needed(m))
    assert out == RollbackCheckResult(
        should_rollback=True,
        reason="Score variance 15.1 exceeds threshold",
    )


def test_checker_latency_gate_wins_before_variance_when_both_trip() -> None:
    cfg = RollbackConfig(min_samples=2, max_latency_increase_pct=50.0, max_score_variance=15.0)
    chk, _cap = _checker_with_logger(cfg)
    m = SimpleNamespace(sample_count=5, latency_increase_pct=99.0, score_variance=99.0)
    out = _run(chk.check_rollback_needed(m))
    assert out.reason == "Latency increase 99.0% exceeds threshold"


def _ab_cfg(**kw: Any) -> SimpleNamespace:
    kw.setdefault("control_version", 3)
    kw.setdefault("treatment_version", 7)
    kw.setdefault("traffic_split", 0.5)
    kw.setdefault("model", "xclip")
    kw.setdefault("enabled", True)
    return SimpleNamespace(**kw)


def test_execute_rollback_success_disables_logs_and_returns_versions() -> None:
    cfg = RollbackConfig()
    chk, cap = _checker_with_logger(cfg)
    ab = _ab_cfg()
    out, calls, _unused = _run_with_metrics(
        PromptRollbackChecker.execute_rollback,
        chk,
        _Sess([]),
        ab,
        "degraded",
    )
    records = cap.records
    assert ab.enabled is False  # _disable_ab_test ran on THIS object
    assert out == RollbackExecutionResult(
        success=True,
        previous_version=7,
        new_version=3,
    )
    assert calls == [("xclip", "performance")]
    assert len(records) == 1
    r = records[0]
    assert r.levelno == logging.WARNING
    assert r.msg == "Rolling back from v7 to v3: degraded"


def test_execute_rollback_falls_back_to_nemotron_without_model_attr() -> None:
    cfg = RollbackConfig()
    chk, cap = _checker_with_logger(cfg)
    ab = _ab_cfg()
    del ab.model
    out, calls, _unused = _run_with_metrics(
        PromptRollbackChecker.execute_rollback,
        chk,
        _Sess([]),
        ab,
        "why",
    )
    records = cap.records
    assert out.success is True
    assert calls == [("nemotron", "performance")]
    assert records[0].msg == "Rolling back from v7 to v3: why"


def test_execute_rollback_failure_path_returns_bare_failure() -> None:
    cfg = RollbackConfig()
    chk, cap = _checker_with_logger(cfg)

    async def _boom(_ab_config: Any) -> None:
        # underscore-prefix: the mock must ACCEPT the arg the call site
        # passes (vulture's unused-arg rule skips _-names)
        raise RuntimeError("snap failed")

    chk._disable_ab_test = _boom  # type: ignore[method-assign]
    out, calls, _unused = _run_with_metrics(
        PromptRollbackChecker.execute_rollback,
        chk,
        _Sess([]),
        _ab_cfg(),
        "ignored",
    )
    records = cap.records
    assert out == RollbackExecutionResult(success=False)
    assert out.previous_version is None
    assert out.new_version is None
    assert calls == []
    assert len(records) == 1
    r = records[0]
    assert r.levelno == logging.ERROR
    assert r.msg == "Rollback failed: snap failed"


# =========================================================================
# PromptEvaluator._calculate_correlation: guard boundaries, the missing
# attribute default, the NaN arm
# =========================================================================


def _corr(pairs: list[Any], diffs: list[float]) -> Any:
    return PromptEvaluator()._calculate_correlation(pairs, diffs)


def test_corr_with_two_events_still_computes() -> None:
    # exactly 2 events: the < 2 guard PASSES (a <= mutant would return None)
    evs = [SimpleNamespace(risk_score=20), SimpleNamespace(risk_score=10)]
    assert _corr(evs, [5.0, 6.0]) == -0.9999999999999999


def test_corr_with_one_event_returns_none() -> None:
    assert _corr([SimpleNamespace(risk_score=20)], [5.0]) is None


def test_corr_missing_risk_score_attr_defaults_to_zero() -> None:
    # the THIRD event has no risk_score: the default 0 renders [20, 1, 0];
    # default 1 would render [20, 1, 1] -> 0.9449111825230679 (measured);
    # default None or an ABSENT default raise inside the try -> None.
    # (Three+ events are REQUIRED: any 2-point Pearson is +/-1 and Pearson
    # is affine-invariant, so 2 points cannot separate these defaults.)
    evs = [
        SimpleNamespace(risk_score=20),
        SimpleNamespace(risk_score=1),
        SimpleNamespace(),
    ]
    assert _corr(evs, [5.0, 2.0, 3.0]) == 0.9294579137854025


def test_corr_constant_scores_yield_nan_becomes_none() -> None:
    evs = [SimpleNamespace(risk_score=5), SimpleNamespace(risk_score=5)]
    assert _corr(evs, [2.0, 2.0]) is None


def test_corr_slices_events_to_the_score_diffs_length() -> None:
    evs = [
        SimpleNamespace(risk_score=20),
        SimpleNamespace(risk_score=0),
        SimpleNamespace(risk_score=0),
    ]
    # len(events)==3 > len(diffs)==2: slicing to 2 leaves [20, 0]
    got = _corr(evs, [5.0, 2.0])
    assert got == 1.0
    assert _corr(evs, [5.0, 2.0, 3.0]) == 0.9449111825230679


def test_corr_length_mismatch_after_slice_returns_none() -> None:
    evs = [SimpleNamespace(risk_score=20), SimpleNamespace(risk_score=1)]
    # three diffs but only two events: original_scores (2) != diffs (3)
    assert _corr(evs, [5.0, 2.0, 3.0]) is None


# =========================================================================
# PromptEvaluator.evaluate_prompt_version / compare_prompt_versions /
# create_evaluation_batch
# =========================================================================


def _evaluate(
    results: list[Any],
    events: list[Any],
    stamps: list[float],
    corr: Any = 0.5,
    version: int = 9,
) -> tuple[Any, list[Any], list[Any], list[Any]]:
    ev = PromptEvaluator()
    seen: list[Any] = []
    corr_seen: list[Any] = []
    queue = list(results)

    async def _run(_version: int, event: Any) -> dict[str, Any]:
        seen.append((_version, event))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def _cc(events: Any, diffs: Any) -> Any:
        corr_seen.append((list(events), list(diffs)))
        return corr

    ev._run_prompt_for_event = _run  # type: ignore[method-assign]
    ev._calculate_correlation = _cc  # type: ignore[method-assign]
    lg = logging.getLogger("eval-spy")
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    cap = _LogCap()
    lg.addHandler(cap)
    ev._logger = lg
    g = _globals_of(PromptEvaluator.evaluate_prompt_version)
    old_time = g["time"]
    g["time"] = _StubTime(stamps)
    batch = EvaluationBatch(events=events, created_at=_dt.datetime(2026, 1, 1))
    try:
        out = _run_outer(ev.evaluate_prompt_version(_Sess([]), version, batch))
    finally:
        g["time"] = old_time
    return out, seen, corr_seen, cap.records


def _run_outer(coro: Any) -> Any:
    return asyncio.run(coro)


def test_evaluate_empty_batch_returns_bare_zero_results() -> None:
    out, seen, corr_seen, records = _evaluate([], [], [0.0])
    assert out == EvaluationResults(total_events=0)
    assert out.average_latency_ms == 0.0
    assert seen == [] and corr_seen == [] and records == []


def test_evaluate_all_failures_warns_per_event_and_returns_zero() -> None:
    evs = [SimpleNamespace(id=1, risk_score=20), SimpleNamespace(id=2, risk_score=9)]
    out, seen, corr_seen, records = _evaluate(
        [RuntimeError("nope1"), ValueError("nope2")],
        evs,
        [0.0, 0.0, 1.0, 1.0],
    )
    assert out == EvaluationResults(total_events=0)
    assert seen == [(9, evs[0]), (9, evs[1])]
    assert corr_seen == []
    assert [r.msg for r in records] == [
        "Evaluation failed for event 1: nope1",
        "Evaluation failed for event 2: nope2",
    ]
    assert all(r.levelno == logging.WARNING for r in records)


def test_evaluate_happy_path_exact_stats_and_latencies() -> None:
    # events risk 20,10; replies risk 25,16 -> diffs [5, 6]
    # stamps: ev1 start 100.0 end 100.5 -> 500.0ms; ev2 101.0 end 101.25 -> 250.0
    evs = [SimpleNamespace(id=1, risk_score=20), SimpleNamespace(id=2, risk_score=10)]
    out, seen, corr_seen, records = _evaluate(
        [{"risk_score": 25}, {"risk_score": 16}],
        evs,
        [100.0, 100.5, 101.0, 101.25],
        corr=0.25,
        version=4,
    )
    assert seen == [(4, evs[0]), (4, evs[1])]
    assert corr_seen == [(evs, [5.0, 6.0])]
    assert out == EvaluationResults(
        total_events=2,
        average_score_diff=5.5,
        score_variance=0.25,
        average_latency_ms=375.0,
        score_correlation=0.25,
    )
    assert records == []


def test_evaluate_missing_score_key_defaults_diff_to_original() -> None:
    # reply WITHOUT risk_score: .get default 0 -> diff == |0 - 20| == 20
    evs = [SimpleNamespace(id=1, risk_score=20), SimpleNamespace(id=2, risk_score=10)]
    out, seen, corr_seen, records = _evaluate(
        [{}, {"risk_score": 16}],
        evs,
        [0.0, 0.0, 0.0, 0.0],
    )
    assert out.total_events == 2
    assert corr_seen == [(evs, [20.0, 6.0])]
    assert out.average_score_diff == 13.0
    assert out.score_variance == 49.0


def test_evaluate_event_without_attr_score_original_defaults_to_zero() -> None:
    evs = [SimpleNamespace(id=1), SimpleNamespace(id=2, risk_score=10)]
    out, seen, corr_seen, records = _evaluate(
        [{"risk_score": 5}, {"risk_score": 16}],
        evs,
        [0.0, 0.0, 0.0, 0.0],
    )
    assert corr_seen == [(evs, [5.0, 6.0])]


def test_evaluate_latency_average_survives_one_failure() -> None:
    evs = [SimpleNamespace(id=1, risk_score=20), SimpleNamespace(id=2, risk_score=10)]
    out, seen, corr_seen, records = _evaluate(
        [{"risk_score": 25}, RuntimeError("late boom")],
        evs,
        [0.0, 0.25, 1.0, 1.0],
    )
    assert out.total_events == 1
    assert out.average_latency_ms == 250.0
    assert len(records) == 1
    assert records[0].msg == "Evaluation failed for event 2: late boom"


def _compare_with(
    va: int,
    vb: int,
    res_a: EvaluationResults,
    res_b: EvaluationResults,
) -> tuple[Any, list[Any]]:
    ev = PromptEvaluator()
    calls: list[Any] = []
    sess = _Sess([])

    async def _ev(session: Any, version: int, batch: Any) -> EvaluationResults:
        calls.append((session, version, batch))
        return res_a if version == va else res_b

    ev.evaluate_prompt_version = _ev  # type: ignore[method-assign]
    batch = EvaluationBatch(events=[], created_at=_dt.datetime(2026, 1, 1))
    out = _run_outer(ev.compare_prompt_versions(sess, va, vb, batch))
    assert calls[0][0] is sess and calls[1][0] is sess
    assert calls[0][2] is batch and calls[1][2] is batch
    assert [c[1] for c in calls] == [va, vb]  # exact positional order
    return out, calls


def test_compare_ties_and_none_score_recommends_a() -> None:
    ra = EvaluationResults(total_events=2, average_score_diff=5.0, score_variance=2.0)
    rb = EvaluationResults(total_events=2, average_score_diff=7.0, score_variance=0.0)
    out, calls = _compare_with(3, 4, ra, rb)
    assert out == VersionComparisonResult(
        version_a_results=ra,
        version_b_results=rb,
        recommended_version=3,
    )


def test_compare_b_wins_on_the_sum_not_just_the_average() -> None:
    ra = EvaluationResults(total_events=2, average_score_diff=5.0, score_variance=10.0)
    rb = EvaluationResults(total_events=2, average_score_diff=9.0, score_variance=0.0)
    # score_a == 15.0 > score_b == 9.0 -> b despite b's WORSE average
    out, _calls = _compare_with(1, 2, ra, rb)
    assert out.recommended_version == 2


def test_compare_exact_tie_recommends_a_via_le_boundary() -> None:
    ra = EvaluationResults(total_events=2, average_score_diff=4.0, score_variance=1.0)
    rb = EvaluationResults(total_events=2, average_score_diff=3.0, score_variance=2.0)
    # both scores 5.0: <= keeps a (a < mutant would flip to b)
    out, _calls = _compare_with(7, 8, ra, rb)
    assert out.recommended_version == 7


def test_compare_none_stats_treated_as_zero_not_crash() -> None:
    ra = EvaluationResults(total_events=1)  # both stats None -> 0
    rb = EvaluationResults(total_events=1, average_score_diff=0.5, score_variance=0.0)
    out, _calls = _compare_with(1, 2, ra, rb)
    assert out.recommended_version == 1


def test_compare_none_defaults_are_zero_not_one() -> None:
    # b's average is None: the or-0 default gives score_b = 0+1 = 1 < 2 =
    # score_a -> b wins; an or-1 mutant renders 1+1 = 2 -> a wins (flip)
    ra = EvaluationResults(total_events=1, average_score_diff=2.0, score_variance=0.0)
    rb = EvaluationResults(total_events=1, average_score_diff=None, score_variance=1.0)
    out, _calls = _compare_with(5, 6, ra, rb)
    assert out.recommended_version == 6
    # b's variance is None: or-0 gives 1+0 = 1 < 1.5 -> b; or-1 gives 2 -> a
    ra2 = EvaluationResults(total_events=1, average_score_diff=1.5, score_variance=0.0)
    rb2 = EvaluationResults(total_events=1, average_score_diff=1.0, score_variance=None)
    out2, _c2 = _compare_with(5, 6, ra2, rb2)
    assert out2.recommended_version == 6


def test_compare_none_variance_only_still_sums() -> None:
    ra = EvaluationResults(total_events=1, average_score_diff=None, score_variance=3.0)
    rb = EvaluationResults(total_events=1, average_score_diff=None, score_variance=1.0)
    out, _calls = _compare_with(1, 2, ra, rb)
    assert out.recommended_version == 2


# =========================================================================
# create_evaluation_batch: cutoff direction, tz, order, limit
# =========================================================================


class _FrozenDT:
    frozen = _dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=_dt.UTC)

    @classmethod
    def now(cls, tz: Any = None) -> _dt.datetime:
        # REAL datetime.now semantics: naive when tz is None
        if tz is None:
            return cls.frozen.replace(tzinfo=None)
        return cls.frozen


def _create_batch(hours_back: int, sample_size: int, rows: list[Any]) -> tuple[Any, Any]:
    g = _globals_of(PromptEvaluator.create_evaluation_batch)
    old = g["datetime"]
    g["datetime"] = _FrozenDT
    sess = _Sess([_Result(rows=rows)])
    try:
        out = _run_outer(
            PromptEvaluator().create_evaluation_batch(
                sess,
                hours_back=hours_back,
                sample_size=sample_size,
            )
        )
    finally:
        g["datetime"] = old
    return out, sess


def test_create_batch_cutoff_is_minus_hours_with_exact_sql() -> None:
    rows = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    out, sess = _create_batch(hours_back=24, sample_size=100, rows=rows)
    assert out.events == rows
    assert _sql(sess.statements[0]) == (
        "SELECT events.id, events.batch_id, events.camera_id, "
        "events.started_at, events.ended_at, events.risk_score, "
        "events.risk_level, events.version, events.summary, "
        "events.reviewed, events.flagged, events.notes, "
        "events.is_fast_path, events.object_types, events.clip_path, "
        "events.search_vector, events.entities, events.flags, "
        "events.confidence_factors, events.recommended_action, "
        "events.deleted_at, events.snooze_until FROM events WHERE "
        "events.started_at >= '2025-12-31 12:00:00+00:00' ORDER BY "
        "events.started_at DESC LIMIT 100"
    )
    assert _params(sess.statements[0]) == {
        "started_at_1": _dt.datetime(2025, 12, 31, 12, 0, tzinfo=_dt.UTC),
        "param_1": 100,
    }
    assert out.created_at is _FrozenDT.frozen
    assert out.created_at.tzinfo is _dt.UTC


def test_create_batch_cutoff_direction_and_window_size() -> None:
    # hours_back=2: cutoff 10:00 same day; also proves - not +
    _out, sess = _create_batch(hours_back=2, sample_size=7, rows=[])
    assert _params(sess.statements[0]) == {
        "started_at_1": _dt.datetime(2026, 1, 1, 10, 0, tzinfo=_dt.UTC),
        "param_1": 7,
    }


def test_create_batch_binds_sample_size_as_the_limit() -> None:
    _out, sess = _create_batch(hours_back=48, sample_size=1, rows=[])
    lit = _sql(sess.statements[0])
    assert lit.endswith("ORDER BY events.started_at DESC LIMIT 1")
    assert _params(sess.statements[0])["param_1"] == 1


def test_test_prompt_event_not_found_exact_message_and_sql():
    sess = _Sess([_Result(one=None)])
    out, cap = _tp_scenario(
        [7.0, 7.9995],
        config={"system_prompt": "SP"},
        event_id=99,
        sess=sess,
    )
    assert sess.calls == ["execute"]
    assert _sql(sess.statements[0]) == (
        "SELECT events.id, events.batch_id, events.camera_id, "
        "events.started_at, events.ended_at, events.risk_score, "
        "events.risk_level, events.version, events.summary, "
        "events.reviewed, events.flagged, events.notes, "
        "events.is_fast_path, events.object_types, events.clip_path, "
        "events.search_vector, events.entities, events.flags, "
        "events.confidence_factors, events.recommended_action, "
        "events.deleted_at, events.snooze_until FROM events WHERE "
        "events.id = 99"
    )
    assert out == {
        "model": NEMO,
        "before_score": None,
        "after_score": None,
        "before_response": None,
        "after_response": None,
        "improved": None,
        "test_duration_ms": 999,
        "error": "Event 99 not found",
    }
    assert cap.records == []


def test_test_prompt_config_without_system_prompt_exact():
    sess = _Sess([_Result(one=_event())])
    out, cap = _tp_scenario(
        [8.0, 8.9995],
        config={"other": 1},
        event_id=7,
        sess=sess,
    )
    assert out == {
        "model": NEMO,
        "before_score": 20,
        "after_score": None,
        "before_response": None,
        "after_response": None,
        "improved": None,
        "test_duration_ms": 999,
        "error": "system_prompt not found in config",
    }
    assert cap.records == []


def _llm_raises(exc: Any) -> Any:
    async def _boom(self: Any, system_prompt: Any, context: Any) -> Any:
        raise exc

    return _boom


def test_test_prompt_timeout_arm_warning_and_error_exact():
    sess = _Sess([_Result(one=_event())])
    exc = httpx.ConnectTimeout("slow engine")
    out, cap = _tp_scenario(
        [9.0, 9.125],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=sess,
        llm=_llm_raises(exc),
    )
    assert out == {
        "model": NEMO,
        "before_score": 20,
        "after_score": None,
        "before_response": None,
        "after_response": None,
        "improved": None,
        "test_duration_ms": 125,
        "error": "Request timed out: slow engine",
    }
    assert len(cap.records) == 1
    r = cap.records[0]
    assert r.levelno == logging.WARNING
    assert r.msg == "Prompt test timed out for model nemotron: slow engine"


def test_test_prompt_http_status_arm_warning_and_error_exact():
    sess = _Sess([_Result(one=_event())])
    exc = httpx.HTTPStatusError(
        "upstream died",
        request=httpx.Request("POST", "http://vlm.test/completion"),
        response=httpx.Response(503),
    )
    out, cap = _tp_scenario(
        [11.0, 11.0],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=sess,
        llm=_llm_raises(exc),
    )
    assert out["error"] == "HTTP error: upstream died"
    assert out["test_duration_ms"] == 0
    assert len(cap.records) == 1
    assert cap.records[0].msg == "Prompt test HTTP error for model nemotron: upstream died"


def test_test_prompt_request_error_arm_warning_and_error_exact():
    sess = _Sess([_Result(one=_event())])
    exc = httpx.ConnectError("engine down")
    out, cap = _tp_scenario(
        [12.0, 12.75],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=sess,
        llm=_llm_raises(exc),
    )
    assert out["error"] == "Request failed: engine down"
    assert out["test_duration_ms"] == 750
    assert len(cap.records) == 1
    assert cap.records[0].msg == "Prompt test request failed for model nemotron: engine down"


def test_test_prompt_data_error_arm_warning_and_error_exact():
    sess = _Sess([_Result(one=_event())])
    exc = ValueError("not a number")
    out, cap = _tp_scenario(
        [13.0, 13.5],
        config={"system_prompt": "SP"},
        event_id=7,
        sess=sess,
        llm=_llm_raises(exc),
    )
    assert out["error"] == "Data error: not a number"
    assert out["test_duration_ms"] == 500
    assert len(cap.records) == 1
    assert cap.records[0].msg == "Prompt test data error for model nemotron: not a number"
