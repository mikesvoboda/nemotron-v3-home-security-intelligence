#!/usr/bin/env python3
"""P0.3 enforcement probe CLI - the S-1 nonce-const check, promoted.

Asks a llama.cpp ``/completion`` endpoint to enforce a JSON grammar and
JUDGES THE REPLY, never the status code (S-1 [V]: the status code carries no
support information on this server - E5 showed nvext.guided_json is accepted
and silently ignored). The probe schema is the REAL verdict schema
(RISK_ANALYSIS_JSON_SCHEMA - single source, spec §3) extended with a required
``probe_const`` string whose value is a fresh uuid4 the prompt never
mentions. Only grammar enforcement can echo it; parrotting cannot.

Verdict vocabulary (shared with backend/services/nemotron_analyzer.py's
runtime gate and s1_nvext's arms):

    ENFORCED      the reply echoes the nonce const -> safe to use
                  constrained decoding at this model AND build.
    IGNORED       schema-valid-or-prose reply WITHOUT the const -> the
                  endpoint accepts the param but does not enforce it.
    INCONCLUSIVE  could not measure: unreachable, non-200, build_info does
                  not contain --expect-build (S-2: enforcement is per-model
                  AND per-build; a stale proof must not launder onto an
                  unknown build), OR the reply ran out of budget before the
                  const could be read (finding A: a truncated reply has no
                  const in it because the const may legally sort last in the
                  grammar, and calling that IGNORED reports a finding the
                  server never gave).

`IGNORED` therefore means one specific thing: a COMPLETE reply without the
const. That distinction is the whole content of finding A, and it is why a
report that shows a wall of refusals should be read for its own probe before
it is read for its model.

Exit codes: ENFORCED -> 0, everything else -> 1 (CI fails closed).

    uv run python scripts/vlm_probes/enforcement.py \
        --url http://host.docker.internal:<port> --expect-build b7972
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx

# Direct-script invocation (uv run python scripts/vlm_probes/enforcement.py)
# has no package context - same bootstrap as the other repo scripts.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Same contract the runtime gate builds - importing keeps CI and runtime
# from drifting apart (a CI pass must be proof about the runtime probe).
from backend.api.schemas.llm_response import RISK_ANALYSIS_JSON_SCHEMA
from backend.services.nemotron_analyzer import (
    PROBE_PROMPT,
    _is_length_truncated,
    _probe_completion,
    build_probe_schema,
)

PROBE_TIMEOUT_SECONDS = 30.0


def _build_info_text(raw: Any) -> str:
    """normalize /props build_info: a plain string on llama.cpp pins, but
    tolerate a structured dict so a different server shape cannot fake a
    build match by str() weirdness."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return " ".join(str(v) for v in raw.values())
    return str(raw or "")


def _verdict(**fields: Any) -> dict[str, Any]:
    return {"probe": "enforcement", **fields}


async def run_probe(
    url: str,
    *,
    expect_build: str | None = None,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """One enforcement probe against ``url`` (base, no trailing /completion).

    Returns a dict with an uppercase ``verdict`` in
    ENFORCED / IGNORED / INCONCLUSIVE plus whatever evidence was gathered.

    ``client`` is the transport seam (tests drive the JUDGEMENT without a
    GPU), the same shape ``tool_calls.py`` exposes. Owned clients are closed
    here; an injected one is left alone.
    """
    base = url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if client is not None:
        # Injected: the caller owns its lifetime, so do not close it.
        return await _run_probe(base, headers, expect_build, client)
    # Owned: kept as `async with httpx.AsyncClient(...)` rather than a manual
    # aclose() so the pre-existing pins that patch httpx.AsyncClient with a
    # context-manager-only fake keep exercising the real call shape.
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS) as owned:
        return await _run_probe(base, headers, expect_build, owned)


