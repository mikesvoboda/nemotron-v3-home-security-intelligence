"""`replay` (P5a design §3): pre-run checks, the import gate, and both client paths."""

from __future__ import annotations

import ast
import asyncio
import dataclasses
import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from synthbench import cli
from synthbench.export import vss
from synthbench.run import replay as replay_module
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
from backend.services import vlm_client as vc
from backend.services.vlm_verdict import VlmAssessContext, VlmAssessRequest
from backend.tests.unit.services.test_vlm_client import make_fake_llama
from backend.tests.unit.synthbench import helpers as h

QWEN = MODELS["qwen3-vl-8b"]
FLAGSHIP = MODELS["flagship"]
COSMOS = MODELS["cosmos-reason2-8b"]
# Cosmos-Reason2's model card instruction: it reasons only when the system prompt asks for this.
COSMOS_FORMAT = (
    "Answer the question using the following format:\n\n<think>\nYour reasoning.\n</think>\n\n"
    "Write your final answer immediately after the </think> tag."
)
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


def _get(
    props: dict[str, Any] | None = None, status: int = 200, served: str = "claude-flagship"
) -> Any:
    props = props or {
        "model_path": "/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
        "build_info": "b7972",
    }

    def get(url: str) -> httpx.Response:
        if url.endswith("/props"):
            return httpx.Response(200, json=props)
        if url.endswith("/v1/models"):
            return httpx.Response(200, json={"data": [{"id": served}]})
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


@pytest.mark.parametrize("state", ["active", "", "activating", "deactivating", "reloading"])
def test_a_renderer_that_is_not_plainly_stopped_is_refused(state: str) -> None:
    """Fail closed: only `inactive` or `failed` counts as stopped. An empty answer (no user
    D-Bus) or a state in motion counts as running, since replay needs the renderer's GPU."""
    with pytest.raises(ReplayRefused, match="renderer is running"):
        check(QWEN, URL, Deps(get=_get(), run=_run(state)))


@pytest.mark.parametrize("state", ["inactive", "failed"])
def test_a_stopped_renderer_passes(state: str) -> None:
    assert check(QWEN, URL, Deps(get=_get(), run=_run(state))) == "b7972"


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


class _Recording(httpx.AsyncBaseTransport):
    """Passes requests on, keeping each verdict request's body and timeouts."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self.inner = inner
        self.verdicts: list[tuple[dict[str, Any], dict[str, Any]]] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        if body.get("response_format", {}).get("json_schema", {}).get("name") == "vlm_verdict":
            self.verdicts.append((body, request.extensions["timeout"]))
        return await self.inner.handle_async_request(request)


def test_a_replay_reads_the_exports_stills_and_records_the_run(tmp_path: Path) -> None:
    """Every item is scored, none refused: the client's capture root is the export, so it can
    read the stills (it refuses any image outside its root). `run.json` records the budget and
    read timeout the requests carried: the shipped client's, for an ai-vlm model."""
    export = _export(tmp_path)
    app = make_fake_llama(model_path="/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf")
    recording = _Recording(httpx.ASGITransport(app=app))
    deps = Deps(get=_get(), run=_run(), inner_transport=recording)
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
    assert record["system_message"] is None
    assert record["read_timeout"] == get_settings().ai_vlm_read_timeout
    assert record["max_tokens"] == vc._ASSESS_MAX_TOKENS
    assert record["thinking"] == "—"
    assert len(recording.verdicts) == 2
    for body, timeout in recording.verdicts:
        assert (body["max_tokens"], timeout["read"]) == (
            record["max_tokens"],
            record["read_timeout"],
        )
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
    # The flagship thinks before answering and spent the whole shipped budget
    # thinking (Task 1 Step 7): it runs with thinking off, at the shipped budget.
    assert seen[0]["chat_template_kwargs"]["enable_thinking"] is False
    assert seen[0]["max_tokens"] == vc._ASSESS_MAX_TOKENS
    assert [message["role"] for message in seen[0]["messages"]] == ["user"]  # no system message


