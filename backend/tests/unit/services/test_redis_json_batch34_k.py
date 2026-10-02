# TARGET-MODULE: backend.services.redis_json
"""Campaign #10 battery K: kill-real for backend/services/redis_json.py survivors.

Campaign #10 (mutation ladder, 2026-09-30). 338 survivor keys, 256/594 = 43.10%
module kt before this battery. The shipped test_redis_json.py suite drives every
method through MagicMock/_client AsyncMocks and asserts RETURN VALUES only, so
the whole execute_command ARGUMENT family (None-substituted, dropped, case- and
XX-wrapped redis commands/paths/values), the log-record family (message XX/case
variants, extra=None, key renames, str(None) error payloads), the
fallback-delegation family (self.get_batch_metadata(None),
self.set_batch_metadata(None, ...)), the split/replace path-parser args and the
singleton settings family survive. This battery:

  * replaces _client with a recorder logging (name, args, kwargs) for
    execute_command/expire/setex/get/exists/delete/pipeline/scan_iter and
    asserts the EXACT call list -- not mock-accepts-anything call_args checks;
  * captures rj.logger with its own handler (get_logger attaches ContextFilter
    to the module logger, so captured records carry the production ambient set)
    and asserts record MESSAGE EQUALITY + the COMPLETE attribute set; ambient
    key audit at authoring (probed THROUGH the real filter): it injects only
    request_id/correlation_id/trace_id/span_id/connection_id/task_id/job_id/
    hostname/container_id/app_version/environment -- none of this module's
    extra keys (batch_id/key/error/path/reason) collide, so a dropped or
    renamed extra key really disappears from the record;
  * pins rj.time so time.time()-derived payloads (append's last_activity str,
    close_time str, from_dict clock defaults) have distinct asserted values;
    the module imports NO asyncio, so battery I's global-sleep hazard is
    structurally absent here;
  * spies on the service's OWN get/set_batch_metadata in a subclass so the
    fallback paths are asserted by EXACT positional forwarding -- a MagicMock
    would accept the None-shifted delegation unchanged;
  * swaps rj.get_settings DIRECTLY (attribute swap spanning the whole awaited
    call, per the await-time-getter rule) around the singleton factory so the
    hasattr(settings, "batch_metadata_ttl") ternary has BOTH polarities --
    real settings LACKS the attribute (probe-verified), so the with-attr stub
    is what makes the non-default branch observable.

Honesty ledger -- registered EQUIVALENTs: NONE. Every one of the 338 survivor
keys is a kill-claim: each survives only because the shipped mocks never look
at arguments/records, and every mutation family above is recorder-, record-,
or equality-observable. Two equivalence claims drafted at inventory time were
WITHDRAWN after reading the actual bodies: _check_json_available 18/19/20 are
delete() ARGUMENT mutants (recorder-visible), and singleton 2 (settings ->
None) is killed by the with-attr polarity asserting ttl == 1234 != 3600. If
the sweep returns GREEN for any key it must be adjudicated BY CONSTRUCTION
before registration -- diff-shape is not a disposition (memory). Key numbers
are the M11-era meta; a coverage-growing battery can renumber tails -- flip
adjudication goes to the body bijection, never the number.
"""

import asyncio
import contextlib
import json
import logging
from types import SimpleNamespace

import backend.services.redis_json as rj

KEY = "batch:meta:B1"
DEFAULT_TTL = rj.DEFAULT_BATCH_META_TTL
NO_CONN = "Redis client not connected"
STD_LOG_ATTRS = frozenset(vars(logging.LogRecord("p", 1, "p", 1, "m", None, None)).keys())

MSG_AVAIL = "RedisJSON module is available"
MSG_UNAVAIL = "RedisJSON module not available, using fallback"
MSG_TRANSIENT = "Error checking RedisJSON availability, using fallback"
MSG_SET_JSON = "Stored batch metadata with RedisJSON"
MSG_SET_STR = "Stored batch metadata with string fallback"
MSG_SET_FAIL = "RedisJSON SET failed, falling back to string"
MSG_GET_FAIL = "RedisJSON GET failed, falling back to string"
MSG_UPDATE_JSON = "Updated batch field with RedisJSON"
MSG_CLOSE_JSON = "Closed batch with RedisJSON"
MSG_SCAN_ERR = "Error reading batch metadata during scan"

