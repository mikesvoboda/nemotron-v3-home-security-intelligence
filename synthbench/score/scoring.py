"""`score`: load replays, their eval store, the export and the audit; write the outputs.

Writes `$SYNTHBENCH_ROOT/runs/scores/<score_id>/`: `results.jsonl` (one row per item per model),
`metrics.json` (the metrics and the run identity), `report.md` and `report.html` (P5a design §5).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.evaluation.eval_store import EvalStore
from backend.evaluation.levels import floor_for_expected_score
from backend.evaluation.vlm_replay import git_commit

from synthbench.audit.page import load_answers
from synthbench.audit.sample import sample as audit_sample
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT
from synthbench.export.sequence import read_sequence_sets
from synthbench.export.vss import (
    SPLIT_FILE,
    ExportedSet,
    read_sets,
    read_split,
    split_sha256,
)
from synthbench.score import report
from synthbench.score.metrics import Item, result_rows, score_models

# 5 (2026-10-07, ISS-037): each `identity.replays[]` block gains `frames_mode` and
# `with_sequences` (how frames reached the wire, and whether the export's sequence sets joined
# the run; `.get()`-based, so a pre-ISS-037 replay records `null`), each `results.jsonl` row
# gains `frames_fed` (what the harness audited that item received, `null` for a pre-audit row)
# and `frames_mode`, and a model block gains `frames` — the same rows bucketed by frames fed —
# only when some row carries the harness audit, so a score over pre-ISS-037 replays keeps the
# version-4 model-block shape. 4 (2026-10-06, ISS-087): each `identity.replays[]` block gains
# `server_settings` — the operator's declaration of what the endpoint was started with, which
# replay cannot observe — and
# each `comparison[]` pair gains `identical`, the items where the two arms agree in risk_score as
# well as in outcome (the verdict agreeing at 70 vs 80 is not the same build's reading repeated).
# Both keys ride unconditionally, so a score over run.json files written before them differs in
# keys from the version-3 score the same replays produced. 3 (2026-10-06, ISS-016): `identity.split`
# and each results row's `split` appear; with a recorded split the model blocks gain dev/holdout
# siblings of `all`. 2 (2026-10-06, ISS-043): `models.*.all` gains s2_cluster/s3_cluster and
# `comparison[]` gains the paired test. Metrics from before each differ in keys, and this field
# is the only signal a reader has for it.
SCORE_VERSION = 5
_REPLAY_KEYS = (
    "replay_id",
    "model",
    "served_id",
    "transport",
    "url",
    "build",
    "commit",
    "eval_run_id",
    "started_utc",
    "limit",
    # The conditions each model ran under (decision A7): the report states them per model.
    "enforcement_probe",
    "request_extra",
    "max_tokens",
    "read_timeout",
    "system_message",
    "thinking",
    # ISS-043: the sampling choice rides with the rest of the conditions.
    "temperature",
    "seed",
    # ISS-087: the operator's declaration of what the endpoint was started with. Absent for a
    # replay run before it, so the read is .get()-based like the keys above.
    "server_settings",
    # ISS-016: which scenarios the replay never scored. Absent for a replay of a pre-split
    # export, so the read is .get()-based like the conditions keys above.
    "split_sha256",
    "split_holdout",
    # ISS-037: how frames reached the wire, and whether the sequence sets joined the run.
    # Absent for a replay run before them, so the read is .get()-based like the keys above.
    "frames_mode",
    "with_sequences",
)


class ScoreRequestError(Exception):
    """The request names replays that cannot be scored together."""


class ScoreRefused(Exception):
    """A replay, its eval store and the export disagree: stop and ask the owner."""


# The export's manifest is where the roster comes from; the identity says so, so a reader knows
# which artifact the number was computed under. B6: no manifest means `unrecorded`, and that is
# the only value a pre-split export's identity can carry.
SPLIT_SOURCE = "splits.json"
UNRECORDED = {"source": "unrecorded"}


@dataclass(frozen=True)
class Replay:
    """A replay's `run.json`."""

    record: Mapping[str, Any]

    @property
    def replay_id(self) -> str:
        return str(self.record["replay_id"])

    @property
    def model(self) -> str:
        return str(self.record["model"])

    @property
    def store(self) -> Path:
        return Path(self.record["store"])

    @property
    def export(self) -> Path:
        return Path(self.record["export"])