def test_cosmos_gets_the_budget_its_long_evidence_needs(tmp_path: Path) -> None:
    """Cosmos's answers ran past the shipped 1024 tokens
    (Task 1 Step 8); with 4096 it finished in 1326 tokens, in about 17 s."""
    export = _export(tmp_path, n=1)
    seen: list[dict[str, Any]] = []

    def vllm(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return _vllm_reply()

    verdict = _assess_first_still(
        client_factory(COSMOS, URL, export, httpx.MockTransport(vllm))(), export
    )
    assert verdict.provenance.model_id == "nvidia/Cosmos-Reason2-8B"
    assert seen[0]["model"] == "nvidia/Cosmos-Reason2-8B"
    assert seen[0]["max_tokens"] == 4096  # over the client's shipped budget
    assert seen[0]["response_format"]["type"] == "json_schema"
    assert "chat_template_kwargs" not in seen[0]


def _chat_bodies(model: Any, export: Path) -> list[dict[str, Any]]:
    """The chat bodies one `assess` over the export's first still sends `model`."""
    seen: list[dict[str, Any]] = []

    def vllm(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return _vllm_reply()

    _assess_first_still(client_factory(model, URL, export, httpx.MockTransport(vllm))(), export)
    return seen


def test_cosmos_is_asked_for_its_reasoning_format_ahead_of_the_shipped_prompt(
    tmp_path: Path,
) -> None:
    """Cosmos reasons only when the system prompt asks for its format; without it, under the
    JSON schema, the reasoning spilled into the first evidence string and looped (owner, Task 1
    Step 8). The system message comes first; the shipped user message follows unchanged."""
    export = _export(tmp_path, n=1)
    [body] = _chat_bodies(COSMOS, export)
    [shipped] = _chat_bodies(dataclasses.replace(COSMOS, system_message=None), export)
    assert body["messages"][0] == {"role": "system", "content": COSMOS_FORMAT}
    assert body["messages"][1:] == shipped["messages"]
    assert [message["role"] for message in shipped["messages"]] == ["user"]
    assert body["model"] == "nvidia/Cosmos-Reason2-8B"
    assert body["max_tokens"] == 4096
    assert body["response_format"]["type"] == "json_schema"


def test_only_the_vllm_comparison_models_change_the_shipped_request() -> None:
    """The ai-vlm models send the shipped body at the shipped timeout (P5a-R2)."""
    extras = {name: dict(model.request_extra) for name, model in MODELS.items()}
    assert {name: extra for name, extra in extras.items() if extra} == {
        "flagship": {"chat_template_kwargs": {"enable_thinking": False}},
        "cosmos-reason2-8b": {"max_tokens": 4096},
    }
    timeouts = {name: model.read_timeout for name, model in MODELS.items()}
    assert {name: t for name, t in timeouts.items() if t is not None} == {
        "cosmos-reason2-8b": 120.0
    }
    systems = {name: model.system_message for name, model in MODELS.items()}
    assert {name: m for name, m in systems.items() if m is not None} == {
        "cosmos-reason2-8b": COSMOS_FORMAT
    }
    # The declared thinking condition the report prints (decision A7): never derived, so it must
    # be pinned directly.
    assert (QWEN.thinking, FLAGSHIP.thinking, COSMOS.thinking) == (
        "—",
        "off",
        "on (asked by its system message; parsed by vLLM)",
    )


@pytest.mark.parametrize("name", ["flagship", "cosmos-reason2-8b"])
def test_a_vllm_request_keeps_the_clients_timeouts(tmp_path: Path, name: str) -> None:
    """`ModelField` rebuilds the chat request; httpcore reads the client's timeouts from the
    request's extensions, so a rebuild that drops them sends vLLM requests with no limit at all,
    and off the per-attempt budget `ai-vlm` requests are held to (P5a-R2). Cosmos's longer
    answers get their own read timeout; the flagship keeps the shipped one."""
    export = _export(tmp_path, n=1)
    timeouts: list[Any] = []

    def vllm(request: httpx.Request) -> httpx.Response:
        timeouts.append(request.extensions.get("timeout"))
        return _vllm_reply()

    model = MODELS[name]
    _assess_first_still(client_factory(model, URL, export, httpx.MockTransport(vllm))(), export)
    settings = get_settings()
    read = settings.ai_vlm_read_timeout if name == "flagship" else 120.0
    assert timeouts == [
        {"connect": settings.ai_connect_timeout, "read": read, "write": read, "pool": read}
    ]


@pytest.mark.parametrize(
    ("name", "extra", "read_timeout", "max_tokens", "system_message", "thinking"),
    [
        (
            "flagship",
            {"chat_template_kwargs": {"enable_thinking": False}},
            None,  # the shipped read timeout
            vc._ASSESS_MAX_TOKENS,
            None,
            "off",
        ),
        (
            "cosmos-reason2-8b",
            {"max_tokens": 4096},
            120.0,
            4096,
            COSMOS_FORMAT,
            "on (asked by its system message; parsed by vLLM)",
        ),
    ],
    ids=["flagship", "cosmos-reason2-8b"],
)
def test_a_vllm_replay_records_the_conditions_it_ran_under(
    tmp_path: Path,
    name: str,
    extra: dict[str, Any],
    read_timeout: float | None,
    max_tokens: int,
    system_message: str | None,
    thinking: str,
) -> None:
    """The effective values, as the requests carried them: the report states each model's."""
    model = MODELS[name]
    export = _export(tmp_path, n=1)
    recording = _Recording(httpx.MockTransport(lambda _: _vllm_reply()))
    deps = Deps(get=_get(served=model.served_id), run=_run(), inner_transport=recording)
    result = execute(
        model, URL, export, tmp_path / "eval" / "eval.sqlite", tmp_path / "runs", None, deps
    )
    assert result.report["s5"]["refusals"] == 0
    record = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["enforcement_probe"] is False
    assert record["request_extra"] == extra
    assert record["system_message"] == system_message
    assert record["thinking"] == thinking
    shipped = get_settings().ai_vlm_read_timeout
    assert record["read_timeout"] == (shipped if read_timeout is None else read_timeout)
    assert record["max_tokens"] == max_tokens
    [(body, timeout)] = recording.verdicts
    assert (body["max_tokens"], timeout["read"]) == (record["max_tokens"], record["read_timeout"])


def test_the_conditions_line_records_the_sampling_choice(tmp_path: Path) -> None:
    """ISS-043's repeat-run term: a comparison is only comparable if the report
    can show both arms sampled alike. The shipped assess path samples at
    temperature 0 with no seed (ISS-078); the conditions line must SAY so, per
    model, and say what the requests actually carried - the record is not
    allowed to claim a sampling the wire did not show."""
    export = _export(tmp_path, n=1)
    recording = _Recording(httpx.MockTransport(lambda _: _vllm_reply()))
    deps = Deps(get=_get(served=FLAGSHIP.served_id), run=_run(), inner_transport=recording)
    result = execute(
        FLAGSHIP, URL, export, tmp_path / "eval" / "eval.sqlite", tmp_path / "runs", None, deps
    )
    record = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["temperature"] == 0.0
    assert record["seed"] is None
    [(body, _)] = recording.verdicts
    assert body["temperature"] == record["temperature"]
    assert "seed" not in body  # unseeded means the wire carries no seed, not seed=None


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


# The export fixture's roster: two incident scenarios enter the draw, the two benign ones join
# dev by rule (B1), so the store ends with four rows and the clamped draw holds one scenario.
SPLIT_ITEMS = {
    "knife_visible": {"benign": 0, "incident": 1},
    "loitering": {"benign": 0, "incident": 1},
    "hooded_jogger": {"benign": 1, "incident": 0},
    "delivery_driver": {"benign": 1, "incident": 0},
}


def _split(export: Path) -> dict[str, Any]:
    """The export's `splits.json` (Task 1's writer) over the roster above; returns the manifest."""
    incident = [name for name, counts in SPLIT_ITEMS.items() if counts["incident"]]
    arm = {row["scenario"]: row["arm"] for row in vss.draw_split(h.VERSION, incident)["scenarios"]}
    arm |= {name: "dev" for name in SPLIT_ITEMS if name not in arm}
    manifest = vss.split_manifest_document(h.VERSION, arm, items_by_scenario=SPLIT_ITEMS)
    vss.write_split(export, manifest)
    return manifest


def _arms_rows(document: dict[str, Any]) -> list[dict[str, str]]:
    """The store's flat rows for a manifest: one per armed scenario, as `put_split` takes them."""
    return [
        {"scenario": name, "arm": arm} for arm, names in document["arms"].items() for name in names
    ]


def _swapped(document: dict[str, Any]) -> dict[str, Any]:
    """A rival manifest: the fixture's two incident scenarios armed the other way round."""
    arms = {
        "holdout": ["loitering"],
        "dev": ["knife_visible", "hooded_jogger", "delivery_driver"],
    }
    draw = [
        row | {"arm": "holdout" if row["scenario"] == "loitering" else "dev"}
        for row in document["draw"]
    ]
    return document | {"arms": arms, "draw": draw, "holdout_k": 1}


def _qwen_app() -> httpx.ASGITransport:
    """The fake llama.cpp server `QWEN` is served by."""
    return httpx.ASGITransport(
        app=make_fake_llama(model_path="/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf")
    )


def test_a_split_export_lands_in_the_store_and_in_run_json(tmp_path: Path) -> None:
    """The replay records the export's roster under the corpus version and names its digest in
    `run.json`, so a later score can say which scenarios it never scored (ISS-016)."""
    export = _export(tmp_path)
    manifest = _split(export)
    digest = vss.split_sha256(manifest)
    store_path = tmp_path / "eval" / "eval.sqlite"
    deps = Deps(get=_get(), run=_run(), inner_transport=_qwen_app())
    result = execute(QWEN, URL, export, store_path, tmp_path / "runs", None, deps)
    record = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["split_sha256"] == digest == vss.split_sha256(vss.read_split(export))
    assert record["split_holdout"] == ["knife_visible"]
    with EvalStore(store_path) as store:
        rows = store.get_split(h.VERSION)
    assert [(row["scenario"], row["arm"]) for row in rows] == [
        ("delivery_driver", "dev"),
        ("hooded_jogger", "dev"),
        ("knife_visible", "holdout"),
        ("loitering", "dev"),
    ]
    assert [(row["seed"], row["manifest_sha256"]) for row in rows] == [
        (manifest["seed"], digest)
    ] * len(rows)


def test_a_store_that_records_another_roster_refuses_the_export(tmp_path: Path) -> None:
    """The store's split is born once (the frozen-item rule again): a replay whose export draws
    the roster the other way round is refused before any GPU time, naming both digests."""
    export = _export(tmp_path)
    manifest = _split(export)
    rival = _swapped(manifest)
    assert vss.split_sha256(rival) != vss.split_sha256(manifest)
    store_path = tmp_path / "eval" / "eval.sqlite"
    store_path.parent.mkdir()
    with EvalStore(store_path) as store:
        store.put_split(
            h.VERSION,
            _arms_rows(rival),
            seed=rival["seed"],
            manifest_sha256=vss.split_sha256(rival),
        )
    requests: list[httpx.Request] = []
    deps = Deps(get=_get(), run=_run(), inner_transport=_refusing(requests))
    recorded, carried = vss.split_sha256(rival), vss.split_sha256(manifest)
    with pytest.raises(ImportRefused) as refusal:
        execute(QWEN, URL, export, store_path, tmp_path / "runs", None, deps)
    # The reader sees both sides of the disagreement: the store's digest and the export's.
    assert re.search(rf"{recorded}.*{carried}", str(refusal.value), re.DOTALL)
    assert requests == []
    assert not (tmp_path / "runs").exists()
    with EvalStore(store_path) as store:
        assert [(row["scenario"], row["arm"]) for row in store.get_split(h.VERSION)] == [
            ("delivery_driver", "dev"),
            ("hooded_jogger", "dev"),
            ("knife_visible", "dev"),  # the store's own roster stands
            ("loitering", "holdout"),
        ]


def test_a_manifestless_export_records_no_split(tmp_path: Path) -> None:
    """B6: an export predating the split still replays; its `run.json` says the split is
    unrecorded rather than claiming an empty holdout."""
    export = _export(tmp_path)
    store_path = tmp_path / "eval" / "eval.sqlite"
    deps = Deps(get=_get(), run=_run(), inner_transport=_qwen_app())
    result = execute(QWEN, URL, export, store_path, tmp_path / "runs", None, deps)
    record = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    assert record["split_sha256"] is None
    assert record["split_holdout"] == []
    with EvalStore(store_path) as store:
        assert store.get_split(h.VERSION) is None


def test_the_model_table_imports_no_backend() -> None:
    """Commands import `synthbench.run.models` at startup, so it must stay backend-free."""
    source = (Path(cli.__file__).parent / "run" / "models.py").read_text(encoding="utf-8")
    imported = [
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert not [module for module in imported if module.startswith("backend")]


def test_every_bench_env_key_is_one_compose_reads() -> None:
    """`.env.bench` is compose's `--env-file` for ai-vlm; a key nothing reads misleads (replay
    finds Cosmos through `SYNTHBENCH_COSMOS_URL`, never a port variable)."""
    repo = Path(cli.__file__).parents[1]
    keys = [
        line.partition("=")[0].strip()
        for line in (repo / ".env.bench").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    compose = (repo / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert keys
    assert [key for key in keys if not re.search(rf"\$\{{?{key}\b", compose)] == []


def test_replay_needs_an_export(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert h.run(tmp_path, "replay", "--model", "flagship") == cli.EXIT_ERROR
    assert "run `export vss` first" in capsys.readouterr().err


def _refusing(requests: list[httpx.Request]) -> httpx.MockTransport:
    """A VLM that answers nothing useful, and remembers being asked."""

    def vlm(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    return httpx.MockTransport(vlm)


def test_a_store_imported_from_an_older_export_is_refused(tmp_path: Path) -> None:
    """Items are immutable and the importer skips an id it holds, so an export rebuilt in place
    (A6 added detections) would replay the old snapshots and score them against the new facts.
    The replay compares what the store holds with what the export declares, and refuses first."""
    export = _export(tmp_path)
    store_path = tmp_path / "eval" / "eval.sqlite"
    store_path.parent.mkdir()
    with EvalStore(store_path) as store:
        assert import_export(store, export) == (2, 0)
    labels_file = export / "threats" / "B-t-001" / vss.LABELS_FILE
    labels = json.loads(labels_file.read_text(encoding="utf-8"))
    labels["detections"] = [{"object_type": "person", "confidence": 1.0}]
    labels_file.write_text(json.dumps(labels), encoding="utf-8")
    requests: list[httpx.Request] = []
    deps = Deps(get=_get(), run=_run(), inner_transport=_refusing(requests))
    refusal = r"predates this export: \S+B-t-001 .*snapshot\.detections.*move the eval store aside"
    with pytest.raises(ReplayRefused, match=refusal):
        execute(QWEN, URL, export, store_path, tmp_path / "runs", None, deps)
    assert requests == []
    assert not (tmp_path / "runs").exists()


def test_the_run_dir_exists_before_the_first_request(tmp_path: Path) -> None:
    """A failure after GPU time must not lose the run: its directory is made first."""
    export = _export(tmp_path, n=1)
    runs = tmp_path / "runs"
    seen: list[list[Path]] = []

    def vllm(request: httpx.Request) -> httpx.Response:
        seen.append(list(runs.iterdir()) if runs.is_dir() else [])
        return _vllm_reply()

    deps = Deps(
        get=_get(served=FLAGSHIP.served_id), run=_run(), inner_transport=httpx.MockTransport(vllm)
    )
    result = execute(FLAGSHIP, URL, export, tmp_path / "eval" / "eval.sqlite", runs, None, deps)
    assert seen == [[result.run_dir]]
    assert (result.run_dir / "run.json").is_file()


def test_a_run_dir_that_cannot_be_made_is_refused_before_the_replay(tmp_path: Path) -> None:
    export = _export(tmp_path, n=1)
    blocked = tmp_path / "runs"
    blocked.write_text("a file where the runs directory goes")
    requests: list[httpx.Request] = []
    deps = Deps(get=_get(), run=_run(), inner_transport=_refusing(requests))
    with pytest.raises(ReplayRefused, match="cannot create the run directory"):
        execute(QWEN, URL, export, tmp_path / "eval" / "eval.sqlite", blocked, None, deps)
    assert requests == []


def _fake_deps(monkeypatch: pytest.MonkeyPatch, transport: httpx.AsyncBaseTransport) -> None:
    """The command builds `Deps()`: give it fakes, so no request leaves the test."""
    monkeypatch.setattr(
        replay_module,
        "Deps",
        lambda: Deps(get=_get(served=FLAGSHIP.served_id), run=_run(), inner_transport=transport),
    )


def test_replay_prints_the_refusal_classes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run of refusals shows why at once: a budget (truncation) reads apart from plumbing."""
    export = _export(tmp_path)
    cut = {"message": {"content": '{"verdict": "rej'}, "finish_reason": "length"}
    _fake_deps(
        monkeypatch, httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [cut]}))
    )
    code = h.run(tmp_path, "replay", "--model", "flagship", "--export", str(export))
    assert code == cli.EXIT_OK
    assert "2 refused (VlmTruncatedError 2)" in capsys.readouterr().out


def test_an_importer_refusal_is_the_owners_not_a_bug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A set whose declared category contradicts its directory is a hard importer refusal
    (`LabelImportError`): exit 2 with its message, not "unexpected error"."""
    export = _export(tmp_path, n=1)
    labels_file = export / "threats" / "B-t-000" / vss.LABELS_FILE
    labels = json.loads(labels_file.read_text(encoding="utf-8"))
    labels["category"] = "normal"
    labels_file.write_text(json.dumps(labels), encoding="utf-8")
    requests: list[httpx.Request] = []
    _fake_deps(monkeypatch, _refusing(requests))
    code = h.run(tmp_path, "replay", "--model", "flagship", "--export", str(export))
    err = capsys.readouterr().err
    assert code == cli.EXIT_ASK
    assert "unexpected error" not in err
    assert "did not import" in err and "B-t-000" in err
    assert requests == []