INFO, WARNING, DEBUG = logging.INFO, logging.WARNING, logging.DEBUG


def _attempt(coro):
    """Run a coroutine to completion, returning (ok, value_or_exception)."""
    try:
        return True, asyncio.run(coro)
    except Exception as exc:
        return False, exc


# ---------------------------------------------------------------------------
# log capture -- records carry the REAL ContextFilter ambient set
# ---------------------------------------------------------------------------
class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextlib.contextmanager
def _capture_logs():
    """Capture through the MODULE logger only. propagate=False is load-
    bearing: a suite-wide run can leave ancestor handlers (formatters stamp
    record.message, other tests' handlers may mutate records) attached to the
    root logger -- that ambient pollution differs between repo-root and
    mutant-home ordering (found at authoring by the serial mutant-home
    gather-repro), and the complete-attr-set asserts must be deterministic
    across both worlds. The ContextFilter that produces the ambient set is
    attached to rj.logger itself, so it keeps running with propagation off."""
    cap = _Capture()
    handlers = rj.logger.handlers[:]
    rj.logger.handlers[:] = [cap]  # ONLY our recorder runs -- a foreign
    # handler left on this logger by another test would format records and
    # stamp volatile attrs (e.g. record.message) onto the records we assert.
    prev, prev_prop = rj.logger.level, rj.logger.propagate
    rj.logger.setLevel(logging.DEBUG)
    rj.logger.propagate = False
    try:
        yield cap
    finally:
        rj.logger.handlers[:] = handlers
        rj.logger.setLevel(prev)
        rj.logger.propagate = prev_prop


def _ambient_attrs() -> frozenset:
    """The ambient set as the MODULE logger's own filters produce it -- no
    ancestor handlers, no formatter mutations (see _capture_logs)."""
    probe = logging.LogRecord("probe", INFO, __file__, 1, "probe", None, None)
    handlers = rj.logger.handlers[:]
    del rj.logger.handlers[:]
    prev_prop = rj.logger.propagate
    rj.logger.propagate = False
    try:
        rj.logger.handle(probe)
    finally:
        rj.logger.handlers[:] = handlers
        rj.logger.propagate = prev_prop
    return frozenset(k for k in vars(probe) if k not in STD_LOG_ATTRS)


_AMBIENT = _ambient_attrs()


def _assert_record(rec, level, message, **explicit):
    """Exact level + EXACT message + EXACT complete attribute set (ambient
    union explicit) + exact explicit values. Message EQUALITY kills the
    XX/case/None variants a fragment assert would pass."""
    assert rec.levelno == level, (rec.levelno, message)
    assert rec.getMessage() == message, rec.getMessage()
    got = frozenset(k for k in vars(rec) if k not in STD_LOG_ATTRS)
    assert got == _AMBIENT | frozenset(explicit), (sorted(got ^ _AMBIENT), message)
    for k, v in explicit.items():
        assert getattr(rec, k) == v, (k, getattr(rec, k), v, message)


def _assert_single(logs, level, message, **explicit):
    """Exactly one record overall, at level/message, complete attrs."""
    assert len(logs.records) == 1, [r.getMessage() for r in logs.records]
    _assert_record(logs.records[0], level, message, **explicit)


# ---------------------------------------------------------------------------
# clock pin (rj.time -- the module's only call-time ambient getter besides
# get_settings, which only the singleton factory reads)
# ---------------------------------------------------------------------------
class _Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def time(self) -> float:
        return self.t


@contextlib.contextmanager
def _clocked(start: float = 1000.0):
    clk = _Clock(start)
    old = rj.time
    rj.time = clk
    try:
        yield clk
    finally:
        rj.time = old


# ---------------------------------------------------------------------------
# redis recorder stand-ins -- every call recorded as (name, args, kwargs)
# ---------------------------------------------------------------------------
class _Pipe:
    def __init__(self) -> None:
        self.cmds: list[tuple] = []
        self.executes = 0

    def execute_command(self, *args) -> None:
        self.cmds.append(args)

    async def execute(self):
        self.executes += 1
        return []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False


