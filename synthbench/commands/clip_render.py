"""`clip render --round <r>`: render each frozen clip's pending attempt with MiniMax-H3 turbo.

Clips design §4. Before its first clip it reads ComfyUI's history. Unless H3 ran last:

- it frees the renderer;
- it checks that the GPU has room for H3's peak;
- it renders a short warm-up clip, so H3 is resident (rulings H3-R15, H3-R16);
- it logs the switch in the round's switches.jsonl.

It yields to the flagship before every clip, and starts a clip only while the clip's timeout
still fits in the agent's 600 s call (H3-R6). Each run resumes where the last one stopped.
Failures are handled as `render` handles them: three failed jobs fail the clip, and an
unreachable renderer stops the run. Each clip gets a 6-frame strip for the agent's triage.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Mapping, Sequence

import httpx

from synthbench.clips import settings as clip_settings
from synthbench.clips.render import (
    WARMUP_IMAGE,
    check_clip,
    clip_graph,
    fit_input,
    strip,
    warmup_graph,
)
from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    append_clip_index,
    append_jsonl,
    now_iso,
    open_round,
    read,
    read_bytes,
    read_clip_index,
    replace_json,
    round_name,
    taxonomy,
    write_new_bytes,
)
from synthbench.commands.render import MAX_RENDER_FAILURES, Deps
from synthbench.contract.clip import (
    ClipAttempt,
    ClipIndexRow,
    ClipProvenance,
    ClipSpec,
    RoundRecord,
    SwitchRow,
    clip_name,
    strip_name,
)
from synthbench.contract.provenance import FailureKind, OutputFile, Provenance, RenderFailure
from synthbench.contract.store import CorpusStore
from synthbench.generate.comfy.client import ComfyClient, ComfyError
from synthbench.generate.render import (
    RendererUnreachable,
    comfy_url,
    last_family,
    wait_for_flagship,
    wait_for_free,
)
from synthbench.status import FlagshipUnknown, flagship_file

CALL_LIMIT_S = (
    570.0  # the agent's Bash call is 600 s (P3-R10); start-up and downloads take the rest
)
# Measured by the clips probe beside the flagship (docs/benchmarks/synthbench/clips-probes.md):
# 243-frame clips took 327.0-328.7 s; H3's load plus a 22-frame clip 61.2 s; the renderer's
# peak was 48.3 GiB.
CLIP_TIMEOUT_S = 500.0  # 1.5 x 328.7 s, rounded up to 10 (ruling H3-R7, amended)
WARMUP_TIMEOUT_S = 240.0  # 61.2 s with warm page cache; room for a cold load of the weights
H3_PEAK_GIB = 49.0  # 48.3 GiB, rounded up
RESERVE_GIB = 4.0  # the renderer's --reserve-vram 4 (agent-driven design §1)


def add_parser(actions: argparse._SubParsersAction[Parser]) -> None:
    parser = actions.add_parser(
        "render",
        help="render the round's pending clips with MiniMax-H3 turbo (switching the renderer "
        "to H3 when needed), yielding to the flagship",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--round", dest="round_name", type=round_name, required=True, help="round name"
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    return execute(args.round_name, env, Deps())


def execute(round_name: str, env: Mapping[str, str], deps: Deps) -> int:
    tax = taxonomy()
    store, record = open_round(tax, env, round_name)
    failed = {e for e, row in read_clip_index(store).items() if row.status == "failed"}
    pending = [
        (s, p)
        for s, p in _frozen_clips(store, record)
        if p.attempts[-1].clip is None and s.event_id not in failed
    ]
    stuck = [s for s, p in pending if _job_failures(p.attempts[-1]) >= MAX_RENDER_FAILURES]
    _mark_failed(store, stuck)
    todo = [(s, p) for s, p in pending if _job_failures(p.attempts[-1]) < MAX_RENDER_FAILURES]
    if not todo:
        if stuck:
            raise AskOwner(_stuck_message(stuck))
        sys.stdout.write(
            f"clip render {record.name}: 0 still to render. Next: open each new strip, write "
            f"triage.jsonl, then clip triage --round {record.name}\n"
        )
        return EXIT_OK
    try:
        return _render_todo(store, record, pending, todo, stuck, env, deps)
    except AskOwner as error:
        if stuck and _stuck_message(stuck) not in str(error):
            raise AskOwner(f"{error} {_stuck_message(stuck)}") from error
        raise


def _render_todo(
    store: CorpusStore,
    record: RoundRecord,
    pending: Sequence[tuple[ClipSpec, ClipProvenance]],
    todo: Sequence[tuple[ClipSpec, ClipProvenance]],
    stuck: list[ClipSpec],
    env: Mapping[str, str],
    deps: Deps,
) -> int:
    try:
        url = comfy_url(env, deps.get)
    except RendererUnreachable as error:
        raise AskOwner(f"{error}: the renderer is down.") from error
    status_file = flagship_file(env)
    latest_start = deps.clock() + CALL_LIMIT_S - CLIP_TIMEOUT_S
    rendered = failed_jobs = 0
    client = ComfyClient(url, transport=deps.transport)
    try:
        _enter_clip_mode(store, record, client, deps)
        for spec, prov in todo:
            if deps.clock() > latest_start:
                break
            try:
                ready = wait_for_flagship(
                    status_file,
                    deadline=latest_start,
                    clock=deps.clock,
                    sleep=deps.sleep,
                    now=deps.now,
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
        f"clip render {record.name}: {rendered} rendered now, {left} still to render, "
        f"{failed_jobs} failed job(s) this run (ComfyUI at {url})\n"
    )
    sys.stdout.write(
        "Next: run clip render again.\n"
        if left
        else f"Next: open each new strip, write triage.jsonl, then clip triage --round "
        f"{record.name}\n"
    )
    if stuck:
        raise AskOwner(_stuck_message(stuck))
    return EXIT_OK


def _enter_clip_mode(
    store: CorpusStore, record: RoundRecord, client: ComfyClient, deps: Deps
) -> None:
    """Switch the renderer to H3 unless H3 ran last (§4.1), and log the switch."""
    try:
        last = last_family(client)
        if last == "h3":
            return
        if last is not None:
            client.free()
        need = H3_PEAK_GIB + RESERVE_GIB
        free_gib = wait_for_free(client, need, clock=deps.clock, sleep=deps.sleep)
        if free_gib < need:
            raise AskOwner(
                f"after freeing the renderer the GPU has {free_gib:.1f} GiB free, and H3 needs "
                f"{need:.0f} GiB: something else holds GPU memory."
            )
        started = deps.clock()
        name = client.upload_png("synthbench-warmup-h3.png", fit_input(WARMUP_IMAGE.read_bytes()))
        client.run(warmup_graph(name), timeout_s=WARMUP_TIMEOUT_S, sleep=deps.sleep)
        seconds = round(deps.clock() - started, 1)
    except httpx.TransportError as error:
        raise AskOwner(
            f"the renderer stopped answering ({type(error).__name__}: {error}); the guard may "
            "have stopped it."
        ) from error
    except (ComfyError, TimeoutError, httpx.HTTPStatusError, KeyError, ValueError) as error:
        raise AskOwner(
            f"switching the renderer to H3 failed ({type(error).__name__}: {error})."
        ) from error
    row = SwitchRow(
        time=now_iso(),
        previous=last or "none",
        free_gib=round(free_gib, 1),
        warmup_seconds=seconds,
    )
    append_jsonl(store, store.round_dir(record.name) / "switches.jsonl", [row])
    sys.stdout.write(
        f"clip render: switched the renderer to H3 (it last ran {last or 'nothing'}); "
        f"{free_gib:.1f} GiB free, warm-up {seconds:.1f} s\n"
    )


def _job_failures(attempt: ClipAttempt) -> int:
    """Failed jobs on the attempt. An unreachable renderer is the owner's, not the job's."""
    return sum(1 for failure in attempt.render_failures if failure.kind == "job")


def _mark_failed(store: CorpusStore, stuck: Sequence[ClipSpec]) -> None:
    append_clip_index(
        store,
        [
            ClipIndexRow(
                event_id=spec.event_id,
                round=spec.round,
                source=spec.source.event_id,
                scenario=spec.cell.scenario,
                label=spec.label,
                status="failed",
                time=now_iso(),
            )
            for spec in stuck
        ],
    )


def _stuck_message(stuck: Sequence[ClipSpec]) -> str:
    these = "This clip is" if len(stuck) == 1 else "These clips are"
    return (
        f"{len(stuck)} clip attempt(s) failed to render {MAX_RENDER_FAILURES} times: "
        f"{', '.join(spec.event_id for spec in stuck)}. {these} now failed, and later runs skip "
        "them; the errors are in provenance.json."
    )


def _frozen_clips(store: CorpusStore, record: RoundRecord) -> list[tuple[ClipSpec, ClipProvenance]]:
    clips: list[tuple[ClipSpec, ClipProvenance]] = []
    unfrozen: list[str] = []
    for event_id in record.event_ids:
        spec = read(store, store.spec_file(event_id), ClipSpec)
        path = store.provenance_file(event_id)
        if not spec.frozen or not path.exists():
            unfrozen.append(event_id)
            continue
        clips.append((spec, read(store, path, ClipProvenance)))
    if unfrozen:
        shown = ", ".join(unfrozen[:5]) + (" ..." if len(unfrozen) > 5 else "")
        raise RequestError(
            f"{len(unfrozen)} clip(s) of round {record.name} have no frozen motion yet "
            f"({shown}); run clip check --round {record.name} first"
        )
    return clips


def _source_render(store: CorpusStore, spec: ClipSpec) -> bytes:
    """The pinned source render's bytes (exit 2 if they changed: clip check says why)."""
    source = spec.source
    attempt = read(store, store.provenance_file(source.event_id), Provenance).attempts[source.k - 1]
    if attempt.render is None:
        raise AskOwner(f"{source.event_id} attempt {source.k} has no render; run clip check.")
    data = read_bytes(store.event_dir(source.event_id) / attempt.render.path)
    if hashlib.sha256(data).hexdigest() != source.render_sha256:
        raise AskOwner(
            f"{spec.event_id}: the source render of {source.event_id} changed; run clip check."
        )
    return data


