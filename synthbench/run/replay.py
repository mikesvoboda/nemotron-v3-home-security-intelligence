"""`replay`: one served model over the exported items, through the shipped replay (P5a §3).

It imports the export into the eval store (idempotent), checks the endpoint, the renderer and the
served model's identity, then runs `backend.evaluation.vlm_replay.run_replay` with a
`VlmClient` whose capture root is the export directory (the client refuses any image outside
it). `ai-vlm` models run the client as the product does; vLLM models run it with the
enforcement probe off (vLLM has no llama.cpp `/props`) and a transport that names the served
model (plan ruling P5a-R2).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from backend.core.config import get_settings
from backend.evaluation.eval_store import EvalStore
from backend.evaluation.label_import import import_generated_items
from backend.evaluation.vlm_replay import git_commit, run_replay
from backend.services.vlm_client import VlmClient

from synthbench.generate.comfy import serve
from synthbench.run.models import Model

Runner = Callable[..., subprocess.CompletedProcess[str]]
Getter = Callable[[str], httpx.Response]


class ReplayRefused(Exception):
    """A pre-run check failed: the run would measure the wrong thing, or disturb the GPU."""


class ImportRefused(Exception):
    """The export did not import cleanly into the eval store."""


def _get(url: str) -> httpx.Response:
    return httpx.get(url, timeout=10.0)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Deps:
    """The replay's outside world; tests replace each piece."""

    get: Getter = _get
    run: Runner = subprocess.run
    inner_transport: httpx.AsyncBaseTransport | None = None
    now: Callable[[], datetime] = field(default=_utc_now)