class _Client:
    """returns/raises are keyed by execute_command's first argument (the
    redis command name); other coroutines have fixed return knobs."""

    def __init__(
        self,
        *,
        returns=None,
        raises=None,
        get_ret=None,
        exists_ret=1,
        scan_keys=(),
    ) -> None:
        self.calls: list[tuple] = []
        self.pipes: list[_Pipe] = []
        self.returns = dict(returns or {})
        self.raises = dict(raises or {})
        self.get_ret = get_ret
        self.exists_ret = exists_ret
        self.scan_keys = tuple(scan_keys)

    async def execute_command(self, *args, **kwargs):
        self.calls.append(("execute_command", args, kwargs))
        cmd = args[0] if args else None
        if cmd in self.raises:
            raise self.raises[cmd]
        return self.returns.get(cmd, "OK")

    async def expire(self, *args, **kwargs):
        self.calls.append(("expire", args, kwargs))
        return True

    async def setex(self, *args, **kwargs):
        self.calls.append(("setex", args, kwargs))
        return "OK"

    async def get(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return self.get_ret

    async def exists(self, *args, **kwargs):
        self.calls.append(("exists", args, kwargs))
        return self.exists_ret

    async def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))
        return 1

    def pipeline(self, *args, **kwargs):
        self.calls.append(("pipeline", args, kwargs))
        pipe = _Pipe()
        self.pipes.append(pipe)
        return pipe

    def scan_iter(self, *args, **kwargs):
        self.calls.append(("scan_iter", args, kwargs))
        keys = self.scan_keys

        async def _gen():
            for k in keys:
                yield k

        return _gen()

    def named(self, name: str) -> list[tuple]:
        return [(a, k) for n, a, k in self.calls if n == name]


class _Redis:
    def __init__(self, client) -> None:
        self._client = client


_MISS = object()


class _Spy(rj.BatchMetadataService):
    """Overrides the service's OWN get/set_batch_metadata so fallback-path
    delegation is asserted by EXACT positional forwarding."""

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.get_meta_calls: list = []
        self.set_meta_calls: list[tuple] = []
        self.meta_result = None
        self.meta_by_id: dict | None = None

    async def get_batch_metadata(self, batch_id):
        self.get_meta_calls.append(batch_id)
        if self.meta_by_id is not None:
            r = self.meta_by_id.get(batch_id, _MISS)
            if r is _MISS:
                return None
        else:
            r = self.meta_result
        if isinstance(r, BaseException):
            raise r
        return r

    async def set_batch_metadata(self, batch_id, metadata, ttl=None):
        self.set_meta_calls.append((batch_id, metadata, ttl))
        return True


def _svc(client, ttl=DEFAULT_TTL, json_available=None, spy=False):
    cls = _Spy if spy else rj.BatchMetadataService
    s = cls(redis_client=_Redis(client), default_ttl=ttl)
    if json_available is not None:
        s._json_available = json_available
    return s


def _full_meta(batch_id="B1", **over):
    m = rj.BatchMetadata(
        batch_id=batch_id,
        camera_id="CAM1",
        status="open",
        detection_ids=[7],
        detection_count=1,
        started_at=5.0,
        last_activity=6.0,
        closed_at=9.0,
        pipeline_start_time="PSTART",
        close_reason="manual",
        processing_metadata={"tag": "T"},
    )
    for k, v in over.items():
        setattr(m, k, v)
    return m


# ---------------------------------------------------------------------------
# disconnected client -- message EQUALITY on all eight guards (the *3 keys)
# ---------------------------------------------------------------------------
def test_disconnected_clients_raise_the_exact_message():
    svc = rj.BatchMetadataService(redis_client=_Redis(None))
    calls = [
        svc.set_batch_metadata("B1", {}),
        svc.get_batch_metadata("B1"),
        svc.get_batch_field("B1", "$.status"),
        svc.update_batch_field("B1", "$.status", "x"),
        svc.append_detection_id("B1", 5),
        svc.close_batch("B1"),
        svc.delete_batch_metadata("B1"),
        svc.get_open_batches_for_camera("CAM1"),
    ]
    for coro in calls:
        ok, exc = _attempt(coro)
        assert ok is False
        assert isinstance(exc, RuntimeError)
        assert str(exc) == NO_CONN, str(exc)


