"""`camera --batch <b>`: a Foscam-style still for each new render (design §3 step 5, §7)."""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Mapping

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    Parser,
    batch_name,
    open_batch,
    read,
    read_bytes,
    read_index,
    replace_json,
    taxonomy,
    write_new_bytes,
)
from synthbench.contract.provenance import OutputFile, Provenance, still_name
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.generate.camera.model import CameraParams, load_params, overlay_time, render_still


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "camera",
        help="turn each new 1280x720 render into a 1920x1080 Foscam-style JPEG still",
        allow_abbrev=False,
    )
    parser.add_argument("--batch", type=batch_name, required=True, help="batch name")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_batch(tax, env, args.batch)
    params = load_params()
    # An event `render` gave up on never gets a render; it is not waiting for one.
    failed = {event for event, row in read_index(store).items() if row.status == "failed"}
    made = waiting = 0
    for event_id in record.event_ids:
        if event_id in failed:
            continue
        spec = read(store, store.spec_file(event_id), Spec)
        path = store.provenance_file(event_id)
        if not spec.frozen or not path.exists():
            continue
        prov = read(store, path, Provenance)
        attempt = prov.attempts[-1]
        if attempt.render is None:
            waiting += 1
        elif attempt.still is None:
            _make_still(store, spec, prov, params)
            made += 1
    sys.stdout.write(
        f"camera {record.name}: {made} still(s) made now; {waiting} attempt(s) still await a "
        "render\n"
    )
    if made:
        sys.stdout.write(
            "Next: open every new still, add its verdict to triage.jsonl, then triage.\n"
        )
    return EXIT_OK


def _make_still(store: CorpusStore, spec: Spec, prov: Provenance, params: CameraParams) -> None:
    attempt = prov.attempts[-1]
    assert attempt.render is not None
    event_dir = store.event_dir(spec.event_id)
    render_file = event_dir / attempt.render.path
    data = read_bytes(render_file)
    if hashlib.sha256(data).hexdigest() != attempt.render.sha256:
        raise AskOwner(f"{render_file} does not match its recorded sha256.")
    stamp = overlay_time(spec.scene_time, spec.cell.weather, attempt.seed)
    try:
        still = render_still(
            data,
            camera=spec.cell.camera,
            lighting=spec.cell.lighting,
            overlay_text=stamp,
            seed=attempt.seed,
            params=params,
        )
    except Exception as error:  # any stage failure on a verified render is the owner's to see
        raise AskOwner(
            f"the camera stage failed on {render_file} ({type(error).__name__}: {error})."
        ) from error
    name = still_name(attempt.k, attempt.seed)
    target = event_dir / name
    if target.exists():  # stored by a run that stopped before recording it
        if read_bytes(target) != still:
            raise AskOwner(
                f"{target} exists, is not recorded, and differs from what the camera stage makes now."
            )
    else:
        write_new_bytes(store, target, still)
    done = attempt.updated(
        still=OutputFile(path=name, sha256=hashlib.sha256(still).hexdigest()),
        camera_params=params.id,
        overlay_time=stamp,
    )
    replace_json(
        store,
        store.provenance_file(spec.event_id),
        prov.updated(attempts=(*prov.attempts[:-1], done)),
    )
