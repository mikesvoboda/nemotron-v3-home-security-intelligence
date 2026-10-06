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
from backend.core.config import Settings, get_settings
from backend.evaluation.assess_input import EvalItem
from backend.evaluation.eval_store import EvalStore
from backend.evaluation.label_import import LabelImportError, import_generated_items
from backend.evaluation.vlm_replay import git_commit, run_replay
from backend.services import vlm_client
from backend.services.vlm_client import VlmClient

from synthbench.export.vss import read_split, split_sha256
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
    """Names the served model in each chat request (vLLM's OpenAI server routes by `model`),
    merges in the model's `request_extra` and puts its `system_message`, if any, ahead of the
    shipped messages."""

    def __init__(
        self,
        model: str,
        inner: httpx.AsyncBaseTransport | None = None,
        extra: Mapping[str, Any] | None = None,
        system_message: str | None = None,
    ) -> None:
        self._model = model
        self._inner = inner or httpx.AsyncHTTPTransport()
        self._extra = dict(extra or {})
        self._system_message = system_message

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/v1/chat/completions"):
            body = json.loads(request.content)
            body |= self._extra
            if self._system_message is not None:
                system = {"role": "system", "content": self._system_message}
                body["messages"] = [system, *body["messages"]]
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


# The only unit states that mean the renderer holds no GPU memory. Anything else, including an
# empty answer (no user D-Bus) or a state in motion (activating, deactivating), counts as running.
_STOPPED_STATES = frozenset({"inactive", "failed"})