# ---------------------------------------------------------------------------
# get_batch_metadata_service singleton (survivors 1-10, 14, 15)
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _fresh_singleton():
    old, rj._batch_metadata_service = rj._batch_metadata_service, None
    try:
        yield
    finally:
        rj._batch_metadata_service = old


@contextlib.contextmanager
def _settings_stub(stub):
    old, rj.get_settings = rj.get_settings, (lambda: stub)
    try:
        yield
    finally:
        rj.get_settings = old


def test_singleton_uses_settings_ttl_and_hands_back_the_same_instance():
    client = _Client()
    with _fresh_singleton(), _settings_stub(SimpleNamespace(batch_metadata_ttl=1234)):
        ok, svc = _attempt(rj.get_batch_metadata_service(_Redis(client)))
        assert ok is True
        assert isinstance(svc, rj.BatchMetadataService)
        assert svc._redis._client is client  # kills redis_client -> None
        assert svc._default_ttl == 1234  # kills ttl None/drop/hasattr flips/XX key
        again_client = _Redis(_Client())
        ok2, again = _attempt(rj.get_batch_metadata_service(again_client))
        assert ok2 is True
        assert again is svc  # kills the inverted None check
        assert again._redis._client is not again_client
        assert rj._batch_metadata_service is svc


def test_singleton_falls_back_to_default_ttl_without_the_attribute():
    with _fresh_singleton(), _settings_stub(SimpleNamespace()):
        ok, svc = _attempt(rj.get_batch_metadata_service(_Redis(_Client())))
        assert ok is True
        assert svc._default_ttl == DEFAULT_TTL  # kills hasattr -> or True


# ---------------------------------------------------------------------------
# _check_json_available (survivors 4-26, 27-36, 39-54)
# ---------------------------------------------------------------------------
def test_check_json_available_probe_uses_exact_commands_and_logs_available():
    client = _Client()
    svc = _svc(client)
    with _capture_logs() as logs:
        ok, res = _attempt(svc._check_json_available())
        assert ok is True and res is True
        _assert_single(logs, INFO, MSG_AVAIL)
    assert client.calls == [
        ("execute_command", ("JSON.SET", "_test_json", "$", "{}"), {}),
        ("delete", ("_test_json",), {}),
    ]
    assert svc._json_available is True
    # cached: second call issues NO new commands and re-reports True
    with _capture_logs() as logs2:
        ok2, res2 = _attempt(svc._check_json_available())
        assert ok2 is True and res2 is True
        assert logs2.records == []
    assert len(client.calls) == 2


def test_check_json_available_unknown_command_takes_the_info_fallback():
    client = _Client(raises={"JSON.SET": RuntimeError("unknown command: JSON.SET")})
    svc = _svc(client)
    with _capture_logs() as logs:
        ok, res = _attempt(svc._check_json_available())
        assert ok is True and res is False
        # ATTRIBUTION: INFO fallback -- NOT the WARNING transient arm.
        _assert_single(logs, INFO, MSG_UNAVAIL)
    assert svc._json_available is False


def test_check_json_available_err_takes_the_info_fallback():
    client = _Client(raises={"JSON.SET": RuntimeError("ERR wrong number")})
    svc = _svc(client)
    with _capture_logs() as logs:
        ok, res = _attempt(svc._check_json_available())
        assert ok is True and res is False
        _assert_single(logs, INFO, MSG_UNAVAIL)  # attribution, not warning
    assert svc._json_available is False


def test_check_json_available_transient_error_warns_with_exact_error_attr():
    client = _Client(raises={"JSON.SET": ConnectionError("socket reset closed")})
    svc = _svc(client)
    with _capture_logs() as logs:
        ok, res = _attempt(svc._check_json_available())
        assert ok is True and res is False
        _assert_single(logs, WARNING, MSG_TRANSIENT, error="socket reset closed")
    assert svc._json_available is False


