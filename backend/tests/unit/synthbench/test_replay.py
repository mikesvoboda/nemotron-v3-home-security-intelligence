"""`replay` (P5a design §3): pre-run checks, the import gate, and both client paths."""

from __future__ import annotations

import ast
import asyncio
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from synthbench import cli
from synthbench.export import vss
from synthbench.run.models import MODELS
from synthbench.run.replay import (
    Deps,
    ImportRefused,
    ReplayRefused,
    check,
    client_factory,
    execute,
    import_export,
)

from backend.core.config import get_settings
from backend.evaluation.eval_store import EvalStore
from backend.services.vlm_verdict import VlmAssessContext, VlmAssessRequest
from backend.tests.unit.services.test_vlm_client import make_fake_llama
from backend.tests.unit.synthbench import helpers as h

QWEN = MODELS["qwen3-vl-8b"]
FLAGSHIP = MODELS["flagship"]
URL = "http://fake-vlm:8098"


@pytest.fixture(autouse=True)
def _fresh_breaker_registry() -> Iterator[None]:
    """The shared "ai-vlm" breaker must not carry failures between tests."""
    from backend.services.circuit_breaker import reset_circuit_breaker_registry

    reset_circuit_breaker_registry()
    yield
    reset_circuit_breaker_registry()


def _export(root: Path, n: int = 2, timestamp: Any = "2026-04-15T14:32:00-04:00") -> Path:
    """An export of n threat sets, each a stand-in still with its attribution."""
    export = root / "exports" / "vss"
    for i in range(n):
        labels = {
            "category": "threats",
            "risk": {"min_score": 70, "max_score": 95},
            "timestamp": timestamp,
            "synthbench": {"event_id": f"B-t-{i:03d}"},
        }
        files = {
            vss.LABELS_FILE: json.dumps(labels).encode(),
            vss.STILL_FILE: b"\xff\xd8\xff" + b"\x00" * 32,
            vss.SIDECAR_FILE: json.dumps(vss.attribution("tierb-v0")).encode(),
        }
        vss.write_set(export, "threats", f"B-t-{i:03d}", files)
    return export


def _run(renderer: str = "inactive") -> Any:
    """systemctl reports `renderer`; podman reports no ComfyUI container."""

    def run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if "is-active" in argv:
            return subprocess.CompletedProcess(argv, 0, renderer + "\n", "")
        return subprocess.CompletedProcess(argv, 1, "", "")  # `container exists`: no container

    return run


def _get(props: dict[str, Any] | None = None, status: int = 200) -> Any:
    props = props or {
        "model_path": "/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
        "build_info": "b7972",
    }

    def get(url: str) -> httpx.Response:
        if url.endswith("/props"):
            return httpx.Response(200, json=props)
        if url.endswith("/v1/models"):
            return httpx.Response(200, json={"data": [{"id": "claude-flagship"}]})
        return httpx.Response(status)

    return get


def test_a_ready_endpoint_passes_and_reports_its_build() -> None:
    assert check(QWEN, URL, Deps(get=_get(), run=_run())) == "b7972"
    assert check(FLAGSHIP, URL, Deps(get=_get(), run=_run())) == ""


def test_an_endpoint_that_does_not_answer_is_refused() -> None:
    def down(url: str) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ReplayRefused, match="does not answer"):
        check(QWEN, URL, Deps(get=down, run=_run()))
    with pytest.raises(ReplayRefused, match="HTTP 503"):
        check(QWEN, URL, Deps(get=_get(status=503), run=_run()))


def test_a_running_renderer_is_refused() -> None:
    with pytest.raises(ReplayRefused, match="renderer is running"):
        check(QWEN, URL, Deps(get=_get(), run=_run("active")))


def test_the_wrong_served_model_is_refused() -> None:
    other = {"model_path": "/models/Qwen3VL-4B-Instruct-Q4_K_M.gguf", "build_info": "b7972"}
    with pytest.raises(ReplayRefused, match="Qwen3VL-4B-Instruct-Q4_K_M"):
        check(QWEN, URL, Deps(get=_get(props=other), run=_run()))