def _render_one(
    store: CorpusStore, spec: ClipSpec, prov: ClipProvenance, client: ComfyClient, deps: Deps
) -> tuple[bool, int]:
    """Render the clip's current attempt. Returns (rendered, its failed jobs)."""
    attempt = prov.attempts[-1]
    event_dir = store.event_dir(spec.event_id)
    name = clip_name(attempt.k, attempt.seed)
    path = event_dir / name
    try:
        fitted = fit_input(_source_render(store, spec))
    except ValueError as error:
        raise AskOwner(f"{spec.event_id}: the source render is not an image ({error}).") from error
    seconds: float | None = None
    if path.exists():  # stored by a run that stopped before recording it: adopt it
        data = read_bytes(path)
        try:
            count = check_clip(data)
        except ValueError as error:
            raise AskOwner(
                f"{path} exists, is not recorded, and is not a clip ({error})."
            ) from error
    else:
        started = deps.clock()
        try:
            uploaded = client.upload_png(f"synthbench-{spec.event_id}-a{attempt.k}.png", fitted)
            clips = client.run(
                clip_graph(spec, attempt, uploaded), timeout_s=CLIP_TIMEOUT_S, sleep=deps.sleep
            )
            if len(clips) != 1:
                raise ValueError(f"expected one clip, got {len(clips)}")
            data = clips[0]
            count = check_clip(data)
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
    strip_path = event_dir / strip_name(attempt.k, attempt.seed)
    if strip_path.exists():
        sheet = read_bytes(strip_path)
    else:
        sheet = strip(data, count)
        write_new_bytes(store, strip_path, sheet)
    done = attempt.updated(
        input_sha256=hashlib.sha256(fitted).hexdigest(),
        clip=OutputFile(path=name, sha256=hashlib.sha256(data).hexdigest()),
        strip=OutputFile(
            path=strip_name(attempt.k, attempt.seed), sha256=hashlib.sha256(sheet).hexdigest()
        ),
        render_seconds=seconds,
        models=clip_settings.model_hashes(),
    )
    replace_json(
        store,
        store.provenance_file(spec.event_id),
        prov.updated(attempts=(*prov.attempts[:-1], done)),
    )
    append_clip_index(
        store,
        [
            ClipIndexRow(
                event_id=spec.event_id,
                round=spec.round,
                source=spec.source.event_id,
                scenario=spec.cell.scenario,
                label=spec.label,
                status="rendered",
                time=now_iso(),
            )
        ],
    )
    return True, _job_failures(attempt)


def _record_failure(
    store: CorpusStore, prov: ClipProvenance, error: Exception, kind: FailureKind
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
