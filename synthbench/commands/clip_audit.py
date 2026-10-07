"""`clip audit sample|page|bias`: the owner's blind clip audit (ISS-038, method per OD-15).

Three steps over one round, sharing this module because they share its two files:

  * `sample` freezes `rounds/<r>/audit-draw.jsonl` - the ready-incident census plus the
    benign mirror (and any OD-15 flagged residue the owner hands in with `--flagged`).
    Write-once like every corpus file: an audit interrupted by a render window resumes the
    same set, and a bigger draw is the next round's manifest, not an edit of this one.
  * `page` serves `synthbench.audit.clip_page` on 127.0.0.1 and appends the owner's picks
    to `$SYNTHBENCH_ROOT/audits/<version>/clip-<round>.jsonl`.
  * `bias` reads both files back and prints the survivor-bias report (the measurement's
    disclosure; `synthbench.score.clip_audit_report` does the statistics).

`build_items` is the only component that touches the corpus for the page: the manifest row,
the ready attempt's provenance, and the mp4's bytes. A clip's spec is never opened - its
frozen motion names the scenario's props, which is the strongest leak the audit has.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from synthbench.audit.clip_page import ClipAuditApp, ClipAuditItem, load_answers, serve
from synthbench.audit.clip_sample import audit_draw, classify_intended_motion
from synthbench.commands.clip_rows import motion_rows
from synthbench.commands.common import (
    EXIT_OK,
    CorpusError,
    Parser,
    RequestError,
    now_iso,
    open_round,
    read,
    read_clip_index,
    round_name,
    taxonomy,
    write_new_bytes,
)
from synthbench.contract.clip import ClipProvenance, ClipSpec, RoundRecord
from synthbench.contract.clip_audit import ClipAuditDrawRow, ClipAuditFlagRow
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT, CorpusStore
from synthbench.taxonomy.model import Taxonomy

DEFAULT_PORT = 8766
MANIFEST = "audit-draw.jsonl"


def add_parser(actions: argparse._SubParsersAction[Parser]) -> None:
    audit = actions.add_parser(
        "audit",
        help="the owner's blind clip audit: sample the draw, serve the page, print the bias",
        allow_abbrev=False,
    )
    steps = audit.add_subparsers(dest="clip_audit_step", required=True, parser_class=Parser)
    _add_sample(steps)
    _add_page(steps)
    _add_bias(steps)


def _add_sample(steps: argparse._SubParsersAction[Parser]) -> None:
    parser = steps.add_parser(
        "sample", help="freeze the round's blind audit draw (write-once)", allow_abbrev=False
    )
    parser.add_argument(
        "--round", dest="round_name", type=round_name, required=True, help="round name"
    )
    parser.add_argument(
        "--flagged",
        type=Path,
        default=None,
        help="a machine pre-screen's flagged-clip rows (ClipAuditFlagRow jsonl) to union in",
    )
    parser.set_defaults(run=sample)


def _add_page(steps: argparse._SubParsersAction[Parser]) -> None:
    parser = steps.add_parser(
        "page", help="serve the blind audit page for the drawn set on 127.0.0.1 (owner)",
        allow_abbrev=False,
    )  # fmt: skip
    parser.add_argument(
        "--round", dest="round_name", type=round_name, required=True, help="round name"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"loopback port (default {DEFAULT_PORT})"
    )
    parser.set_defaults(run=page)


def _add_bias(steps: argparse._SubParsersAction[Parser]) -> None:
    parser = steps.add_parser(
        "bias", help="print the survivor-bias report over the answered draw (owner)",
        allow_abbrev=False,
    )  # fmt: skip
    parser.add_argument(
        "--round", dest="round_name", type=round_name, required=True, help="round name"
    )
    parser.set_defaults(run=bias)


def clip_audit_log(version: str, round_name: str, env: Mapping[str, str]) -> Path:
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    return root / "audits" / version / f"clip-{round_name}.jsonl"


def draw_file(store: CorpusStore, name: str) -> Path:
    return store.round_dir(name) / MANIFEST


def read_draw(store: CorpusStore, name: str) -> list[ClipAuditDrawRow]:
    """The frozen manifest (exit 1 when the draw was never sampled)."""
    path = draw_file(store, name)
    if not path.exists():
        raise RequestError(
            f"round {name} has no audit draw; run clip audit sample --round {name} first"
        )
    try:
        return [
            ClipAuditDrawRow.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise CorpusError("read", path, error) from error


def build_items(store: CorpusStore, name: str) -> list[ClipAuditItem]:
    """The drawn clips as page items: manifest row plus the ready attempt's mp4 bytes -
    the whole of it: no taxonomy, and no spec either (a clip's blind half).

    The clip file itself is checked only for existence by name - `clip check` is the
    command that verifies bytes against sha256s, and the page must stay openable while a
    render window is mid-flight. Every drawn clip is ready, so a missing provenance or clip
    file means the store is not what the manifest says; that is exit 1 the owner can see.
    """
    items: list[ClipAuditItem] = []
    for row in read_draw(store, name):
        path = store.provenance_file(row.event_id)
        if not path.exists():
            raise RequestError(f"{row.event_id} has no provenance.json; the draw names no clip")
        prov = read(store, path, ClipProvenance)
        output = prov.attempts[-1].clip
        clip_path = store.event_dir(row.event_id) / (output.path if output else "")
        if output is None or not clip_path.is_file():
            raise RequestError(
                f"{row.event_id} is drawn but its clip file is not in the store; run clip "
                "render, or restore it"
            )
        items.append(ClipAuditItem(row=row, clip_path=clip_path))
    return items


def build_app(
    tax: Taxonomy, store: CorpusStore, name: str, env: Mapping[str, str], port: int
) -> ClipAuditApp:
    """The page over this round's draw and this version's clip answer log."""
    return ClipAuditApp(
        build_items(store, name), clip_audit_log(tax.version, name, env), now_iso, port=port
    )


# -- sample ---------------------------------------------------------------------------


def sample(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_round(tax, env, args.round_name)
    manifest = draw_file(store, record.name)
    if manifest.exists():
        raise RequestError(
            f"round {record.name}'s audit draw is already frozen at {manifest}. The audit "
            "runs on the frozen set; clips that became ready since then join the NEXT "
            "round's draw."
        )
    flagged = _flagged(args.flagged, record)
    specs = [read(store, store.spec_file(e), ClipSpec) for e in record.event_ids]
    statuses = {e: row.status for e, row in read_clip_index(store).items()}
    rows = audit_draw(
        specs, motion_rows(store, record), statuses, round_name=record.name, flagged=flagged
    )
    if not rows:
        raise RequestError(
            f"round {record.name} has no ready clip to audit; the draw is ready clips only, "
            "so finish clip render and clip triage first"
        )
    data = "".join(row.model_dump_json() + "\n" for row in rows).encode(encoding="utf-8")
    write_new_bytes(store, manifest, data)
    counts: Counter[str] = Counter(row.basis for row in rows)
    sys.stdout.write(
        f"audit sample {record.name}: census {counts['ready-census']}, benign "
        f"{counts['benign-stratified']}, flagged {counts['flagged']}\n  {manifest}\n"
        f"Next: clip audit page --round {record.name}\n"
    )
    return EXIT_OK


def _flagged(path: Path | None, record: RoundRecord) -> list[ClipAuditFlagRow]:
    """The owner's pre-screen rows (OD-15 item 1), every one naming a clip of this round.

    Checked before anything is written: a partly-applied pre-screen is no pre-screen, so a
    row for another round's clip fails the whole run, not that row.
    """
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RequestError(f"cannot read {path} ({type(error).__name__}); rewrite it") from error
    rows: list[ClipAuditFlagRow] = []
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = ClipAuditFlagRow.model_validate_json(line)
        except ValidationError as error:
            problems.append(f"line {number}: not a flagged row ({error.errors()[0]['msg']})")
            continue
        if row.event_id not in record.event_ids:
            problems.append(f"line {number}: {row.event_id} is not in round {record.name}")
            continue
        rows.append(row)
    if problems:
        raise RequestError(f"{path}:\n  " + "\n  ".join(problems))
    return rows


# -- page and bias ---------------------------------------------------------------------


def page(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_round(tax, env, args.round_name)
    app = build_app(tax, store, record.name, env, args.port)
    done = sum(1 for item in app.items if app.answered(item))
    sys.stdout.write(
        f"clip audit {record.name}: {len(app.items)} clips, {done} fully answered; answers go "
        f"to {app.log}\n  open http://127.0.0.1:{args.port}/ (remote: ssh -L {args.port}:"
        f"127.0.0.1:{args.port} <this host>); Ctrl-C stops. The page shows the clip and the"
        " conditions only - no scenario, label or motion.\n"
    )
    sys.stdout.flush()
    try:
        serve(app)
    except KeyboardInterrupt:
        pass
    except OSError as error:
        raise RequestError(
            f"cannot listen on 127.0.0.1:{args.port} ({error}); pick another --port"
        ) from error
    return EXIT_OK


def _population(
    store: CorpusStore, record: RoundRecord, statuses: Mapping[str, str]
) -> dict[str, tuple[str, str]]:
    """Every clip of the round with a frozen motion, as (intended-motion class, outcome) -
    the survivor denominator the report prints.

    A clip with no motions.jsonl row is left out rather than counted as `other`: never
    prompted, it has no intended motion to be a survivor OF, so it belongs to no class. (A
    clip whose motion matches no keyword family does count, and the report prints that count
    out loud.) The outcome collapses the six index statuses to the three the report reads:
    `ready` and `failed` stand, everything else - sampled, prompted, rendered and awaiting
    triage, rerolled - is `open`, because a clip H3 has not finished deciding survived
    nothing yet.
    """
    population: dict[str, tuple[str, str]] = {}
    for event_id, motion in motion_rows(store, record).items():
        status = statuses.get(event_id, "")
        outcome = status if status in ("ready", "failed") else "open"
        population[event_id] = (classify_intended_motion(motion), outcome)
    return population


def bias(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store, record = open_round(tax, env, args.round_name)
    from synthbench.score.clip_audit_report import report  # lazy: it borrows backend's Wilson

    answers, _ = load_answers(clip_audit_log(tax.version, record.name, env))
    statuses = {e: row.status for e, row in read_clip_index(store).items()}
    sys.stdout.write(
        report(
            tax,
            record.name,
            tax.version,
            read_draw(store, record.name),
            answers,
            _population(store, record, statuses),
            now_iso(),
        )
    )
    return EXIT_OK