class ModelField(httpx.AsyncBaseTransport):
    """Names the served model in each chat request (vLLM's OpenAI server routes by `model`) and
    merges in the model's `request_extra`."""

    def __init__(
        self,
        model: str,
        inner: httpx.AsyncBaseTransport | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        self._model = model
        self._inner = inner or httpx.AsyncHTTPTransport()
        self._extra = dict(extra or {})

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/v1/chat/completions"):
            body = json.loads(request.content)
            body |= self._extra
            body["model"] = self._model
            headers = [
                (key, value)
                for key, value in request.headers.multi_items()
                if key.lower() != "content-length"
            ]
            # The extensions carry the client's timeouts (httpcore reads them there): without
            # them a vLLM request has no limit, and not the budget ai-vlm requests have.
            request = httpx.Request(
                "POST",
                request.url,
                headers=headers,
                content=json.dumps(body).encode(),
                extensions=request.extensions,
            )
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def renderer_stopped(run: Runner) -> bool:
    """True only when the renderer unit is not active and no ComfyUI container runs. A state
    that cannot be read counts as running: replay needs the renderer's GPU memory."""
    try:
        active = run(
            ["systemctl", "--user", "is-active", "synthbench-renderer"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
        return active != "active" and not serve.container_running(run)
    except OSError, subprocess.SubprocessError, serve.ServeError:
        return False


def served_identity(model: Model, url: str, get: Getter) -> tuple[str, str]:
    """(identity, build) as the endpoint reports them."""
    if model.transport == "ai-vlm":
        props = get(f"{url}/props").json()
        return Path(props.get("model_path") or "").stem, str(props.get("build_info", ""))
    ids = [str(entry["id"]) for entry in get(f"{url}/v1/models").json().get("data", [])]
    return (model.served_id if model.served_id in ids else ", ".join(ids)), ""


def check(model: Model, url: str, deps: Deps) -> str:
    """Refuse unless the endpoint answers, the renderer is stopped and the endpoint serves
    `model`. Returns the build the endpoint reports ("" for vLLM)."""
    probe = f"{url}/health" if model.transport == "ai-vlm" else f"{url}/v1/models"
    try:
        status = deps.get(probe).status_code
    except httpx.HTTPError as error:
        raise ReplayRefused(f"{model.name}: {probe} does not answer ({error})") from error
    if status != 200:
        raise ReplayRefused(f"{model.name}: {probe} answered HTTP {status}")
    if not renderer_stopped(deps.run):
        raise ReplayRefused(
            "the renderer is running, or its state cannot be read: stop synthbench-renderer "
            "first (replay needs its GPU memory)"
        )
    try:
        identity, build = served_identity(model, url, deps.get)
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise ReplayRefused(
            f"{model.name}: cannot read {url}'s model identity ({error})"
        ) from error
    if identity != model.served_id:
        raise ReplayRefused(f"{url} serves {identity!r}, not {model.name} ({model.served_id})")
    return build


def client_factory(
    model: Model, url: str, export: Path, inner: httpx.AsyncBaseTransport | None = None
) -> Callable[[], VlmClient]:
    """The replay's client: the shipped `VlmClient`, reading stills from the export."""

    def build() -> VlmClient:
        # camera_timezone=None as vlm_replay.client_factory pins it: the prompt shows the stored
        # timestamp verbatim. The capture root is the export: the client refuses images elsewhere.
        update: dict[str, Any] = {"camera_timezone": None, "foscam_base_path": str(export)}
        transport = inner
        if model.transport == "vllm":
            update |= {
                "vlm_enforcement_probe_enabled": False,
                "vlm_model_id": model.served_id,
                "nemotron_verification_engine": "vllm",
            }
            transport = ModelField(model.served_id, inner, model.request_extra)
        settings = get_settings().model_copy(update=update)
        return VlmClient(settings=settings, base_url=url, transport=transport)

    return build


def import_export(store: EvalStore, export: Path) -> tuple[int, int]:
    """Import the export: (new items, already imported). Any other skip is refused."""
    rows = import_generated_items(corpus_dir=export, store=store)
    skipped = [(row, row.reason or "") for row in rows if row.skipped]
    already = [row for row, reason in skipped if reason.startswith("already imported")]
    other = [(row, reason) for row, reason in skipped if not reason.startswith("already imported")]
    if other:
        shown = "; ".join(f"{row.item_id}: {reason}" for row, reason in other[:5])
        more = f" (+{len(other) - 5} more)" if len(other) > 5 else ""
        raise ImportRefused(shown + more)
    return len(rows) - len(already), len(already)


def check_stills(store: EvalStore, export: Path) -> None:
    """Refuse unless every stored item's stills lie under the export. The store is per version
    and the replay replays every item in it, while the client reads no image outside its capture
    root (the export, P5a-R9): a still stored from another export, or as a relative path, would
    come back refused on every item, and items are immutable, so re-importing cannot mend it."""
    root = export.resolve()
    outside = [
        (item.item_id, path)
        for item in store.iter_items(with_media_only=True)
        for path in item.media_paths
        if not (Path(path).is_absolute() and Path(path).resolve().is_relative_to(root))
    ]
    if outside:
        items = len({item_id for item_id, _ in outside})
        item_id, path = outside[0]
        raise ReplayRefused(
            f"the eval store holds {items} item(s) whose stills lie outside the export {root} "
            f"(first: {item_id}: {path}); replay with the export the store was imported from, "
            "or move the eval store aside"
        )


@dataclass(frozen=True)
class ReplayResult:
    replay_id: str
    run_dir: Path
    report: dict[str, Any]


def execute(
    model: Model,
    url: str,
    export: Path,
    store_path: Path,
    runs_dir: Path,
    limit: int | None,
    deps: Deps,
) -> ReplayResult:
    """Check, import, replay, and record the run under `runs_dir/<replay_id>/run.json`."""
    # Resolved before the import: the importer stores media paths as joined from the export.
    export = export.resolve()
    build = check(model, url, deps)
    started = deps.now()
    replay_id = f"{started:%Y%m%dT%H%M%SZ}-{model.name}"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with EvalStore(store_path) as store:
        new, already = import_export(store, export)
        check_stills(store, export)
        candidate = f"{model.served_id}@{model.transport}" + (f":{build}" if build else "")
        report = asyncio.run(
            run_replay(
                store,
                candidate=candidate,
                engine="llama.cpp" if model.transport == "ai-vlm" else "vllm",
                limit=limit,
                make_client=client_factory(model, url, export, deps.inner_transport),
            )
        )
    run_dir = runs_dir / replay_id
    run_dir.mkdir(parents=True)
    record = {
        "replay_id": replay_id,
        "model": model.name,
        "served_id": model.served_id,
        "transport": model.transport,
        "url": url,
        "build": build,
        "enforcement_probe": model.transport == "ai-vlm",
        "request_extra": dict(model.request_extra),
        "export": str(export),
        "store": str(store_path),
        "eval_run_id": report["run_id"],
        "imported_new": new,
        "already_imported": already,
        "limit": limit,
        "commit": git_commit(),
        "started_utc": started.isoformat(timespec="seconds"),
        "report": report,
    }
    (run_dir / "run.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return ReplayResult(replay_id, run_dir, report)