# ---------------------------------------------------------------------------
# BatchMetadata.from_dict (survivors 6-9, 17-20, 24-36, 58-75, 80, 82)
# ---------------------------------------------------------------------------
def test_from_dict_on_empty_payload_uses_the_pinned_clock_and_exact_defaults():
    with _clocked(1234.5):
        ok, m = _attempt(_coro_from_dict({}))
        assert ok is True
        assert m.batch_id == ""
        assert m.camera_id == ""
        assert m.status == "open"
        assert m.detection_ids == []
        assert m.detection_count == 0
        assert m.started_at == 1234.5  # clock, not real time / None / dropped
        assert m.last_activity == 1234.5
        assert m.closed_at is None
        assert m.pipeline_start_time is None
        assert m.close_reason is None
        assert m.processing_metadata == {}


async def _coro_from_dict(data):
    return rj.BatchMetadata.from_dict(data)


def test_from_dict_reads_present_keys_by_their_exact_names():
    data = {
        "batch_id": "B9",
        "camera_id": "CAM9",
        "started_at": 5.0,
        "last_activity": 6.0,
        "closed_at": 9.0,
        "pipeline_start_time": "PSTART",
        "processing_metadata": {"tag": "T"},
    }
    with _clocked(1234.5):
        ok, m = _attempt(_coro_from_dict(data))
        assert ok is True
        assert m.batch_id == "B9"
        assert m.camera_id == "CAM9"
        assert m.started_at == 5.0  # not clock-default / None / XX-keyed
        assert m.last_activity == 6.0
        assert m.closed_at == 9.0
        assert m.pipeline_start_time == "PSTART"
        assert m.processing_metadata == {"tag": "T"}


# ---------------------------------------------------------------------------
# set_batch_metadata (survivors 16-50, 53, 59-69)
# ---------------------------------------------------------------------------
def test_set_batch_metadata_json_arm_sends_exact_payload_and_ttl():
    client = _Client()
    svc = _svc(client, json_available=True)
    meta = _full_meta()
    with _capture_logs() as logs:
        ok, res = _attempt(svc.set_batch_metadata("B1", meta, ttl=77))
        assert ok is True and res is True
        _assert_single(logs, DEBUG, MSG_SET_JSON, batch_id="B1", key=KEY)
    assert client.calls == [
        ("execute_command", ("JSON.SET", KEY, "$", json.dumps(meta.to_dict())), {}),
        ("expire", (KEY, 77), {}),
    ]


def test_set_batch_metadata_json_arm_default_ttl_when_ttl_none():
    client = _Client()
    svc = _svc(client, json_available=True)
    ok, res = _attempt(svc.set_batch_metadata("B1", _full_meta().to_dict()))
    assert ok is True and res is True
    assert client.named("expire") == [((KEY, DEFAULT_TTL), {})]


def test_set_batch_metadata_json_failure_warns_then_uses_string_fallback():
    client = _Client(raises={"JSON.SET": RuntimeError("boom")})
    svc = _svc(client, json_available=True)
    meta = _full_meta()
    payload = json.dumps(meta.to_dict())
    with _capture_logs() as logs:
        ok, res = _attempt(svc.set_batch_metadata("B1", meta, ttl=77))
        assert ok is True and res is True
        assert len(logs.records) == 2
        _assert_record(logs.records[0], WARNING, MSG_SET_FAIL, error="boom")
        _assert_record(logs.records[1], DEBUG, MSG_SET_STR, batch_id="B1", key=KEY)
    assert client.named("setex") == [((KEY, 77, payload), {})]


def test_set_batch_metadata_string_arm_is_the_only_caller_of_setex():
    client = _Client()
    svc = _svc(client, json_available=False)
    meta = _full_meta()
    with _capture_logs() as logs:
        ok, res = _attempt(svc.set_batch_metadata("B1", meta))
        assert ok is True and res is True
        _assert_single(logs, DEBUG, MSG_SET_STR, batch_id="B1", key=KEY)
    assert client.calls == [
        ("setex", (KEY, DEFAULT_TTL, json.dumps(meta.to_dict())), {}),
    ]


