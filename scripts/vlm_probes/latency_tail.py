r"""Measure the shipped VLM call path's latency distribution and reply-length tail.

B1.1's MEASURE checkbox. Every throughput figure in the repo is inherited
(the ~57 tok/s in the vlm_client comment descends from a vendor 30B number
rescaled in prose; the sweep's tok/s ran a foreign scratchpad recipe at a
180 s timeout override), and the only latency ever committed is a sweep
CONTROL arm - text-only, no images, not an S4 reading (F13). This probe
measures the real thing instead: it drives the shipped `VlmClient` (same
prompt render, same `_ASSESS_MAX_TOKENS`, same per-attempt
`ai_vlm_read_timeout`, same budget-vs-fault classification) against a test
endpoint and reports:

  * per-rep wall latency of the full `assess()` call: median / p95 / max,
    nearest-rank - the p95 an S4 (<= 30 s incl. cold starts) is judged
    against, printed with its hardware caveat rather than as a verdict;
  * the reply-length tail: n, median / p95 / p99 / max completion tokens
    (the server's own `usage`) - the tail decides whether
    `_ASSESS_MAX_TOKENS = 2048` can shrink, and cutting the cap below the
    tail re-creates finding A's fabricated verdict field;
  * the engine's own decode rate (`timings.predicted_per_second` off the
    llama.cpp reply) - the number the vlm_client comment has always cited
    second-hand; after this run posts, the comment quotes a measurement;
  * the D1 outcome counts: a read timeout is BUDGET (the client raises
    VlmSlowReplyError and charges the breaker nothing), a refused
    connection or HTTP fault is FAULT - plus `reasked_reps`, reps whose
    wire window holds more than one chat call WITHOUT being a fast-fault
    retry: an old client re-asked timed-out replies, which is the exact
    behaviour B1.1 reddens, so a nonzero count here says the binary under
    test is not the B1.1 build.

Reps are sequential: the deployment's VLM_PARALLEL slots would let two
in-flight requests share decode throughput and turn "p95" into a load
number. The first rep is UNMEASURED warm-up by default (--warm-reps): it
completes the enforcement probe (its /props + probe chat ride rep 1's
assess() and would skew that sample) and absorbs the first real decode.
Set --warm-reps 0 to include them - that is how a cold reading is taken:
idle the endpoint past VLM_SLEEP_IDLE_SECONDS, then run with no warm-up
(one rep is a valid cold sample; the batch aggregator's wake() ping is
production's wake path and a harness must not pretend to be it).

F13: a GB300 reading is INDICATIVE ONLY; S1/S4 close on 24 GB hardware.
The JSON says so in the field names.

Usage (operator, against a TEST deployment - never the live stack):

  VLM_URL=http://test-host:8098 uv run python scripts/vlm_probes/latency_tail.py \
      --url "$VLM_URL" --camera front_door --dir /data/foscam \
      --pattern 'Camera*/**/*.jpg' --frames 4 --reps 40 --expect-build b7972

  # the cap-decision check against a proposed smaller cap:
  ... --cap 1024      # exits 1 if any measured reply outran the proposal

Exit codes: 0 the run measured and found nothing to report (zero BUDGET
overruns, p95 within S4, and with --cap no reply outran it); 1 something
the ladder must change (a BUDGET overrun at this cap+timeout, p95 over
S4's 30 s, or the --cap tail check failed); 2 the run could not measure
(endpoint faulted, breaker open, or fewer than --min-completed replies
completed WITHOUT a budget outcome) - "could not
measure", never a verdict about the engine. An all-timeout run is NOT
inconclusive: it is exit 1, evidence that this cap+timeout cannot carry
the corpus.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any, ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
from backend.core.mime_types import IMAGE_MIME_TYPES
from backend.services.circuit_breaker import get_circuit_breaker, reset_circuit_breaker_registry
from backend.services.token_counter import get_token_counter
from backend.services.vlm_client import (
    _ASSESS_MAX_TOKENS,
    BREAKER_NAME,
    CHAT_PATH,
    ConstrainedDecodingNotEnforced,
    VlmClient,
    VlmClientError,
    VlmSlowReplyError,
    VlmUnavailableError,
    get_settings,
)
from backend.services.vlm_verdict import VlmAssessRequest

# The spec bar S4 is judged against, in ms (00-audit: p95 <= 30 s including
# cold starts). Named here so the JSON carries the bar next to the number.
S4_P95_MS = 30_000


class _TailRecorder(httpx.AsyncBaseTransport):
    """Wrap the real transport and record what the WIRE says per chat call.

    The same recording-transport trick `test_vlm_client.py` uses (test-side
    only until B1.1; prod stays blind), pointed at a live socket instead of
    an ASGI fake. Records EVERY chat attempt - the client's retry behaviour
    is part of what is being measured, so an attempt that is about to be
    retried must still leave its mark.

    `wall_ms` times the inner transport call itself, not the response parse,
    and is set even when the inner call raises - which is how a rep httpx
    cut off at the read budget still carries the seconds the engine spent.
    """

    calls: ClassVar[list[dict[str, Any]]] = []  # per-process log; one run = one process

    def __init__(self, inner: httpx.AsyncBaseTransport, api_key: str | None = None) -> None:
        self._inner = inner
        self._api_key = api_key

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self._api_key:  # the shipped client sends no auth header; this endpoint may want one
            request.headers["authorization"] = f"Bearer {self._api_key}"
        started = time.monotonic()
        record: dict[str, Any] = {
            "path": request.url.path,
            "wall_ms": None,
            "status": None,
            "error": None,
            "max_tokens": None,
            "completion_tokens": None,
            "finish": None,
            "predicted_per_second": None,
            "content_tokens_est": None,
        }
        # /props (the build pin) is not a completion; recording it would skew
        # the per-rep chat count the re-ask guard reads.
        if request.url.path != CHAT_PATH:
            return await self._inner.handle_async_request(request)
        self.calls.append(record)
        try:
            sent = json.loads(bytes(await request.aread()))
            record["max_tokens"] = sent.get("max_tokens")
        except Exception:  # pragma: no cover - the client always sends JSON
            record["max_tokens"] = None  # a non-JSON body is still a call of record
        try:
            response = await self._inner.handle_async_request(request)
        except Exception as exc:
            record["wall_ms"] = int((time.monotonic() - started) * 1000)
            record["error"] = type(exc).__name__
            raise
        record["wall_ms"] = int((time.monotonic() - started) * 1000)
        record["status"] = response.status_code
        body = bytes(await response.aread())  # the stream is one-shot; re-issued below
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:  # pragma: no cover - a torn body still counts as a call
            return response
        response = httpx.Response(
            response.status_code, headers=dict(response.headers), content=body, request=request
        )
        usage = payload.get("usage") or {}
        choice = (payload.get("choices") or [{}])[0]
        record["completion_tokens"] = usage.get("completion_tokens")
        record["finish"] = choice.get("finish_reason") or payload.get("stop_reason")
        # llama.cpp answers with its own measurement; take the engine's
        # number over a wall-clock estimate derived around prefill.
        timings = payload.get("timings") or {}
        rate = timings.get("predicted_per_second") or payload.get("tokens_per_second")
        if isinstance(rate, int | float):
            record["predicted_per_second"] = float(rate)
        content = (choice.get("message") or {}).get("content")
        if isinstance(content, str) and record["completion_tokens"] is None:
            # tiktoken is cl100k_base and llama.cpp serves Qwen tokens - a
            # labelled proxy for the missing `usage`, never a server count.
            record["content_tokens_est"] = get_token_counter().count_tokens(content)
        return response


def _dial_transport() -> httpx.AsyncBaseTransport:
    """The one place this harness opens a socket. A named function so the
    committed tests can stand a fake where the dialer is without patching
    httpx itself (the injected `transport` seam covers `run`; `main` dials)."""
    return httpx.AsyncHTTPTransport()


def _nearest_rank(sorted_values: list[int], q: float) -> int:
    """Rank ceil(q*n), clamped - the formula `vlm_replay.compute_report` was
    corrected to (its `int(n*q)` index sat one rank high at every
    whole-multiple n)."""
    return sorted_values[min(math.ceil(len(sorted_values) * q) - 1, len(sorted_values) - 1)]


def _stills(args: argparse.Namespace) -> list[str]:
    """Absolute still paths the client's three guards will pass: under --dir
    (the same resolve + is_relative_to root check `_image_parts` applies), a
    still by suffix (IMAGE_MIME_TYPES), and under vlm_max_image_bytes BY
    BYTES. The client re-checks all three; pre-checking means a 40-rep run
    fails on frame 0 naming files, not on rep 37 with a VlmImageError."""
    root = Path(args.dir).resolve()
    limit = get_settings().vlm_max_image_bytes
    found: list[str] = []
    for path in sorted(root.glob(args.pattern)):
        if path.suffix.lower() not in IMAGE_MIME_TYPES:
            continue
        try:
            resolved = path.resolve()
        except OSError:  # pragma: no cover - exotic FS errors
            continue
        if not resolved.is_relative_to(root) or not resolved.is_file():
            continue
        if resolved.stat().st_size > limit:
            continue
        found.append(str(resolved))
    if len(found) < args.frames:
        raise SystemExit(
            f"--frames {args.frames} needs {args.frames} stills under {root}/{args.pattern}; "
            f"found {len(found)} passing the client's own guards (root, still type, byte cap)"
        )
    return found[: args.frames]


def _request(camera: str, stills: list[str]) -> VlmAssessRequest:
    """One FIXED synthetic context, deliberately identical on every rep: the
    tail then describes the engine, not corpus variance. One detection row
    because `image_paths` is min_length=1 (the assess leg has no text-only
    shape) and one row is the smallest real prompt the render produces.
    Real-corpus variance is what the replay harness measures; B1.1 asked
    for the call path's latency at a known request."""
    return VlmAssessRequest(
        image_paths=list(stills),
        context={
            "camera_id": camera,
            "detections": [{"object_type": "person", "confidence": 0.9}],
            "zones": [],
            "timestamp": "2026-10-08T12:00:00+00:00",
        },
    )


