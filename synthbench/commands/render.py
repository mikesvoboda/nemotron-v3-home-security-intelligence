"""`render --batch <b>`: render each frozen event's pending attempt through ComfyUI.

Agent-driven design §3 step 4. It yields to the flagship before every image (§5.2) and starts
no new image once its time budget is spent (plan ruling P3-R10); each run resumes where the last
one stopped. A failed job is recorded and retried on the next run. The third failed job on one
attempt fails its event: render marks it `failed` in the index, renders the rest, and exits 2
once; later runs skip it. A renderer that stops answering, or an unknown flagship state, stops
the run (exit 2); an unreachable renderer is recorded but does not count as a failed job.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections.abc import Callable, Mapping, Sequence
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
    read_index,
    replace_json,
    taxonomy,
    write_new_bytes,
)
from synthbench.contract.corpus import BatchRecord, IndexRow
from synthbench.contract.provenance import (
    Attempt,
    FailureKind,
    OutputFile,
    Provenance,
    RenderFailure,
    render_name,
)
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.generate.comfy.client import ComfyClient, ComfyError
from synthbench.generate.render import (
    FLUX2_NEED_GIB,
    RendererUnreachable,
    attempt_graph,
    check_png,
    comfy_url,
    last_family,
    model_hashes,
    wait_for_flagship,
    wait_for_free,
)
from synthbench.status import FlagshipUnknown, flagship_file

DEFAULT_BUDGET_S = 480
# MAX_BUDGET_S + RENDER_TIMEOUT_S = 480 + 90 = 570 s, under the Bash tool's 600 s per-call cap
# (P3-R10): one hung image must not be able to outlive the call the agent renders it in. The
# margin covers start-up, the renderer probe and the last download, which the budget leaves out.
MAX_BUDGET_S = 480
MAX_RENDER_FAILURES = 3
RENDER_TIMEOUT_S = 90.0


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
    if not 30 <= value <= MAX_BUDGET_S:
        raise argparse.ArgumentTypeError(f"budget must be 30..{MAX_BUDGET_S} seconds, got {value}")
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
    failed = {event for event, row in read_index(store).items() if row.status == "failed"}
    pending = [
        (s, p)
        for s, p in _frozen_events(store, record)
        if p.attempts[-1].render is None and s.event_id not in failed
    ]
    # Over the limit but not marked yet: a run that stopped between provenance and the index.
    stuck = [s for s, p in pending if _job_failures(p.attempts[-1]) >= MAX_RENDER_FAILURES]
    _mark_failed(store, stuck)
    todo = [(s, p) for s, p in pending if _job_failures(p.attempts[-1]) < MAX_RENDER_FAILURES]
    if not todo:
        if stuck:
            raise AskOwner(_stuck_message(stuck))
        sys.stdout.write(f"render {batch}: 0 still to render. Next: camera --batch {batch}\n")
        return EXIT_OK
    try:
        return _render_todo(store, batch, pending, todo, stuck, budget_s, env, deps)
    except AskOwner as error:
        # Another stop ended the run: it must still name the events failed before it.
        if stuck and _stuck_message(stuck) not in str(error):
            raise AskOwner(f"{error} {_stuck_message(stuck)}") from error
        raise


def _leave_clip_mode(client: ComfyClient, deps: Deps) -> None:
    """Free the renderer when its last job was not FLUX.2 (ruling H3-R13), and wait until the
    memory is back (H3-R16). FLUX.2 then loads with the first image: the unit's warm-up
    measured 24-48 s, inside RENDER_TIMEOUT_S."""
    try:
        last = last_family(client)
        if last not in ("h3", "other"):
            return
        client.free()
        free = wait_for_free(client, FLUX2_NEED_GIB, clock=deps.clock, sleep=deps.sleep)
    except httpx.TransportError as error:
        raise AskOwner(
            f"the renderer stopped answering ({type(error).__name__}: {error})."
        ) from error
    except (httpx.HTTPStatusError, ComfyError, KeyError) as error:
        raise AskOwner(
            f"cannot switch the renderer back to FLUX.2 ({type(error).__name__}: {error})."
        ) from error
    if free < FLUX2_NEED_GIB:
        raise AskOwner(
            f"after freeing the renderer the GPU has {free:.1f} GiB free; FLUX.2 needs "
            f"{FLUX2_NEED_GIB:.0f} GiB: something else holds GPU memory."
        )
    sys.stdout.write(
        f"render: the renderer last ran {last} models; freed them ({free:.1f} GiB free), so "
        "FLUX.2 loads with the first image\n"
    )


def _render_todo(
    store: CorpusStore,
    batch: str,
    pending: Sequence[tuple[Spec, Provenance]],
    todo: Sequence[tuple[Spec, Provenance]],
    stuck: list[Spec],
    budget_s: float,
    env: Mapping[str, str],
    deps: Deps,
) -> int:
    """Render `todo` until the budget, appending events that fail for good to `stuck`."""
    try:
        url = comfy_url(env, deps.get)
    except RendererUnreachable as error:
        raise AskOwner(f"{error}: the renderer is down.") from error
    status_file = flagship_file(env)
    deadline = deps.clock() + budget_s
    rendered = failed_jobs = 0
    client = ComfyClient(url, transport=deps.transport)
    try:
        _leave_clip_mode(client, deps)
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
                    _mark_failed(store, [spec])
                    stuck.append(spec)
    finally:
        client.close()
    left = len(pending) - len(stuck) - rendered
    sys.stdout.write(
        f"render {batch}: {rendered} rendered now, {left} still to render, {failed_jobs} failed "
        f"job(s) this run (ComfyUI at {url})\n"
    )
    sys.stdout.write("Next: run render again.\n" if left else f"Next: camera --batch {batch}\n")
    if stuck:
        raise AskOwner(_stuck_message(stuck))
    return EXIT_OK


def _job_failures(attempt: Attempt) -> int:
    """Failed jobs on the attempt. An unreachable renderer is the owner's, not the job's."""
    return sum(1 for failure in attempt.render_failures if failure.kind == "job")


def _mark_failed(store: CorpusStore, stuck: Sequence[Spec]) -> None:
    append_index(
        store,
        [
            IndexRow(
                event_id=spec.event_id,
                batch=spec.batch,
                scenario=spec.cell.scenario,
                label=spec.label,
                status="failed",
                time=now_iso(),
            )
            for spec in stuck
        ],
    )


def _stuck_message(stuck: Sequence[Spec]) -> str:
    these = "This event is" if len(stuck) == 1 else "These events are"
    return (
        f"{len(stuck)} attempt(s) failed to render {MAX_RENDER_FAILURES} times: "
        f"{', '.join(spec.event_id for spec in stuck)}. {these} now failed, and later runs skip "
        "them; the errors are in provenance.json. The owner may sample replacements."
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
    """Render the event's current attempt. Returns (rendered, its failed jobs)."""
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
            _record_failure(store, prov, error, "unreachable")
            raise AskOwner(
                f"the renderer stopped answering ({type(error).__name__}: {error}); the guard may "
                "have stopped it."
            ) from error
        except (ComfyError, TimeoutError, httpx.HTTPStatusError, KeyError, ValueError) as error:
            return False, _record_failure(store, prov, error, "job")
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
    return True, _job_failures(attempt)


def _record_failure(
    store: CorpusStore, prov: Provenance, error: Exception, kind: FailureKind
) -> int:
    """Record a failure on the current attempt; returns how many failed jobs it has now."""
    failure = RenderFailure(
        time=now_iso(), error=f"{type(error).__name__}: {error}"[:500], kind=kind
    )
    attempt = prov.attempts[-1]
    failed = attempt.updated(render_failures=(*attempt.render_failures, failure))
    replace_json(
        store,
        store.provenance_file(prov.event_id),
        prov.updated(attempts=(*prov.attempts[:-1], failed)),
    )
    return _job_failures(failed)
