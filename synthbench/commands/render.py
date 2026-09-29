"""`render --batch <b>`: render each frozen event's pending attempt through ComfyUI.

Agent-driven design §3 step 4. It yields to the flagship before every image (§5.2) and starts
no new image once its time budget is spent (plan ruling P3-R10); each run resumes where the last
one stopped. A failed job is recorded and retried on the next run; three failures on one
attempt, a renderer that stops answering, or an unknown flagship state stop the run (exit 2).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    append_index,
    batch_name,
    now_iso,
    open_batch,
    read,
    read_bytes,
    replace_json,
    taxonomy,
    write_new_bytes,
)
from synthbench.contract.corpus import BatchRecord, IndexRow
from synthbench.contract.provenance import OutputFile, Provenance, RenderFailure, render_name
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.generate.comfy.client import ComfyClient, ComfyError
from synthbench.generate.render import (
    RendererUnreachable,
    attempt_graph,
    check_png,
    comfy_url,
    model_hashes,
    wait_for_flagship,
)
from synthbench.status import FlagshipUnknown, flagship_file

DEFAULT_BUDGET_S = 480
MAX_RENDER_FAILURES = 3
RENDER_TIMEOUT_S = 600.0


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Deps:
    """What render reaches outside the corpus; tests pass fakes."""

    transport: httpx.BaseTransport | None = None
    get: Callable[..., httpx.Response] = httpx.get
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = _utc_now


def _budget(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"budget must be whole seconds: {text!r}") from None
    if not 30 <= value <= 3600:
        raise argparse.ArgumentTypeError(f"budget must be 30..3600 seconds, got {value}")
    return value


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "render",
        help="render the batch's pending attempts at 1280x720 through ComfyUI, yielding to the flagship",
        allow_abbrev=False,
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.add_argument(
        "--budget-seconds",
        type=_budget,
        default=DEFAULT_BUDGET_S,
        help=f"start no new image after this many seconds (default {DEFAULT_BUDGET_S}); "
        "run render again to continue",
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    return execute(args.batch, args.budget_seconds, env, Deps())


def execute(batch: str, budget_s: float, env: Mapping[str, str], deps: Deps) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, batch)
    pending = [(s, p) for s, p in _frozen_events(store, record) if p.attempts[-1].render is None]
    stuck = [
        s.event_id for s, p in pending if len(p.attempts[-1].render_failures) >= MAX_RENDER_FAILURES
    ]
    todo = [(s, p) for s, p in pending if s.event_id not in stuck]
    if not todo:
        if stuck:
            raise AskOwner(_stuck_message(stuck))
        sys.stdout.write(f"render {batch}: nothing to render. Next: camera --batch {batch}\n")
        return EXIT_OK
    try:
        url = comfy_url(env, deps.get)
    except RendererUnreachable as error:
        raise AskOwner(f"{error}: the renderer is down.") from error
    status_file = flagship_file(env)
    deadline = deps.clock() + budget_s
    rendered = failed_jobs = 0
    client = ComfyClient(url, transport=deps.transport)
    try:
        for spec, prov in todo:
            if deps.clock() >= deadline:
                break
            try:
                ready = wait_for_flagship(
                    status_file, deadline=deadline, clock=deps.clock, sleep=deps.sleep, now=deps.now
                )
            except FlagshipUnknown as error:
                raise AskOwner(f"{error}.") from error
            if not ready:
                break
            done, failures = _render_one(store, spec, prov, client, deps)
            if done:
                rendered += 1
            else:
                failed_jobs += 1
                if failures >= MAX_RENDER_FAILURES:
                    stuck.append(spec.event_id)
    finally:
        client.close()
    left = len(pending) - rendered
    sys.stdout.write(
        f"render {batch}: {rendered} rendered now, {left} still to render, {failed_jobs} failed "
        f"job(s) this run (ComfyUI at {url})\n"
    )
    sys.stdout.write("Next: run render again.\n" if left else f"Next: camera --batch {batch}\n")
    if stuck:
        raise AskOwner(_stuck_message(stuck))
    return EXIT_OK


def _stuck_message(stuck: list[str]) -> str:
    return (
        f"{len(stuck)} attempt(s) failed to render {MAX_RENDER_FAILURES} times: "
        f"{', '.join(stuck)}. Their errors are in provenance.json."
    )


def _frozen_events(store: CorpusStore, record: BatchRecord) -> list[tuple[Spec, Provenance]]:
    events: list[tuple[Spec, Provenance]] = []
    unfrozen: list[str] = []
    for event_id in record.event_ids:
        spec = read(store, store.spec_file(event_id), Spec)
        path = store.provenance_file(event_id)
        if not spec.frozen or not path.exists():
            unfrozen.append(event_id)
            continue
        events.append((spec, read(store, path, Provenance)))
    if unfrozen:
        shown = ", ".join(unfrozen[:5]) + (" ..." if len(unfrozen) > 5 else "")
        raise RequestError(
            f"{len(unfrozen)} event(s) of batch {record.name} have no frozen prompt yet "
            f"({shown}); run check --batch {record.name} first"
        )
    return events


def _render_one(
    store: CorpusStore, spec: Spec, prov: Provenance, client: ComfyClient, deps: Deps
) -> tuple[bool, int]:
    """Render the event's current attempt. Returns (rendered, failures recorded for it)."""
    attempt = prov.attempts[-1]
    name = render_name(attempt.k, attempt.seed)
    path = store.event_dir(spec.event_id) / name
    seconds: float | None = None
    if path.exists():  # stored by a run that stopped before recording it: adopt it
        data = read_bytes(path)
        try:
            check_png(data)
        except ValueError as error:
            raise AskOwner(
                f"{path} exists, is not recorded, and is not a render ({error})."
            ) from error
    else:
        started = deps.clock()
        try:
            images = client.run(
                attempt_graph(spec, attempt), timeout_s=RENDER_TIMEOUT_S, sleep=deps.sleep
            )
            if len(images) != 1:
                raise ValueError(f"expected one image, got {len(images)}")
            data = images[0]
            check_png(data)
        except httpx.TransportError as error:
            _record_failure(store, prov, error)
            raise AskOwner(
                f"the renderer stopped answering ({type(error).__name__}: {error}); the guard may "
                "have stopped it."
            ) from error
        except (ComfyError, TimeoutError, httpx.HTTPStatusError, KeyError, ValueError) as error:
            return False, _record_failure(store, prov, error)
        seconds = round(deps.clock() - started, 1)
        write_new_bytes(store, path, data)
    done = attempt.updated(
        render=OutputFile(path=name, sha256=hashlib.sha256(data).hexdigest()),
        render_seconds=seconds,
        models=model_hashes(),
    )
    replace_json(
        store,
        store.provenance_file(spec.event_id),
        prov.updated(attempts=(*prov.attempts[:-1], done)),
    )
    append_index(
        store,
        [
            IndexRow(
                event_id=spec.event_id,
                batch=spec.batch,
                scenario=spec.cell.scenario,
                label=spec.label,
                status="rendered",
                time=now_iso(),
            )
        ],
    )
    return True, len(attempt.render_failures)


def _record_failure(store: CorpusStore, prov: Provenance, error: Exception) -> int:
    """Record a failed job on the current attempt; returns how many it has now."""
    attempt = prov.attempts[-1]
    failure = RenderFailure(time=now_iso(), error=f"{type(error).__name__}: {error}"[:500])
    failures = (*attempt.render_failures, failure)
    replace_json(
        store,
        store.provenance_file(prov.event_id),
        prov.updated(attempts=(*prov.attempts[:-1], attempt.updated(render_failures=failures))),
    )
    return len(failures)