async def _run_probe(
    base: str, headers: dict[str, str], expect_build: str | None, client: httpx.AsyncClient
) -> dict[str, Any]:
    # Build gate BEFORE any completion (S-2's per-build lesson).
    build_info = ""
    try:
        props_resp = await client.get(f"{base}/props", headers=headers)
        build_info = _build_info_text((props_resp.json() or {}).get("build_info"))
    except Exception as e:
        return _verdict(
            verdict="INCONCLUSIVE",
            why=f"could not read /props build_info ({e!r}) while "
            f"--expect-build={expect_build!r} is pinned",
        )
    if expect_build and expect_build not in build_info:
        return _verdict(
            verdict="INCONCLUSIVE",
            build_info=build_info,
            why=f"build_info lacks pinned {expect_build!r} - enforcement "
            "varies per build; probing completions here would launder a "
            "stale proof onto an unknown server",
        )

    schema, nonce = build_probe_schema(RISK_ANALYSIS_JSON_SCHEMA, nonce=str(uuid.uuid4()))
    try:
        status, content, stop = await _probe_completion(
            client, base, headers, PROBE_PROMPT, schema
        )
    except Exception as e:
        return _verdict(verdict="INCONCLUSIVE", why=f"completion request failed ({e!r})")
    if status != 200:
        return _verdict(
            verdict="INCONCLUSIVE",
            why=f"completion returned HTTP {status} - not measurable",
        )

    try:
        obj = json.loads(content)
    except Exception:
        obj = None
    if isinstance(obj, dict) and obj.get("probe_const") == nonce:
        # The const is the whole question, so a stop reason cannot answer it
        # negatively - a reply that echoed then ran out of budget enforced the
        # grammar. Losing this to a budget would be the mirror of finding A.
        return _verdict(
            verdict="ENFORCED",
            build_info=build_info,
            stop_reason=stop,
            why="nonce const echoed - grammar, not parroting",
        )
    if _is_length_truncated(stop):
        # FINDING A. The reply hit its token budget, so the const may simply
        # never have been emitted - it can legally sort LAST in the grammar.
        # That is "could not measure", NOT "measured: this server ignores the
        # grammar", and the difference decides an M2 pick: on the shipped
        # multimodal shape six scenes truncate at 400 tokens while three of
        # the same four echo the const at 1200 (ledger finding A [V]).
        # Fail-closed is unchanged - INCONCLUSIVE still exits 1.
        return _verdict(
            verdict="INCONCLUSIVE",
            build_info=build_info,
            stop_reason=stop,
            content_head=content[:200],
            why="reply hit its token budget before the const could be read "
            f"(stop={stop!r}, n_predict=400) - enforcement UNMEASURED at this "
            "budget, not absent. Re-run with a larger budget to decide.",
        )
    # A COMPLETE reply with no const: the E5 evidence itself. Finding A's
    # triage does not reach here, and must not - forgiving prose would
    # downgrade the probe rather than repair it.
    return _verdict(
        verdict="IGNORED",
        build_info=build_info,
        stop_reason=stop,
        content_head=content[:200],
        why="reply did not echo the never-prompted const - json_schema is "
        "accepted but not enforced at this model/build (E5's finding)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="endpoint base URL, e.g. http://host:8080")
    parser.add_argument(
        "--expect-build",
        default=None,
        help="substring the /props build_info must contain (e.g. b7972); "
        "mismatch is INCONCLUSIVE before any completion",
    )
    parser.add_argument("--api-key", default=None, help="bearer token if the endpoint has one")
    args = parser.parse_args(argv)

    # No schema-file flag on purpose: the probe schema IS the parser's schema
    # (single source, §3) - an operator override there would let CI prove
    # nothing about runtime.
    result = asyncio.run(
        run_probe(args.url, expect_build=args.expect_build, api_key=args.api_key)
    )
    print(json.dumps(result, indent=2))  # noqa: T201 - CLI output IS the product
    return 0 if result["verdict"] == "ENFORCED" else 1


if __name__ == "__main__":
    sys.exit(main())
