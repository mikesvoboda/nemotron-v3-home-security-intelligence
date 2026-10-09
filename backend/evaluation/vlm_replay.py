"""The Phase 2 replay harness (plan 2.1, spec "Phase 2: 2.1 The replay harness").

Runs the frozen corpus against a served `ai-vlm` through the SHIPPED
`VlmClient`, and writes the results through `EvalStore`. Rev 5 dropped the
offline 30B control replay; rev 6's rule survives and is what the name means:
replay reads the items' STORED `specialist_outputs` and never re-runs a
specialist - the GIVENS are the point of a replay.

Replay measures the judge production runs (B1.2, D6). Every verdict passes
through the analyzer's own `apply_verdict_invariants` with production's
`SeverityService`, so a row's score and level are the ones the analyzer would
store (a `rejected` verdict clamps to the LOW band); the model's raw score stays
in the row's verdict dump, and `invariants.clamped` says when the table moved it.

Frame supply is a MODE (ISS-037), not an assumption. `selector` (the default)
is production's key-frame selection: the SHIPPED `build_assess_request` with
production's `key_frame_spread_seconds`. `stored` is the historical behavior -
the item's own `media_paths` (≤4, the wire's field constraint) fed straight to
the wire: the REQUEST a stored-mode replay builds is identical to what this
harness sent before B1.2, so a re-run of a committed corpus reproduces the
committed prompt bytes, but it is not what production sends. `selector` and
`burst` apply only to items whose detections
name the frame each row was seen on (sequence sets; a still's declared
detections carry no `file_path`): the selector mode drives the SHIPPED
`build_assess_request`/`select_key_frames` - that import is lazy and inside
that branch only, because the analyzer module pulls in `vlm_specialists` at
top level and the AST doctrine below is about THIS module's own imports -
which collapses a same-camera same-class triplet to one frame, the collapse
ISS-005 exists to fix, now measured instead of asserted. The burst mode feeds
every frame (≤4) with the per-frame `frame_detection_ids` link, the shape
ISS-003's funded arm (a) will use. Which frames an item actually reached the
model with is recorded in `raw_response.harness` on EVERY row, refusals
included: a report that cannot say how many frames a run fed cannot answer
the question the run was for.

The pieces it deliberately does NOT have:

* **no specialist import at all** - not even to prove the negative: the
  module never imports `vlm_specialists`, which `test_vlm_replay.py` asserts
  at the AST level (the `test_no_seam_constructs_nemotron_directly` doctrine).
* **no score on a refusal.** §6 step 2's shape at the row level: verdict
  `verification_failed`, risk_score NULL, the error class in `raw_response`
  for the audit trail. A NULL folded into 0 would be the null-lie at the one
  reader that computes the report.

S1/S4 are NOT computed here: F13 keeps fit and latency to 24 GB hardware; the
latency distribution this prints is labelled indicative, per run, with the
commit pinned in the run's model string.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import statistics
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.core.config import get_settings
from backend.evaluation.assess_input import EvalItem
from backend.evaluation.eval_store import EvalStore
from backend.evaluation.levels import floor_for_expected_score
from backend.evaluation.s_metrics import (
    s2_false_positive_rate,
    s3_recall,
    s5_refusals,
    uncertain_rate,
)
from backend.services.constrained_decoding import (  # R8 S2a: hoisted home
    ConstrainedDecodingNotEnforced,
)
from backend.services.severity import SeverityService, get_severity_service
from backend.services.vlm_client import VlmClient, VlmClientError
from backend.services.vlm_verdict import VlmAssessContext, VlmAssessRequest, VlmVerdict

_LOG = logging.getLogger(__name__)

# The analyzer's ladder covers engine failures, not programming errors - the
# replay mirrors that set EXACTLY, so a bug propagates loud here too.
_DEGRADABLE_ERRORS: tuple[type[BaseException], ...] = (
    VlmClientError,
    ConstrainedDecodingNotEnforced,
)

MAX_REPLAY_IMAGES = 4  # VlmAssessRequest.image_paths' own field constraint

FRAMES_MODES = ("stored", "selector", "burst")  # how an item's frames reach the wire
# Production's selection is the default (B1.2): a replay that fed other frames
# would measure a request production never sends. `stored` stays for re-running
# a committed corpus byte for byte; `burst` is ISS-003's funded arm.
DEFAULT_FRAMES_MODE = "selector"


def _sequence_rows(item: EvalItem) -> list[dict[str, Any]]:
    """The item's detection rows that NAME a frame, ready for the production builders.

    A sequence set's rows carry `file_path` (the frame's name inside the set) and an ISO
    `detected_at` string; a still's declared rows carry neither. Two repairs make the rows
    what the production builders expect: `file_path` resolves to the store's media path
    (the set's names are relative by construction; the wire is fed paths), and the ISO
    string rehydrates to a `datetime`, because `build_frame_refs` reads timestamps only
    from datetime objects and a string would silently rank every frame at epoch 0 — the
    selector's recency tiebreak blinded by the store's own serialization, not by the
    selector. A row naming a file the item does not have is DROPPED, loudly counted by the
    caller's fallback: pointing the wire at a path the store does not hold is worse."""
    by_name = {Path(path).name: path for path in item.media_paths}
    rows: list[dict[str, Any]] = []
    for row in item.snapshot.detections:
        media = by_name.get(str(row.get("file_path") or ""))
        if media is None:
            continue
        moment = row.get("detected_at")
        if isinstance(moment, str):
            try:
                moment = datetime.fromisoformat(moment)
            except ValueError:
                pass  # unparseable stays as-is; build_frame_refs treats it as no time
        rows.append({**row, "file_path": media, "detected_at": moment})
    return rows


def _build_request(
    item: EvalItem, context: VlmAssessContext, *, frames_mode: str
) -> tuple[VlmAssessRequest, dict[str, Any]]:
    """The request this item becomes under `frames_mode`, plus its frame audit.

    The audit is the slice's evidence chain: `frames_fed` is what the wire was given
    (the report buckets rows by it), `selector_collapsed` says the selector was given
    more distinct frames than it attached (ISS-005's measurement, item by item), and
    `mode_fell_back` records an item that could not be fed the mode it was asked for —
    counted, never silently stored. Programming errors propagate (the module's standing
    posture); only the two expected fallbacks are caught."""
    if frames_mode not in FRAMES_MODES:
        raise ValueError(f"frames_mode must be one of {FRAMES_MODES}, got {frames_mode!r}")
    media = list(item.media_paths)[:MAX_REPLAY_IMAGES]

    def stored(fell_back: str | None = None) -> tuple[VlmAssessRequest, dict[str, Any]]:
        audit: dict[str, Any] = {
            "frames_mode": frames_mode,
            "frames_fed": len(media),
            "selector_collapsed": False,
        }
        if fell_back is not None:
            audit["mode_fell_back"] = fell_back
        return VlmAssessRequest(image_paths=media, context=context), audit

    if frames_mode == "stored":
        return stored()
    rows = _sequence_rows(item)
    if not rows:
        return stored(fell_back="no per-frame detection rows")
    if frames_mode == "burst":
        on_frame = [[row["id"] for row in rows if row["file_path"] == path] for path in media]
        request = VlmAssessRequest(image_paths=media, context=context, frame_detection_ids=on_frame)
        return request, {
            "frames_mode": frames_mode,
            "frames_fed": len(request.image_paths),
            "selector_collapsed": False,
        }
    # selector: the SHIPPED builders, lazily — vlm_analyzer imports vlm_specialists at
    # top level, and the AST doctrine pins THIS module's imports, so the sequence mode
    # that wants production's selection must import production inside the branch.
    from backend.services.vlm_analyzer import build_assess_request

    # Production's selection parameters, read the way the analyzer reads them
    # (`analyze_batch` passes settings.key_frame_spread_seconds); a selector
    # without the spread collapses a long-spanning class to one frame that
    # production would have widened. `camera_timezone` stays None: the client
    # pins it for the prompt (stored timestamps are not capture moments), which
    # is also production's default (CAMERA_TIMEZONE unset).
    spread_seconds = get_settings().key_frame_spread_seconds
    request = build_assess_request(context=context, detections=rows, spread_seconds=spread_seconds)
    distinct_frames = len({row["file_path"] for row in rows})
    return request, {
        "frames_mode": frames_mode,
        "frames_fed": len(request.image_paths),
        "selector_collapsed": len(request.image_paths) < distinct_frames,
        "spread_seconds": spread_seconds,
    }


def client_factory(base_url: str | None = None) -> Callable[[], VlmClient]:
    """The production client (settings → `ai_vlm_url`, breaker, probe), or an
    explicit endpoint when one is named. Tests pass a fake with the same
    no-arg signature.

    It is a FACTORY rather than an instance so a test can inject a double
    without the harness knowing it did - and `run_replay` calls it exactly
    ONCE per run, because one run is one endpoint at one build (the client's
    own documented lifetime, and the enforcement cache's correct scope).

    The `base_url` form exists because a run must be able to SAY which endpoint
    it measured: two candidates behind two published ports is exactly the
    2.2 bake-off's shape, and a run whose report cannot name its endpoint is
    not a pinned run (F13).
    """

    def build() -> VlmClient:
        # camera_timezone pinned to None: stored snapshot timestamps are not
        # capture moments (epoch sentinel, generated_at, event.started_at), and
        # a run records only candidate@commit, so the prompt must not change
        # with the replay host's CAMERA_TIMEZONE.
        settings = get_settings().model_copy(update={"camera_timezone": None})
        return VlmClient(settings=settings, base_url=base_url)

    return build


def git_commit(short: bool = True) -> str:
    """The run's commit, from the repo. A run that cannot say which code made
    it is not a pinned run (F13); 'unknown' is allowed to appear so the
    absence stays visible rather than the run being refused silently."""
    try:
        # S603 is about untrusted input; this argv is a fixed literal (no
        # shell, no interpolation, check=True, 10 s timeout) - the same
        # posture as the repo's shell scripts pinning a commit for a report.
        out = subprocess.run(  # noqa: S603
            ["git", "rev-parse"] + (["--short"] if short else []) + ["HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


async def replay_item(
    client: Any,
    item: EvalItem,
    *,
    frames_mode: str = DEFAULT_FRAMES_MODE,
    severity: SeverityService | None = None,
) -> dict[str, Any]:
    """One item -> one `put_result`-ready row. Maps the client's raise set to
    the shipped ladder (`verification_failed` + NULL), exactly like
    `vlm_analyzer` does for events, and scores the verdict through the
    analyzer's own `apply_verdict_invariants` (B1.2): the row's verdict, score
    and level are what the analyzer stores for the same verdict. `severity`
    defaults to production's service; `run_replay` passes one per run.

    `frames_mode` decides how the item's frames reach the wire (module
    docstring); the audit of that decision rides in `raw_response.harness`
    on the refusal path too — a refusal fed 3 frames is a data point about
    3-frame input, and dropping it would bias the per-mode counts toward
    the items that answered."""
    snap = item.snapshot
    context = VlmAssessContext(
        camera_id=snap.camera_id,
        detections=list(snap.detections),
        zones=list(snap.zones),
        zone_crossing=snap.zone_crossing,
        household=dict(snap.household),
        timestamp=snap.timestamp,
        specialist_outputs=dict(snap.specialist_outputs),
    )
    # The analyzer's invariant table, lazily for the same reason as the
    # selector branch: vlm_analyzer imports vlm_specialists at top level, and
    # the AST doctrine pins THIS module's imports. One implementation of the
    # table, shared, never a copy that could drift from production's.
    from backend.services.vlm_analyzer import apply_verdict_invariants

    severity = severity or get_severity_service()
    request, harness = _build_request(item, context, frames_mode=frames_mode)
    started = time.monotonic()
    try:
        verdict: VlmVerdict = await client.assess(request)
        latency_ms = int((time.monotonic() - started) * 1000)
        outcome = apply_verdict_invariants(verdict, severity)
        row = {
            "item_id": item.item_id,
            "verdict": outcome["verdict"],
            "risk_score": outcome["risk_score"],
            "risk_level": outcome["risk_level"],
            # `harness` is a SIBLING of the verdict dump, never inside it:
            # VlmVerdict is extra="forbid" (the wire carries no bookkeeping)
            # and every reader of raw_response so far reads through keys it
            # knows (verdict fields, `error`) — an added top-level key is
            # invisible to all of them and survives the store's JSON round trip.
            # The dump keeps the MODEL's score; `invariants` records what the
            # table made of it, so a stored row says its level and its clamp.
            "raw_response": {
                **verdict.model_dump(),
                "harness": harness,
                "invariants": {
                    "risk_level": outcome["risk_level"],
                    "clamped": outcome["risk_score"] != verdict.risk_score,
                },
            },
        }
    except _DEGRADABLE_ERRORS as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        _LOG.warning(
            "replay item %s refused: %s: %s",
            item.item_id,
            type(exc).__name__,
            exc,
        )
        row = {
            "item_id": item.item_id,
            "verdict": "verification_failed",
            "risk_score": None,
            "risk_level": None,  # the analyzer's NULL level for a bottomed-out ladder
            # the ladder's audit half (prompt-hygiene doctrine): the WHY
            # lives in the row/log, never in a score.
            "raw_response": {
                "error": type(exc).__name__,
                "detail": str(exc),
                "harness": harness,
            },
        }
    row["latency_ms"] = latency_ms  # not stored in `results`; the report reads it live
    return row


def _labels_and_items(store: EvalStore) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    labels: dict[str, str] = {}
    items: dict[str, dict[str, Any]] = {}
    for item in store.iter_items():
        labels[item.item_id] = item.expected_label
        items[item.item_id] = {
            "label": item.expected_label,
            "floor": floor_for_expected_score(item.expected_risk_score),
        }
    return labels, items


def compute_report(rows: list[dict[str, Any]], store: EvalStore) -> dict[str, Any]:
    """Aggregate only (D10): rates, n, Wilson - never per-item content."""
    labels, items = _labels_and_items(store)
    latencies = sorted(r["latency_ms"] for r in rows if r.get("latency_ms") is not None)
    # Nearest-rank p95: the value at rank ceil(0.95n), clamped to the last
    # index. `latencies[int(n * 0.95)]` was one rank high at every whole-
    # multiple n (n=20 -> index 19 -> rank 20 = the max) — and at n=13 the
    # two agree (ceil(12.35) = 13), which is why the bake-off's three
    # indicative figures stay valid while the formula was still wrong.
    p95 = (
        latencies[min(math.ceil(len(latencies) * 0.95) - 1, len(latencies) - 1)]
        if latencies
        else None
    )
    return {
        "s2": s2_false_positive_rate(rows, labels),
        "s3": s3_recall(rows, items),
        "verdict_mix": uncertain_rate(rows),
        "s5": s5_refusals(rows),
        # B1.2: how far this run sits from production's own path, as counts. A
        # clamp is a score the invariant table moved (the raw one is in the row);
        # a fallback is an item the requested frames mode could not feed, so it
        # was fed its stored frames instead.
        "parity": {
            "clamped": sum(
                1
                for r in rows
                if (r.get("raw_response") or {}).get("invariants", {}).get("clamped")
            ),
            "fell_back": sum(
                1
                for r in rows
                if (r.get("raw_response") or {}).get("harness", {}).get("mode_fell_back")
            ),
        },
        "latency_ms_indicative_only": {
            "n": len(latencies),
            "median": statistics.median(latencies) if latencies else None,
            "p95": p95,
            "max": latencies[-1] if latencies else None,
            "note": "GB300 numbers are indicative; S1/S4 close on 24 GB hardware (F13)",
        },
    }


async def run_replay(
    store: EvalStore,
    *,
    candidate: str,
    engine: str = "llama.cpp",
    limit: int | None = None,
    with_media_only: bool = True,
    make_client: Callable[[], Any] | None = None,
    endpoint: str | None = None,
    frames_mode: str = DEFAULT_FRAMES_MODE,
) -> dict[str, Any]:
    """One run of the harness. `candidate` names the exact build (weights +
    quant + image tag); it lands in the run row's `model` next to the commit,
    because 'the same replay per candidate' is only comparable if the run says
    what it ran.

    `endpoint` is the other half of that sentence — WHICH URL was measured.
    It is resolved once here and the client is built from that same value, so
    the report cannot name a URL the run did not call: a bake-off with two
    candidates on two published ports has exactly one way to mix them up, and
    it is not by being careful. When no factory is injected the run also says
    where the URL came from (`--vlm-url` or settings), since "we measured the
    default" is the sentence a stale `AI_VLM_URL` in the environment produces.

    Returns the aggregate report + the run id. Raises FileNotFoundError for a
    generation with nothing runnable (gen-1: every item is media-less, so the
    replay would be 0 items - said loudly, not run silently empty).
    """
    commit = git_commit()
    if frames_mode not in FRAMES_MODES:
        # Checked before the run row exists, like `limit`: a typo'd mode that
        # raised on the first item would leave a started run that never
        # completes, and the store's run table would carry a half a run.
        raise ValueError(f"frames_mode must be one of {FRAMES_MODES}, got {frames_mode!r}")
    if not with_media_only:
        # A structural refusal, not a policy one: `VlmAssessRequest.image_paths`
        # is min_length=1 on the SHIPPED wire, so a media-less item has no
        # expressible `vlm_assess` request at all. The 408 born-labeled items
        # are not "unmeasured" - until media exists they cannot be assessed by
        # anything speaking this wire. Saying that beats crashing per item.
        raise ValueError(
            "with_media_only=False cannot run: the vlm wire requires >=1 image "
            "path per request (VlmAssessRequest min_length=1), so label-only "
            "items are unassessable until media exists for them (ledger item 19)."
        )
    items = store.iter_items(with_media_only=True)
    if not items:
        raise FileNotFoundError(
            "this generation has no media-bearing items to replay (gen-1's "
            "shape: 421 label-only items). Build/replay generation 2+ "
            "(build_gen2); with_media_only=False is refused because an imageless "
            "vlm_assess cannot be built (image_paths requires >=1 path)."
        )
    if limit is not None and limit < 1:
        # `items[:0]` is [] and a run over nothing completes a FULL report
        # (run row, JSON file, exit 0); `items[:-1]` silently drops the last
        # item. This module already refuses a media-less generation loudly -
        # a vacuous denominator arriving through `--limit` was the last hole
        # in that posture.
        raise ValueError(f"limit must be >= 1 (got {limit}); omit it to replay everything")
    if limit is not None:
        items = items[:limit]

    if make_client is not None and endpoint is not None:
        # The docstring's claim ("the report cannot name a URL the run did
        # not call") was only true while the injected branch echoed nothing.
        # A caller that passes BOTH - a per-candidate factory pinning the
        # image plus an endpoint "for the record" - is one port-table slip
        # away from a report naming candidate A's URL for a run that dialed
        # B. The harness cannot verify an injected transport, so it refuses
        # the contradiction instead of printing the caller's assertion.
        raise ValueError(
            "endpoint is not recordable alongside an injected make_client: the "
            "factory owns its transport and the run cannot verify the URL it "
            "dials. Omit endpoint (the report then says vlm_url_source="
            "'injected'), or let the run build its own client from it."
        )

    url: str | None
    if make_client is None:
        # The run builds its own client, so it can name the URL it built it
        # from - and where that URL came from, because "we measured the
        # default" is exactly what a stale AI_VLM_URL in the environment
        # produces: a green-looking run against the wrong candidate.
        url_source = "cli" if endpoint is not None else "settings"
        url = endpoint if endpoint is not None else get_settings().ai_vlm_url
        make_client = client_factory(url)
    else:
        # An injected factory owns its transport; the harness must not claim
        # to know the URL it calls, so the field says "injected" and the URL
        # is None. (Naming one is refused above.)
        url, url_source = None, "injected"

    run_id = store.start_run(engine=engine, model=f"{candidate}@{commit}")
    rows: list[dict[str, Any]] = []
    # ONE client for the whole run. The shipped client is "one client per
    # endpoint" and caches its enforcement proof per instance on purpose
    # (S-2: a proof must not launder onto another build), so a client per item
    # re-probes per item - and five probe failures trip the SHARED `ai-vlm`
    # breaker, after which every remaining item answers VlmUnavailableError
    # without I/O. That report would describe a breaker, not a model. One run
    # is one endpoint at one build, which is exactly the client's own
    # lifetime; the close sits in `finally` so a propagating bug cannot leak
    # the httpx lifecycle. (Measured on the 2.1.6 smoke's repro - ledger
    # finding B.)
    client = make_client()
    severity = get_severity_service()  # production's thresholds, once per run
    try:
        for item in items:
            row = await replay_item(client, item, frames_mode=frames_mode, severity=severity)
            store.put_result(
                run_id,
                row["item_id"],
                verdict=row["verdict"],
                risk_score=row["risk_score"],
                raw_response=row["raw_response"],
            )
            rows.append(row)
    finally:
        await client.close()

    report = compute_report(rows, store)
    # Which corpus this measured, plan 2.1.5's requirement: without it two
    # generations that share the 13 stock media items produce byte-
    # comparable S2/S3 rows under indistinguishable headers - the exact
    # ambiguity gen-2 exists to remove. Counts + the store DIRECTORY NAME
    # (the generation, by ruling); never an absolute path, never item ids
    # (D10). The corpus-wide counts, not the replayed subset, so a --limit
    # run still says what generation it drew from.
    all_items = store.iter_items()
    corpus_labels: dict[str, int] = {}
    for it in all_items:
        key = it.expected_label or "unlabeled"
        corpus_labels[key] = corpus_labels.get(key, 0) + 1
    report["corpus"] = {
        "store_dir": store.dir_name,
        "items": len(all_items),
        "with_media": sum(1 for it in all_items if it.media_paths),
        "labels": dict(sorted(corpus_labels.items())),
    }
    report["run_id"] = run_id
    report["candidate"] = candidate
    report["engine"] = engine
    report["commit"] = commit
    report["frames_mode"] = frames_mode  # which supply fed every item in this run
    # The bands every row's level and clamp came from (ISS-014: replay "records
    # the thresholds it used") - env-configurable in production, so a report
    # that cannot say them cannot be compared with another host's.
    report["severity_thresholds"] = {
        "low_max": severity.low_max,
        "medium_max": severity.medium_max,
        "high_max": severity.high_max,
    }
    report["n_items"] = len(items)
    report["vlm_url"] = url
    report["vlm_url_source"] = url_source
    report["started_at_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    return report


def save_vlm_report(report: dict[str, Any], out_path: str | Path) -> Path:
    """Aggregate JSON only - no per-item rows, no imagery (D10)."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", required=True, help="generation store dir (holds eval.sqlite)")
    ap.add_argument(
        "--candidate", required=True, help="exact build id, e.g. Qwen3VL-4B-Q4_K_M@ai-vlm:sm103-v12"
    )
    ap.add_argument("--engine", default="llama.cpp")
    ap.add_argument(
        "--vlm-url",
        default=None,
        help="endpoint to measure (default: settings.ai_vlm_url, recorded either way)",
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument(
        "--frames",
        choices=FRAMES_MODES,
        default=DEFAULT_FRAMES_MODE,
        help="how frames reach the wire (ISS-037): selector (default, production's "
        "build_assess_request with its key_frame_spread_seconds over the item's "
        "per-frame detections), stored (the historical media_paths feed, for "
        "re-running a committed corpus byte for byte), burst (every frame with "
        "frame_detection_ids)",
    )
    ap.add_argument(
        "--all-items", action="store_true", help="replay every item, not just media-bearing"
    )
    ap.add_argument("--out", default=None, help="aggregate report path (JSON)")
    args = ap.parse_args(argv)

    store = EvalStore(Path(args.store) / "eval.sqlite")
    try:
        report = asyncio.run(
            run_replay(
                store,
                candidate=args.candidate,
                engine=args.engine,
                limit=args.limit,
                with_media_only=not args.all_items,
                endpoint=args.vlm_url,
                frames_mode=args.frames,
            )
        )
    finally:
        # The client gets a `finally` close three floors down; the store
        # connection owed the same since the day this CLI opened it.
        store.close()
    out = save_vlm_report(
        report,
        Path(args.out) if args.out else Path(args.store) / "reports" / f"{report['run_id']}.json",
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("run_id", "candidate", "commit", "frames_mode", "n_items", "vlm_url")
            },
            indent=2,
        )
    )
    print(f"report -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