def _classify(exc: BaseException) -> tuple[str, str]:
    """(bucket, detail) off the exception TYPE the shipped client raises -
    D1's ruling read back: BUDGET answers the breaker's question "stop
    calling this engine?" NO; FAULT answers yes."""
    if isinstance(exc, VlmSlowReplyError):
        return "BUDGET", "read timeout (no retry, no breaker charge)"
    if isinstance(exc, ConstrainedDecodingNotEnforced):
        # The probe leg's slow answer is the same budget on the other leg
        # (B1.1); its text names the budget. Anything else from this class
        # is a genuine enforcement/service fault.
        text = str(exc).lower()
        if "timeout" in text or "budget" in text:
            return "BUDGET", "probe read timeout"
        return "FAULT", f"probe: {str(exc)[:200]}"
    if isinstance(exc, VlmUnavailableError):
        return "FAULT", "breaker open (refused without I/O)"
    if isinstance(exc, VlmClientError):
        return "FAULT", str(exc)[:200]
    return "FAULT", f"{type(exc).__name__}: {exc}"[:200]


# httpx raises these when a LIVE request outruns the read budget; anything
# else the transport raises happened BEFORE any reply was in flight - a
# connection refused, a connect timeout - which is what the §6 ladder's one
# sanctioned re-ask is for.
_SLOW_TRANSPORT_ERRORS = frozenset({"ReadTimeout", "TimeoutException"})


