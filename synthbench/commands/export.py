"""`export vss`: ready Tier B events in the VSS eval store's import layout (P5a design §2).

An owner command, not the generation agent's. It reads the corpus and never writes it; the sets
go to `$SYNTHBENCH_ROOT/exports/<version>/vss/`.
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
    read_index,
    taxonomy,
)
from synthbench.contract.provenance import Provenance
from synthbench.contract.spec import Spec
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT, CorpusStore
from synthbench.export import vss


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
