# TARGET-MODULE: backend.services.gpu_config_service
"""Battery V — campaign #20 of the ladder (batch-38): kill-real coverage for
``backend/services/gpu_config_service.py`` (266 survivors at 52.9204% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, so every seam swap restores in ``finally``.

What kills what:
* YAML WHOLE-STRING — the three generators (``generate_override_content``,
  ``generate_assignments_content``, ``_build_override_content``) die to FULL
  STRING EQUALITY against plain-code mirrors (header + yaml.dump of a literal
  dict with the fixed kwargs), so ``default_flow_style``/``sort_keys`` value
  and deletion flips, key NAME/CASE flips (``driver``/``device_ids``/
  ``capabilities``/``environment``/``services``), ``str(None)`` values, the
  XX/upper string flips and the header flip all bite. The clock is a fake
  ``datetime`` whose ``now(None)`` RAISES — killing every
  ``datetime.now(UTC) -> now(None)`` key in ``apply_gpu_config``,
  ``generate_assignments_content`` and ``_build_override_content`` (stamping
  the mirrors deterministically).
* DATACLASS ROUND-TRIPS — ``GpuAssignment.__post_init__`` dies to whole
  ``to_dict()`` equality under three polarities (override-only, limit-only,
  BOTH set — the BOTH-set polarity kills the ``is None -> is not None`` gate
  flips that silently OVERWRITE an explicit limit); ``GpuAssignment.to_dict``
  / ``ApplyResult.to_dict`` / ``ServiceRestartStatus.from_dict`` /
  ``_result_from_dict`` die to whole-dict equality under a PRESENT polarity
  (every field populated: name-flips, ``=None`` kwargs, arg-DELETION kwargs,
  ``.get`` name-flips) plus an ABSENT polarity (``completed_at``/
  ``service_statuses``/``changed_services`` missing — the trailing-comma
  ``.get(k, )`` arg-deletion turns the ``{}``/``[]`` default into ``None``
  which then CRASHES ``.items()`` or leaks ``None`` through ``to_dict``;
  ``_result_from_dict`` m5's ``completed_at = ""`` is caught by an
  ``is None`` attribute polarity).
* LOG RECORDS — a fake logger recording ``(level, msg, kwargs)`` compared as
  a WHOLE LIST: ``__init__`` (msg family, ``extra=None``, extra-deletion and
  the full ``extra`` dict: name/case flips, ``str(None)`` values, the
  ``redis_enabled is None`` polarity), ``write_config_files`` (4 records),
  ``_generate_override_file``, ``get_container_status`` (no-client warning +
  exception-arm warning), ``apply_gpu_config`` (no-changes info, changes
  info, ``exc_info`` True/None/False/deleted on the error arm) and
  ``_recreate_service`` (enter info, no-compose error, timeout error,
  success/``returncode: 1`` flip, failure records — with 600-char non-
  repeating stdout/stderr so ``[:500] -> [:501]`` bites).
* REDIS SPY — ``_persist_operation_status`` pins the WHOLE
  ``((key, payload), {"expire": 3600})`` call tuple (key ``None``/deletion,
  payload ``None``/deletion, expire ``None``/deletion all diverge), and
  ``apply_gpu_config`` is adjudicated by the FULL persist SEQUENCE against a
  plain-code mirror (initial PENDING -> RESTARTING+started -> RUNNING/FAILED
  +completed -> final), which kills the ``=None`` status/started/completed/
  error assignments that the final ``to_dict`` cannot see.
  ``get_operation_status`` pins the ``redis.get`` KEY arg.
* COMPOSE SUBPROCESS — a fake ``asyncio`` (``create_subprocess_exec`` spy
  with whole ``(args, kwargs)`` equality — the full cmd list, ``PIPE``/
  ``DEVNULL`` sentinels, ``cwd=str(root)`` — plus ``wait_for`` recording the
  timeout value and a timeout arm that closes the coroutine and raises
  ``TimeoutError``, pinning ``process.kill``/``wait``): kills the
  ``-f``/``up``/``-d``/``--force-recreate``/``--no-deps`` XX/case flips,
  ``str(None)`` paths, ``stdout=None``, ``cwd=None``/deletion/``str(None)``,
  ``timeout=None``; ``_get_compose_command`` dies to (return value, whole
  probe-call list) under three availability scenarios (podman works / only
  the two-part ``docker compose`` works / docker-compose works — the
  ``continue -> break``, ``" " in -> not in`` and third-entry flips need the
  right scenario), plus the ``logger.debug(None)`` record.

Honesty ledger — dispositions registered EQUIVALENT (the sweep must show
GREEN on exactly these; anything else GREEN is a test gap). Each is a BODY
proof, not a diff shape. PyYAML behavior measured THIS session against the
installed package:

* generate_override_content m37 / generate_assignments_content m20 /
  _build_override_content m41 — ``sort_keys=False`` -> ``sort_keys=None``:
  PyYAML tests the flag truthily, ``bool(None) == bool(False)``, dumps byte-
  identical (measured equal to the reference dump).
* generate_override_content m39 / generate_assignments_content m22 /
  _build_override_content m43 — the ``default_flow_style=False`` ARG
  DELETION: PyYAML's own default for the parameter is False — measured
  identical to the reference dump.
* get_container_status m8 — ``dict.fromkeys(service_names, None)`` with the
  ``None`` arg DELETED (trailing comma): ``fromkeys``' own default value is
  None, the dicts are equal. (NOT the getattr raise family — the default is
  a plain None.)
* apply_gpu_config m48 — the ``status=RestartStatus.PENDING`` kwarg DELETION
  at the ``ServiceRestartStatus(...)`` construction: the dataclass field's
  default is exactly ``RestartStatus.PENDING`` — reconstructed identical.

(_result_from_dict m5 ``completed_at = ""`` was initially a ledger candidate
but is NOT equivalent: ``.completed_at`` is observable to any caller that
reads the attribute (contract ``datetime | None``) — killed here by an
``is None`` polarity on the absent-completed_at payload. ApplyResult.to_dict
m10 ``or True`` likewise stays KILLABLE: completed_at=None makes
``None.isoformat()`` RAISE while the orig yields None.)

All other survivor keys have an explicit kill polarity in this battery.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from backend.services.gpu_config_service import (
    ApplyResult,
    GpuAssignment,
    GpuConfigService,
    RestartStatus,
    ServiceRestartStatus,
)

_OP = "op-fixed"
_STAMP = "2026-06-15T10:00:00+00:00"
_NOW = datetime.fromisoformat(_STAMP)
_SVC_A = "ai-llm"
_SVC_B = "ai-enrich"
_KEY = f"gpu_config:operation:{_OP}"


def _globals_of(fn: Any) -> dict[str, Any]:
    """Module globals of the REAL function (mutant-tree wrappers delegate)."""
    f = fn
    while hasattr(f, "__wrapped__"):
        f = f.__wrapped__
    return f.__globals__


_G = _globals_of(GpuConfigService.apply_gpu_config)


def _swap(key: str, value: Any) -> Any:
    old = _G[key]

    def restore() -> None:
        _G[key] = old

    _G[key] = value
    return restore


class _Env:
    """A bundle of seam swaps with one finally-friendly close()."""

    def __init__(self, swappers: list[Any]) -> None:
        self._swappers = swappers

    def close(self) -> None:
        for s in reversed(self._swappers):
            s()


class _Obj:
    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class _Logger:
    def __init__(self) -> None:
        self.records: list[Any] = []

    def info(self, msg: Any = None, **kw: Any) -> None:
        self.records.append(("info", msg, kw))

    def debug(self, msg: Any = None, **kw: Any) -> None:
        self.records.append(("debug", msg, kw))

    def warning(self, msg: Any = None, **kw: Any) -> None:
        self.records.append(("warning", msg, kw))

    def error(self, msg: Any = None, **kw: Any) -> None:
        self.records.append(("error", msg, kw))


class _FixedNow:
    """Fake module ``datetime``: now(UTC) fixed, now(None) RAISES."""

    @staticmethod
    def now(tz: Any) -> Any:
        if tz is None:
            raise RuntimeError("naive now")
        return _NOW

    @staticmethod
    def fromisoformat(value: Any) -> Any:
        return datetime.fromisoformat(value)


class _Proc:
    def __init__(self, rc: int, out: bytes, err: bytes) -> None:
        self.returncode = rc
        self._out = out
        self._err = err
        self.kills = 0
        self.waits = 0

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._out, self._err

    def kill(self) -> None:
        self.kills += 1

    async def wait(self) -> int:
        self.waits += 1
        return self.returncode


class _FakeAsyncio:
    """Fake module ``asyncio``: exec spy + wait_for with timeout arm."""

    def __init__(
        self,
        exists: Any = None,
        *,
        timeout: bool = False,
        rc: int = 0,
        out: str = "ok",
        err: str = "bad",
    ) -> None:
        self.exec_calls: list[Any] = []
        self.wait_args: list[Any] = []
        self.procs: list[_Proc] = []
        self._exists = exists
        self._timeout = timeout
        self._rc = rc
        self._out = out
        self._err = err
        self.subprocess = _Obj(PIPE="PIPE", DEVNULL="DEVNULL")

    async def create_subprocess_exec(self, *args: Any, **kwargs: Any) -> _Proc:
        self.exec_calls.append((args, kwargs))
        if self._exists is not None and not self._exists(args):
            raise FileNotFoundError(repr(args[0]))
        # a --version probe succeeds (rc 0) iff the binary "exists" (not
        # raised above); the real up command returns self._rc.
        rc = 0 if "--version" in args else self._rc
        p = _Proc(rc, self._out.encode(), self._err.encode())
        self.procs.append(p)
        return p

    async def wait_for(self, coro: Any, timeout: Any = None) -> Any:
        self.wait_args.append(timeout)
        if self._timeout:
            coro.close()
            raise TimeoutError
        return await coro


class _Redis:
    def __init__(self, data: Any = None) -> None:
        self.gets: list[Any] = []
        self.sets: list[Any] = []
        self._data = data

    async def get(self, key: Any) -> Any:
        self.gets.append(key)
        return self._data

    async def set(self, *args: Any, **kwargs: Any) -> None:
        self.sets.append((args, kwargs))


class _Docker:
    def __init__(self, missing: bool = False, raises: bool = False) -> None:
        self.by_name: list[Any] = []
        self.status_args: list[Any] = []
        self._missing = missing
        self._raises = raises

    async def get_container_by_name(self, name: Any) -> Any:
        self.by_name.append(name)
        if self._raises:
            raise RuntimeError("docker down")
        if self._missing:
            return None
        return _Obj(id=f"id-{name}")

    async def get_container_status(self, cid: Any) -> Any:
        self.status_args.append(cid)
        return "running"


def _tmp() -> str:
    return tempfile.mkdtemp()


def _svc(
    tmp: str,
    *,
    redis: Any = None,
    docker: Any = None,
    compose_file_path: Any = None,
    config_dir: Any = None,
) -> GpuConfigService:
    return GpuConfigService(
        redis_client=redis,
        docker_client=docker,
        compose_file_path=compose_file_path,
        project_root=tmp,
        config_dir=Path(tmp) / "cfg" if config_dir is None else config_dir,
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _st(
    name: str, status: str, started: Any = None, completed: Any = None, error: Any = None
) -> dict:
    return {
        "service_name": name,
        "status": status,
        "started_at": started,
        "completed_at": completed,
        "error": error,
    }


def _payload(
    success: bool,
    statuses: dict,
    changed: list,
    completed: Any = None,
    error: Any = None,
) -> dict:
    return {
        "success": success,
        "operation_id": _OP,
        "started_at": _STAMP,
        "completed_at": completed,
        "changed_services": changed,
        "service_statuses": statuses,
        "error": error,
    }


# --- GpuAssignment.__post_init__ (8) + to_dict (2) --------------------------


def test_post_init_override_only() -> None:
    a = GpuAssignment("ai-llm", 0, vram_budget_override=2.0)
    assert a.to_dict() == {
        "service_name": "ai-llm",
        "gpu_index": 0,
        "vram_limit_mb": 2048,
        "vram_budget_override": 2.0,
    }


def test_post_init_limit_only() -> None:
    a = GpuAssignment("ai-llm", 1, vram_limit_mb=1024)
    assert a.to_dict() == {
        "service_name": "ai-llm",
        "gpu_index": 1,
        "vram_limit_mb": 1024,
        "vram_budget_override": 1.0,
    }


def test_post_init_both_set_keeps_explicit() -> None:
    a = GpuAssignment("ai-llm", 0, vram_limit_mb=1024, vram_budget_override=2.0)
    assert a.to_dict() == {
        "service_name": "ai-llm",
        "gpu_index": 0,
        "vram_limit_mb": 1024,
        "vram_budget_override": 2.0,
    }


def test_post_init_neither_set() -> None:
    a = GpuAssignment("ai-llm", 2)
    assert a.to_dict() == {
        "service_name": "ai-llm",
        "gpu_index": 2,
        "vram_limit_mb": None,
        "vram_budget_override": None,
    }


def test_gpu_assignment_to_dict_names() -> None:
    a = GpuAssignment("ai-llm", 3, vram_limit_mb=512)
    assert sorted(a.to_dict()) == [
        "gpu_index",
        "service_name",
        "vram_budget_override",
        "vram_limit_mb",
    ]
    assert a.to_dict()["vram_limit_mb"] == 512


# --- ApplyResult.to_dict (1) + ServiceRestartStatus.from_dict (10) ----------


def test_apply_result_to_dict_full_and_falsy() -> None:
    r = ApplyResult(
        success=True,
        operation_id=_OP,
        started_at=_NOW,
        changed_services=[_SVC_A],
        service_statuses={_SVC_A: ServiceRestartStatus(_SVC_A, RestartStatus.RUNNING, _NOW, _NOW)},
        error=None,
    )
    assert r.to_dict() == {
        "success": True,
        "operation_id": _OP,
        "started_at": _STAMP,
        "completed_at": None,
        "changed_services": [_SVC_A],
        "service_statuses": {
            _SVC_A: {
                "service_name": _SVC_A,
                "status": "running",
                "started_at": _STAMP,
                "completed_at": _STAMP,
                "error": None,
            }
        },
        "error": None,
    }
    r.completed_at = _NOW
    assert r.to_dict()["completed_at"] == _STAMP


def _restart_payload() -> dict:
    return {
        "service_name": _SVC_A,
        "status": "restarting",
        "started_at": _STAMP,
        "completed_at": _STAMP,
        "error": "boom",
    }


def test_restart_from_dict_present_polarity() -> None:
    p = _restart_payload()
    s = ServiceRestartStatus.from_dict(p)
    assert s.to_dict() == p
    assert s.started_at == _NOW and s.completed_at == _NOW


def test_restart_from_dict_absent_polarity() -> None:
    p = {
        "service_name": _SVC_A,
        "status": "pending",
        "started_at": None,
        "completed_at": None,
        "error": None,
    }
    s = ServiceRestartStatus.from_dict(p)
    assert s.to_dict() == p
    assert s.completed_at is None and s.error is None


# --- _result_from_dict (29) --------------------------------------------------


def _result_payload() -> dict:
    return {
        "success": True,
        "operation_id": _OP,
        "started_at": _STAMP,
        "completed_at": _STAMP,
        "changed_services": [_SVC_A],
        "service_statuses": {_SVC_A: _restart_payload()},
        "error": "e1",
    }


def test_result_from_dict_present_polarity() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        env = _Env([_swap("logger", log)])
        try:
            s = _svc(tmp)
            p = _result_payload()
            r = s._result_from_dict(p)
            assert r.to_dict() == p
            assert r.started_at == _NOW and r.completed_at == _NOW
        finally:
            env.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_result_from_dict_absent_polarity() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        env = _Env([_swap("logger", log)])
        try:
            s = _svc(tmp)
            # KEYS OMITTED (not null): this polarity exercises the
            # .get-default family (m15/m17/m39/m41 arg-deletions turn the
            # {} / [] defaults into None).
            p = {"success": False, "operation_id": _OP, "started_at": _STAMP}
            r = s._result_from_dict(p)
            assert r.completed_at is None
            assert r.changed_services == []
            assert r.service_statuses == {}
            assert r.error is None
        finally:
            env.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- generate_override_content (2 killable + 1 ledgered EQUIV) --------------


def _expected_override_yaml(assignments: list[GpuAssignment]) -> str:
    services: dict = {}
    for a in assignments:
        cfg: dict = {
            "deploy": {
                "resources": {
                    "reservations": {
                        "devices": [
                            {
                                "driver": "nvidia",
                                "device_ids": [str(a.gpu_index)],
                                "capabilities": ["gpu"],
                            }
                        ]
                    }
                }
            }
        }
        if a.vram_budget_override is not None:
            cfg["environment"] = [f"VRAM_BUDGET_GB={a.vram_budget_override}"]
        services[a.service_name] = cfg
    return "# Auto-generated by GPU Config Service - DO NOT EDIT MANUALLY\n" + yaml.dump(
        {"services": services}, default_flow_style=False, sort_keys=False
    )


def _gen_assigns() -> list[GpuAssignment]:
    return [GpuAssignment(_SVC_A, 0, vram_limit_mb=2048), GpuAssignment(_SVC_B, 1)]


def test_generate_override_content_full_string() -> None:
    tmp = _tmp()
    try:
        s = _svc(tmp)
        a = _gen_assigns()
        assert s.generate_override_content(a) == _expected_override_yaml(a)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- generate_assignments_content (4 killable + 1 ledgered EQUIV) -----------


def _expected_assignments_yaml(assignments: list[GpuAssignment], strategy: str) -> str:
    data = {
        "generated_at": _STAMP,
        "strategy": strategy,
        "assignments": {
            a.service_name: {"gpu": a.gpu_index, "vram_budget": a.vram_budget_override}
            for a in assignments
        },
    }
    return "# Auto-generated - for reference only\n" + yaml.dump(
        data, default_flow_style=False, sort_keys=False
    )


def test_generate_assignments_content_full_string() -> None:
    tmp = _tmp()
    try:
        s = _svc(tmp)
        a = _gen_assigns()
        env = _Env([_swap("datetime", _FixedNow)])
        try:
            assert s.generate_assignments_content(a, "vram_based") == _expected_assignments_yaml(
                a, "vram_based"
            )
        finally:
            env.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- write_config_files (4) ---------------------------------------------------


def test_write_config_files_records_paths_and_files() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        s = _svc(tmp)
        env = _Env([_swap("logger", log), _swap("datetime", _FixedNow)])
        try:
            a = _gen_assigns()
            ov, af = _run(s.write_config_files(a, "manual"))
            assert (ov, af) == (s.override_file, s.assignments_file)
            assert log.records == [
                (
                    "info",
                    f"Writing GPU config files: strategy=manual, assignments={len(a)}",
                    {},
                ),
                ("debug", f"Wrote override file: {ov}", {}),
                ("debug", f"Wrote assignments file: {af}", {}),
                ("info", f"GPU config files written successfully: {ov}, {af}", {}),
            ]
            assert ov.read_text() == _expected_override_yaml(a)
            assert af.read_text() == _expected_assignments_yaml(a, "manual")
        finally:
            env.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- _build_override_content (17 killable + 2 ledgered EQUIV) ----------------


def _expected_build_yaml(assignments: dict, stamp: str = _STAMP) -> str:
    services: dict = {}
    for name, a in assignments.items():
        cfg: dict = {"environment": [f"NVIDIA_VISIBLE_DEVICES={a.gpu_index}"]}
        if a.vram_limit_mb is not None:
            cfg["deploy"] = {
                "resources": {
                    "reservations": {
                        "devices": [
                            {
                                "driver": "nvidia",
                                "device_ids": [str(a.gpu_index)],
                                "capabilities": ["gpu"],
                            }
                        ]
                    }
                }
            }
        services[name] = cfg
    header = (
        "# GPU Configuration Override\n"
        "# Generated by GpuConfigService\n"
        f"# Generated at: {stamp}\n"
        "#\n"
        "# This file is auto-generated. Do not edit manually.\n"
        "#\n"
    )
    doc = {"version": "3.8", "services": services}
    return header + yaml.dump(doc, default_flow_style=False, sort_keys=False)


def test_build_override_content_full_string() -> None:
    tmp = _tmp()
    try:
        s = _svc(tmp)
        assigns = {
            _SVC_A: GpuAssignment(_SVC_A, 0, vram_limit_mb=4096),
            _SVC_B: GpuAssignment(_SVC_B, 1),
        }
        env = _Env([_swap("datetime", _FixedNow)])
        try:
            assert s._build_override_content(assigns) == _expected_build_yaml(assigns)
        finally:
            env.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- _generate_override_file (5) ----------------------------------------------


def test_generate_override_file_writes_and_logs() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        s = _svc(tmp)
        env = _Env([_swap("logger", log), _swap("datetime", _FixedNow)])
        try:
            assigns = {_SVC_A: GpuAssignment(_SVC_A, 0, vram_limit_mb=4096)}
            _run(s._generate_override_file(assigns))
            assert log.records == [
                (
                    "info",
                    f"Generated GPU override file: {s._override_file}",
                    {"extra": {"services": [_SVC_A]}},
                )
            ]
            assert s._override_file.read_text() == _expected_build_yaml(assigns)
        finally:
            env.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- __init__ log record (20) -------------------------------------------------


def test_init_log_record_with_redis() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        env = _Env([_swap("logger", log)])
        try:
            s = GpuConfigService(
                redis_client=_Redis(),
                project_root=tmp,
                compose_file_path=Path(tmp) / "custom-compose.yml",
                config_dir=Path(tmp) / "cfg2",
            )
        finally:
            env.close()
        assert log.records == [
            (
                "info",
                "GpuConfigService initialized",
                {
                    "extra": {
                        "compose_file": str(Path(tmp) / "custom-compose.yml"),
                        "override_file": str(Path(tmp) / "docker-compose.gpu-override.yml"),
                        "config_dir": str(Path(tmp) / "cfg2"),
                        "redis_enabled": True,
                    }
                },
            )
        ]
        assert s._compose_file == Path(tmp) / "custom-compose.yml"
        assert s.override_file == Path(tmp) / "cfg2" / "docker-compose.gpu-override.yml"
        assert s.assignments_file == Path(tmp) / "cfg2" / "gpu-assignments.yml"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_init_log_record_defaults_no_redis() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        env = _Env([_swap("logger", log)])
        try:
            s = GpuConfigService(project_root=tmp)
        finally:
            env.close()
        assert log.records == [
            (
                "info",
                "GpuConfigService initialized",
                {
                    "extra": {
                        "compose_file": str(Path(tmp) / "docker-compose.prod.yml"),
                        "override_file": str(Path(tmp) / "docker-compose.gpu-override.yml"),
                        "config_dir": "config",
                        "redis_enabled": False,
                    }
                },
            )
        ]
        assert s._compose_file == Path(tmp) / "docker-compose.prod.yml"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- get_container_status (11 killable + 1 ledgered EQUIV) --------------------


def test_container_status_no_client() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        s = _svc(tmp)
        env = _Env([_swap("logger", log)])
        try:
            got = _run(s.get_container_status([_SVC_A, _SVC_B]))
        finally:
            env.close()
        assert got == {_SVC_A: None, _SVC_B: None}
        assert log.records == [
            ("warning", "Docker client not available for container status check", {})
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_container_status_found_and_missing() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        dc = _Docker()
        s = _svc(tmp, docker=dc)
        env = _Env([_swap("logger", log)])
        try:
            got = _run(s.get_container_status([_SVC_A]))
        finally:
            env.close()
        assert got == {_SVC_A: "running"}
        assert dc.by_name == [_SVC_A]
        assert dc.status_args == [f"id-{_SVC_A}"]
        assert log.records == []
        dc2 = _Docker(missing=True)
        s._docker_client = dc2  # type: ignore[method-assign]
        assert _run(s.get_container_status([_SVC_B])) == {_SVC_B: None}
        assert dc2.by_name == [_SVC_B]
        assert dc2.status_args == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_container_status_exception_arm() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        s = _svc(tmp, docker=_Docker(raises=True))
        env = _Env([_swap("logger", log)])
        try:
            got = _run(s.get_container_status([_SVC_A]))
        finally:
            env.close()
        assert got == {_SVC_A: None}
        assert log.records == [
            (
                "warning",
                f"Failed to get container status for {_SVC_A}: docker down",
                {"extra": {"service_name": _SVC_A}},
            )
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- get_operation_status (2) + _persist_operation_status (7) -----------------


def test_get_operation_status_pins_redis_key() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        r = _Redis(data=_result_payload())
        s = _svc(tmp, redis=r)
        env = _Env([_swap("logger", log)])
        try:
            got = _run(s.get_operation_status(_OP))
        finally:
            env.close()
        assert r.gets == [_KEY]
        assert got is not None and got.to_dict() == _result_payload()
        r2 = _Redis(data=None)
        s._redis = r2  # type: ignore[method-assign]
        assert _run(s.get_operation_status(_OP)) is None
        assert r2.gets == [_KEY]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _persist_result() -> ApplyResult:
    return ApplyResult(
        success=True,
        operation_id=_OP,
        started_at=_NOW,
        changed_services=[_SVC_A],
        service_statuses={_SVC_A: ServiceRestartStatus(_SVC_A, RestartStatus.RUNNING, _NOW)},
        error=None,
    )


def test_persist_operation_status_whole_call() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        r = _Redis()
        s = _svc(tmp, redis=r)
        env = _Env([_swap("logger", log)])
        try:
            res = _persist_result()
            _run(s._persist_operation_status(res))
        finally:
            env.close()
        assert r.sets == [((_KEY, res.to_dict()), {"expire": 3600})]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- _get_compose_command (23 killable) ----------------------------------------


def test_compose_command_podman_ok() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        s = _svc(tmp)
        fa = _FakeAsyncio(exists=lambda args: args[0] == "podman-compose")
        env = _Env([_swap("logger", log), _swap("asyncio", fa)])
        try:
            got = _run(s._get_compose_command())
        finally:
            env.close()
        assert got == "podman-compose"
        assert fa.exec_calls == [
            (("podman-compose", "--version"), {"stdout": "DEVNULL", "stderr": "DEVNULL"})
        ]
        assert log.records == [("debug", "Using compose command: podman-compose", {})]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_compose_command_two_word_only() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        s = _svc(tmp)
        fa = _FakeAsyncio(exists=lambda args: args[0] == "docker")
        env = _Env([_swap("logger", log), _swap("asyncio", fa)])
        try:
            got = _run(s._get_compose_command())
        finally:
            env.close()
        assert got == "docker compose"
        assert fa.exec_calls == [
            (("podman-compose", "--version"), {"stdout": "DEVNULL", "stderr": "DEVNULL"}),
            (("docker-compose", "--version"), {"stdout": "DEVNULL", "stderr": "DEVNULL"}),
            (("docker", "compose", "--version"), {"stdout": "DEVNULL", "stderr": "DEVNULL"}),
        ]
        assert log.records == [("debug", "Using compose command: docker compose", {})]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_compose_command_none_available() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        s = _svc(tmp)
        fa = _FakeAsyncio(exists=lambda _args: False)
        env = _Env([_swap("logger", log), _swap("asyncio", fa)])
        try:
            got = _run(s._get_compose_command())
        finally:
            env.close()
        assert got is None
        assert len(fa.exec_calls) == 3
        assert log.records == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- _recreate_service (56 killable) -------------------------------------------


def _recreate_env(tmp: str, fa: _FakeAsyncio, log: _Logger) -> tuple:
    s = _svc(
        tmp,
        compose_file_path=Path(tmp) / "prod.yml",
    )
    env = _Env([_swap("logger", log), _swap("asyncio", fa)])
    return s, env


_LONG_OUT = "".join(f"s{i}" for i in range(300))
_LONG_ERR = "".join(f"e{i}" for i in range(300))


def test_recreate_service_no_compose_found() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        fa = _FakeAsyncio(exists=lambda _args: False)
        s, env = _recreate_env(tmp, fa, log)
        try:
            ok = _run(s._recreate_service(_SVC_A))
        finally:
            env.close()
        assert ok is False
        assert log.records == [
            (
                "info",
                f"Restarting service via compose: {_SVC_A}",
                {"extra": {"service_name": _SVC_A}},
            ),
            ("error", "Neither podman-compose nor docker-compose found", {}),
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_recreate_service_success_whole_call() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        fa = _FakeAsyncio(exists=lambda args: args[0] == "podman-compose", out=_LONG_OUT)
        s, env = _recreate_env(tmp, fa, log)
        try:
            ok = _run(s._recreate_service(_SVC_A))
        finally:
            env.close()
        assert ok is True
        assert fa.exec_calls[-1] == (
            (
                "podman-compose",
                "-f",
                str(Path(tmp) / "prod.yml"),
                "-f",
                str(Path(tmp) / "docker-compose.gpu-override.yml"),
                "up",
                "-d",
                "--force-recreate",
                "--no-deps",
                _SVC_A,
            ),
            {"stdout": "PIPE", "stderr": "PIPE", "cwd": tmp},
        )
        assert fa.wait_args == [120.0]
        assert log.records == [
            (
                "info",
                f"Restarting service via compose: {_SVC_A}",
                {"extra": {"service_name": _SVC_A}},
            ),
            ("debug", "Using compose command: podman-compose", {}),
            (
                "info",
                f"Successfully restarted {_SVC_A}",
                {
                    "extra": {
                        "service_name": _SVC_A,
                        "returncode": 0,
                        "stdout": _LONG_OUT[:500],
                    }
                },
            ),
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_recreate_service_failure_rc() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        fa = _FakeAsyncio(exists=lambda args: args[0] == "podman-compose", rc=7, err=_LONG_ERR)
        s, env = _recreate_env(tmp, fa, log)
        try:
            ok = _run(s._recreate_service(_SVC_A))
        finally:
            env.close()
        assert ok is False
        assert log.records == [
            (
                "info",
                f"Restarting service via compose: {_SVC_A}",
                {"extra": {"service_name": _SVC_A}},
            ),
            ("debug", "Using compose command: podman-compose", {}),
            (
                "error",
                f"Failed to restart {_SVC_A}: exit code 7",
                {
                    "extra": {
                        "service_name": _SVC_A,
                        "returncode": 7,
                        "stderr": _LONG_ERR[:500],
                    }
                },
            ),
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_recreate_service_timeout_arm() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        fa = _FakeAsyncio(exists=lambda args: args[0] == "podman-compose", timeout=True)
        s, env = _recreate_env(tmp, fa, log)
        try:
            ok = _run(s._recreate_service(_SVC_A))
        finally:
            env.close()
        assert ok is False
        assert fa.procs[-1].kills == 1 and fa.procs[-1].waits == 1
        assert log.records == [
            (
                "info",
                f"Restarting service via compose: {_SVC_A}",
                {"extra": {"service_name": _SVC_A}},
            ),
            ("debug", "Using compose command: podman-compose", {}),
            (
                "error",
                f"Compose command timed out for {_SVC_A}",
                {"extra": {"service_name": _SVC_A, "timeout": 120.0}},
            ),
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_recreate_service_exec_filenotfound_arm() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        fa = _FakeAsyncio(exists=lambda args: "--version" in args)
        s, env = _recreate_env(tmp, fa, log)
        try:
            ok = _run(s._recreate_service(_SVC_A))
        finally:
            env.close()
        assert ok is False
        assert log.records == [
            (
                "info",
                f"Restarting service via compose: {_SVC_A}",
                {"extra": {"service_name": _SVC_A}},
            ),
            ("debug", "Using compose command: podman-compose", {}),
            (
                "error",
                "Compose command not found: podman-compose",
                {"extra": {"compose_cmd": "podman-compose"}},
            ),
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- apply_gpu_config (39 killable + 1 ledgered EQUIV) ------------------------


def _apply_svc(tmp: str, redis: Any, recreate_ok: bool, calls: list) -> GpuConfigService:
    s = _svc(tmp, redis=redis)

    async def _rc(name: Any) -> bool:
        calls.append(name)
        return recreate_ok

    s._recreate_service = _rc  # type: ignore[method-assign]
    s.set_current_assignments({_SVC_A: GpuAssignment(_SVC_A, 0, vram_limit_mb=2048)})
    return s


def _st_payload(status: str, started: Any = None, completed: Any = None, error: Any = None) -> dict:
    return {_SVC_A: _st(_SVC_A, status, started, completed, error)}


def _seq_payload(
    oid: str, success: bool, statuses: dict, completed: Any = None, error: Any = None
) -> dict:
    return {
        "success": success,
        "operation_id": oid,
        "started_at": _STAMP,
        "completed_at": completed,
        "changed_services": [_SVC_A],
        "service_statuses": statuses,
        "error": error,
    }


def test_apply_gpu_config_no_changes() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        r = _Redis()
        s = _svc(tmp, redis=r)
        s.set_current_assignments({_SVC_A: GpuAssignment(_SVC_A, 0, vram_limit_mb=2048)})
        calls: list = []
        env = _Env([_swap("logger", log), _swap("datetime", _FixedNow)])
        try:
            res = _run(s.apply_gpu_config({_SVC_A: GpuAssignment(_SVC_A, 0, vram_limit_mb=2048)}))
        finally:
            env.close()
        assert res.success is True
        assert res.changed_services == []
        assert res.started_at == _NOW
        assert res.completed_at == _NOW
        assert log.records == [
            (
                "info",
                "No GPU configuration changes detected",
                {"extra": {"operation_id": res.operation_id}},
            )
        ]
        assert r.sets == []
        assert calls == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_apply_gpu_config_success_sequence() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        r = _Redis()
        calls: list = []
        s = _apply_svc(tmp, r, True, calls)
        env = _Env([_swap("logger", log), _swap("datetime", _FixedNow)])
        try:
            res = _run(s.apply_gpu_config({_SVC_A: GpuAssignment(_SVC_A, 1, vram_limit_mb=2048)}))
        finally:
            env.close()
        oid = res.operation_id
        key = f"gpu_config:operation:{oid}"
        assert res.success is True
        assert res.changed_services == [_SVC_A]
        assert res.completed_at == _NOW
        assert res.error is None
        st = res.service_statuses[_SVC_A]
        assert st.status is RestartStatus.RUNNING
        assert st.started_at == _NOW and st.completed_at == _NOW
        assert st.error is None
        assert calls == [_SVC_A]
        assert s.get_current_assignments() == {_SVC_A: GpuAssignment(_SVC_A, 1, vram_limit_mb=2048)}
        assert log.records == [
            (
                "info",
                "GPU configuration changes detected for 1 services",
                {"extra": {"operation_id": oid, "changed_services": [_SVC_A]}},
            ),
            (
                "info",
                f"Generated GPU override file: {s._override_file}",
                {"extra": {"services": [_SVC_A]}},
            ),
        ]
        assert r.sets == [
            (
                (key, _seq_payload(oid, False, _st_payload("pending"))),
                {"expire": 3600},
            ),
            (
                (key, _seq_payload(oid, False, _st_payload("restarting", started=_STAMP))),
                {"expire": 3600},
            ),
            (
                (
                    key,
                    _seq_payload(
                        oid, False, _st_payload("running", started=_STAMP, completed=_STAMP)
                    ),
                ),
                {"expire": 3600},
            ),
            (
                (
                    key,
                    _seq_payload(
                        oid,
                        True,
                        _st_payload("running", started=_STAMP, completed=_STAMP),
                        completed=_STAMP,
                    ),
                ),
                {"expire": 3600},
            ),
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_apply_gpu_config_failure_sequence() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        r = _Redis()
        calls: list = []
        s = _apply_svc(tmp, r, False, calls)
        env = _Env([_swap("logger", log), _swap("datetime", _FixedNow)])
        try:
            res = _run(s.apply_gpu_config({_SVC_A: GpuAssignment(_SVC_A, 1, vram_limit_mb=2048)}))
        finally:
            env.close()
        oid = res.operation_id
        key = f"gpu_config:operation:{oid}"
        assert res.success is False
        assert res.error is None
        st = res.service_statuses[_SVC_A]
        assert st.status is RestartStatus.FAILED
        assert st.error == f"Failed to restart service {_SVC_A}"
        assert s.get_current_assignments() == {_SVC_A: GpuAssignment(_SVC_A, 0, vram_limit_mb=2048)}
        assert r.sets[-1] == (
            (
                key,
                _seq_payload(
                    oid,
                    False,
                    _st_payload(
                        "failed",
                        started=_STAMP,
                        completed=_STAMP,
                        error=f"Failed to restart service {_SVC_A}",
                    ),
                    completed=_STAMP,
                ),
            ),
            {"expire": 3600},
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_apply_gpu_config_exception_arm() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        r = _Redis()
        s = _svc(tmp, redis=r)

        async def _boom() -> dict:
            raise RuntimeError("boom")

        s._load_assignments = _boom  # type: ignore[method-assign]
        env = _Env([_swap("logger", log), _swap("datetime", _FixedNow)])
        try:
            res = _run(s.apply_gpu_config(None))
        finally:
            env.close()
        oid = res.operation_id
        key = f"gpu_config:operation:{oid}"
        assert res.success is False
        assert res.error == "boom"
        assert res.completed_at == _NOW
        assert log.records == [
            (
                "error",
                "Failed to apply GPU configuration: boom",
                {"extra": {"operation_id": oid}, "exc_info": True},
            )
        ]
        assert len(r.sets) == 1
        args, kwargs = r.sets[0]
        assert args[0] == key
        payload = args[1]
        assert payload["error"] == "boom"
        assert payload["completed_at"] == _STAMP
        assert kwargs == {"expire": 3600}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_apply_gpu_config_operation_id_shape() -> None:
    tmp = _tmp()
    log = _Logger()
    try:
        s = _svc(tmp)
        env = _Env([_swap("logger", log), _swap("datetime", _FixedNow)])
        try:
            res1 = _run(s.apply_gpu_config({}))
            res2 = _run(s.apply_gpu_config({}))
        finally:
            env.close()
        assert isinstance(res1.operation_id, str) and len(res1.operation_id) == 36
        assert res1.operation_id != res2.operation_id
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