# ---------------------------------------------------------------------------
# get_batch_metadata (survivors 6-14, 18-34)
# ---------------------------------------------------------------------------
def test_get_batch_metadata_json_arm_parses_the_whole_document():
    meta = _full_meta()
    client = _Client(returns={"JSON.GET": json.dumps(meta.to_dict())})
    svc = _svc(client, json_available=True)
    ok, got = _attempt(svc.get_batch_metadata("B1"))
    assert ok is True
    assert got == meta  # every present-key parsed by its exact name
    assert client.calls == [("execute_command", ("JSON.GET", KEY), {})]


def test_get_batch_metadata_string_arm_parses_the_document():
    meta = _full_meta()
    client = _Client(get_ret=json.dumps(meta.to_dict()))
    svc = _svc(client, json_available=False)
    ok, got = _attempt(svc.get_batch_metadata("B1"))
    assert ok is True and got == meta
    assert client.calls == [("get", (KEY,), {})]


def test_get_batch_metadata_missing_key_falls_back_with_no_warning():
    meta = _full_meta()
    client = _Client(
        raises={"JSON.GET": RuntimeError("no such key")},
        get_ret=json.dumps(meta.to_dict()),
    )
    svc = _svc(client, json_available=True)
    with _capture_logs() as logs:
        ok, got = _attempt(svc.get_batch_metadata("B1"))
        assert ok is True and got == meta
        assert logs.records == []  # classification: suppressed, not warned
    assert client.named("get") == [((KEY,), {})]


def test_get_batch_metadata_other_error_warns_and_falls_back():
    meta = _full_meta()
    client = _Client(
        raises={"JSON.GET": RuntimeError("connection reset")},
        get_ret=json.dumps(meta.to_dict()),
    )
    svc = _svc(client, json_available=True)
    with _capture_logs() as logs:
        ok, got = _attempt(svc.get_batch_metadata("B1"))
        assert ok is True and got == meta
        _assert_single(logs, WARNING, MSG_GET_FAIL, error="connection reset")
    assert client.named("get") == [((KEY,), {})]


# ---------------------------------------------------------------------------
# get_batch_field (survivors 6-16, 24, 28, 35)
# ---------------------------------------------------------------------------
def test_get_batch_field_json_arm_sends_exact_path_command():
    client = _Client(returns={"JSON.GET": '["closed"]'})
    svc = _svc(client, json_available=True)
    ok, got = _attempt(svc.get_batch_field("B1", "$.status"))
    assert ok is True and got == "closed"
    assert client.calls == [("execute_command", ("JSON.GET", KEY, "$.status"), {})]


def test_get_batch_field_fallback_walks_nested_paths_on_the_real_id():
    svc = _svc(_Client(), json_available=False, spy=True)
    svc.meta_by_id = {"B1": _full_meta()}
    ok, got = _attempt(svc.get_batch_field("B1", "$.processing_metadata.tag"))
    assert ok is True and got == "T"  # split(None)/split("XX.XX") return None
    assert svc.get_meta_calls == ["B1"]


# ---------------------------------------------------------------------------
# update_batch_field (survivors 6-9, 19-33, 42-70)
# ---------------------------------------------------------------------------
def test_update_batch_field_json_arm_sends_exact_partial_update():
    client = _Client()
    svc = _svc(client, json_available=True)
    with _capture_logs() as logs:
        ok, res = _attempt(svc.update_batch_field("B1", "$.detection_count", 42))
        assert ok is True and res is True
        _assert_single(logs, DEBUG, MSG_UPDATE_JSON, batch_id="B1", path="$.detection_count")
    assert client.calls == [
        ("execute_command", ("JSON.SET", KEY, "$.detection_count", "42"), {}),
        ("expire", (KEY, DEFAULT_TTL), {}),
    ]


def test_update_batch_field_json_arm_without_refresh_never_expires():
    client = _Client()
    svc = _svc(client, json_available=True)
    ok, res = _attempt(svc.update_batch_field("B1", "$.detection_count", 42, refresh_ttl=False))
    assert ok is True and res is True
    assert client.named("expire") == []


