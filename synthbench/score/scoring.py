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
from synthbench.export.vss import ExportedSet, read_sets
from synthbench.score import report
from synthbench.score.metrics import Item, result_rows, score_models

# 2 (2026-10-06, ISS-043): `models.*.all` gains s2_cluster/s3_cluster and
# `comparison[]` gains the paired test; metrics.json from before that differs
# in keys, and this field is the only signal a reader has for it.
SCORE_VERSION = 2
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
)


class ScoreRequestError(Exception):
    """The request names replays that cannot be scored together."""


class ScoreRefused(Exception):
    """A replay, its eval store and the export disagree: stop and ask the owner."""


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
    sets = read_sets(export)
    with EvalStore(store_path) as store:
        items = load_items(store, sets)
        loaded = [
            (replay.model, replay.replay_id, store.replay(str(replay.record["eval_run_id"])))
            for replay in replays
        ]
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
    sampled = [str(exported.facts["event_id"]) for exported in audit_sample(sets)]
    metrics = score_models(loaded, items, answers, sampled)
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
    results = result_rows(loaded, items, answers, set(metrics["audit"]["generation_errors"]))
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