def test_the_import_is_idempotent_and_refuses_a_bad_set(tmp_path: Path) -> None:
    export = _export(tmp_path)
    with EvalStore(tmp_path / "eval.sqlite") as store:
        assert import_export(store, export) == (2, 0)
        assert import_export(store, export) == (0, 2)
    bad = _export(tmp_path / "bad", timestamp="noon")
    with EvalStore(tmp_path / "bad.sqlite") as store, pytest.raises(ImportRefused, match="noon"):
        import_export(store, bad)


def test_a_replay_reads_the_exports_stills_and_records_the_run(tmp_path: Path) -> None:
    """Every item is scored, none refused: the client's capture root is the export, so it can
    read the stills (it refuses any image outside its root)."""
    export = _export(tmp_path)
    app = make_fake_llama(model_path="/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf")
    deps = Deps(get=_get(), run=_run(), inner_transport=httpx.ASGITransport(app=app))
    result = execute(
        QWEN, URL, export, tmp_path / "eval" / "eval.sqlite", tmp_path / "runs", None, deps
    )
    assert result.report["n_items"] == 2
    assert result.report["s5"]["refusals"] == 0
    record = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["model"] == "qwen3-vl-8b"
    assert record["build"] == "b7972"
    assert record["enforcement_probe"] is True
    assert record["request_extra"] == {}
    with EvalStore(tmp_path / "eval" / "eval.sqlite") as store:
        rows = store.replay(record["eval_run_id"])
    assert [row["risk_score"] for row in rows] == [50, 50]  # the fake's schema-filled verdict


def _vllm_reply() -> httpx.Response:
    """A vLLM chat reply carrying a schema-valid verdict."""
    verdict = {
        "verdict": "rejected",
        "risk_score": 12,
        "summary": "s",
        "reasoning": "r",
        "description": "d",
        "criteria": [{"name": "n", "passed": False, "evidence": "e"}],
        "provenance": {"engine": "x", "model_id": "y"},
    }
    choice = {"message": {"content": json.dumps(verdict)}, "finish_reason": "stop"}
    return httpx.Response(200, json={"choices": [choice]})


def _assess_first_still(client: Any, export: Path) -> Any:
    """One `assess` over the export's first still, closing the client after."""
    still = str(export / "threats" / "B-t-000" / vss.STILL_FILE)
    context = VlmAssessContext(camera_id="c", timestamp="2026-04-15T14:32:00-04:00")
    request = VlmAssessRequest(image_paths=[still], context=context)

    async def assess() -> Any:
        try:
            return await client.assess(request)
        finally:
            await client.close()

    return asyncio.run(assess())


