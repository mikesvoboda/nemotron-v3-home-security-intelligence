"""The Phase 2 replay harness (plan 2.1, spec "Phase 2: 2.1 The replay harness").

Runs the frozen corpus against a served `ai-vlm` through the SHIPPED
`VlmClient`, and writes the results through `EvalStore`. Rev 5 dropped the
offline 30B control replay; rev 6's rule survives and is what the name means:
replay reads the items' STORED `specialist_outputs` and never re-runs a
specialist - the GIVENS are the point of a replay.

The pieces it deliberately does NOT have:

* **no `harness.py`.** That module is the legacy Nemotron prompt harness
  (it POSTs to a live `nemotron_url`); F10 makes the legacy path unsupported,
  so the vlm replay stands beside it and imports nothing from it.
* **no key-frame selection.** Production selects the ≤4 frames with
  `build_assess_request`/`select_key_frames` from DETECTION ROWS; a frozen
  item has none (a stock item's snapshot carries zero detections - the loader
  refuses to claim them from a still), so replay feeds the item's own
  `media_paths` (≤4, the wire's field constraint) directly.
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
from backend.services.nemotron_analyzer import ConstrainedDecodingNotEnforced
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


def client_factory(base_url: str | None = None) -> Callable[[], VlmClient]:
    """The production client (settings → `ai_vlm_url`, breaker, probe), or an
    explicit endpoint when one is named. Tests pass a fake with the same
    no-arg signature - the seam is this FACTORY, never an instance, so the
    per-item `close()` lifecycle stays real.

    The `base_url` form exists because a run must be able to SAY which endpoint
    it measured: two candidates behind two published ports is exactly the
    2.2 bake-off's shape, and a run whose report cannot name its endpoint is
    not a pinned run (F13).
    """
    if base_url is not None:
        return lambda: VlmClient(base_url=base_url)
    return VlmClient


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


async def replay_item(client: Any, item: EvalItem) -> dict[str, Any]:
    """One item -> one `put_result`-ready row. Maps the client's raise set to
    the shipped ladder (`verification_failed` + NULL), exactly like
    `vlm_analyzer` does for events."""
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
    started = time.monotonic()
    try:
        request = VlmAssessRequest(
            image_paths=list(item.media_paths)[:MAX_REPLAY_IMAGES], context=context
        )
        verdict: VlmVerdict = await client.assess(request)
        latency_ms = int((time.monotonic() - started) * 1000)
        row = {
            "item_id": item.item_id,
            "verdict": verdict.verdict,
            "risk_score": verdict.risk_score,
            "raw_response": verdict.model_dump(),
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
            # the ladder's audit half (prompt-hygiene doctrine): the WHY
            # lives in the row/log, never in a score.
            "raw_response": {"error": type(exc).__name__, "detail": str(exc)},
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
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else None
    return {
        "s2": s2_false_positive_rate(rows, labels),
        "s3": s3_recall(rows, items),
        "verdict_mix": uncertain_rate(rows),
        "s5": s5_refusals(rows),
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
    if limit is not None:
        items = items[:limit]

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
        # stays whatever the caller named (None unless it chose to say).
        url, url_source = endpoint, "injected"

    run_id = store.start_run(engine=engine, model=f"{candidate}@{commit}")
    rows: list[dict[str, Any]] = []
    for item in items:
        client = make_client()
        try:
            row = await replay_item(client, item)
        finally:
            await client.close()
        store.put_result(
            run_id,
            row["item_id"],
            verdict=row["verdict"],
            risk_score=row["risk_score"],
            raw_response=row["raw_response"],
        )
        rows.append(row)

    report = compute_report(rows, store)
    report["run_id"] = run_id
    report["candidate"] = candidate
    report["engine"] = engine
    report["commit"] = commit
    report["n_items"] = len(items)
    report["vlm_url"] = url
    report["vlm_url_source"] = url_source
    report["started_at_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    return report


def save_vlm_report(report: dict[str, Any], out_path: str | Path) -> Path:
    """Aggregate JSON only - no per-item rows, no imagery (D10). The
    legacy `reports.py` writers are shaped for harness DataFrames; this
    stands beside them rather than bending them."""
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
        "--all-items", action="store_true", help="replay every item, not just media-bearing"
    )
    ap.add_argument("--out", default=None, help="aggregate report path (JSON)")
    args = ap.parse_args(argv)

    store = EvalStore(Path(args.store) / "eval.sqlite")
    report = asyncio.run(
        run_replay(
            store,
            candidate=args.candidate,
            engine=args.engine,
            limit=args.limit,
            with_media_only=not args.all_items,
            endpoint=args.vlm_url,
        )
    )
    out = save_vlm_report(
        report,
        Path(args.out) if args.out else Path(args.store) / "reports" / f"{report['run_id']}.json",
    )
    print(
        json.dumps(
            {k: report[k] for k in ("run_id", "candidate", "commit", "n_items", "vlm_url")},
            indent=2,
        )
    )
    print(f"report -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