@dataclass(frozen=True)
class ScoreResult:
    score_id: str
    out_dir: Path
    metrics: dict[str, Any]


def load_replay(replays_dir: Path, replay_id: str) -> Replay:
    path = replays_dir / replay_id / "run.json"
    if not path.is_file():
        raise ScoreRequestError(f"no replay {replay_id!r} under {replays_dir}")
    try:
        return Replay(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise ScoreRefused(f"{path} does not read: {error}") from error


def load_items(store: EvalStore, sets: Sequence[ExportedSet]) -> dict[str, Item]:
    """Every item in both the store and the export: label and floor from the store (the label
    authority, as `vlm_replay` derives them), facts and still from the export."""
    by_id = {exported.item_id: exported for exported in sets}
    items: dict[str, Item] = {}
    for item in store.iter_items(with_media_only=True):
        exported = by_id.get(item.item_id)
        if exported is not None:
            items[item.item_id] = Item(
                item_id=item.item_id,
                label=item.expected_label,
                floor=floor_for_expected_score(item.expected_risk_score),
                facts=exported.facts,
                still=exported.still,
            )
    return items


def weights_identity(transport: str, served_id: str, env: Mapping[str, str]) -> str:
    """What the host recorded about a model's weights: for `ai-vlm`, the model file's line in
    the `SHA256SUMS` the weights copy wrote; for vLLM, the Hugging Face snapshot revision."""
    if transport == "ai-vlm":
        sums = Path(env.get("AI_MODELS_PATH", "/export/models/ai_models")) / "vlm" / "SHA256SUMS"
        try:
            lines = sums.read_text(encoding="utf-8").splitlines()
        except OSError:
            return "unrecorded"
        for line in lines:
            digest, _, name = line.partition(" ")
            if name.strip().lstrip("*") == f"{served_id}.gguf":
                return f"sha256:{digest}"
        return "unrecorded"
    repo = "models--" + served_id.replace("/", "--")
    ref = Path(env.get("HF_HOME", "/export/models")) / "hub" / repo / "refs" / "main"
    try:
        return f"revision:{ref.read_text(encoding='utf-8').strip()}"
    except OSError:
        return "unrecorded"


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _labels_digest(sets: Sequence[ExportedSet]) -> str:
    """One digest over every set's labels (which carry each still's sha256)."""
    digest = hashlib.sha256()
    for exported in sorted(sets, key=lambda s: s.item_id):
        digest.update(exported.item_id.encode())
        digest.update(json.dumps(exported.labels, sort_keys=True).encode())
    return digest.hexdigest()


def _one(values: set[Path], what: str) -> Path:
    if len(values) != 1:
        shown = ", ".join(sorted(str(v) for v in values))
        raise ScoreRequestError(f"the replays name different {what}s ({shown}): score them apart")
    return next(iter(values))


def _split_of(manifest: dict[str, Any]) -> dict[str, Any]:
    """The identity's `split` block: exactly the keys a reader needs, taken from the manifest the
    cross-check just accepted."""
    return {
        "source": SPLIT_SOURCE,
        "sha256": split_sha256(manifest),
        "seed": manifest["seed"],
        "holdout_k": manifest["holdout_k"],
        "holdout": list(manifest["arms"]["holdout"]),
        "items": manifest["items"],
    }


def _candidate_versions(
    export: Path, store: EvalStore, manifest: Mapping[str, Any] | None
) -> list[str]:
    """The corpus version keys worth asking the store about (its `splits` rows are keyed by it).

    A manifest states its own version, which is the case that matters. Without one there is
    nothing inside the export to read, so fall back to the two names the layout gives it: the
    store's directory (`eval_store`'s own rule — the directory names the generation it holds) and
    the export's parent (`$SYNTHBENCH_ROOT/exports/<version>/vss`, what `export vss` writes). A
    store kept somewhere else entirely answers nothing, which reads as unrecorded: the one drift
    this function cannot see is a roster in a store that hides its version from both paths.
    """
    if manifest is not None:
        return [str(manifest["corpus_version"])]
    names = [store.dir_name]
    if export.name == "vss":
        names.append(export.parent.name)
    return list(dict.fromkeys(names))


def load_split(
    store: EvalStore,
    export: Path,
    replay_records: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str] | None, dict[str, Any]]:
    """One split truth for this score, from the three places that can hold it (design §4).

    The export's `splits.json`, the store's `splits` rows and each replay's `run.json` are read
    together and cross-checked before any of them is trusted; the function returns the
    scenario→arm table and the identity block built from the same manifest. `unrecorded` —
    `(None, {"source": "unrecorded"})` — requires that the store AND the export are both empty
    (B6); one holding a split the other does not is `ScoreRefused`, not a silent fallback, and so
    is a replay record naming a different digest (B8).

    The manifest is the authority for the identity's numbers; the store's rows are what the import
    actually recorded, so the roster, the digest on every row and each replay's digest are all
    checked against it. An arm outside dev/holdout is refused by the store at import, so a row
    that agrees on arm and digest needs no further rule.
    """
    manifest = read_split(export)
    digest = split_sha256(manifest) if manifest is not None else None
    versions = _candidate_versions(export, store, manifest)
    stored: list[dict[str, Any]] | None = None
    found = versions[0]  # only the message's subject when no version holds rows at all
    for version in versions:
        if rows := store.get_split(version):
            stored, found = rows, version
            break

    if manifest is None:
        if stored is not None:
            raise ScoreRefused(
                f"the eval store records a split for {found!r} "
                f"({stored[0]['manifest_sha256']}, {len(stored)} scenarios) but {export} carries "
                f"no {SPLIT_FILE}: the export this store was imported from is not the one being "
                "scored; move the eval store aside and replay the export you mean to score"
            )
        for record in replay_records:
            if carried := record.get("split_sha256"):
                raise ScoreRefused(
                    f"the split disagrees: the replay {str(record.get('replay_id'))!r} recorded "
                    f"split_sha256 {carried}, but {export} carries no {SPLIT_FILE}: its export "
                    "predates the split these replays measured"
                )
        # Both sources empty: the export predates the split and scores exactly as it did (B6).
        return None, dict(UNRECORDED)

    if stored is None:
        armed = manifest["arms"]["dev"] + manifest["arms"]["holdout"]
        raise ScoreRefused(
            f"{export / SPLIT_FILE} carries a split ({digest}, {len(armed)} scenarios) but the "
            f"eval store records none for {manifest['corpus_version']!r}: the store was imported "
            "before the split existed; move it aside and replay this export"
        )

    arm_of = {name: arm for arm, names in manifest["arms"].items() for name in names}
    roster = {str(row["scenario"]): str(row["arm"]) for row in stored}
    stale = sorted({str(row["manifest_sha256"]) for row in stored} - {digest})
    if roster != arm_of or stale:
        moved = sorted(name for name, arm in arm_of.items() if roster.get(name) != arm)
        shown = ", ".join(map(repr, moved[:3])) or "none"
        raise ScoreRefused(
            f"the split disagrees: for {found!r} the eval store holds {len(roster)} scenarios "
            f"under manifest_sha256 {stored[0]['manifest_sha256']}, {export / SPLIT_FILE} holds "
            f"{len(arm_of)} under {digest} (armed differently: {shown}"
            f"{'' if len(moved) <= 3 else f', +{len(moved) - 3} more'})"
        )
    for record in replay_records:
        carried = record.get("split_sha256")
        if carried != digest:
            raise ScoreRefused(
                f"the split disagrees: the replay {str(record.get('replay_id'))!r} recorded "
                f"split_sha256 {carried or 'nothing'}, not the export's {digest}: score replays of "
                "one export together, and replays of different exports apart"
            )
    return arm_of, _split_of(manifest)