def test_update_batch_field_fallback_writes_field_and_default_ttl():
    svc = _svc(_Client(), json_available=False, spy=True)
    svc.meta_by_id = {"B1": _full_meta()}
    ok, res = _attempt(svc.update_batch_field("B1", "$.close_reason", "idle"))
    assert ok is True and res is True
    assert svc.get_meta_calls == ["B1"]
    assert len(svc.set_meta_calls) == 1
    batch_id, data, ttl = svc.set_meta_calls[0]
    assert batch_id == "B1"
    assert ttl == DEFAULT_TTL  # refresh-True polarity (kills and/or flips)
    assert data["close_reason"] == "idle"
    assert data["batch_id"] == "B1"


def test_update_batch_field_fallback_refresh_false_stores_ttl_none():
    svc = _svc(_Client(), json_available=False, spy=True)
    svc.meta_by_id = {"B1": _full_meta()}
    ok, res = _attempt(svc.update_batch_field("B1", "$.close_reason", "idle", refresh_ttl=False))
    assert ok is True and res is True
    batch_id, data, ttl = svc.set_meta_calls[0]
    assert batch_id == "B1" and ttl is None
    assert data["close_reason"] == "idle"


def test_update_batch_field_fallback_walks_nested_parent_path():
    svc = _svc(_Client(), json_available=False, spy=True)
    svc.meta_by_id = {"B1": _full_meta()}
    ok, res = _attempt(svc.update_batch_field("B1", "$.processing_metadata.tag", "NEW"))
    assert ok is True and res is True
    _, data, _ = svc.set_meta_calls[0]
    assert data["processing_metadata"] == {"tag": "NEW"}


def test_update_batch_field_fallback_on_missing_batch_returns_false():
    svc = _svc(_Client(), json_available=False, spy=True)
    svc.meta_by_id = {}
    ok, res = _attempt(svc.update_batch_field("B1", "$.close_reason", "idle"))
    assert ok is True and res is False
    assert svc.get_meta_calls == ["B1"]
    assert svc.set_meta_calls == []


# ---------------------------------------------------------------------------
# append_detection_id (survivors 6-61, 77-85)
# ---------------------------------------------------------------------------
def test_append_detection_id_json_arm_runs_the_exact_five_command_sequence():
    client = _Client(returns={"JSON.GET": "[3]"})
    svc = _svc(client, json_available=True)
    with _clocked(1234.5):
        ok, res = _attempt(svc.append_detection_id("B1", 99))
        assert ok is True and res == 3
    assert client.calls == [
        ("execute_command", ("JSON.ARRAPPEND", KEY, "$.detection_ids", "99"), {}),
        ("execute_command", ("JSON.NUMINCRBY", KEY, "$.detection_count", "1"), {}),
        ("execute_command", ("JSON.SET", KEY, "$.last_activity", "1234.5"), {}),
        ("expire", (KEY, DEFAULT_TTL), {}),
        ("execute_command", ("JSON.GET", KEY, "$.detection_count"), {}),
    ]


def test_append_detection_id_fallback_appends_recounts_and_resaves():
    meta = _full_meta(detection_ids=[7], detection_count=1)
    svc = _svc(_Client(), json_available=False, spy=True)
    svc.meta_by_id = {"B1": meta}
    with _clocked(1234.5):
        ok, res = _attempt(svc.append_detection_id("B1", 99))
        assert ok is True and res == 2
    assert svc.get_meta_calls == ["B1"]
    assert len(svc.set_meta_calls) == 1
    batch_id, saved, ttl = svc.set_meta_calls[0]
    assert batch_id == "B1" and ttl is None
    assert saved.detection_ids == [7, 99]
    assert saved.detection_count == 2
    assert saved.last_activity == 1234.5


def test_append_detection_id_fallback_on_missing_batch_returns_minus_one():
    svc = _svc(_Client(), json_available=False, spy=True)
    svc.meta_by_id = {}
    ok, res = _attempt(svc.append_detection_id("B1", 99))
    assert ok is True and res == -1
    assert svc.get_meta_calls == ["B1"]
    assert svc.set_meta_calls == []


