"""`export vss`: ready Tier B events in the VSS eval store's import layout (P5a design §2).

An owner command, not the generation agent's. It reads the corpus and never writes it; the sets
go to `$SYNTHBENCH_ROOT/exports/<version>/vss/`. `--sequences` additionally samples each READY
clip's triaged mp4 into a multi-frame set under `<out>/sequences/` (ISS-037); the stills' layout
and split are untouched by it.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from synthbench.commands.common import (
    EXIT_OK,
    AskOwner,
    CorpusError,
    Parser,
    RequestError,
    check_manifest,
    read,
    read_bytes,
    read_clip_index,
    read_index,
    taxonomy,
)
from synthbench.contract.clip import ClipProvenance, ClipSpec
from synthbench.contract.provenance import Provenance
from synthbench.contract.spec import Spec
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT, CorpusStore
from synthbench.export import sequence, vss
from synthbench.taxonomy.model import Taxonomy


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    export = commands.add_parser(
        "export", help="write corpus events in layouts other tools read (owner)", allow_abbrev=False
    )
    targets = export.add_subparsers(dest="export_target", required=True, parser_class=Parser)
    parser = targets.add_parser(
        "vss",
        help="ready Tier B events in the VSS eval store's import layout",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="export directory (default: $SYNTHBENCH_ROOT/exports/<version>/vss)",
    )
    parser.add_argument(
        "--sequences",
        type=int,
        choices=sorted(sequence.FRAME_FRACTIONS),
        default=None,
        help="also export each READY clip as a multi-frame sequence of N JPEG frames "
        "(ISS-037); the stills are still exported, and the split never sees the sequences",
    )
    parser.set_defaults(run=run_vss)


def export_dir(version: str, env: Mapping[str, str]) -> Path:
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    return root / "exports" / version / "vss"


def run_vss(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    store = CorpusStore.from_env(tax.version, env)
    out: Path = args.out if args.out is not None else export_dir(tax.version, env)
    # The corpus is append-only: no export, nor the staging directory written beside it, goes
    # inside it (resolved, so `..` and symlinks cannot slip one in).
    if out.resolve().is_relative_to(store.root.resolve()):
        raise RequestError(
            f"--out {out} is inside the corpus ({store.root}), which is append-only; export "
            "under $SYNTHBENCH_ROOT/exports/"
        )
    if not store.index_file.exists():
        raise RequestError(f"corpus version {tax.version} has no events; nothing to export")
    check_manifest(store)
    if args.sequences is not None:
        run_sequences(store, tax, out, frames=args.sequences)
    written = unchanged = 0
    skipped: Counter[str] = Counter()
    # The split's population (ISS-016 design §2): this export's scenarios and their item counts by
    # label, which is what the holdout is drawn from and what the manifest's totals read off.
    items: dict[str, dict[str, int]] = {}
    for event_id, row in sorted(read_index(store).items()):
        if row.status != "ready":
            skipped[row.status] += 1
            continue
        spec = read(store, store.spec_file(event_id), Spec)
        category = vss.category_of(spec)
        if spec.tier != "B":
            skipped[f"tier {spec.tier}"] += 1
            continue
        if category is None:
            skipped["ambiguous"] += 1
            continue
        if vss.CATEGORY_LABEL[category] != spec.label:
            raise AskOwner(
                f"{event_id} is labeled {spec.label} but its group {spec.cell.group} exports as "
                f"{category}/ ({vss.CATEGORY_LABEL[category]}): the taxonomy disagrees with itself."
            )
        items.setdefault(spec.cell.scenario, {"benign": 0, "incident": 0})[spec.label] += 1
        still = read(store, store.provenance_file(event_id), Provenance).attempts[-1].still
        if still is None:
            raise AskOwner(f"{event_id} is ready but its last attempt has no still.")
        data = read_bytes(store.event_dir(event_id) / still.path)
        if hashlib.sha256(data).hexdigest() != still.sha256:
            raise AskOwner(f"{event_id}'s still does not match its recorded sha256.")
        try:
            if vss.write_set(out, category, event_id, vss.set_files(spec, data, still.sha256)):
                written += 1
            else:
                unchanged += 1
        except vss.ExportConflict as error:
            raise AskOwner(f"{error}.") from error
        except OSError as error:
            raise CorpusError("write", out / category / event_id, error) from error
    not_exported = ", ".join(f"{why} {n}" for why, n in sorted(skipped.items())) or "none"
    sys.stdout.write(
        f"export vss {tax.version}: {written} written now, {unchanged} unchanged; not exported: "
        f"{not_exported}\n  {out}\n"
    )
    if tax.version not in vss.SPLIT_SEEDS:
        # No fallback seed (design §2): a new corpus gets its own pre-registered string first.
        # B6's optionality is this same path — sets exported, split unrecorded, exit 0.
        sys.stdout.write(f"no split registered for {tax.version}\n")
        return EXIT_OK
    for scenario, counts in sorted(items.items()):
        if counts["benign"] and counts["incident"]:
            raise AskOwner(
                f"{scenario} contributes both labels, but the split's unit is the scenario and a "
                "scenario sits in exactly one arm: the split's premise has broken."
            )
    if not items:
        # A registered seed is not a population: nothing was exported, so there is nothing to
        # draw, and the degenerate manifest a draw over the empty set implies would burn the
        # create-once slot against the real export that follows. B6's path instead: sets only,
        # split unrecorded, exit 0 — and the slot stays fresh for the export that has events.
        sys.stdout.write(f"no ready tier B events for {tax.version}: no split written\n")
        return EXIT_OK
    # Only a scenario with an incident item can be drawn; benign joins the arm table as dev (B1).
    incident = sorted(name for name, counts in items.items() if counts["incident"])
    arm = {
        row["scenario"]: row["arm"] for row in vss.draw_split(tax.version, incident)["scenarios"]
    }
    arm |= {name: "dev" for name in items if name not in arm}
    try:
        manifest = vss.split_manifest_document(tax.version, arm, items_by_scenario=items)
        write = vss.write_split(out, manifest)
    except vss.ExportConflict as error:
        raise AskOwner(f"{error}.") from error
    items_by_arm = manifest["items"]
    sys.stdout.write(
        f"split {tax.version}: holdout_k {manifest['holdout_k']}; "
        f"holdout {', '.join(manifest['arms']['holdout']) or 'none'}; "
        f"dev {', '.join(manifest['arms']['dev']) or 'none'}; "
        f"items holdout {items_by_arm['holdout']['incident']} incident, "
        f"{items_by_arm['holdout']['benign']} benign; "
        f"dev {items_by_arm['dev']['incident']} incident, {items_by_arm['dev']['benign']} benign; "
        f"sha256 {vss.split_sha256(manifest)}{'' if write else ' (unchanged)'}\n"
    )
    return EXIT_OK


def run_sequences(store: CorpusStore, tax: Taxonomy, out: Path, *, frames: int) -> None:
    """`export vss --sequences N`: every READY clip becomes a frame-sampled sequence set.

    ISS-037's corpus, and its honesty is in the details. The set's truth is the clip spec's
    declared truth (the same cell/label/band/subjects the clip was rendered to), exported
    undistributed and unaudited exactly as the clips are — the register records that
    frame-sampled triplets stand in for scripted ones. Only a clip whose TRIAGED mp4 matches
    its recorded sha256 is sampled; the sampling is the fixed FRAME_FRACTIONS, so a set is
    re-derivable from the mp4 and these constants, which is what keeps a create-once export
    checkable by `replay --check-current`.
    """
    sequences_dir = out / sequence.SEQUENCE_DIR
    if sequences_dir.resolve().is_relative_to(store.root.resolve()):
        raise RequestError(  # run_vss already refused this for --out; this guards --out --sequences
            f"--out {out} is inside the corpus ({store.root}), which is append-only; export "
            "under $SYNTHBENCH_ROOT/exports/"
        )
    clip_rows = read_clip_index(store)
    written = unchanged = 0
    skipped: Counter[str] = Counter()
    for event_id in sorted(clip_rows):
        row = clip_rows[event_id]
        if row.status != "ready":
            skipped[row.status] += 1
            continue
        spec = read(store, store.spec_file(event_id), ClipSpec)
        category = vss.category_of(spec)
        if category is None:
            skipped["ambiguous"] += 1
            continue
        if vss.CATEGORY_LABEL[category] != spec.label:
            raise AskOwner(
                f"{event_id} is labeled {spec.label} but its group {spec.cell.group} exports as "
                f"{category}/ ({vss.CATEGORY_LABEL[category]}): the taxonomy disagrees with itself."
            )
        if not spec.frozen:
            raise AskOwner(
                f"{event_id} is ready without a frozen prompt; a ready clip is one the triage "
                "verdicts were written against."
            )
        prov = read(store, store.provenance_file(event_id), ClipProvenance)
        attempt = prov.attempts[-1]
        if attempt.clip is None or attempt.triage is None or attempt.triage.verdict != "ok":
            raise AskOwner(
                f"{event_id} is ready in the index but its last attempt lacks an ok-triaged clip."
            )
        mp4 = read_bytes(store.event_dir(event_id) / attempt.clip.path)
        if hashlib.sha256(mp4).hexdigest() != attempt.clip.sha256:
            raise AskOwner(f"{event_id}'s clip does not match its recorded sha256.")
        try:
            count = sequence.clip_frame_count(mp4)
            indices = sequence.sample_indices(count, frames)
            jpegs, fps = sequence.sample_frames(mp4, indices)
        except ValueError as error:
            raise AskOwner(f"{event_id}: {error}") from error
        offsets = sequence.offsets_ms(indices, fps)
        frame_files = [f"{sequence.FRAME_FILE_STEM}{i + 1}.jpg" for i in range(len(jpegs))]
        times = sequence.sequence_timestamps(spec.scene_time, spec.cell.weather, offsets)
        subjects = [s.model_dump(mode="json", by_alias=True) for s in spec.subjects]
        props = [p.model_dump(mode="json", by_alias=True) for p in spec.props]
        detections = sequence.frame_detections([*spec.subjects, *spec.props], frame_files, times)
        facts = {
            "event_id": spec.event_id,
            "corpus_version": spec.corpus_version,
            "round": spec.round,
            "label": spec.label,
            "risk_band": list(spec.risk_band),
            "scene_time": spec.scene_time,
            "cell": spec.cell.model_dump(mode="json"),
            "subjects": subjects,
            "props": props,
            "source_clip": {
                "path": attempt.clip.path,
                "sha256": attempt.clip.sha256,
                "attempt_k": attempt.k,
                "seed": attempt.seed,
                "frame_count": count,
                "fps": fps,
            },
        }
        files = sequence.sequence_files(
            facts,
            category=category,
            jpeg_frames=jpegs,
            offsets_ms=offsets,
            times=times,
            detections=detections,
            corpus_version=spec.corpus_version,
        )
        try:
            if sequence.write_sequence_set(
                sequences_dir, category, sequence.sequence_name(event_id, frames), files
            ):
                written += 1
            else:
                unchanged += 1
        except vss.ExportConflict as error:  # write_sequence_set delegates to vss.write_set
            raise AskOwner(f"{error}.") from error
        except OSError as error:
            raise CorpusError("write", sequences_dir / category / event_id, error) from error
    not_exported = ", ".join(f"{why} {n}" for why, n in sorted(skipped.items())) or "none"
    sys.stdout.write(
        f"export sequences {tax.version}: {frames}-frame sets; {written} written now, "
        f"{unchanged} unchanged; not exported: {not_exported}\n  {sequences_dir}\n"
    )