def execute(
    replay_ids: Sequence[str],
    replays_dir: Path,
    scores_dir: Path,
    audit_log: Path,
    env: Mapping[str, str],
    now: datetime,
) -> ScoreResult:
    """Score the named replays together and write the outputs under `scores_dir/<score_id>/`."""
    replays = [load_replay(replays_dir, replay_id) for replay_id in replay_ids]
    models = [replay.model for replay in replays]
    if len(set(models)) != len(models):
        raise ScoreRequestError(f"one replay per model: {', '.join(sorted(models))}")
    store_path = _one({replay.store for replay in replays}, "eval store")
    export = _one({replay.export for replay in replays}, "export")
    if not store_path.is_file():
        raise ScoreRefused(f"the eval store {store_path} is missing")
    stills = read_sets(export)
    sets = stills
    # ISS-037: the export's sequence sets join the scored population only when some replay
    # being scored ran them (its run.json's `with_sequences`): a stored-only score of the same
    # export keeps exactly the item population it scored before sequences existed, and a
    # sequence run's rows resolve instead of hitting the missing-item refusal below.
    if any(replay.record.get("with_sequences") for replay in replays):
        sets = stills + read_sequence_sets(export)
    with EvalStore(store_path) as store:
        items = load_items(store, sets)
        loaded = [
            (replay.model, replay.replay_id, store.replay(str(replay.record["eval_run_id"])))
            for replay in replays
        ]
        # One roster for the whole score: the rows' arms and the identity's split come from here,
        # and the report's dev/holdout tables (Task 6) take the same table.
        scenario_arm, split_identity = load_split(
            store, export, [replay.record for replay in replays]
        )
        if scenario_arm is not None:
            # `export vss` arms every scenario it exports, so a scenario missing from a roster
            # that exists means hand-edited or mismatched data — name it, never label it
            # `unrecorded` and let it score as if it were in dev.
            unarmed = sorted(
                {str(item.facts["cell"]["scenario"]) for item in items.values()}
                - scenario_arm.keys()
            )
            if unarmed:
                raise ScoreRefused(
                    f"{export / SPLIT_FILE} does not arm {unarmed[0]}"
                    f"{' (+' + str(len(unarmed) - 1) + ' more)' if len(unarmed) > 1 else ''}, which "
                    "this export holds items for: the roster and the export are not the same "
                    "export's; move the eval store aside and replay the export you mean to score"
                )
    for model, _, rows in loaded:
        if not rows:
            raise ScoreRefused(f"{model}'s replay has no results in {store_path}")
        missing = sorted({row["item_id"] for row in rows} - items.keys())
        if missing:
            raise ScoreRefused(
                f"{model}'s replay scored {len(missing)} item(s) the export at {export} does not "
                f"hold, first {missing[0]}"
            )
    answers = load_answers(audit_log)
    # The audit's population is the stills the owner was shown — never the sequence sets, whose
    # frames come from a separate render (ISS-038): the sampler gets the stills' list.
    sampled = [str(exported.facts["event_id"]) for exported in audit_sample(stills)]
    metrics = score_models(loaded, items, answers, sampled, scenario_arm=scenario_arm)
    score_id = f"{now:%Y%m%dT%H%M%SZ}"
    identity = {
        "score_id": score_id,
        "score_version": SCORE_VERSION,
        "commit": git_commit(),
        "created_utc": now.isoformat(timespec="seconds"),
        "corpus_version": sorted(
            {str(item.facts.get("corpus_version")) for item in items.values()}
        ),
        "export": {"path": str(export), "items": len(sets), "labels_sha256": _labels_digest(sets)},
        "eval_store": {"path": str(store_path)},
        "split": split_identity,
        "audit": {"path": str(audit_log), "sha256": _sha256(audit_log)},
        "replays": [
            {key: replay.record.get(key) for key in _REPLAY_KEYS}
            | {
                "weights": weights_identity(
                    str(replay.record.get("transport", "")),
                    str(replay.record.get("served_id", "")),
                    env,
                )
            }
            for replay in replays
        ],
    }
    results = result_rows(
        loaded,
        items,
        answers,
        set(metrics["audit"]["generation_errors"]),
        scenario_arm=scenario_arm,
    )
    out_dir = scores_dir / score_id
    out_dir.mkdir(parents=True)
    (out_dir / "results.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in results), encoding="utf-8"
    )
    document = {"identity": identity, **metrics}
    (out_dir / "metrics.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    (out_dir / "report.md").write_text(report.markdown(metrics, identity, root), encoding="utf-8")
    (out_dir / "report.html").write_text(report.html(identity, results, out_dir), encoding="utf-8")
    return ScoreResult(score_id, out_dir, document)