# ---------------------------------------------------------------------------
# close_batch (survivors 6-14, 15-53, 54-64, 67, 75)
# ---------------------------------------------------------------------------
def test_close_batch_json_arm_pipelines_the_exact_three_sets():
    client = _Client()
    svc = _svc(client, json_available=True)
    with _clocked(999.25), _capture_logs() as logs:
        ok, res = _attempt(svc.close_batch("B1", "idle"))
        assert ok is True and res is True
        _assert_single(logs, DEBUG, MSG_CLOSE_JSON, batch_id="B1", reason="idle")
    assert client.calls[:2] == [
        ("exists", (KEY,), {}),
        ("pipeline", (), {"transaction": True}),
    ]
    assert client.pipes[0].cmds == [
        ("JSON.SET", KEY, "$.status", '"closed"'),
        ("JSON.SET", KEY, "$.closed_at", "999.25"),
        ("JSON.SET", KEY, "$.close_reason", '"idle"'),
    ]
    assert client.pipes[0].executes == 1
    assert len(client.pipes) == 1


def test_close_batch_json_arm_absent_key_returns_false_without_pipelining():
    client = _Client(exists_ret=0)
    svc = _svc(client, json_available=True)
    with _capture_logs() as logs:
        ok, res = _attempt(svc.close_batch("B1", "idle"))
        assert ok is True and res is False
        assert logs.records == []
    assert client.calls == [("exists", (KEY,), {})]
    assert client.pipes == []


def test_close_batch_fallback_sets_closed_state_and_stores():
    meta = _full_meta(status="open", closed_at=None, close_reason=None)
    svc = _svc(_Client(), json_available=False, spy=True)
    svc.meta_by_id = {"B1": meta}
    with _clocked(999.25):
        ok, res = _attempt(svc.close_batch("B1", "idle"))
        assert ok is True and res is True
    assert svc.get_meta_calls == ["B1"]
    batch_id, saved, ttl = svc.set_meta_calls[0]
    assert batch_id == "B1" and ttl is None
    assert saved.status == "closed"
    assert saved.closed_at == 999.25
    assert saved.close_reason == "idle"


def test_close_batch_fallback_on_missing_batch_returns_false():
    svc = _svc(_Client(), json_available=False, spy=True)
    svc.meta_by_id = {}
    ok, res = _attempt(svc.close_batch("B1"))
    assert ok is True and res is False
    assert svc.get_meta_calls == ["B1"]
    assert svc.set_meta_calls == []


# ---------------------------------------------------------------------------
# get_open_batches_for_camera (survivors 7-15, 20-41)
# ---------------------------------------------------------------------------
def test_open_batches_scan_matches_prefix_and_handles_both_key_types():
    m1 = _full_meta()
    m2 = _full_meta(batch_id="B2", camera_id="CAM2")
    client = _Client(scan_keys=(b"batch:meta:B1", "batch:meta:B2"))
    svc = _svc(client, json_available=False, spy=True)
    svc.meta_by_id = {"B1": m1, "B2": m2}
    with _capture_logs() as logs:
        ok, got = _attempt(svc.get_open_batches_for_camera("CAM1"))
        assert ok is True
        assert [m.batch_id for m in got] == ["B1"]
        assert logs.records == []  # str keys decode without hitting except
    assert svc.get_meta_calls == ["B1", "B2"]
    assert client.named("scan_iter") == [
        ((), {"match": "batch:meta:*", "count": 100}),
    ]


def test_open_batches_scan_logs_per_key_failures_with_exact_attrs():
    client = _Client(scan_keys=(b"batch:meta:B9",))
    svc = _svc(client, json_available=False, spy=True)
    svc.meta_by_id = {"B9": RuntimeError("boom")}
    with _capture_logs() as logs:
        ok, got = _attempt(svc.get_open_batches_for_camera("CAM1"))
        assert ok is True and got == []
        _assert_single(logs, DEBUG, MSG_SCAN_ERR, key=b"batch:meta:B9", error="boom")
    assert svc.get_meta_calls == ["B9"]