def _legitimate_retry(assess_calls: list[dict[str, Any]]) -> bool:
    """True when a second chat call in the window is the §6 ladder's
    sanctioned re-ask: only a FAST first failure (connection refused, 5xx)
    earns one. The FIRST call decides - a fast error (any transport
    exception but a read timeout) or a non-200 reply - because a client that
    re-asked a SUCCESS, or the timed-out reply B1.1 forbids re-asking, put
    no fast failure first."""
    first = assess_calls[0]
    if first["error"]:
        return first["error"] not in _SLOW_TRANSPORT_ERRORS
    return first["status"] is not None and first["status"] != 200


async def run(
    url: str,
    *,
    camera: str,
    stills: list[str],
    reps: int,
    probe: bool = True,
    expect_build: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
    min_completed: int = 5,
    warm_reps: int = 1,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """`reps` sequential `assess()` calls after `warm_reps` unmeasured ones;
    aggregate summary only, no per-item content (the repo's own reporting
    doctrine: `vlm_replay.compute_report` "never per-item content").

    The `ai-vlm` breaker is a process-wide registry singleton - a run that
    inherited a warm breaker from earlier code in the same process would
    report a state this endpoint never caused, so the registry is reset
    here. This is a one-shot measurement CLI; nothing else in the repo
    resets the registry outside tests and shutdown.

    `transport` is the test seam (the same doctrine as enforcement.py's
    injected client: the judgement must be drivable without a GPU): a fake
    stands where `httpx.AsyncHTTPTransport()` would otherwise dial $VLM_URL.
    """
    reset_circuit_breaker_registry()
    _TailRecorder.calls.clear()
    updates: dict[str, Any] = {"vlm_enforcement_probe_enabled": probe}
    if expect_build:
        updates["vlm_required_build"] = expect_build
    if timeout is not None:  # an override changes what THIS harness budgets only
        updates["ai_vlm_read_timeout"] = timeout
    settings = get_settings().model_copy(update=updates)
    client = VlmClient(
        settings=settings,
        transport=_TailRecorder(transport or _dial_transport(), api_key=api_key),
        base_url=url,
    )
    request = _request(camera, stills)

    outcomes = {"OK": 0, "BUDGET": 0, "FAULT": 0}
    details: set[str] = set()
    latencies: list[int] = []
    budget_walls: list[int] = []
    reply_tokens: list[int] = []
    rates: list[float] = []
    est_fallbacks = 0
    reasked = 0
    cursor = 0  # index into _TailRecorder.calls where the current rep began

    async def one_rep(measure: bool) -> None:
        nonlocal cursor, reasked, est_fallbacks
        started = time.monotonic()
        fault: BaseException | None = None
        try:
            await client.assess(request)
        except (VlmClientError, ConstrainedDecodingNotEnforced) as exc:
            fault = exc
        wall = int((time.monotonic() - started) * 1000)
        rep_calls = [c for c in _TailRecorder.calls[cursor:] if c["path"] == CHAT_PATH]
        cursor = len(_TailRecorder.calls)
        # The probe leg's chat call (its own max_tokens, one per client
        # lifetime) rides rep 1's window when --warm-reps 0; the re-ask
        # guard and the reply-tail sample are about the ASSESS leg only.
        assess_calls = [c for c in rep_calls if c["max_tokens"] == _ASSESS_MAX_TOKENS]
        if not measure:
            return
        # A rep whose window holds >1 chat call is only a violation when it
        # was NOT a fast-fault the §6 ladder legitimately re-asks (a refused
        # connection retries by design - the second call is the point). An
        # OK rep must hold exactly one assess call, and a read-timeout rep
        # must hold no call AFTER the timed-out one: the old client re-asked
        # the timed-out reply, which is the behaviour B1.1 reddens.
        if len(assess_calls) > 1 and not _legitimate_retry(assess_calls):
            reasked += 1
        if fault is None:
            outcomes["OK"] += 1
            latencies.append(wall)
            assess_call = assess_calls[-1] if assess_calls else None
            if assess_call is not None:
                n = assess_call["completion_tokens"]
                if n is None:
                    n = assess_call["content_tokens_est"]
                    if n is not None:
                        est_fallbacks += 1  # only when the proxy WAS the number
                if n is not None:
                    reply_tokens.append(int(n))
                if assess_call["predicted_per_second"] is not None:
                    rates.append(assess_call["predicted_per_second"])
        else:
            bucket, detail = _classify(fault)
            outcomes[bucket] += 1
            details.add(f"{bucket}: {detail}")
            if bucket == "BUDGET":
                budget_walls.append(wall)

    cursor = len(_TailRecorder.calls)
    for _ in range(warm_reps):
        await one_rep(measure=False)
    cursor = len(_TailRecorder.calls)
    for _ in range(reps):
        await one_rep(measure=True)

    breaker_open = get_circuit_breaker(BREAKER_NAME).is_open
    await client.close()

    lat_sorted, rep_sorted = sorted(latencies), sorted(reply_tokens)
    p95 = _nearest_rank(lat_sorted, 0.95) if lat_sorted else None
    return {
        "endpoint": url,
        "config": {
            "reps": reps,
            "warm_reps": warm_reps,
            "frames": len(stills),
            "probe": probe,
            "expect_build": expect_build,
            "read_timeout_s": settings.ai_vlm_read_timeout,
            "max_tokens": _ASSESS_MAX_TOKENS,
            "served_build_info": client._build_info or None,
        },
        "outcomes": outcomes,
        "outcome_details": sorted(details),
        "latency_ms_indicative_only": {
            "n": len(lat_sorted),
            "median": statistics.median(lat_sorted) if lat_sorted else None,
            "p95": p95,
            "max": lat_sorted[-1] if lat_sorted else None,
            "note": "F13: indicative off this hardware; S1/S4 close on 24 GB",
        },
        "s4": {
            "target_p95_ms": S4_P95_MS,
            "measured_p95_ms": p95,
            "within": p95 is not None and p95 <= S4_P95_MS,
        },
        "reply_tokens": {
            "n": len(rep_sorted),
            "source": "usage.completion_tokens; tiktoken est. as labelled fallback",
            "tiktoken_fallback_replies": est_fallbacks,
            "median": statistics.median(rep_sorted) if rep_sorted else None,
            "p95": _nearest_rank(rep_sorted, 0.95) if rep_sorted else None,
            "p99": _nearest_rank(rep_sorted, 0.99) if rep_sorted else None,
            "max": rep_sorted[-1] if rep_sorted else None,
        },
        "decode_tok_s": {
            "median": statistics.median(rates) if rates else None,
            "source": "llama.cpp timings.predicted_per_second (engine-measured)",
            "n": len(rates),
        },
        "budget_wall_ms_max": max(budget_walls) if budget_walls else None,
        "reasked_reps": reasked,
        "breaker_open_after_run": breaker_open,
        "budget_overruns": outcomes["BUDGET"],
        # A BUDGET outcome is evidence too: the endpoint accepted, decoded and
        # worked - it just outran OUR number - so an all-timeout run is a loud
        # "this cap+timeout cannot carry this corpus" (exit 1), not
        # "could not measure". A FAULT reply proves nothing about the engine,
        # which is why only FAULTs can starve a run into INCONCLUSIVE.
        "measured": (outcomes["OK"] + outcomes["BUDGET"]) >= min_completed and not breaker_open,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="B1.1: measure the shipped VLM call path's latency and reply-length tails"
    )
    parser.add_argument("--url", required=True, help="test endpoint base, e.g. http://host:8098")
    parser.add_argument("--camera", required=True, help="camera id rendered into the prompt")
    parser.add_argument(
        "--dir",
        required=True,
        help="capture root (the deployment's FTP root) the stills must live under",
    )
    parser.add_argument("--pattern", default="*.jpg", help="glob under --dir (default *.jpg)")
    parser.add_argument("--frames", type=int, default=1, help="stills per request (1-4)")
    parser.add_argument("--reps", type=int, default=40)
    parser.add_argument(
        "--warm-reps",
        type=int,
        default=1,
        help="unmeasured reps first (absorb the probe leg + first decode); 0 for a cold reading",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=None,
        help=f"proposed reply cap: fail if the measured tail outran it (off by default; shipped cap is {_ASSESS_MAX_TOKENS})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="override ai_vlm_read_timeout for THIS run only (default: shipped value)",
    )
    parser.add_argument(
        "--expect-build", default=None, help="substring /props build_info must contain (e.g. b7972)"
    )
    parser.add_argument("--api-key", default=None, help="bearer token if the endpoint has one")
    parser.add_argument(
        "--no-probe", action="store_true", help="skip the enforcement-probe leg (not recommended)"
    )
    parser.add_argument(
        "--min-completed",
        type=int,
        default=5,
        help="fewer completed-or-budget replies than this and the run is INCONCLUSIVE (exit 2)",
    )
    args = parser.parse_args(argv)

    if not 1 <= args.frames <= 4:
        raise SystemExit("--frames is 1-4 (the client's own image_paths limit)")
    if args.no_probe and args.expect_build:
        raise SystemExit(
            "--expect-build rides the probe leg (/props is only read there); drop --no-probe "
            "to pin the build, or drop the pin"
        )
    stills = _stills(args)

    summary = asyncio.run(
        run(
            args.url,
            camera=args.camera,
            stills=stills,
            reps=args.reps,
            probe=not args.no_probe,
            expect_build=args.expect_build,
            api_key=args.api_key,
            timeout=args.timeout,
            min_completed=args.min_completed,
            warm_reps=args.warm_reps,
        )
    )
    print(json.dumps(summary, indent=2))

    if not summary["measured"]:
        print(
            f"INCONCLUSIVE: completed {summary['outcomes']['OK']}/{args.reps}, "
            f"breaker open after run: {summary['breaker_open_after_run']} "
            "- the endpoint faulted; nothing was measured about the engine",
            file=sys.stderr,
        )
        return 2
    if summary["reasked_reps"]:
        print(
            f"FAIL: {summary['reasked_reps']} rep(s) show more than one assess call after a "
            "non-fast fault - this binary re-asks what B1.1 says never to re-ask",
            file=sys.stderr,
        )
        return 1
    if summary["budget_overruns"]:
        print(
            f"FAIL: {summary['budget_overruns']} BUDGET overrun(s) at "
            f"timeout={summary['config']['read_timeout_s']}s "
            f"cap={_ASSESS_MAX_TOKENS} - this cap+timeout cannot carry this corpus",
            file=sys.stderr,
        )
        return 1
    if not summary["s4"]["within"]:
        print(
            f"FAIL: p95 {summary['s4']['measured_p95_ms']} ms exceeds S4's "
            f"{S4_P95_MS} ms bar on this hardware",
            file=sys.stderr,
        )
        return 1
    if args.cap is not None and summary["reply_tokens"]["max"] > args.cap:
        print(
            f"FAIL: reply tail max {summary['reply_tokens']['max']} outran the proposed "
            f"cap {args.cap}; shrinking the cap below the tail re-creates finding A",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