def renderer_stopped(run: Runner) -> bool:
    """True only when the renderer unit is plainly stopped and no ComfyUI container runs. A
    state that cannot be read counts as running: replay needs the renderer's GPU memory."""
    try:
        state = run(
            ["systemctl", "--user", "is-active", "synthbench-renderer"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
        return state in _STOPPED_STATES and not serve.container_running(run)
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


def client_settings(model: Model, export: Path) -> Settings:
    """The shipped settings with the replay's changes for `model`."""
    # camera_timezone=None as vlm_replay.client_factory pins it: the prompt shows the stored
    # timestamp verbatim. The capture root is the export: the client refuses images elsewhere.
    update: dict[str, Any] = {"camera_timezone": None, "foscam_base_path": str(export)}
    if model.read_timeout is not None:
        # VlmClient builds its httpx timeout from this setting on first use.
        update["ai_vlm_read_timeout"] = model.read_timeout
    if model.transport == "vllm":
        update |= {
            "vlm_enforcement_probe_enabled": False,
            "vlm_model_id": model.served_id,
            "nemotron_verification_engine": "vllm",
        }
    settings: Settings = get_settings().model_copy(update=update)
    return settings


def client_factory(
    model: Model, url: str, export: Path, inner: httpx.AsyncBaseTransport | None = None
) -> Callable[[], VlmClient]:
    """The replay's client: the shipped `VlmClient`, reading stills from the export."""

    def build() -> VlmClient:
        transport = inner
        if model.transport == "vllm":
            transport = ModelField(
                model.served_id, inner, model.request_extra, model.system_message
            )
        settings = client_settings(model, export)
        return VlmClient(settings=settings, base_url=url, transport=transport)

    return build


def conditions(model: Model, export: Path) -> dict[str, Any]:
    """The conditions the replay runs `model` under, as its requests carry them: `run.json`
    records them and the report states them per model (decision A7)."""
    settings = client_settings(model, export)
    # Only `ModelField` (vLLM models) applies the request extra and the system message.
    applied = model.transport == "vllm"
    extra = dict(model.request_extra) if applied else {}
    # The shipped verdict budget is private to the client; it is read, never restated here.
    shipped_budget = vlm_client._ASSESS_MAX_TOKENS
    return {
        "enforcement_probe": settings.vlm_enforcement_probe_enabled,
        "request_extra": extra,
        "max_tokens": int(extra.get("max_tokens", shipped_budget)),
        "read_timeout": settings.ai_vlm_read_timeout,
        "system_message": model.system_message if applied else None,
        "thinking": model.thinking,
        # ISS-043's repeat-run term: the sampling choice, as the requests carry
        # it. The shipped assess path is greedy at temperature 0 with NO seed
        # (ISS-078) — the report must be able to show two arms were sampled
        # alike, and a "the runs are deterministic" claim must rest on this
        # line, not on memory. `seed` is None because the assess body carries
        # no seed key; an empty slot here would read the same as "seeded
        # nothing" only because that is what it is.
        "temperature": float(extra.get("temperature", vlm_client._ASSESS_TEMPERATURE)),
        "seed": extra.get("seed"),
    }


def _import(store: EvalStore, export: Path) -> tuple[int, int]:
    """Import the export into `store`: (new items, already imported). Any other skip is
    refused, and so is a set the importer refuses outright (`LabelImportError`)."""
    try:
        rows = import_generated_items(corpus_dir=export, store=store)
    except LabelImportError as error:
        raise ImportRefused(str(error)) from error
    skipped = [(row, row.reason or "") for row in rows if row.skipped]
    already = [row for row, reason in skipped if reason.startswith("already imported")]
    other = [(row, reason) for row, reason in skipped if not reason.startswith("already imported")]
    if other:
        shown = "; ".join(f"{row.item_id}: {reason}" for row, reason in other[:5])
        more = f" (+{len(other) - 5} more)" if len(other) > 5 else ""
        raise ImportRefused(shown + more)
    return len(rows) - len(already), len(already)


def import_split(store: EvalStore, export: Path) -> dict[str, Any]:
    """Record the export's dev/holdout split in `store`; the run.json fields for it (ISS-016).

    An export written before the split carries no manifest and records nothing — the run reports
    the split as unrecorded (`None`/`[]`) rather than as an empty holdout. A store that already
    holds a different roster for the corpus version raises `ValueError` naming both digests; that
    is a refusal like any other import refusal, so it comes back as `ImportRefused`.
    """
    document = read_split(export)
    if document is None:
        return {"split_sha256": None, "split_holdout": []}
    rows = [
        {"scenario": name, "arm": arm} for arm, names in document["arms"].items() for name in names
    ]
    digest = split_sha256(document)
    try:
        store.put_split(
            str(document["corpus_version"]),
            rows,
            seed=str(document["seed"]),
            manifest_sha256=digest,
        )
    except ValueError as error:
        raise ImportRefused(str(error)) from error
    return {"split_sha256": digest, "split_holdout": list(document["arms"]["holdout"])}


def _differing_fields(held: EvalItem, declared: EvalItem) -> list[str]:
    """The item fields (and snapshot fields) where the store and the export disagree."""
    now, before = declared.model_dump(), held.model_dump()
    fields = [key for key in now if key != "snapshot" and now[key] != before.get(key)]
    snapshot, old = now.get("snapshot") or {}, before.get("snapshot") or {}
    return fields + [f"snapshot.{key}" for key in snapshot if snapshot[key] != old.get(key)]


def check_current(store: EvalStore, export: Path) -> None:
    """Refuse unless every item the store already holds matches its set in the export.

    The importer skips an id the store holds (items are immutable), so an export rebuilt in
    place would replay the old snapshots and be scored against the new facts. The export is
    imported into a scratch store by the same importer, and each held item is compared whole:
    label, expected risk score, timestamp, detections and stills among the rest."""
    with EvalStore(":memory:") as scratch:
        _import(scratch, export)
        declared = scratch.iter_items()
    stale = [
        (held, item)
        for item in declared
        if (held := store.get_item(item.item_id)) is not None
        and held.model_dump_json() != item.model_dump_json()
    ]
    if stale:
        held, item = stale[0]
        fields = ", ".join(_differing_fields(held, item)) or "content"
        raise ReplayRefused(
            f"the eval store predates this export: {item.item_id} differs from its set "
            f"({fields}), {len(stale)} item(s) in all; move the eval store aside and replay again"
        )


def import_export(store: EvalStore, export: Path) -> tuple[int, int]:
    """Import the export: (new items, already imported). Any other skip is refused, and so is
    a store whose items differ from the export's sets (`check_current`)."""
    check_current(store, export)
    return _import(store, export)


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
    ran_under = conditions(model, export)  # before the replay: nothing after it may fail first
    started = deps.now()
    replay_id = f"{started:%Y%m%dT%H%M%SZ}-{model.name}"
    run_dir = runs_dir / replay_id
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with EvalStore(store_path) as store:
        # The items the store already holds: stills under this export (the specific refusal
        # first), then content as its sets declare it (in the import). New items come from
        # this export's sets, so their stills lie under it.
        check_stills(store, export)
        new, already = import_export(store, export)
        # After the items: a store whose recorded roster disagrees with this export's manifest is
        # refused before the run directory is made. The export carried no manifest -> unrecorded.
        split = import_split(store, export)
        # Made before the replay, so a failure here costs no GPU time and one after it cannot
        # lose the run's place; run.json is written once the replay ends.
        try:
            run_dir.mkdir(parents=True)
        except OSError as error:
            raise ReplayRefused(f"cannot create the run directory {run_dir} ({error})") from error
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
    record = {
        "replay_id": replay_id,
        "model": model.name,
        "served_id": model.served_id,
        "transport": model.transport,
        "url": url,
        "build": build,
        **ran_under,
        "export": str(export),
        "store": str(store_path),
        "eval_run_id": report["run_id"],
        "imported_new": new,
        "already_imported": already,
        "limit": limit,
        **split,
        "commit": git_commit(),
        "started_utc": started.isoformat(timespec="seconds"),
        "report": report,
    }
    (run_dir / "run.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return ReplayResult(replay_id, run_dir, report)