def test_a_vllm_model_gets_its_name_the_schema_and_no_probe(tmp_path: Path) -> None:
    export = _export(tmp_path, n=1)
    seen: list[dict[str, Any]] = []

    def vllm(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        seen.append({"path": request.url.path, **body})
        if body.get("model") != "claude-flagship":
            return httpx.Response(404, json={"error": "no such model"})
        return _vllm_reply()

    client = client_factory(FLAGSHIP, URL, export, httpx.MockTransport(vllm))()
    verdict = _assess_first_still(client, export)
    assert (verdict.verdict, verdict.risk_score) == ("rejected", 12)
    assert verdict.provenance.model_id == "claude-flagship"
    assert [call["path"] for call in seen] == ["/v1/chat/completions"]  # no /props probe
    assert seen[0]["model"] == "claude-flagship"
    assert seen[0]["response_format"]["type"] == "json_schema"
    # The flagship thinks before answering and spent the whole shipped 1024-token budget
    # thinking (Task 1 Step 7): it runs with thinking off, at the shipped budget.
    assert seen[0]["chat_template_kwargs"]["enable_thinking"] is False
    assert seen[0]["max_tokens"] == 1024
    # Only the flagship adds a field; Cosmos and the ai-vlm models send the shipped body.
    extras = {name: dict(model.request_extra) for name, model in MODELS.items()}
    assert {name: extra for name, extra in extras.items() if extra} == {
        "flagship": {"chat_template_kwargs": {"enable_thinking": False}}
    }


def test_a_vllm_request_keeps_the_clients_timeouts(tmp_path: Path) -> None:
    """`ModelField` rebuilds the chat request; httpcore reads the client's timeouts from the
    request's extensions, so a rebuild that drops them sends vLLM requests with no limit at all,
    and off the per-attempt budget `ai-vlm` requests are held to (P5a-R2)."""
    export = _export(tmp_path, n=1)
    timeouts: list[Any] = []

    def vllm(request: httpx.Request) -> httpx.Response:
        timeouts.append(request.extensions.get("timeout"))
        return _vllm_reply()

    _assess_first_still(client_factory(FLAGSHIP, URL, export, httpx.MockTransport(vllm))(), export)
    settings = get_settings()
    read = settings.ai_vlm_read_timeout
    assert timeouts == [
        {"connect": settings.ai_connect_timeout, "read": read, "write": read, "pool": read}
    ]


def test_a_vllm_replay_records_the_fields_it_adds(tmp_path: Path) -> None:
    export = _export(tmp_path, n=1)
    deps = Deps(
        get=_get(), run=_run(), inner_transport=httpx.MockTransport(lambda _: _vllm_reply())
    )
    result = execute(
        FLAGSHIP, URL, export, tmp_path / "eval" / "eval.sqlite", tmp_path / "runs", None, deps
    )
    assert result.report["s5"]["refusals"] == 0
    record = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["enforcement_probe"] is False
    assert record["request_extra"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_a_relative_export_is_resolved_before_the_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The importer stores media paths as joined from the export, so a relative export would
    store relative paths the client resolves against the capture root: every item refused, and
    the bad paths kept for good (items are immutable, re-imports skip them)."""
    _export(tmp_path)
    monkeypatch.chdir(tmp_path)
    app = make_fake_llama(model_path="/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf")
    deps = Deps(get=_get(), run=_run(), inner_transport=httpx.ASGITransport(app=app))
    store_path = tmp_path / "eval" / "eval.sqlite"
    result = execute(QWEN, URL, Path("exports/vss"), store_path, tmp_path / "runs", None, deps)
    assert result.report["s5"]["refusals"] == 0
    with EvalStore(store_path) as store:
        stored = [path for item in store.iter_items() for path in item.media_paths]
    assert len(stored) == 2
    assert all(Path(path).is_absolute() for path in stored)
    record = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["export"] == str((tmp_path / "exports" / "vss").resolve())


@pytest.mark.parametrize("stored", ["another export", "a relative path"])
def test_a_store_whose_stills_lie_outside_the_export_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stored: str
) -> None:
    """The store is per version and a replay replays every item in it, so stills stored from
    another export (or as relative paths, by an unresolved export) would all be refused: the
    replay refuses before its first request instead."""
    store_path = tmp_path / "eval" / "eval.sqlite"
    store_path.parent.mkdir()
    export = _export(tmp_path)
    if stored == "another export":
        first = _export(tmp_path / "first")
    else:
        monkeypatch.chdir(tmp_path)
        first = Path("exports/vss")
    with EvalStore(store_path) as store:
        assert import_export(store, first) == (2, 0)
    requests: list[httpx.Request] = []

    def vlm(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    deps = Deps(get=_get(), run=_run(), inner_transport=httpx.MockTransport(vlm))
    with pytest.raises(ReplayRefused, match="outside the export"):
        execute(QWEN, URL, export, store_path, tmp_path / "runs", None, deps)
    assert requests == []
    assert not (tmp_path / "runs").exists()


def test_the_model_table_imports_no_backend() -> None:
    """Commands import `synthbench.run.models` at startup, so it must stay backend-free."""
    source = (Path(cli.__file__).parent / "run" / "models.py").read_text(encoding="utf-8")
    imported = [
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert not [module for module in imported if module.startswith("backend")]


def test_replay_needs_an_export(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert h.run(tmp_path, "replay", "--model", "flagship") == cli.EXIT_ERROR
    assert "run `export vss` first" in capsys.readouterr().err
